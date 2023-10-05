# xArguebuf

To convert the conversations to graphs, only the first section (Docker Usage) is relevant.
Please ignore the sections afterwards (Counting Tweets and below).

## Usage

The app is currently supplied as a pre-built Docker image.
Execute the following to install the image:

```sh
docker load -i dockerImage.tar.gz
```

To read and write data, you have to bind a folder (e.g., `./data`) to the container.
The command to run can simply be appended to the invocation.
Thus, run it as follows:

```sh
docker run -it --rm -v $(pwd)/data:/app/data xarguebuf $CMD
```

To get an overview of the options, run `xarguebuf convert --help`.
As a start, you may want to try the following: `xarguebuf convert ./data/conversations.jsonl ./data/graphs --tweet-min-chars 50`.
_Please note:_ Graphs having more than 1000 nodes will not be rendered as this takes way too much time.

## X (formerly Twitter)

We only considered tweets that were posted between 2020-02-03 (start of primaries in Iowa) and 2020-11-02 (day before election).
Removed from the result sets are retweets, replies, and quotes.
We further restrict the potential conversation starting points to tweets that were posted by verified users and are in English.
The conversations have been downloaded on 2022-12-08.

```sh
$QUERY="#2020election OR #2020elections OR #4moreyears OR #americafirst OR #biden OR #biden2020 OR #bidenharris2020 OR #bluewave2020 OR #covid19 OR #debate2020 OR #donaldtrump OR #draintheswamp OR #election2020 OR #electionday OR #elections_2020 OR #elections2020 OR #fourmoreyears OR #gop OR #joebiden OR #kag OR #kag2020 OR #keepamericagreat OR #latinosfortrump OR #maga OR #maga2020 OR #makeamericagreatagain OR #mypresident OR #november3rd OR #novemberiscoming OR #patriotismwins OR #qanon OR #redwave OR #stopthesteal OR #trump OR #trump2020 OR #trump2020landslide OR #trumphasnoplan OR #trumpliespeopledie OR #trumppence2020 OR #trumpvirus OR #uselections OR #vote OR #vote2020 OR #votebluetosaveamerica OR #votered OR #voteredlikeyourlifedependsonit OR #voteredtosaveamerica OR #votetrump2020 OR #votetrumpout OR #yourchoice OR #americafirst"
$PARAMETERS="-is:retweet -is:reply -is:quote is:verified lang:en"
$START_TIME="2020-02-03"
$END_TIME="2020-11-02"
```

### Counting Tweets

```sh
xarguebuf count --start-time "$START_TIME" --end-time "$END_TIME" "($QUERY) $PARAMETERS"
```

Number of matched tweets: 2181969

### Downloading Tweets

```sh
# Save all tweets that match the query
xarguebuf api search --archive --sort-order relevancy --start-time "$START_TIME" --end-time "$END_TIME" --minimal-fields --limit 500 --max-results 100 "($QUERY) $PARAMETERS" data/tweets.jsonl
# Extract their IDs
xarguebuf api dehydrate data/tweets.jsonl data/tweetids.txt
# Download the complete archive of all conversations that above tweets are part of
xarguebuf api conversations --archive --start-time "$START_TIME" --end-time "$END_TIME" data/tweetsids.txt data/conversations.jsonl
```

### Converting Conversations to Graphs

To ensure a certain argumentative quality, we require tweets to have at least 20 chars and one interaction (i.e., like, quote, retweet, reply).
Further, we require graphs to have at least 2 levels and 3 nodes and thus employ a meaningful structure.
We discard graphs having more than 50 nodes to keep the annotation effort manageable.

```sh
xarguebuf convert ./data/conversations.jsonl ./data/graphs --tweet-min-chars 20 --tweet-min-interactions 1 --graph-min-depth 2 --graph-min-nodes 3 --graph-max-nodes 50
```

## Hacker News

The data has been downloaded on 2023-10-05.

```sh
# Ask HN posts
xarguebuf hn api --output-folder ./data/hn/askstories --endpoint-name askstories --story-min-score 10 --story-min-descendants 10 --story-max-descendants 100 --comment-min-chars 20 --graph-min-depth 2
# Regular posts
xarguebuf hn api --output-folder ./data/hn/beststories --endpoint-name beststories --story-min-score 10 --story-min-descendants 10 --story-max-descendants 100 --comment-min-chars 20 --graph-min-depth 2
```
