import json
import re
import typing as t
from collections import defaultdict
from pathlib import Path

import arguebuf
import grpc
import pendulum
from arg_services.mining.v1 import entailment_pb2, entailment_pb2_grpc
from pendulum.datetime import DateTime
from pendulum.parser import parse as dt_parse
from rich import print
from rich.progress import track

from twitter2arguebuf import model

handle_pattern = re.compile(r"^@\w+")
url_pattern = re.compile(r"https?:\/\/t.co\/\w+")


def parse_response(
    f: t.IO[str],
) -> t.Tuple[t.Set[str], t.Dict[str, model.Tweet], t.Dict[str, model.User],]:
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


def process_tweet(text: t.Optional[str], clean: bool) -> t.Optional[str]:
    if clean and text:
        text = url_pattern.sub("", text)
        text = text.strip()

        while handle_pattern.search(text):
            text = handle_pattern.sub("", text).strip()

        text = text.replace("  ", " ")

    return text


def build_subtree(
    level: int,
    g: arguebuf.Graph,
    parent: arguebuf.AtomNode,
    tweets: t.Mapping[str, t.Collection[model.Tweet]],
    participants: t.Mapping[str, arguebuf.Participant],
    client: t.Optional[entailment_pb2_grpc.EntailmentServiceStub],
    language: str,
    clean: bool,
    min_chars: int,
    min_interactions: int,
) -> None:
    for tweet in tweets[parent.id]:
        if (text := process_tweet(tweet["text"], clean)) and len(text) > min_chars:
            atom = arguebuf.AtomNode(
                id=tweet["id"],
                text=text,
                resource=arguebuf.Reference(text=text),
                metadata=arguebuf.Metadata(
                    created=parse_timestamp(tweet.get("created_at")),
                    updated=pendulum.now(),
                ),
                participant=participants[tweet["author_id"]]
                if tweet.get("author_id")
                else None,
            )
            scheme_type = None

            if client:
                res: entailment_pb2.EntailmentResponse = client.Entailment(
                    entailment_pb2.EntailmentRequest(
                        language=language,
                        premise=atom.plain_text,
                        claim=parent.plain_text,
                    )
                )

                if res.entailment_type == entailment_pb2.ENTAILMENT_TYPE_ENTAILMENT:
                    scheme_type = arguebuf.Support.DEFAULT

                elif (
                    res.entailment_type == entailment_pb2.ENTAILMENT_TYPE_CONTRADICTION
                ):
                    scheme_type = arguebuf.Attack.DEFAULT

            scheme = arguebuf.SchemeNode(scheme_type, id=f"{atom.id},{parent.id}")

            if metrics := tweet.get("public_metrics"):
                likes = metrics.get("like_count", 0)
                replies = metrics.get("reply_count", 0)
                quotes = metrics.get("quote_count", 0)
                retweets = metrics.get("retweet_count", 0)

                if (
                    likes + replies + quotes + retweets >= min_interactions
                ):  #  or level > 1
                    g.add_edge(arguebuf.Edge(atom, scheme))
                    g.add_edge(arguebuf.Edge(scheme, parent))

                    build_subtree(
                        level + 1,
                        g,
                        atom,
                        tweets,
                        participants,
                        client,
                        language,
                        clean,
                        min_chars,
                        min_interactions,
                    )


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
    client: t.Optional[entailment_pb2_grpc.EntailmentServiceStub],
    clean: bool,
    min_chars: int,
    min_interactions: int,
    min_depth: int,
) -> arguebuf.Graph:
    g = arguebuf.Graph()
    assert mc_tweet.get("id")

    mc = arguebuf.AtomNode(
        process_tweet(mc_tweet["text"], clean),
        metadata=arguebuf.Metadata(
            created=parse_timestamp(mc_tweet.get("created_at")), updated=pendulum.now()
        ),
        participant=participants[mc_tweet["author_id"]]
        if mc_tweet.get("author_id")
        else None,
        id=mc_tweet["id"],
    )
    g.add_node(mc)
    g.major_claim = mc
    build_subtree(
        level=1,
        g=g,
        parent=mc,
        client=client,
        tweets=referenced_tweets,
        participants=participants,
        clean=clean,
        min_chars=min_chars,
        min_interactions=min_interactions,
        language="en",
    )

    for leaf in g.leaf_nodes:
        if g.node_distance(leaf, mc, min_depth, ignore_schemes=True):
            nodes_to_remove = {leaf}

            while nodes_to_remove:
                node_to_remove = nodes_to_remove.pop()
                nodes_to_remove.update(g.outgoing_nodes(node_to_remove))

                if node_to_remove.id != mc.id:
                    g.remove_node(node_to_remove)

    g.clean_participants()

    return g


def conversation_path(folder: Path, mc: t.Optional[arguebuf.AtomNode]):
    assert mc

    return (
        folder
        / (
            mc.participant.username
            if mc.participant and mc.participant.username
            else ""
        )
        / mc.id
    )


def convert(
    input_folder: Path,
    input_pattern: str,
    output_folder: t.Optional[Path] = None,
    entailment_address: t.Optional[str] = None,
    render: bool = False,
    clean: bool = True,
    min_chars: int = 0,
    min_interactions: int = 0,
    min_depth: int = 0,
):
    client = (
        entailment_pb2_grpc.EntailmentServiceStub(
            grpc.insecure_channel(entailment_address)
        )
        if entailment_address
        else None
    )

    for input_file in input_folder.glob(input_pattern):
        print(f"Processing '{input_file}'")

        with input_file.open("r", encoding="utf-8") as f:
            conversation_ids, tweets, users = parse_response(f)

        referenced_tweets = parse_referenced_tweets(tweets)
        participants = parse_participants(users)

        for conversation_id in track(
            conversation_ids, description=f"Converting tweets..."
        ):
            if mc_tweet := tweets.get(conversation_id):
                g = parse_graph(
                    mc_tweet,
                    referenced_tweets,
                    participants,
                    client,
                    clean,
                    min_chars,
                    min_interactions,
                    min_depth,
                )

                if len(g.atom_nodes) > 1:
                    output_path = conversation_path(
                        output_folder or input_folder, g.major_claim
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    g.to_file(output_path.with_suffix(".json"))

                    if render:
                        arguebuf.render(g.to_gv("svg"), output_path.with_suffix(".svg"))
