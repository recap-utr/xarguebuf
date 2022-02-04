import json
import os
import typing as t
from pathlib import Path
from urllib.parse import urlparse

import typer
from dotenv import load_dotenv
from pytwitter import Api
from pytwitter.models.ext import Response

from twitter2arguebuf import model

load_dotenv()


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


def download(
    output_folder: Path,
    ids: t.List[str] = typer.Option(list, "--id"),
    urls: t.List[str] = typer.Option(list, "--url"),
    query: t.Optional[str] = None,
):
    conversation_ids = set()

    for url in urls:
        parsed_url = urlparse(url)
        url_segments = str(parsed_url.path).split("/")
        ids.append(url_segments[-1])

    for id in ids:
        tweet = t.cast(Response, client.get_tweet(id, tweet_fields=["conversation_id"]))

        if isinstance(tweet.data, model.Tweet):
            conversation_ids.add(tweet.data.conversation_id)

    if query:
        query_args = json.loads(query)

        if "tweet_fields" in query_args:
            if "conversation_id" not in query_args["tweet_fields"]:
                query_args["tweet_fields"].append("conversation_id")
        else:
            query_args["tweet_fields"] = ["conversation_id"]

        query_res = t.cast(Response, client.search_tweets(**query_args))

        if query_res.data:
            if isinstance(query_res.data, list):
                for tweet in query_res.data:
                    if isinstance(tweet, model.Tweet) and (
                        conversation_id := tweet.conversation_id
                    ):
                        conversation_ids.add(conversation_id)
            elif isinstance(query_res.data, model.Tweet) and (
                conversation_id := query_res.data.conversation_id
            ):
                conversation_ids.add(conversation_id)

    for conversation_id in conversation_ids:
        first_pass = True
        pagination_token = None
        conversation = model.Conversation()

        tweet = t.cast(
            Response,
            client.get_tweet(conversation_id, **api_args),
        )
        append_response(
            tweet,
            conversation,
        )

        while pagination_token or first_pass:
            first_pass = False

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

        username = ""

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
        conversation_path.parent.mkdir(parents=True, exist_ok=True)

        with (conversation_path).with_suffix(".json").open("w", encoding="utf-8") as f:
            json.dump(conversation.to_dict(), f)
