"""Submit a reviewed pilot subset once, or collect its saved batch receipt."""

import argparse
import getpass
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import batchlane as bl
import httpx
from batchlane import _http
from batchlane.adapters.anthropic import AnthropicAdapter

ROOT = Path(__file__).resolve().parents[2]


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="+", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--budget-usd", type=float, required=True)
    args = parser.parse_args()
    source = ROOT / "tmp/pilot/requests.jsonl"
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    selected = [row for row in rows if row["custom_id"] in args.ids]
    if len(set(args.ids)) != len(args.ids) or len(selected) != len(args.ids):
        raise ValueError("Request IDs must exist and must not repeat.")
    if len(selected) > 6 or any(
        row["model"] != "anthropic/claude-sonnet-5"
        or row["params"] != {"max_tokens": 32768}
        for row in selected
    ):
        raise ValueError("Unexpected pilot configuration.")
    plan = bl.plan([bl.BatchLine(**row) for row in selected])
    if plan.n_chunks != 1:
        raise ValueError("The pilot must fit in one batch.")
    adapter = AnthropicAdapter()
    prepared = adapter.build_requests(plan.chunks[0])
    fingerprint = hashlib.sha256(json.dumps(selected).encode()).hexdigest()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    handle_path = args.run_dir / "handle.json"
    intent_path = args.run_dir / "intent.json"
    if intent_path.exists():
        intent = json.loads(intent_path.read_text())
        if intent["sha256"] != fingerprint:
            raise ValueError("Saved run uses different requests.")
        if not handle_path.exists():
            raise RuntimeError(
                "Submission intent has no receipt; inspect provider first."
            )
    key = os.environ.get("ANTHROPIC_API_KEY") or getpass.getpass("API key (hidden): ")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    with httpx.Client(headers=headers, timeout=90) as client:
        if handle_path.exists():
            handle = bl.BatchHandle.from_json(handle_path.read_text())
        else:
            counts = []
            for row in prepared:
                params = row["params"]
                response = client.post(
                    "https://api.anthropic.com/v1/messages/count_tokens",
                    json={"model": params["model"], "messages": params["messages"]},
                )
                response.raise_for_status()
                counts.append(response.json()["input_tokens"])
            estimate = sum(counts) / 1e6 + len(selected) * 32768 * 5 / 1e6
            save(
                args.run_dir / "preflight.json",
                {
                    "input_tokens": counts,
                    "max_output_tokens_per_request": 32768,
                    "batch_cost_at_output_cap_usd": estimate,
                    "approved_subset_budget_usd": args.budget_usd,
                },
            )
            if estimate * 1.05 > args.budget_usd:
                raise ValueError("Counted request cost exceeds budget with 5% margin.")
            print(
                f"Counted inputs: {counts}; at output caps: ${estimate:.4f}", flush=True
            )
            with intent_path.open("x", encoding="utf-8") as stream:
                json.dump(
                    {
                        "sha256": fingerprint,
                        "ids": args.ids,
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    },
                    stream,
                )
            # A retry after an ambiguous POST timeout could create a second paid job.
            with patch(
                "batchlane.adapters.anthropic.request", _http.request.__wrapped__
            ):
                handle = bl.submit(
                    [bl.BatchLine(**row) for row in selected], api_key=key
                )
            handle_path.write_text(handle.to_json(), encoding="utf-8")
            print(f"Saved receipt: {handle.job_id}", flush=True)
        url = f"https://api.anthropic.com/v1/messages/batches/{handle.job_id}"
        previous = None
        while True:
            response = client.get(url)
            response.raise_for_status()
            status = response.json()
            save(args.run_dir / "status.json", status)
            counts = status["request_counts"]
            if counts != previous:
                print(f"Batch status: {counts}", flush=True)
                previous = counts
            if status["processing_status"] == "ended":
                break
            time.sleep(20)
        response = client.get(status["results_url"])
        response.raise_for_status()
        (args.run_dir / "results.jsonl").write_text(response.text, encoding="utf-8")
        print(f"Saved raw results to {args.run_dir}", flush=True)


if __name__ == "__main__":
    main()
