import json
import re
import sys
import typing as t
from collections import defaultdict
from pathlib import Path

import arguebuf
import grpc
import pendulum
import rich_click as click
import typed_settings as ts
from arg_services.mining.v1beta import entailment_pb2_grpc
from pendulum.datetime import DateTime
from pendulum.parser import parse as dt_parse
from rich import print
from rich.progress import track

from xarguebuf import common

from . import model

HANDLE_PATTERN = re.compile(r"^@\w+")
URL_PATTERN = re.compile(r"https?:\/\/t.co\/\w+")
# https://developer.twitter.com/en/docs/twitter-api/tweets/search/api-reference/get-tweets-search-all


@ts.settings(frozen=True)
class TweetConfig:
    raw_text: bool = ts.option(
        default=False,
        click={"param_decls": "--tweet-raw-text", "is_flag": True},
        help=(
            "By default, the texts of the tweets will be cleaned (e.g., resolve links"
            " and hide the initial user mention). Set to `no-clean` to disable."
        ),
    )
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
    min_interactions: int = ts.option(
        default=0,
        help=(
            "Number of interactions (likes + replies + quotes + retweets) a tweet"
            " should have to be included in the graph. Note: If a tweet has less"
            " interactions, all replies to it will be removed as well."
        ),
    )
    max_interactions: int = ts.option(
        default=sys.maxsize,
        help=(
            "Number of interactions (likes + replies + quotes + retweets) a tweet"
            " should have at most to be included in the graph. Note: If a tweet has"
            " more interactions, all replies to it will be removed as well."
        ),
    )
    userdata: t.List[str] = ts.option(
        factory=lambda: [
            "public_metrics",
            "context_annotations",
            "entities",
            "possibly_sentitive",
            "attachments",
            "geo",
            "source",
        ],
        help=(
            "Additional fields of the `tweet` api response that shall be stored as"
            " `userdata` in the arguebuf file (if returned by Twitter)."
        ),
    )
    language: str = ts.option(
        default="en", help="Only include tweets with matching language"
    )


@ts.settings(frozen=True)
class Config:
    graph: common.GraphConfig = common.GraphConfig()
    tweet: TweetConfig = TweetConfig()


def parse_response(
    f: t.IO[str],
) -> t.Tuple[
    t.Set[str],
    t.Dict[str, model.Tweet],
    t.Dict[str, model.User],
]:
    conversations: set[str] = set()
    tweets: dict[str, model.Tweet] = {}
    users: dict[str, model.User] = {}

    total_iterations = sum(1 for _ in f)
    f.seek(0)

    for line in track(f, "Reading file...", total=total_iterations):
        res = json.loads(line)

        data = res.get("data")
        includes = res.get("includes")

        if data is not None:
            if not isinstance(data, list):
                data = [data]

            if includes is not None and includes.get("tweets") is not None:
                data.extend(includes["tweets"])

            for tweet in data:
                tweets[tweet["id"]] = tweet

                if tweet.get("conversation_id") is not None:
                    conversations.add(tweet["conversation_id"])

            if includes is not None and includes.get("users") is not None:
                for user in includes["users"]:
                    users[user["id"]] = user

    return conversations, tweets, users


def parse_timestamp(value: t.Optional[str]) -> t.Optional[DateTime]:
    if value:
        timestamp = dt_parse(value)

        if isinstance(timestamp, DateTime):
            return timestamp

    return None


OptionalString = t.TypeVar("OptionalString", str, None)


def process_tweet(text: OptionalString, raw_text: bool) -> OptionalString:
    if text is not None and not raw_text:
        out: str = text
        out = URL_PATTERN.sub("", out)
        out = out.strip()

        while HANDLE_PATTERN.search(out):
            out = HANDLE_PATTERN.sub("", out).strip()

        out = out.replace("  ", " ")

        return out

    return text


def build_atom(
    tweet: model.Tweet,
    text: str,
    participants: t.Mapping[str, arguebuf.Participant],
    config: TweetConfig,
):
    return arguebuf.AtomNode(
        id=tweet["id"],
        text=text,
        reference=arguebuf.Reference(text=text),
        metadata=arguebuf.Metadata(
            created=parse_timestamp(tweet.get("created_at")),
            updated=pendulum.now(),
        ),
        userdata={key: tweet[key] for key in config.userdata if key in tweet},
        participant=(
            participants[tweet["author_id"]] if tweet.get("author_id") else None
        ),
    )


def build_subtree(
    level: int,
    g: arguebuf.Graph,
    parent: arguebuf.AtomNode,
    tweets: t.Mapping[str, t.Collection[model.Tweet]],
    participants: t.Mapping[str, arguebuf.Participant],
    config: Config,
) -> None:
    for tweet in tweets[parent.id]:
        if (
            (text := process_tweet(tweet["text"], config.tweet.raw_text))
            and len(text) >= config.tweet.min_chars
            and len(text) <= config.tweet.max_chars
            and tweet["lang"] == config.tweet.language
        ):
            atom = build_atom(tweet, text, participants, config.tweet)
            scheme = arguebuf.SchemeNode(id=f"{atom.id},{parent.id}")

            if metrics := tweet.get("public_metrics"):
                likes = metrics.get("like_count", 0)
                replies = metrics.get("reply_count", 0)
                quotes = metrics.get("quote_count", 0)
                retweets = metrics.get("retweet_count", 0)
                interactions = likes + replies + quotes + retweets

                if (
                    interactions >= config.tweet.min_interactions
                    and interactions <= config.tweet.max_interactions
                ):  #  or level > 1
                    g.add_edge(arguebuf.Edge(atom, scheme))
                    g.add_edge(arguebuf.Edge(scheme, parent))

                    build_subtree(level + 1, g, atom, tweets, participants, config)


def parse_referenced_tweets(
    tweets: t.Mapping[str, model.Tweet]
) -> defaultdict[str, list[model.Tweet]]:
    referenced_tweets: defaultdict[str, list[model.Tweet]] = defaultdict(list)

    for tweet_id, tweet in tweets.items():
        if subtweets := tweet.get("referenced_tweets"):
            for subtweet in subtweets:
                if (
                    subtweet["type"] == "replied_to"
                    and subtweet["id"]
                    and subtweet["id"] in tweets
                ):
                    referenced_tweets[subtweet["id"]].append(tweets[tweet_id])

    return referenced_tweets


def parse_participants(
    users: t.Mapping[str, model.User]
) -> t.Dict[str, arguebuf.Participant]:
    participants: dict[str, arguebuf.Participant] = {}

    for user in users.values():
        participants[user["id"]] = arguebuf.Participant(
            user.get("name"),
            user.get("username"),
            None,
            user.get("url"),
            user.get("location"),
            user.get("description"),
            metadata=arguebuf.Metadata(
                created=parse_timestamp(user.get("created_at")) or pendulum.now(),
                updated=pendulum.now(),
            ),
            id=user["id"],
        )

    return participants


def parse_graph(
    mc_tweet: model.Tweet,
    referenced_tweets: t.Mapping[str, t.Collection[model.Tweet]],
    participants: t.Mapping[str, arguebuf.Participant],
    entailment_client: t.Optional[entailment_pb2_grpc.EntailmentServiceStub],
    config: Config,
) -> arguebuf.Graph:
    g = arguebuf.Graph()
    mc_text: str = process_tweet(mc_tweet["text"], config.tweet.raw_text)

    mc = build_atom(mc_tweet, mc_text, participants, config.tweet)
    g.add_node(mc)
    g.major_claim = mc
    build_subtree(
        level=1,
        g=g,
        parent=mc,
        tweets=referenced_tweets,
        participants=participants,
        config=config,
    )

    common.prune_graph(g, config.graph)
    common.predict_schemes(g, client=entailment_client)

    return g


def conversation_path(folder: Path, mc: t.Optional[arguebuf.AtomNode]):
    assert mc is not None

    return (
        folder
        / (
            mc.participant.username
            if mc.participant and mc.participant.username
            else ""
        )
        / mc.id
    )


@click.group()
def cli():
    pass


@cli.command("convert")
@click.argument(
    "input_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    # help="Path to `jsonl` file that should be processed.",
)
@click.argument(
    "output_folder",
    type=click.Path(writable=True, file_okay=False, path_type=Path),
    # help="Path to a folder where the processed graphs should be stored.",
)
@click.option("--entailment-address", hidden=True, default=None)
@ts.click_options(Config, "xarguebuf.convert")
def convert(
    config: Config,
    input_file: Path,
    output_folder: Path,
    entailment_address: t.Optional[str],
):
    """Convert INPUT_FILE (.jsonl) to argument graphs and save them to OUTPUT_FOLDER"""
    entailment_client = (
        entailment_pb2_grpc.EntailmentServiceStub(
            grpc.insecure_channel(entailment_address)
        )
        if entailment_address
        else None
    )

    common.prepare_output(output_folder, config)

    print(f"Processing '{input_file}'")

    with input_file.open("r", encoding="utf-8") as f:
        conversation_ids, tweets, users = parse_response(f)

    referenced_tweets = parse_referenced_tweets(tweets)
    participants = parse_participants(users)

    for conversation_id in track(conversation_ids, description="Converting tweets..."):
        if mc_tweet := tweets.get(conversation_id):
            g = parse_graph(
                mc_tweet, referenced_tweets, participants, entailment_client, config
            )
            mc = g.major_claim

            if mc is not None:
                common.serialize(
                    g,
                    output_folder,
                    config.graph,
                    mc.id,
                )
