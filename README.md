# gguri

Task queue orchestration toolkit for long-running agent workflows.

## What it includes
- Markdown + SQLite queue backends
- Dispatcher / Watchdog operation docs
- Reviewer Gate loop (PASS / RETRY / BLOCK)
- Token guardrails and reliability policies
- Operator CLI (`orch.py`, `ops.py`)

## Quick start
```bash
python3 -m pytest automation/orchestrator/tests -q
python3 automation/orchestrator/orch.py list
```

## Project layout
- `automation/orchestrator/` — core code, docs, tests
- `.github/workflows/ci.yml` — CI pipeline

## Notes
Runtime logs are ignored from Git and should stay local.
