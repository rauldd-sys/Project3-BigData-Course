#!/usr/bin/env python3
"""
Mapper for Hadoop Streaming: emits (country, date, cases) tuples for rolling 14-day aggregation.

Output format: country<TAB>date,cases
"""

import json
import sys


def parse_line(raw_line: str):
    try:
        record = json.loads(raw_line)
    except json.JSONDecodeError:
        return None

    country = record.get("countriesAndTerritories")
    date_rep = record.get("dateRep")
    cases = record.get("cases")

    if not country or not date_rep or cases is None:
        return None

    try:
        cases = int(cases)
    except (TypeError, ValueError):
        cases = 0

    return country, date_rep, cases


def main():
    for line in sys.stdin:
        parsed = parse_line(line)
        if not parsed:
            continue
        country, date_rep, cases = parsed
        print(f"{country}\t{date_rep},{cases}")


if __name__ == "__main__":
    main()
