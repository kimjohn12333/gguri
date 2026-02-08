from __future__ import annotations

import argparse
import subprocess
from typing import Callable, Iterable


Runner = Callable[[list[str], int], tuple[int, str, str]]


def _default_runner(cmd: list[str], timeout_seconds: int) -> tuple[int, str, str]:
    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except FileNotFoundError:
        return 127, "", f"command_not_found:{cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def _session_args(session: str | None) -> list[str]:
    if not session:
        return []
    return [f"--session={session}"]


def _contains_all(snapshot_text: str, required_terms: Iterable[str]) -> list[str]:
    lower = snapshot_text.lower()
    missing: list[str] = []
    for term in required_terms:
        t = term.strip()
        if not t:
            continue
        if t.lower() not in lower:
            missing.append(t)
    return missing


def validate_ui(
    url: str,
    required_terms: list[str] | None = None,
    *,
    timeout_seconds: int = 45,
    session: str | None = None,
    runner: Runner | None = None,
) -> dict:
    """Run a minimal Playwright-CLI UI smoke validation.

    Flow:
    1) playwright-cli open <url>
    2) playwright-cli snapshot
    3) Verify required terms appear in snapshot output
    """

    run = runner or _default_runner
    terms = required_terms or []

    open_cmd = ["playwright-cli", *_session_args(session), "open", url]
    rc, out, err = run(open_cmd, timeout_seconds)
    if rc != 0:
        reason = (err or out).strip() or f"open_failed_rc={rc}"
        return {
            "ok": False,
            "reasons": [f"ui_open_failed:{reason}"],
            "missing": terms,
            "snapshot_excerpt": "",
        }

    snapshot_cmd = ["playwright-cli", *_session_args(session), "snapshot"]
    rc, out, err = run(snapshot_cmd, timeout_seconds)
    if rc != 0:
        reason = (err or out).strip() or f"snapshot_failed_rc={rc}"
        return {
            "ok": False,
            "reasons": [f"ui_snapshot_failed:{reason}"],
            "missing": terms,
            "snapshot_excerpt": "",
        }

    snapshot_text = (out or "") + ("\n" + err if err else "")
    missing = _contains_all(snapshot_text, terms)
    if missing:
        return {
            "ok": False,
            "reasons": [f"ui_missing_terms:{','.join(missing)}"],
            "missing": missing,
            "snapshot_excerpt": snapshot_text[:400],
        }

    return {
        "ok": True,
        "reasons": ["ui_smoke_passed"],
        "missing": [],
        "snapshot_excerpt": snapshot_text[:400],
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run UI smoke validation using playwright-cli")
    p.add_argument("--url", required=True)
    p.add_argument("--contains", action="append", default=[], help="Text that must appear in snapshot output")
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--session", help="Optional playwright-cli session name")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate_ui(
        args.url,
        args.contains,
        timeout_seconds=args.timeout_seconds,
        session=args.session,
    )
    if result["ok"]:
        print("UI_SMOKE_OK")
        return 0

    print("UI_SMOKE_FAIL: " + ";".join(result.get("reasons", [])))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
