# Day 3 accuracy and evidence patch

## What changed

- Added `get_monthly_expense_breakdown`, which groups posted operating-expense ledger lines by calendar month and account.
- Added account shares calculated against that same month's expense total, not the full multi-month total.
- Added stable evidence identifiers to monthly P&L and expense results.
- Updated the agent instructions to use server-calculated ratio fields verbatim, cite the tool and period for material numeric claims, and state when the available data is insufficient.
- Updated the capabilities endpoint and tests to include the new tool.

## Why this matters

A three-month expense breakdown can identify the largest expense accounts across the whole period, but cannot establish which account drove a particular month's increase. The new tool supplies that monthly detail. The LLM is also instructed not to recalculate precomputed financial ratios itself.

## Apply

Extract `ProfitPulse_AI_Day3_Accuracy_Patch.zip` into the existing project directory. It overlays only backend source, tests and this document. It does not include `.env`, database initialization files, or Docker volumes.

Then rebuild and verify:

```bash
docker compose build --no-cache api
docker compose up -d --force-recreate api
docker compose exec api pytest -q
curl -s http://localhost:8000/api/v1/agent/capabilities | python3 -m json.tool
```

The capabilities response should include `get_monthly_expense_breakdown`.

To exercise the new evidence path, ask the agent to explain operating-expense changes month by month for `2026-08-01` through `2026-10-31`. Confirm it calls both `get_monthly_financial_trend` and `get_monthly_expense_breakdown`, quotes the returned ratios as-is, and cites the months/accounts used.

## Validation status in the packaging environment

Python syntax parsing passed for all five changed Python files. Full pytest execution could not be completed in the packaging environment because the LangChain/LangGraph dependencies were not installed and package-index access was unavailable. Run the Docker-based pytest command above in the user's existing project environment before considering the patch verified.

## Important remaining limitations

- Evidence references are grounded tool/period identifiers, not formal audit-trail records or links to individual journal entries.
- The prompt reduces unsupported claims but cannot mathematically guarantee that an LLM will never hallucinate. Production should add a structured claim-validation layer and evaluation set.
- This project is still a demo decision-support system. Keep tenant authentication, accounting policy, tax treatment, data-import reconciliation, and audit review in scope before real customer use.
