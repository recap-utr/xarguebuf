import os
import typing as t
from datetime import datetime

from dotenv import load_dotenv
from rich import print
from twarc.client2 import Twarc2

load_dotenv()


def count(
    query: str,
    start_time: t.Optional[datetime] = None,
    end_time: t.Optional[datetime] = None,
):
    client = Twarc2(bearer_token=os.getenv("BEARER_TOKEN"))
    response = client.counts_all(
        query,
        start_time=start_time,
        end_time=end_time,
        granularity="day",
    )

    total_tweets = sum(entry["meta"]["total_tweet_count"] for entry in response)
    print(total_tweets)
