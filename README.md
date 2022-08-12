# Twitter2Arguebuf

## Downloading Tweets

```sh
QUERY="INSERT_YOUR_QUERY_HERE"
# Save all tweet ids that match your query
poetry run python -m twarc search --archive --sort-order relevancy --start-time 2020-01-01 --end-time 2021-01-31 --minimal-fields --limit 90 --max-results 50 "$QUERY" /dev/stdout | poetry run python -m twarc dehydrate - data/tweets.txt
# Download the complete archive of all conversations that above tweets are part of
poetry run python -m twarc conversations --archive --start-time 2020-01-01 --end-time 2021-01-31 data/tweets.txt data/conversations.jsonl
# Convert the saved conversations to argument graphs
poetry run python -m twitter2arguebuf convert data conversations.jsonl --output-folder data/generated-graphs --render --min-chars 70 --min-interactions 0 --min-depth 2
```

## Exemplary Queries

- `((#trump2020 OR #trump OR #kag OR #americafirst OR #kag2020 OR #maga2020 OR #trump2020landslide OR #donaldtrump OR #mypresident) OR (#bidenharris2020 OR #joebiden OR #biden2020 OR #demconvention OR #dembate OR #democrats OR #yanggang OR #biden OR #votetrumpout) OR (#wwg1wga OR #stopthesteal OR #qanon OR #dobbs) OR (#vote OR #election2020 OR #debates2020 OR #2020election OR #november3rd OR #novemberiscoming OR #elections_2020 OR #2020elections OR #uselections)) -is:retweet -is:reply -is:quote -is:nullcast lang:en`
- `(#vote OR #election2020 OR #elections2020) -is:retweet -is:reply -is:quote -is:nullcast lang:en`
- Potentially useful filter: `is:verified`
