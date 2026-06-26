#!/usr/bin/env python3
"""End-to-end test harness for a running QueueStorm Investigator service.

For every public sample case it POSTs the ``input`` to ``/analyze-ticket``,
measures the call latency, and compares the response to ``expected_output``.

Cases run strictly **one at a time**: each request waits for the previous
response, then pauses ``--delay`` seconds (default 1.0) before firing the next.
The pause is excluded from the reported latency.

Two kinds of fields are treated differently:

* **Structured fields** (decide PASS/FAIL): ``relevant_transaction_id``,
  ``evidence_verdict``, ``case_type``, ``department``, ``severity``,
  ``human_review_required``. These have one correct value, so a mismatch fails
  the case.
* **Free-text fields** (logged only, never fail a case): ``agent_summary``,
  ``recommended_next_action``, ``customer_reply``. Many valid phrasings exist
  (especially with the LLM on), so we just record expected vs. actual side by
  side for human review.

Outputs (written to ``test-log/``, which is git-ignored):
  * ``summary_<ts>.txt``  — per-case PASS/FAIL, structured diffs, latency table.
  * ``text_fields_<ts>.md`` — expected vs. actual for the 3 free-text fields.
  * ``results_<ts>.json`` — full machine-readable record of the run.

Usage:
    uv run python scripts/run_test_suite.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLE_FILE = REPO_ROOT / "docs" / "SUST_Preli_Sample_Cases.json"
LOG_DIR = REPO_ROOT / "test-log"

# Fields with exactly one correct value -> a mismatch fails the case.
STRUCTURED_FIELDS = [
    "relevant_transaction_id",
    "evidence_verdict",
    "case_type",
    "department",
    "severity",
    "human_review_required",
]

# Open-ended text -> logged for human comparison, never fails a case.
TEXT_FIELDS = ["agent_summary", "recommended_next_action", "customer_reply"]


def _structured_diffs(actual: dict, expected: dict) -> list[str]:
    diffs = []
    for field in STRUCTURED_FIELDS:
        if field not in expected:
            continue
        got = actual.get(field)
        exp = expected[field]
        if got != exp:
            diffs.append(f"{field}: got={got!r} expected={exp!r}")
    return diffs


def run(base_url: str, sample_file: Path, timeout: float, delay: float) -> int:
    cases = json.loads(sample_file.read_text(encoding="utf-8"))["cases"]
    url = base_url.rstrip("/") + "/analyze-ticket"

    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary_path = LOG_DIR / f"summary_{ts}.txt"
    text_path = LOG_DIR / f"text_fields_{ts}.md"
    json_path = LOG_DIR / f"results_{ts}.json"

    records: list[dict] = []
    summary_lines: list[str] = []
    text_lines: list[str] = []

    header = f"QueueStorm test run @ {ts}  ->  {url}"
    summary_lines.append(header)
    summary_lines.append("=" * len(header))
    summary_lines.append("")

    text_lines.append(f"# QueueStorm free-text field comparison — {ts}")
    text_lines.append("")
    text_lines.append(
        "These fields are **not** scored pass/fail — many valid phrasings exist. "
        "Shown for human review only."
    )
    text_lines.append("")

    passed = 0
    errored = 0
    latencies: list[float] = []

    for idx, case in enumerate(cases):
        # Sequential pacing: wait `delay` seconds between cases (after the
        # previous response landed). The delay is NOT counted in latency.
        if idx > 0 and delay > 0:
            time.sleep(delay)

        case_id = case["id"]
        label = case.get("label", "")
        expected = case["expected_output"]

        record: dict = {
            "id": case_id,
            "label": label,
            "status": None,
            "http_status": None,
            "latency_ms": None,
            "structured_diffs": [],
            "text_fields": {},
        }

        start = time.perf_counter()
        try:
            resp = httpx.post(url, json=case["input"], timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.perf_counter() - start) * 1000.0
            record["status"] = "ERROR"
            record["latency_ms"] = round(latency_ms, 1)
            record["error"] = f"{type(exc).__name__}: {exc}"
            records.append(record)
            errored += 1
            summary_lines.append(
                f"{case_id:<10} ERROR  {record['error']}  ({latency_ms:.0f} ms)"
            )
            continue

        latency_ms = (time.perf_counter() - start) * 1000.0
        latencies.append(latency_ms)
        record["latency_ms"] = round(latency_ms, 1)
        record["http_status"] = resp.status_code

        if resp.status_code != 200:
            record["status"] = "ERROR"
            record["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            records.append(record)
            errored += 1
            summary_lines.append(
                f"{case_id:<10} ERROR  HTTP {resp.status_code}  ({latency_ms:.0f} ms)"
            )
            continue

        body = resp.json()
        diffs = _structured_diffs(body, expected)
        record["structured_diffs"] = diffs

        # Capture the free-text fields (expected vs. actual) for the log.
        for field in TEXT_FIELDS:
            record["text_fields"][field] = {
                "expected": expected.get(field, ""),
                "actual": body.get(field, ""),
            }

        if diffs:
            record["status"] = "FAIL"
            summary_lines.append(
                f"{case_id:<10} FAIL   ({latency_ms:.0f} ms)  {label}"
            )
            for d in diffs:
                summary_lines.append(f"             - {d}")
        else:
            record["status"] = "PASS"
            passed += 1
            summary_lines.append(
                f"{case_id:<10} PASS   ({latency_ms:.0f} ms)  {label}"
            )

        # Build the text-field comparison section.
        text_lines.append(f"## {case_id} — {label}")
        text_lines.append(f"_Structured result: {record['status']} · latency {latency_ms:.0f} ms_")
        text_lines.append("")
        for field in TEXT_FIELDS:
            text_lines.append(f"### {field}")
            text_lines.append("")
            text_lines.append("| | text |")
            text_lines.append("|---|---|")
            exp_txt = str(expected.get(field, "")).replace("\n", " ").replace("|", "\\|")
            act_txt = str(body.get(field, "")).replace("\n", " ").replace("|", "\\|")
            text_lines.append(f"| **expected** | {exp_txt} |")
            text_lines.append(f"| **actual** | {act_txt} |")
            text_lines.append("")

        records.append(record)

    total = len(cases)
    scored = total - errored

    # Latency stats.
    summary_lines.append("")
    summary_lines.append("-" * 60)
    if latencies:
        latencies_sorted = sorted(latencies)
        avg = sum(latencies) / len(latencies)
        p95_idx = max(0, int(round(0.95 * (len(latencies_sorted) - 1))))
        summary_lines.append(
            "Latency (ms): "
            f"min={min(latencies):.0f}  "
            f"avg={avg:.0f}  "
            f"p95={latencies_sorted[p95_idx]:.0f}  "
            f"max={max(latencies):.0f}"
        )
    summary_lines.append("")
    summary_lines.append(
        f"RESULT: {passed}/{total} passed"
        + (f"  ({errored} errored)" if errored else "")
        + f"  [structured fields: {STRUCTURED_FIELDS}]"
    )

    summary_text = "\n".join(summary_lines) + "\n"
    summary_path.write_text(summary_text, encoding="utf-8")
    text_path.write_text("\n".join(text_lines) + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "timestamp": ts,
                "base_url": url,
                "passed": passed,
                "errored": errored,
                "total": total,
                "latency_ms": {
                    "min": min(latencies) if latencies else None,
                    "avg": (sum(latencies) / len(latencies)) if latencies else None,
                    "max": max(latencies) if latencies else None,
                },
                "cases": records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Console output.
    print(summary_text)
    print(f"Logs written to:\n  {summary_path}\n  {text_path}\n  {json_path}")

    return 0 if (passed == total and errored == 0) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--sample-file", default=str(DEFAULT_SAMPLE_FILE))
    parser.add_argument("--timeout", type=float, default=35.0)
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between cases (after the previous response). "
        "Default 1.0. Set 0 to fire as fast as possible.",
    )
    args = parser.parse_args()
    return run(args.base_url, Path(args.sample_file), args.timeout, args.delay)


if __name__ == "__main__":
    raise SystemExit(main())
