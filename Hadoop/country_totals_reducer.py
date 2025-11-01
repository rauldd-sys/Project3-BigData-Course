#!/usr/bin/env python3
"""
Reducer for Hadoop Streaming: aggregates cases and deaths per country.

Input: country<TAB>cases,deaths (from country_totals_mapper.py)
Output: country<TAB>total_cases,total_deaths
"""

import sys


def emit(country: str, cases: int, deaths: int):
    print(f"{country}\t{cases},{deaths}")


def flush(current_country, totals):
    if current_country is None:
        return
    emit(current_country, totals["cases"], totals["deaths"])


def main():
    current_country = None
    totals = {"cases": 0, "deaths": 0}

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            country, payload = line.split("\t", 1)
            cases_str, deaths_str = payload.split(",", 1)
            cases = int(cases_str)
            deaths = int(deaths_str)
        except ValueError:
            # Malformed line; skip
            continue

        if country != current_country:
            flush(current_country, totals)
            current_country = country
            totals = {"cases": 0, "deaths": 0}

        totals["cases"] += cases
        totals["deaths"] += deaths

    flush(current_country, totals)


if __name__ == "__main__":
    main()
