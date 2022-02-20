import os
import typing as t
from datetime import datetime

import typer
from dotenv import load_dotenv
from twarc.client2 import Twarc2

load_dotenv()

client = Twarc2(bearer_token=os.getenv("BEARER_TOKEN"))


def count(
    query: str,
    start_time: t.Optional[datetime] = None,
    end_time: t.Optional[datetime] = None,
):
    response = client.counts_all(
        query,
        start_time=start_time,
        end_time=end_time,
        granularity="day",
    )

    total_tweets = sum(entry["meta"]["total_tweet_count"] for entry in response)
    typer.echo(total_tweets)
