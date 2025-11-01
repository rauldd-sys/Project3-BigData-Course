#!/usr/bin/env python3
"""
Reducer for Hadoop Streaming: computes peak 14-day rolling case counts per country.

Input: country<TAB>date,cases (from rolling14_mapper.py)
Output: country<TAB>peakRolling14
"""

import sys
from datetime import datetime

DATE_FORMAT = "%d/%m/%Y"


def flush(country, entries):
    if country is None:
        return

    sorted_entries = sorted(entries, key=lambda item: item[0])
    peak = 0
    window_sum = 0
    window = []

    for date_obj, cases in sorted_entries:
        window.append((date_obj, cases))
        window_sum += cases

        # Remove entries older than 14 days window (inclusive of current day)
        while window:
            delta = (date_obj - window[0][0]).days
            if delta >= 14:
                _, oldest_cases = window.pop(0)
                window_sum -= oldest_cases
            else:
                break

        if window_sum > peak:
            peak = window_sum

    print(f"{country}\t{peak}")


def main():
    current_country = None
    entries = []

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            country, payload = line.split("\t", 1)
            date_str, cases_str = payload.split(",", 1)
            date_obj = datetime.strptime(date_str, DATE_FORMAT)
            cases = int(cases_str)
        except ValueError:
            continue

        if country != current_country:
            flush(current_country, entries)
            current_country = country
            entries = []

        entries.append((date_obj, cases))

    flush(current_country, entries)


if __name__ == "__main__":
    main()
