#!/usr/bin/env python3
"""Hit a running QueueStorm service with the public sample inputs and diff the
core decision fields against expected_output.

Usage:
    python scripts/run_sample_cases.py \
        --base-url http://localhost:8000 \
        --sample-file docs/SUST_Preli_Sample_Cases.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

CORE_FIELDS = ["relevant_transaction_id", "evidence_verdict", "case_type", "department"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--sample-file",
        default=str(Path(__file__).resolve().parent.parent / "docs" / "SUST_Preli_Sample_Cases.json"),
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    cases = json.loads(Path(args.sample_file).read_text(encoding="utf-8"))["cases"]
    url = args.base_url.rstrip("/") + "/analyze-ticket"

    passed = 0
    for case in cases:
        try:
            resp = httpx.post(url, json=case["input"], timeout=args.timeout)
        except Exception as exc:  # noqa: BLE001
            print(f"{case['id']} ERROR  {type(exc).__name__}: {exc}")
            continue
        if resp.status_code != 200:
            print(f"{case['id']} HTTP {resp.status_code}  {resp.text[:120]}")
            continue
        body = resp.json()
        exp = case["expected_output"]
        diffs = [
            f"{f}: got={body.get(f)!r} exp={exp[f]!r}"
            for f in CORE_FIELDS
            if body.get(f) != exp[f]
        ]
        if body.get("severity") != exp["severity"]:
            diffs.append(f"severity: got={body.get('severity')} exp={exp['severity']}")
        if not diffs:
            passed += 1
            print(f"{case['id']} OK")
        else:
            print(f"{case['id']} DIFF  " + "; ".join(diffs))

    print(f"\n{passed}/{len(cases)} cases match expected core fields.")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
