"""
PySpark job for Project 3 - Health Data Analytics.

Usage example (inside spark-submit):
    spark-submit --master local[4] spark_health_analysis.py \
        --input data_integration_and_big_data/Project3/data/encounters.ndjson \
        --output analytics_spark

The job produces three outputs:
    1. country_totals: total cases/deaths and derived KPIs by country
    2. continent_yearly: yearly totals per continent
    3. monthly_trend: global monthly cases/deaths
Each dataset is written as Parquet under the provided output directory.
"""

from __future__ import annotations

import argparse
from typing import Tuple

from pyspark.sql import DataFrame, SparkSession, functions as F


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to encounters.ndjson")
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for aggregated Parquet datasets",
    )
    return parser.parse_args()


def read_dataset(spark: SparkSession, path: str) -> DataFrame:
    df = (
        spark.read.option("multiline", "false")
        .json(path)
        .withColumnRenamed("Cumulative_number_for_14_days_of_COVID-19_cases_per_100000", "cumulative14d")
    )
    return df


def compute_country_totals(df: DataFrame) -> DataFrame:
    aggregated = (
        df.groupBy("countriesAndTerritories")
        .agg(
            F.sum("cases").alias("total_cases"),
            F.sum("deaths").alias("total_deaths"),
            F.max("popData2019").alias("population"),
            F.max("continentExp").alias("continent"),
        )
        .withColumn(
            "case_fatality_rate",
            F.when(F.col("total_cases") > 0, F.round(F.col("total_deaths") / F.col("total_cases") * 100, 2)).otherwise(None),
        )
        .withColumn(
            "cases_per_100k",
            F.when(
                F.col("population") > 0,
                F.round(F.col("total_cases") / F.col("population") * 100000, 2),
            ).otherwise(None),
        )
        .orderBy(F.desc("total_cases"))
    )
    return aggregated


def compute_continent_yearly(df: DataFrame) -> DataFrame:
    return (
        df.groupBy("continentExp", "year")
        .agg(F.sum("cases").alias("cases"), F.sum("deaths").alias("deaths"))
        .orderBy("continentExp", "year")
    )


def compute_monthly_trend(df: DataFrame) -> DataFrame:
    return (
        df.groupBy("year", "month")
        .agg(F.sum("cases").alias("cases"), F.sum("deaths").alias("deaths"))
        .orderBy("year", "month")
    )


def write_output(df: DataFrame, path: str):
    df.write.mode("overwrite").parquet(path)


def main():
    args = parse_args()
    spark = SparkSession.builder.appName("HealthDataAnalytics").getOrCreate()

    raw_df = read_dataset(spark, args.input)

    country_totals = compute_country_totals(raw_df)
    continent_yearly = compute_continent_yearly(raw_df)
    monthly_trend = compute_monthly_trend(raw_df)

    write_output(country_totals, f"{args.output}/country_totals")
    write_output(continent_yearly, f"{args.output}/continent_yearly")
    write_output(monthly_trend, f"{args.output}/monthly_trend")

    # Convenience: show top rows for quick validation
    print("Top 10 countries by total cases:")
    country_totals.show(10, truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
