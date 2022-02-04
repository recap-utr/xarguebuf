import json
import re
import typing as t
from collections import defaultdict
from pathlib import Path

import arguebuf
import pendulum

from twitter2arguebuf import model

handle_pattern = re.compile(r"^@\w+")
url_pattern = re.compile(r"https?:\/\/t.co\/\w+")


def parse_timestamp(value: t.Optional[str]) -> t.Optional[pendulum.DateTime]:
    if value:
        timestamp = pendulum.parse(value)

        if isinstance(timestamp, pendulum.DateTime):
            return timestamp

    return None


def process_tweet(
    text: t.Optional[str], clean: bool, min_chars: int
) -> t.Optional[str]:
    if not text:
        return None

    if clean:
        text = url_pattern.sub("", text)
        text = text.strip()

        while handle_pattern.search(text):
            text = handle_pattern.sub("", text).strip()

        text = text.replace("  ", " ")

    if len(text) < min_chars:
        return None

    return text


def build_subtree(
    level: int,
    g: arguebuf.Graph,
    parent: arguebuf.AtomNode,
    tweets: t.Mapping[str, t.Collection[model.Tweet]],
    participants: t.Mapping[str, arguebuf.Participant],
    clean: bool,
    min_chars: int,
    min_interactions: int,
) -> None:
    for tweet in tweets[parent.id]:
        if tweet.id:
            if text := process_tweet(tweet.text, clean, min_chars):
                atom = arguebuf.AtomNode(
                    id=tweet.id,
                    text=text,
                    created=parse_timestamp(tweet.created_at),
                    updated=pendulum.now(),
                    participant=participants[tweet.author_id]
                    if tweet.author_id
                    else None,
                )
                scheme = arguebuf.SchemeNode(None, id=f"{atom.id}->{parent.id}")

                if metrics := tweet.public_metrics:
                    likes = metrics.like_count or 0
                    replies = metrics.reply_count or 0
                    quotes = metrics.quote_count or 0
                    retweets = metrics.retweet_count or 0

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
                            clean,
                            min_chars,
                            min_interactions,
                        )


# 1428023656895057920
# 1471031322479140864


def convert(
    input_folder: Path,
    input_pattern: str,
    output_folder: Path,
    render: bool = False,
    clean: bool = True,
    min_chars: int = 0,
    min_interactions: int = 0,
    min_depth: int = 1,
):
    for input_file in input_folder.glob(input_pattern):
        with input_file.open("r", encoding="utf-8") as f:
            conversation: model.Conversation = model.Conversation.from_dict(
                json.load(f)
            )

        conversation_id = input_file.stem

        tweets = {
            tweet.id: tweet
            for tweet in conversation.includes.tweets + conversation.data
            if tweet.id
        }
        referenced_tweets = defaultdict(list)
        participants = {}

        for tweet_id, tweet in tweets.items():
            if subtweets := tweet.referenced_tweets:
                for subtweet in subtweets:
                    if (
                        subtweet.type == "replied_to"
                        and subtweet.id
                        and subtweet.id in tweets
                    ):
                        referenced_tweets[subtweet.id].append(tweets[tweet_id])

        g = arguebuf.Graph()

        for user in conversation.includes.users:
            if user.id not in participants:
                participant_id = user.id or arguebuf.unique_id()
                participants[participant_id] = arguebuf.Participant(
                    user.name,
                    user.username,
                    None,
                    user.url,
                    user.location,
                    user.description,
                    created=parse_timestamp(user.created_at) or pendulum.now(),
                    updated=pendulum.now(),
                    _id=user.id or arguebuf.unique_id(),
                )

        mc_tweet = tweets[conversation_id]

        if mc_tweet.id:
            mc = arguebuf.AtomNode(
                process_tweet(mc_tweet.text, clean, min_chars),
                created=parse_timestamp(mc_tweet.created_at),
                updated=pendulum.now(),
                participant=participants[mc_tweet.author_id]
                if mc_tweet.author_id
                else None,
                id=mc_tweet.id,
            )
            g.add_node(mc)
            g.major_claim = mc
            build_subtree(
                1,
                g,
                mc,
                referenced_tweets,
                participants,
                clean,
                min_chars,
                min_interactions,
            )

            for leaf in g.leaf_nodes:
                if g.node_distance(leaf, mc, min_depth, ignore_schemes=True):
                    nodes_to_remove = set([leaf])

                    while nodes_to_remove:
                        node_to_remove = nodes_to_remove.pop()
                        nodes_to_remove.update(g.outgoing_nodes(node_to_remove))

                        if node_to_remove != mc:
                            g.remove_node(node_to_remove)

            conversation_path = output_folder / input_file.relative_to(input_folder)
            conversation_path.parent.mkdir(parents=True, exist_ok=True)
            g.to_file(conversation_path.with_suffix(".json"))

            if render:
                arguebuf.render(g.to_gv("svg"), conversation_path.with_suffix(".svg"))
