# Project 3 – Hadoop Streaming Cheatsheet

The commands below assume you are inside the course Hadoop Docker container (`rdurandealba/hadoop_mac_class`) with the project folder mounted at `/workspace`. Adjust paths if your setup differs.

## 1. One-time setup

```bash
# inside the container
cd /workspace/data_integration_and_big_data/Project3/Hadoop
export HADOOP_USER_NAME=hduser

# Put the COVID NDJSON dataset into HDFS
hdfs dfs -mkdir -p /user/hduser/covid/input
hdfs dfs -copyFromLocal /Users/raulduran/Documents/M2_GENIOMHE/data_integration_and_big_data/Project3/data/encounters.ndjson /user/hduser/covid/input/encounters.ndjson

# Make mapper/reducer scripts executable
chmod +x country_totals_mapper.py country_totals_reducer.py \
         rolling14_mapper.py rolling14_reducer.py
```

To verify everything is reachable:

```bash
hdfs dfs -ls /user/hduser/covid/input
```

## 2. Job: total cases & deaths per country

```bash
# Optional local smoke test
head -5 encounters.ndjson \
  | ./country_totals_mapper.py \
  | sort \
  | ./country_totals_reducer.py

# Run on Hadoop
time hadoop jar /opt/hadoop/share/hadoop/tools/lib/hadoop-streaming-3.3.6.jar \
  -files /workspace/country_totals_mapper.py,\
/workspace/country_totals_reducer.py \
  -mapper /workspace/country_totals_mapper.py \
  -reducer /workspace/country_totals_reducer.py \
  -input /user/hduser/covid/input/encounters.ndjson \
  -output /user/hduser/covid/output_country_totals

# Inspect top countries
hdfs dfs -cat /user/hduser/covid/output_country_totals/part-* \
  | sort -t$'\t' -k2,2nr \
  | head -n 15
```

Clean up the output if you plan to re-run:

```bash
hdfs dfs -rm -r /user/hduser/covid/output_country_totals
```

## 3. Job: peak 14-day rolling cases per country

```bash
# Optional local smoke test
head -5 encounters.ndjson \
  | ./rolling14_mapper.py \
  | sort \
  | ./rolling14_reducer.py

# Run on Hadoop
time hadoop jar /opt/hadoop/share/hadoop/tools/lib/hadoop-streaming-3.3.6.jar \
  -files /workspace/rolling14_mapper.py,\
/workspace/rolling14_reducer.py \
  -mapper /workspace/rolling14_mapper.py \
  -reducer /workspace/rolling14_reducer.py \
  -input /user/hduser/covid/input/encounters.ndjson \
  -output /user/hduser/covid/output_peak14

# Inspect top peaks
hdfs dfs -cat /user/hduser/covid/output_peak14/part-* \
  | sort -t$'\t' -k2,2nr \
  | head -n 15
```

Clean up the output if you plan to re-run:

```bash
hdfs dfs -rm -r /user/hduser/covid/output_peak14
```
