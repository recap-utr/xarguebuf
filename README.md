# Twitter2Arguebuf

## Counting Tweets

```sh
QUERY="INSERT_YOUR_QUERY_HERE"
poetry run python -m twitter2arguebuf count --start-time 2020-02-03 --end-time 2020-11-02 "($QUERY) -is:retweet -is:reply -is:quote is:verified lang:en"
```

## Downloading Tweets

Specify the query

`QUERY="2020election OR #biden2020 OR #trump2020"`

Save all tweet ids that match your query

`poetry run python -m twarc search --archive --sort-order relevancy --start-time 2020-02-03 --end-time 2020-11-02 --minimal-fields --limit 500 --max-results 100 "($QUERY) -is:retweet -is:reply -is:quote is:verified lang:en" /dev/stdout | poetry run python -m twarc dehydrate - data/tweets.txt`

Download the complete archive of all conversations that above tweets are part of

`poetry run python -m twarc conversations --archive --start-time 2020-02-03 --end-time 2020-11-02 data/tweets.txt data/conversations.jsonl`

Convert the saved conversations to argument graphs

`poetry run python -m twitter2arguebuf convert data conversations.jsonl --output-folder data/graphs --render --min-chars 50 --min-interactions 0 --min-depth 1`

## Exemplary Queries

The `-is:nullcast` filter results in API errors but is potentially useful.

### Experimental version

```txt
(#trump2020 OR #trump OR #kag OR #americafirst OR #kag2020 OR #maga2020 OR #trump2020landslide OR #donaldtrump OR #mypresident) OR (#bidenharris2020 OR #joebiden OR #biden2020 OR #demconvention OR #dembate OR #democrats OR #yanggang OR #biden OR #votetrumpout) OR (#wwg1wga OR #stopthesteal OR #qanon OR #dobbs) OR (#vote OR #election2020 OR #debates2020 OR #2020election OR #november3rd OR #novemberiscoming OR #elections_2020 OR #2020elections OR #uselections)
```

### Long version (too long for the API)

```txt
#2020election OR #2020elections OR #2020usaelection OR #4moreyears OR #americafirst OR #biden OR #biden2020 OR #bidencorruption OR #bidencrimefamiily OR #bidencrimefamily OR #bidenharris2020 OR #blexit OR #bluewave2020 OR #covid19 OR #debate2020 OR #donaldtrump OR #draintheswamp OR #election2020 OR #electionday OR #elections_2020 OR #elections2020 OR #fourmoreyears OR #gop OR #hunterbidenlaptop OR #joebiden OR #kag OR #kag2020 OR #keepamericagreat OR #latinosfortrump OR #maga OR #maga2020 OR #maga2020landslidevictory OR #makeamericagreatagain OR #michigan OR #miga OR #mypresident OR #november3rd OR #novemberiscoming OR #patriotismwins OR #pennsylvania OR #qanon OR #redwave OR #restart_opposition OR #sleepyjoe OR #stopthesteal OR #trump OR #trump2020 OR #trump2020landslide OR #trump2020landslidevictory OR #trump2020nowmorethanever OR #trump2020tosaveamerica OR #trumphasnoplan OR #trumplandslidevictory2020 OR #trumpliespeopledie OR #trumppence2020 OR #trumprally OR #trumptaxreturns OR #trumpvirus OR #usa OR #uselections OR #vote OR #vote2020 OR #votebluetosaveamerica OR #votered OR #voteredlikeyourlifedependsonit OR #voteredtosaveamerica OR #voteredtosaveamerica2020 OR #votetrump2020 OR #votetrumpout OR #walkaway OR #wwg1wga OR #yourchoice
```

### Medium version

```txt
#2020election OR #2020elections OR #4moreyears OR #americafirst OR #biden OR #biden2020 OR #bidenharris2020 OR #bluewave2020 OR #covid19 OR #debate2020 OR #donaldtrump OR #draintheswamp OR #election2020 OR #electionday OR #elections_2020 OR #elections2020 OR #fourmoreyears OR #gop OR #joebiden OR #kag OR #kag2020 OR #keepamericagreat OR #latinosfortrump OR #maga OR #maga2020 OR #makeamericagreatagain OR #mypresident OR #november3rd OR #novemberiscoming OR #patriotismwins OR #qanon OR #redwave OR #stopthesteal OR #trump OR #trump2020 OR #trump2020landslide OR #trumphasnoplan OR #trumpliespeopledie OR #trumppence2020 OR #trumpvirus OR #uselections OR #vote OR #vote2020 OR #votebluetosaveamerica OR #votered OR #voteredlikeyourlifedependsonit OR #voteredtosaveamerica OR #votetrump2020 OR #votetrumpout OR #yourchoice OR #americafirst
```

### Short version

```txt
#2020election OR #2020elections OR #biden OR #bidenharris2020 OR #bluewave2020 OR #donaldtrump OR #election2020 OR #mypresident OR #november3rd OR #novemberiscoming OR #trump OR #trump2020 OR #trumphasnoplan OR #trumpliespeopledie OR #trumptaxreturns OR #trumpvirus OR #uselections OR #vote OR #votebluetosaveamerica OR #voteredlikeyourlifedependsonit OR #votetrumpout OR #yourchoice
```

## Datset

- Number of matched tweets: 2181969
- Query: `#2020election OR #2020elections OR #4moreyears OR #americafirst OR #biden OR #biden2020 OR #bidenharris2020 OR #bluewave2020 OR #covid19 OR #debate2020 OR #donaldtrump OR #draintheswamp OR #election2020 OR #electionday OR #elections_2020 OR #elections2020 OR #fourmoreyears OR #gop OR #joebiden OR #kag OR #kag2020 OR #keepamericagreat OR #latinosfortrump OR #maga OR #maga2020 OR #makeamericagreatagain OR #mypresident OR #november3rd OR #novemberiscoming OR #patriotismwins OR #qanon OR #redwave OR #stopthesteal OR #trump OR #trump2020 OR #trump2020landslide OR #trumphasnoplan OR #trumpliespeopledie OR #trumppence2020 OR #trumpvirus OR #uselections OR #vote OR #vote2020 OR #votebluetosaveamerica OR #votered OR #voteredlikeyourlifedependsonit OR #voteredtosaveamerica OR #votetrump2020 OR #votetrumpout OR #yourchoice OR #americafirst`
