# Day 3.1: Currency and deterministic trend reliability

This overlay adds tenant-configured currency metadata to financial and business tools and exposes deterministic month-over-month revenue and operating-expense changes from Python.

## Changes
- Reads `organizations.base_currency` per request and returns both `currency` and a known `currency_symbol`. Missing configuration remains null; the tool never silently defaults to INR or USD.
- Adds deterministic month-over-month revenue and operating-expense amount/percentage changes to `get_monthly_financial_trend`. Comparisons are withheld when a calendar month is missing from the returned series.
- Tightens the agent prompt: use returned currency, precomputed ratios and account shares; do not recalculate them in prose; do not claim an account is newly incurred merely because it first appears in the requested period.
- Adds regression tests for the August–October 2026 changes and zero prior-period denominators.

## Expected demo values
- August to September revenue change: -₹72,970.23 (-19.65%).
- September to October revenue change: -₹61,190.47 (-20.51%).
- September to October operating-expense change: +₹74,000.00 (+36.63%).
- August to October revenue change is not the month-over-month metric; compute cumulative change only if explicitly requested and have the tool return it.

## Apply
Extract this ZIP at the project root (`~/Projects/profitpulse_day1_complete`), then rebuild the API and run tests as shown in `APPLY_DAY3_1_PATCH.txt`. Do not replace `.env`, and do not remove the PostgreSQL volume.
