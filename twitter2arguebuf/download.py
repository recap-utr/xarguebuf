import json
import os
import typing as t
from pathlib import Path
from urllib.parse import urlparse

import typer
from dataclasses_json import dataclass_json
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


@app.command()
def run(output_folder: Path, ids_urls: t.List[str]):
    ids: t.Set[str] = set()

    for id_url in ids_urls:
        if "twitter.com/" in id_url:
            url = urlparse(id_url)
            url_segments = str(url.path).split("/")
            ids.add(url_segments[-1])
        else:
            ids.add(id_url)

    for id in ids:
        first_pass = True
        pagination_token = None
        conversation = model.Conversation()
        conversation_id = id

        user_tweet = t.cast(
            Response, client.get_tweet(id, tweet_fields=["conversation_id"])
        )

        if isinstance(user_tweet.data, model.Tweet):
            conversation_id = user_tweet.data.conversation_id

        root_tweet = t.cast(
            Response,
            client.get_tweet(conversation_id or id, **api_args),
        )
        append_response(
            root_tweet,
            conversation,
        )

        while pagination_token or first_pass:
            first_pass = False

            res: Response = t.cast(
                Response,
                client.search_tweets(
                    f"conversation_id:{conversation_id}",
                    start_time=root_tweet.data.created_at
                    if isinstance(root_tweet.data, model.Tweet)
                    else None,
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
            isinstance(root_tweet.data, model.Tweet)
            and root_tweet.includes
            and root_tweet.includes.users
            and (
                found_name := (
                    next(
                        iter(
                            user.username
                            for user in root_tweet.includes.users
                            if user.id == root_tweet.data.author_id
                        )
                    )
                )
            )
        ):
            username = found_name

        conversation_path = output_folder / username / id
        conversation_path.parent.mkdir(parents=True, exist_ok=True)

        with (conversation_path).with_suffix(".json").open("w", encoding="utf-8") as f:
            json.dump(conversation.to_dict(), f)


if __name__ == "__main__":
    app()
