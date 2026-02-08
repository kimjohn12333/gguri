#!/usr/bin/env python3
"""Coupang purchase-flow intake for orchestrator queue.

MVP goal:
- Turn one natural-language buying request into a robust queue task
- Keep flow uninterrupted inside a single worker task
- Support safe mode (approval before payment) and auto mode
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from automation.orchestrator.orch import KST, QueueFile, QueueRow

ORCH_ID_RE = re.compile(r"^ORCH-(\d+)$")


@dataclass
class PurchaseSpec:
    request: str
    mode: str  # safe | auto
    max_price: int | None
    qty: int
    must_have: list[str]
    avoid: list[str]


def _clean(text: str) -> str:
    return " ".join(text.strip().split())


def _next_orch_id(rows: list[QueueRow]) -> str:
    max_num = 0
    for r in rows:
        m = ORCH_ID_RE.match(r.id)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"ORCH-{max_num + 1:03d}"


def _task_line(spec: PurchaseSpec) -> str:
    parts = [f"[쿠팡구매/{spec.mode}] {spec.request}", f"qty={spec.qty}"]
    if spec.max_price is not None:
        parts.append(f"max_price={spec.max_price}")
    if spec.must_have:
        parts.append("must=" + ",".join(spec.must_have))
    if spec.avoid:
        parts.append("avoid=" + ",".join(spec.avoid))
    return " | ".join(parts)


def _success_criteria(spec: PurchaseSpec) -> str:
    base = [
        "1) 쿠팡 후보 3개 비교(가격/배송/판매자/리뷰)",
        "2) 제약 충족 최종 1개 선정",
        "3) 장바구니 담기 및 옵션/수량 확인",
    ]
    if spec.mode == "safe":
        base.append("4) 결제 직전 도달 후 사용자 승인 요청")
    else:
        base.append("4) 주문 완료 + 주문번호/결제결과 기록")
    return "; ".join(base)


def build_spec(args: argparse.Namespace) -> PurchaseSpec:
    request = _clean(args.request)
    if not request:
        raise ValueError("request is empty")
    if args.qty < 1:
        raise ValueError("qty must be >= 1")
    if args.max_price is not None and args.max_price < 0:
        raise ValueError("max-price must be >= 0")

    return PurchaseSpec(
        request=request,
        mode=args.mode,
        max_price=args.max_price,
        qty=args.qty,
        must_have=[_clean(x) for x in args.must_have if _clean(x)],
        avoid=[_clean(x) for x in args.avoid if _clean(x)],
    )


def cmd_plan(args: argparse.Namespace) -> int:
    spec = build_spec(args)
    print(f"request: {spec.request}")
    print(f"mode: {spec.mode}")
    print(f"task: {_task_line(spec)}")
    print(f"success_criteria: {_success_criteria(spec)}")
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    spec = build_spec(args)
    qf = QueueFile(Path(args.queue))
    row_id = _next_orch_id(qf.rows)

    now_tag = datetime.now(KST).strftime("%Y%m%d-%H%M")
    notes = f"coupang_intake:{now_tag} mode={spec.mode}"

    qf.rows.append(
        QueueRow(
            id=row_id,
            status="PENDING",
            priority=args.priority,
            task=_task_line(spec),
            success_criteria=_success_criteria(spec),
            owner_session="-",
            started_at_kst="-",
            due_at_kst=args.due_at_kst or "-",
            notes=notes,
        )
    )
    qf.save()

    print(f"created=1 id={row_id}")
    print(f"task={_task_line(spec)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Coupang purchase intake for orchestrator")
    p.add_argument("--queue", default="automation/orchestrator/QUEUE.md")

    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--request", required=True, help="What to buy (natural-language)")
    common.add_argument("--mode", choices=["safe", "auto"], default="safe")
    common.add_argument("--max-price", type=int)
    common.add_argument("--qty", type=int, default=1)
    common.add_argument("--must-have", action="append", default=[])
    common.add_argument("--avoid", action="append", default=[])

    plan = sub.add_parser("plan", parents=[common], help="Preview generated task only")
    plan.set_defaults(func=cmd_plan)

    submit = sub.add_parser("submit", parents=[common], help="Write one purchase task into queue")
    submit.add_argument("--priority", choices=["P0", "P1", "P2"], default="P0")
    submit.add_argument("--due-at-kst")
    submit.set_defaults(func=cmd_submit)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
