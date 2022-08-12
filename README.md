# Twitter2Arguebuf

## Downloading Tweets

```sh
QUERY="INSERT_YOUR_QUERY_HERE"
poetry run python -m twarc search --archive --sort-order relevancy --start-time 2020-01-01 --end-time 2021-01-31 --minimal-fields --limit 100 --max-results 55 "$QUERY" data/tweets.jsonl
poetry run python -m twarc dehydrate data/tweets.jsonl data/tweet-ids.txt
poetry run python -m twarc conversations --archive --conversation-limit 1000 --sort-order relevancy --start-time 2020-01-01 --end-time 2021-01-31 data/tweet-ids.txt data/conversations.jsonl
poetry run python -m twitter2arguebuf convert data conversations.jsonl --output-folder data/generated-graphs --render --min-chars 70 --min-interactions 1 --min-depth 1
```

## Queries

- `((#trump2020 OR #trump OR #kag OR #americafirst OR #kag2020 OR #maga2020 OR #trump2020landslide OR #donaldtrump OR #mypresident) OR (#bidenharris2020 OR #joebiden OR #biden2020 OR #demconvention OR #dembate OR #democrats OR #yanggang OR #biden OR #votetrumpout) OR (#wwg1wga OR #stopthesteal OR #qanon OR #dobbs) OR (#vote OR #election2020 OR #debates2020 OR #2020election OR #november3rd OR #novemberiscoming OR #elections_2020 OR #2020elections OR #uselections)) -is:retweet -is:reply -is:quote -is:nullcast lang:en`
- `(#vote OR #election2020 OR #elections2020) -is:retweet -is:reply -is:quote -is:nullcast is:verified lang:en`
