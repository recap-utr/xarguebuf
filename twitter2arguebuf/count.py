import typing as t
from datetime import datetime

import rich_click as click
from rich import print
from twarc.client2 import Twarc2


@click.group()
def cli():
    pass


@cli.command()
@click.argument("query", type=str)
@click.option(
    "--start-time",
    type=click.DateTime(formats=("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S")),
    help="Match tweets created after UTC time (ISO 8601/RFC 3339)",
)
@click.option(
    "--end-time",
    type=click.DateTime(formats=("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S")),
    help="Match tweets sent before UTC time (ISO 8601/RFC 3339)",
)
@click.option(
    "--bearer-token",
    type=str,
    envvar="BEARER_TOKEN",
    help="Twitter app access bearer token.",
)
def count(
    query: str,
    start_time: t.Optional[datetime] = None,
    end_time: t.Optional[datetime] = None,
    bearer_token: t.Optional[str] = None,
):
    client = Twarc2(bearer_token=bearer_token)
    response = client.counts_all(
        query,
        start_time=start_time,
        end_time=end_time,
        granularity="day",
    )

    total_tweets = sum(entry["meta"]["total_tweet_count"] for entry in response)
    print(total_tweets)
