import json
import os
import typing as t
from pathlib import Path
from urllib.parse import urlparse

import pendulum
import typer
from dateutil import parser as dt_parser
from dotenv import load_dotenv
from pytwitter import Api
from pytwitter.models.ext import Response

from twitter2arguebuf import model

load_dotenv()

app = typer.Typer()


def append_response(res: Response, conversation: model.Conversation):
    if res.data:
        if isinstance(res.data, list) and all(
            isinstance(item, model.Tweet) for item in res.data
        ):
            conversation.data.extend(t.cast(t.Iterable[model.Tweet], res.data))

        elif isinstance(res.data, model.Tweet):
            conversation.data.append(res.data)

        else:
            raise RuntimeError(
                f"Expected 'List[Tweet]' or 'Tweet' in 'res.data', but got '{type(res.data)}':\n{res.data}."
            )

    if res.includes:
        for key in ["media", "polls", "places", "tweets", "users"]:
            if value := getattr(res.includes, key):
                getattr(conversation.includes, key).extend(value)


api_args = {
    "tweet_fields": [
        "author_id",
        "conversation_id",
        "created_at",
        # "in_reply_to_user_id",
        "referenced_tweets",
        "public_metrics",
    ],
    "user_fields": [
        "name",
        "username",
        "url",
        "location",
        "description",
        "created_at",
        "public_metrics",
    ],
    "expansions": ["author_id"],  # "referenced_tweets.id"
}


client = Api(bearer_token=os.getenv("BEARER_TOKEN"))
error_message = "You have to specify either the ID or the URL of a tweet."


def _rf3339(datetime: t.Optional[str]) -> t.Optional[str]:
    if datetime is None:
        return None

    dt = dt_parser.parse(datetime)
    pendulum_dt = pendulum.instance(dt)

    return pendulum_dt.to_rfc3339_string()


def _conversation_ids(
    ids: t.Optional[t.List[str]] = None,
    urls: t.Optional[t.List[str]] = None,
    query: t.Optional[str] = None,
    start_time: t.Optional[str] = None,
    end_time: t.Optional[str] = None,
    max_results: t.Optional[int] = None,
) -> t.Set[str]:
    conversation_ids = set()

    if not ids:
        ids = []

    if not max_results:
        max_results = 10

    if urls:
        for url in urls:
            parsed_url = urlparse(url)
            url_segments = str(parsed_url.path).split("/")
            ids.append(url_segments[-1])

    for id in ids:
        tweet = t.cast(Response, client.get_tweet(id, tweet_fields=["conversation_id"]))

        if isinstance(tweet.data, model.Tweet):
            conversation_ids.add(tweet.data.conversation_id)

    if query:
        first_pass = True
        pagination_token = None

        while (pagination_token or first_pass) and len(conversation_ids) < max_results:
            first_pass = False

            res = t.cast(
                Response,
                client.search_tweets(
                    query,
                    start_time=_rf3339(start_time),
                    end_time=_rf3339(end_time),
                    max_results=min(max_results, 500),
                    tweet_fields=["conversation_id"],
                    next_token=pagination_token,
                ),
            )

            if res.data:
                if isinstance(res.data, list):
                    for tweet in res.data:
                        if isinstance(tweet, model.Tweet) and (
                            conversation_id := tweet.conversation_id
                        ):
                            conversation_ids.add(conversation_id)
                elif isinstance(res.data, model.Tweet) and (
                    conversation_id := res.data.conversation_id
                ):
                    conversation_ids.add(conversation_id)

            pagination_token = res.meta.next_token if res.meta else None

    return conversation_ids


@app.command()
def count(
    query: str, start_time: t.Optional[str] = None, end_time: t.Optional[str] = None
):
    total_tweets = 0
    first_pass = True
    pagination_token = None

    while first_pass or pagination_token:
        first_pass = False

        res = t.cast(
            Response,
            client.get_tweets_counts(
                query,
                search_type="all",
                start_time=_rf3339(start_time),
                end_time=_rf3339(end_time),
                granularity="day",
                next_token=pagination_token,
            ),
        )

        if meta := res.meta:
            if tweet_count := meta.total_tweet_count:
                total_tweets += tweet_count
                typer.echo(f"\rCurrently retrieved tweets: {total_tweets}", nl=False)

            if token := meta.next_token:
                pagination_token = token

    typer.echo()


@app.command()
def conversations(
    ids: t.Optional[t.List[str]] = typer.Option(None, "--id"),
    urls: t.Optional[t.List[str]] = typer.Option(None, "--url"),
    query: t.Optional[str] = None,
    start_time: t.Optional[str] = None,
    end_time: t.Optional[str] = None,
    max_results: t.Optional[int] = None,
):
    typer.echo(_conversation_ids(ids, urls, query, start_time, end_time, max_results))


# (#vote OR #election2020 OR #elections2020) -is:retweet -is:reply -is:quote -is:nullcast lang:en
# https://twitter.com/JoeBiden/status/1351897267666608129


@app.command()
def download(
    output_folder: Path,
    ids: t.Optional[t.List[str]] = typer.Option(None, "--id"),
    urls: t.Optional[t.List[str]] = typer.Option(None, "--url"),
    query: t.Optional[str] = None,
    start_time: t.Optional[str] = None,
    end_time: t.Optional[str] = None,
    max_results: t.Optional[int] = None,
):
    conversation_ids = _conversation_ids(
        ids, urls, query, start_time, end_time, max_results
    )

    for conversation_id in conversation_ids:
        first_pass = True
        pagination_token = None
        conversation = model.Conversation()
        username = ""

        tweet = t.cast(
            Response,
            client.get_tweet(conversation_id, **api_args),
        )

        append_response(
            tweet,
            conversation,
        )

        if (
            isinstance(tweet.data, model.Tweet)
            and tweet.includes
            and tweet.includes.users
            and (
                found_name := (
                    next(
                        iter(
                            user.username
                            for user in tweet.includes.users
                            if user.id == tweet.data.author_id
                        )
                    )
                )
            )
        ):
            username = found_name

        conversation_path = output_folder / username / conversation_id

        while pagination_token or first_pass:
            first_pass = False

            try:
                res: Response = t.cast(
                    Response,
                    client.search_tweets(
                        f"conversation_id:{conversation_id}",
                        since_id=conversation_id,
                        query_type="all",
                        **api_args,
                        max_results=500,
                        next_token=pagination_token,
                    ),
                )

                pagination_token = res.meta.next_token if res.meta else None
                append_response(res, conversation)
            except Exception:
                _save(conversation_path, conversation)

        _save(conversation_path, conversation)


def _save(path: Path, conversation: model.Conversation) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with (path).with_suffix(".json").open("w", encoding="utf-8") as f:
        json.dump(conversation.to_dict(), f)
