import json
import os
import typing as t
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pendulum
import typer
from dateutil import parser as dt_parser
from dotenv import load_dotenv
from pytwitter import Api
from pytwitter.models.ext import Response
from twarc.client2 import Twarc2

from twitter2arguebuf import model

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

    typer.echo(f"{total_tweets=}")
