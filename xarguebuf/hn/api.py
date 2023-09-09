import asyncio
import itertools
import sys
import typing as t
from collections import defaultdict
from functools import wraps
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Literal, Optional

import arguebuf
import grpc
import httpx
import pendulum
import rich
import rich_click as click
import typed_settings as ts
from arg_services.mining.v1beta import entailment_pb2_grpc
from pendulum.datetime import DateTime
from pydantic import BaseModel

from xarguebuf import common


class Story(BaseModel):
    id: int
    by: str
    time: int
    text: Optional[str] = None
    kids: Optional[list[int]] = None
    url: Optional[str] = None
    score: int
    title: str
    descendants: int


class Comment(BaseModel):
    id: int
    by: str
    time: int
    text: str
    parent: int
    kids: t.Optional[list[int]] = None


Item = Story | Comment


class User(BaseModel):
    id: str
    created: int
    karma: int
    about: t.Optional[str] = None
    submitted: t.Optional[list[int]] = None


class RawItem(BaseModel):
    id: int
    type: Literal["job", "story", "comment", "poll", "pollopt"]
    deleted: Optional[bool] = None
    by: Optional[str] = None
    time: Optional[int] = None
    text: Optional[str] = None
    dead: Optional[bool] = None
    parent: Optional[int] = None
    poll: Optional[int] = None
    kids: Optional[list[int]] = None
    url: Optional[str] = None
    score: Optional[int] = None
    title: Optional[str] = None
    parts: Optional[list[int]] = None
    descendants: Optional[int] = None

    def parse(self) -> Item | None:
        if self.deleted or self.dead:
            return None
        elif self.type == "story":
            return Story(**self.model_dump())
        elif self.type == "comment":
            return Comment(**self.model_dump())

        raise ValueError(f"Item type '{self.type}' not supported")


# https://stackoverflow.com/a/925630
class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, data: str) -> None:
        self.text.write(data)

    def get_data(self) -> str:
        return self.text.getvalue()


def strip_tags(html: str) -> str:
    s = MLStripper()
    s.feed(html)
    return s.get_data()


@ts.settings(frozen=True)
class CommentConfig:
    min_chars: int = ts.option(
        default=0,
        help=(
            "Number of characters a tweet should have to be included in the graph."
            " Note: If a tweet has less characters, all replies to it will be removed"
            " as well."
        ),
    )
    max_chars: int = ts.option(
        default=sys.maxsize,
        help=(
            "Number of characters a tweet should have at most to be included in the"
            " graph. Note: If a tweet has less characters, all replies to it will be"
            " removed as well."
        ),
    )


@ts.settings(frozen=True)
class StoryConfig:
    min_score: int = ts.option(
        default=0,
    )
    max_score: int = ts.option(
        default=sys.maxsize,
    )


@ts.settings(frozen=True)
class EndpointConfig:
    name: t.Optional[str] = ts.option(
        default=None,
        click={
            "type": click.Choice(
                [
                    "topstories",
                    "newstories",
                    "beststories",
                    "askstories",
                    "showstories",
                    "jobstories",
                ]
            )
        },
    )
    max_stories: int = ts.option(
        default=sys.maxsize,
    )


@ts.settings(frozen=True)
class Config:
    graph: common.GraphConfig = common.GraphConfig()
    comment: CommentConfig = CommentConfig()
    story: StoryConfig = StoryConfig()
    endpoint: EndpointConfig = EndpointConfig()
    output_folder: Path = ts.option(default=Path("data/hn"))
    entailment_address: t.Optional[str] = ts.option(default=None)


def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@click.group()
def cli():
    pass


@cli.command("api")
@click.argument("ids", type=int, nargs=-1)
@ts.click_options(Config, "xarguebuf.hn")
@coro
async def hn(config: Config, ids: tuple[int, ...]):
    all_ids = list(ids)
    common.prepare_output(config.output_folder, config, ["output_folder"])

    entailment_client = (
        entailment_pb2_grpc.EntailmentServiceStub(
            grpc.insecure_channel(config.entailment_address)
        )
        if config.entailment_address
        else None
    )

    async with httpx.AsyncClient(
        base_url="https://hacker-news.firebaseio.com/v0/"
    ) as http_client:
        if config.endpoint.name is not None:
            res = await http_client.get(f"{config.endpoint.name}.json")
            endpoint_ids: list[int] = res.json()[: config.endpoint.max_stories]
            all_ids.extend(endpoint_ids)

        for id in all_ids:
            g = await build_graph(id, config, http_client, entailment_client)
            mc = g.major_claim
            assert mc is not None

            common.serialize(
                g,
                config.output_folder,
                config.graph,
                mc.id,
                mc.participant.id if mc.participant else None,
            )


async def build_graph(
    id: int,
    config: Config,
    http_client: httpx.AsyncClient,
    entailment_client: t.Optional[entailment_pb2_grpc.EntailmentServiceStub],
) -> arguebuf.Graph:
    rich.print(f"Processing story {id}...")
    parent: int | None = id
    item: RawItem | None = None

    while parent is not None:
        response = await http_client.get(f"item/{parent}.json")
        item = RawItem(**response.json())
        parent = item.parent

    assert item is not None

    story = item.parse()
    assert isinstance(story, Story)

    comments = await fetch_comments(story, http_client)
    comments_chain = itertools.chain.from_iterable(comments.values())
    participants = await build_participants([story, *comments_chain], http_client)

    mc = build_atom(story, participants)
    g = arguebuf.Graph()
    g.add_node(mc)
    g.major_claim = mc

    g = build_subtree(0, g, mc, comments, participants)
    g = common.prune_graph(g, config.graph)
    g = common.predict_schemes(g, client=entailment_client)

    return g


def parse_timestamp(value: int) -> DateTime:
    return pendulum.from_timestamp(value)


def build_atom_text(item: Item) -> str:
    text = item.text if item.text else ""
    text = text.replace("<p>", "\n").replace("</p>", "")
    text = strip_tags(text)

    if isinstance(item, Story) and item.title:
        text = f"{item.title}\n\n{text}"

    return text


def build_atom(
    item: Item, participants: t.Mapping[str, arguebuf.Participant]
) -> arguebuf.AtomNode:
    metadata = arguebuf.Metadata(
        created=parse_timestamp(item.time), updated=pendulum.now()
    )
    if isinstance(item, Story):
        return arguebuf.AtomNode(
            id=str(item.id),
            text=build_atom_text(item),
            participant=participants[item.by],
            metadata=metadata,
            userdata={
                "descendants": item.descendants,
                "score": item.score,
                "title": item.title,
                "url": item.url,
            },
        )

    elif isinstance(item, Comment):
        return arguebuf.AtomNode(
            id=str(item.id),
            text=build_atom_text(item),
            participant=participants[item.by],
            metadata=metadata,
        )

    raise ValueError(f"Item type '{type(item)}' not supported")


async def build_participants(
    items: t.Iterable[Item], http_client: httpx.AsyncClient
) -> dict[str, arguebuf.Participant]:
    participants: dict[str, arguebuf.Participant] = {}

    for item in items:
        if item.by not in participants:
            res = await http_client.get(f"user/{item.by}.json")
            user = User(**res.json())

            participants[user.id] = arguebuf.Participant(
                id=user.id,
                username=user.id,
                description=user.about,
                metadata=arguebuf.Metadata(
                    created=parse_timestamp(user.created), updated=pendulum.now()
                ),
                userdata={
                    "karma": user.karma,
                    "submissions": len(user.submitted) if user.submitted else 0,
                },
            )

    return participants


async def fetch_comments(
    story: Story, http_client: httpx.AsyncClient
) -> dict[str, list[Comment]]:
    queue: list[int] = []

    if story.kids is not None:
        queue.extend(story.kids)

    comments: defaultdict[str, list[Comment]] = defaultdict(list)

    while len(queue) > 0:
        comment_id = queue.pop()
        res = await http_client.get(f"item/{comment_id}.json")
        item = RawItem(**res.json())
        comment = item.parse()

        if isinstance(comment, Comment):
            comments[str(comment.parent)].append(comment)

            if comment.kids is not None:
                queue.extend(comment.kids)

    return comments


def build_subtree(
    level: int,
    g: arguebuf.Graph,
    parent: arguebuf.AtomNode,
    comments: t.Mapping[str, t.Collection[Comment]],
    participants: t.Mapping[str, arguebuf.Participant],
) -> arguebuf.Graph:
    for comment in comments[parent.id]:
        atom = build_atom(comment, participants)
        scheme = arguebuf.SchemeNode(id=f"{atom.id,parent.id}")
        g.add_edge(arguebuf.Edge(atom, scheme))
        g.add_edge(arguebuf.Edge(scheme, parent))

        build_subtree(level + 1, g, atom, comments, participants)

    return g
