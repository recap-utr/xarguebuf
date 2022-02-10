import json
import re
import typing as t
from collections import defaultdict
from pathlib import Path

import arguebuf
import pendulum
from pytwitter.models.ext import Response

from twitter2arguebuf import model

handle_pattern = re.compile(r"^@\w+")
url_pattern = re.compile(r"https?:\/\/t.co\/\w+")


# def append_response(res: t.Mapping[str, t.Any], conv: model.Conversation):
#     data = res["data"]
#     includes = res["includes"]

#     if isinstance(data, list):
#         conv.data.extend(model.Tweet.from_dict(x) for x in data)
#     else:
#         conv.data.append(model.Tweet.from_dict(data))

#     conv.includes.media.extend(model.Media.from_dict(x) for x in includes["media"])
#     conv.includes.polls.extend(model.Poll.from_dict(x) for x in includes["polls"])
#     conv.includes.places.extend(model.Place.from_dict(x) for x in includes["places"])
#     conv.includes.tweets.extend(model.Tweet.from_dict(x) for x in includes["tweets"])
#     conv.includes.users.extend(model.User.from_dict(x) for x in includes["users"])


def parse_response(
    f: t.IO[str],
) -> t.Tuple[t.Set[str], t.Dict[str, model.Tweet], t.Dict[str, model.User]]:
    conversations = set()
    tweets = {}
    users = {}

    for line in f:
        res = json.loads(line)

        data = res["data"]
        includes = res["includes"]

        if not isinstance(data, list):
            data = [data]

        for tweet in data:
            tweets[tweet["id"]] = model.Tweet.from_dict(tweet)
            conversations.add(tweet["conversation_id"])

        for user in includes.get("users", tuple()):
            users[user["id"]] = model.User.from_dict(user)

    return conversations, tweets, users


def parse_timestamp(value: t.Optional[str]) -> t.Optional[pendulum.DateTime]:
    if value:
        timestamp = pendulum.parse(value)

        if isinstance(timestamp, pendulum.DateTime):
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
    clean: bool,
    min_chars: int,
    min_interactions: int,
) -> None:
    for tweet in tweets[parent.id]:
        if tweet.id:
            if (text := process_tweet(tweet.text, clean)) and len(text) > min_chars:
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


def parse_referenced_tweets(
    tweets: t.Mapping[str, model.Tweet]
) -> t.Dict[str, t.List[model.Tweet]]:
    referenced_tweets = defaultdict(list)

    for tweet_id, tweet in tweets.items():
        if subtweets := tweet.referenced_tweets:
            for subtweet in subtweets:
                if (
                    subtweet.type == "replied_to"
                    and subtweet.id
                    and subtweet.id in tweets
                ):
                    referenced_tweets[subtweet.id].append(tweets[tweet_id])

    return referenced_tweets


def parse_participants(
    users: t.Mapping[str, model.User]
) -> t.Dict[str, arguebuf.Participant]:
    participants = {}

    for user in users.values():
        assert user.id

        participants[user.id] = arguebuf.Participant(
            user.name,
            user.username,
            None,
            user.url,
            user.location,
            user.description,
            created=parse_timestamp(user.created_at) or pendulum.now(),
            updated=pendulum.now(),
            _id=user.id,
        )

    return participants


def parse_graph(
    mc_tweet: model.Tweet,
    referenced_tweets: t.Mapping[str, t.Collection[model.Tweet]],
    participants: t.Mapping[str, arguebuf.Participant],
    clean: bool,
    min_chars: int,
    min_interactions: int,
    min_depth: int,
) -> arguebuf.Graph:
    g = arguebuf.Graph()
    assert mc_tweet.id

    mc = arguebuf.AtomNode(
        process_tweet(mc_tweet.text, clean),
        created=parse_timestamp(mc_tweet.created_at),
        updated=pendulum.now(),
        participant=participants[mc_tweet.author_id] if mc_tweet.author_id else None,
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

                if node_to_remove.id != mc.id:
                    g.remove_node(node_to_remove)

    g.clean_participants()

    return g


def conversation_path(folder: Path, mc: arguebuf.AtomNode):
    return (
        folder
        / (
            mc.participant.username
            if mc.participant and mc.participant.username
            else ""
        )
        / mc.id
    )


def save_graph(folder: Path, g: arguebuf.Graph):
    mc = g.major_claim
    assert mc

    path = conversation_path(folder, mc).with_suffix(".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    g.to_file(path)


def render_graph(folder: Path, g: arguebuf.Graph):
    mc = g.major_claim
    assert mc

    path = conversation_path(folder, mc).with_suffix(".svg")
    path.parent.mkdir(parents=True, exist_ok=True)
    arguebuf.render(g.to_gv("svg"), path)


def convert(
    input_folder: Path,
    input_pattern: str,
    output_folder: Path,
    render: bool = False,
    clean: bool = True,
    min_chars: int = 0,
    min_interactions: int = 0,
    min_depth: int = 0,
):
    for input_file in input_folder.glob(input_pattern):
        with input_file.open("r", encoding="utf-8") as f:
            conversation_ids, tweets, users = parse_response(f)

        referenced_tweets = parse_referenced_tweets(tweets)
        participants = parse_participants(users)

        for conversation_id in conversation_ids:
            if mc_tweet := tweets.get(conversation_id):
                g = parse_graph(
                    mc_tweet,
                    referenced_tweets,
                    participants,
                    clean,
                    min_chars,
                    min_interactions,
                    min_depth,
                )

                save_graph(output_folder, g)

                if render:
                    render_graph(output_folder, g)
