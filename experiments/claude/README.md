# Claude image pilot

See [the pilot specification](../../docs/PILOT.md) for request contents, budgets,
and quality gates. Install the sibling batchlane checkout in your environment:

```bash
pip install ../batchlane
python experiments/claude/prepare.py
```

`prepare.py` performs no API calls. `run.py` requires explicit request IDs and a
budget, counts tokens, submits through batchlane once, and saves a batch receipt
before polling. The API key is read from the environment or a hidden terminal
prompt; it is never written to the repository.

After approval, the first request is run with:

```bash
python experiments/claude/run.py \
  --ids KPUR_2013_02_20_p1_tiles \
  --run-dir tmp/pilot/claude/first --budget-usd 0.25
```

Repeating the command with an existing receipt collects that job. An intent
without a receipt requires inspecting the provider before resubmission; a
submission timeout may have created a paid job. The runner disables automatic
POST retries to avoid duplicating that job. It does not retry failed inference.

The three front pages are diagnostic, not held-out gold. Inspect first-page
results before submitting the remaining approved variants. Never put a key in
a command argument, committed file, or notebook output.
