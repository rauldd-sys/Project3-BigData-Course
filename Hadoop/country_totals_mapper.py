#!/usr/bin/env python3
"""
Mapper for Hadoop Streaming: aggregates total cases and deaths per country.

Input: NDJSON line with fields defined in health_data.json (e.g., countriesAndTerritories, cases, deaths).
Output: country<TAB>cases,deaths
"""

import json
import sys


def parse_line(raw_line: str):
    try:
        record = json.loads(raw_line)
    except json.JSONDecodeError:
        return None

    country = record.get("countriesAndTerritories")
    if not country:
        return None

    cases = record.get("cases") or 0
    deaths = record.get("deaths") or 0

    try:
        cases = int(cases)
    except (TypeError, ValueError):
        cases = 0

    try:
        deaths = int(deaths)
    except (TypeError, ValueError):
        deaths = 0

    return country, cases, deaths


def main():
    for line in sys.stdin:
        parsed = parse_line(line)
        if not parsed:
            continue
        country, cases, deaths = parsed
        print(f"{country}\t{cases},{deaths}")


if __name__ == "__main__":
    main()
