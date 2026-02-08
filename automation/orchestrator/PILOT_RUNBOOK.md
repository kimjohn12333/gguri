# Team Mode Pilot Runbook (MVP)

Path: `automation/orchestrator/PILOT_RUNBOOK.md`
Scope: ORCH-008 smoke run for token-efficient Team Mode operation.

## 1) Objective / Scope
- Validate one end-to-end Team Mode cycle:
  - task creation
  - worker assignment
  - compact report collection
  - lead finalization
- Enforce `automation/orchestrator/TOKEN_POLICY.md` Compact Report format.
- Keep output practical (single pilot run, single smoke log).

## 2) Prerequisites
- Queue item exists and is `IN_PROGRESS`: `ORCH-008` in `automation/orchestrator/QUEUE.md`
- Team rules reviewed:
  - `automation/orchestrator/TEAM_MODE.md`
  - `automation/orchestrator/TOKEN_POLICY.md`
- Task template available: `automation/orchestrator/team_task_template.json`
- Queue CLI available: `python3 automation/orchestrator/orch.py`

## 3) Run Procedure (MVP)
1. **Create tasks**
   - Define 1 lead task + 1~3 worker subtasks (clear file-path outputs first).
   - Use `[TASK <id>]` prefix and success criteria as checkable bullets.
2. **Assign workers**
   - Lead assigns each subtask to one worker session.
   - Keep instructions compact: objective, paths, validation command, stop condition.
3. **Collect compact reports**
   - Require worker output in Compact Report only:
     - `[REPORT <task-id>]`
     - `Status / Files / Diff-Summary / Validation / Risks / Next`
   - Reject long narrative; request reformat when template is violated.
4. **Finalize**
   - Lead merges worker outcomes into one short summary.
   - Persist artifacts (docs/logs) to repository paths.
   - Update queue terminal state via CLI:
     - success: `orch.py done`
     - failure: `orch.py fail`

## 4) Failure Handling Checkpoints
- **Checkpoint A: Task definition ambiguity**
  - Signal: worker asks scope clarification repeatedly.
  - Action: rewrite task with exact output paths + acceptance lines.
- **Checkpoint B: Compact report violation**
  - Signal: verbose/raw dump instead of template.
  - Action: request strict re-report using Compact Report.
- **Checkpoint C: Validation failure**
  - Signal: file missing / command fails / malformed markdown.
  - Action: return task to worker with one explicit fix list.
- **Checkpoint D: Dependency blocked**
  - Signal: external auth/tooling unavailable.
  - Action: stop run, mark queue `FAILED` with reason + next action.

## 5) Rollback Steps
1. Revert pilot-only doc/log edits if run is invalid.
2. Restore queue status from incorrect terminal state if needed.
3. Record rollback reason in queue notes (1-2 lines, actionable).
4. Re-run from Step 1 with narrowed scope (single worker first).

## 6) Minimum Exit Criteria
- `automation/orchestrator/PILOT_RUNBOOK.md` exists.
- `automation/orchestrator/pilot_logs/ORCH-008-smoke-2026-02-07.md` exists.
- `automation/orchestrator/README.md` references both paths.
- `automation/orchestrator/QUEUE.md` shows ORCH-008 terminal status + concise notes.

## 7) Operator Procedure (Incidents)
Use `ops.py` for fast triage/contain/recovery during pilot incidents.

1. **Triage current load**
   - `python3 automation/orchestrator/ops.py status`
   - (db mode) `python3 automation/orchestrator/ops.py --db automation/orchestrator/db/queue.db status`
2. **Contain runaway work**
   - `python3 automation/orchestrator/ops.py cancel --id ORCH-xxx`
   - Result: item moves to `BLOCKED` with cancellation note.
3. **Replan**
   - `python3 automation/orchestrator/ops.py replan --id ORCH-xxx --notes "<why/how>"`
   - Rule: `IN_PROGRESS -> BLOCKED`, otherwise `-> PENDING`.
4. **Retry transient failures**
   - `python3 automation/orchestrator/ops.py retry --id ORCH-xxx`
   - In db mode, max-attempt and retry policy are enforced.
5. **Close the loop**
   - After mitigation, use `orch.py done/fail` for terminal outcome with concise notes.
