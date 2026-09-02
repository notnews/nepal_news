# Pilot: image extraction and cost

Original design prepared 2026-09-05. The first goal is to learn whether the
extraction unit should be a page, a crop, or a locally detected region. See
[measured results](../experiments/claude/RESULTS.md) for submitted requests,
actual spending, and quality failures.

## Inventory and inputs

The three issues have 19, 19, and 12 pages: 50 total. The pilot uses only page 1
of each issue. These pages are diagnostic examples, not a representative sample
of interior pages or a held-out evaluation set.

`python experiments/claude/prepare.py` renders them using Poppler at 150 DPI and
creates two requests per page:

1. One overview with a maximum edge of 2,240 pixels.
2. The same overview plus six overlapping detail crops, in a 2-column,
   3-row grid. Each crop has a 5% tile-size margin on each edge where possible.

Both variants request the same JSON: item types, headlines, bylines, verbatim
bodies, continuation cues, and ordered regions. The prompt prohibits translation
and invented text, asks for missing/unreadable flags, and uses full-page
normalized coordinates. It is a diagnostic subset of the proposed schema.

At 150 DPI the Kantipur front pages are 1,971 × 3,100 pixels; TKP is
2,244 × 3,225. Separate 300-DPI renders are available for local visual comparison.
The six Claude requests contain 24 images and 53,642 visual tokens under the
current documented patch-count rule. All prepared images fit the high-resolution
limits without provider downscaling. Image files and payloads are under ignored
`tmp/pilot/`; the manifest records PDF hashes, image paths, crop bounds, and
request IDs. The preparation script contains no submission code.

High-resolution Claude models downscale images beyond their resolution/token
limits. Raising whole-page DPI alone can therefore fail to improve the text
actually seen. The crops test legibility while preserving an overview for story
association. [Anthropic vision documentation](https://platform.claude.com/docs/en/build-with-claude/vision).

## Expense

The selected model is `claude-sonnet-5`. Current batch rates are $1 per million
input tokens and $5 per million output tokens; synchronous rates are twice
those amounts. Prices checked against the live documentation on 2026-09-05.
[Official pricing](https://platform.claude.com/docs/en/about-claude/pricing).

For the six prepared requests, allow 2,000 text/overhead input tokens per
request, in addition to the counted image tokens:

| Generated tokens per request | Six-request batch estimate |
|---|---:|
| 6,000 | $0.25 |
| 16,000 | $0.55 |
| All requests reach the 32,768-token cap | $1.05 |

Formula: `(53,642 + 6 × 2,000) / 1,000,000 + 6 × output_tokens × 5 / 1,000,000`.
Image counts are derived from actual files; the text allowance and output
range are assumptions. Generated tokens include any billed reasoning. Sonnet 5
has adaptive thinking enabled by default; the request uses model defaults and
does not set temperature. [Model documentation](https://platform.claude.com/docs/en/models/sonnet-5/overview).

A $3 pilot budget leaves room for one repeat, but no repeat should be submitted
before inspecting the first six results. Failed/truncated outputs can still
cost money. No automatic retry round is prepared.

For all 50 pages, an illustrative 5,000–15,000 input and 10,000–25,000 generated
tokens per page gives $2.75–$7.00 for one Sonnet batch pass. This is a scenario,
not extrapolation from measured page outputs. Every resolution/model variant
adds another pass. Very dense Nepali pages could exceed the output assumption.
Record actual provider token usage and stop reasons before revising the estimate.

## Batchlane

Inspected the local `../batchlane` Anthropic adapter and cost implementation.
It can build image requests and preserve custom IDs. Set `max_tokens` explicitly:
the adapter's default of 1,024 would be inadequate for newspaper transcription.
The local cost helper uses LiteLLM's model registry/token estimator, with a
character-count fallback. Do not use that fallback to price base64 images or
assume its model prices are current; use the provider's rates and token count
endpoint before submission, then response usage afterward.

The prepared JSONL rows map directly to `batchlane.BatchLine(**row)`. Submit only
the six reviewed rows; save the returned batch handle immediately and reuse it
for status/results rather than resubmitting. Save raw responses, usage, stop
reasons, and model ID before parsing the requested JSON. A batch may take up to
24 hours. [Official batch documentation](https://platform.claude.com/docs/en/build-with-claude/batch-processing).

The runner reads `ANTHROPIC_API_KEY` or uses a hidden terminal prompt. It
does not persist the credential. The supplied key was verified with the
provider before the first paid request.

## Local comparator: Surya

Surya 0.22.1 was installed into `/tmp/nepal-surya-venv`; its public model weights
use `/tmp/nepal-surya-models`. The existing `llama-server` supports the local
Apple Silicon backend. There is no per-request API bill for this route; model
downloads, disk, runtime, and electricity are local costs. Surya provides OCR,
layout labels, reading order, and boxes, but newspaper story association still
needs evaluation. [Surya documentation](https://github.com/datalab-to/surya).

The initial local command is:

```bash
HF_HOME=/tmp/nepal-surya-models \
MODEL_CACHE_DIR=/tmp/nepal-surya-models \
SURYA_INFERENCE_BACKEND=llamacpp \
SURYA_INFERENCE_PARALLEL=1 \
IMAGE_DPI=150 IMAGE_DPI_HIGHRES=150 \
/tmp/nepal-surya-venv/bin/surya_ocr pdfs/KPUR_2013_02_20.pdf \
  --page_range 0 --output_dir tmp/pilot/surya
```

## What determines the next step

Require all six requests to return parseable JSON with no truncation. Record
peak generated tokens, measured cost, latency, and per-page failures. If any
request uses more than 60% of its output allowance, review the budget before
scaling. Evaluate quality separately from these execution gates.

Compare visible story inventory, first/last body lines, column reading order,
bylines, caption separation, and text in ads. Manually transcribe a few fixed
Nepali and English crops to measure text errors. Treat inferred rectangles as
approximate until checked against renders. Choose crops if they recover text
missing in overviews; choose local regions plus Claude association if Surya's
text is usable but its story grouping is not. Add interior and continuation
pages only after this diagnostic comparison, with a separate cost estimate.

## Offline verification

The six rows passed `batchlane.plan` using the sibling checkout. They fit in
one batch (38,147,680 serialized bytes); the Anthropic payload preserved the
model name, image counts (1 or 7), base64 image sources, and 32,768-token caps.
Local unit tests and black/isort/flake8 passed. Tile tests check complete
coverage with odd image dimensions and overlap between neighboring tiles.

## Surya full-page observation

The first Kantipur full-page generation used 4,121 prompt tokens and 12,263
generated tokens, filling the local server's 16,384-token context. The server
reported `truncated = 1` after 443 seconds (about 7.4 minutes), and Surya began
additional processing. That fallback was stopped rather than allowed to run
unbounded. No completed page result was produced by this attempt. The preserved
log is `tmp/pilot/surya-full-page.log`.

This is a concrete configuration limit, not proof that Surya cannot transcribe
Nepali. Before retrying whole pages, increase the per-slot context with room
for both the observed image prompt and the desired output, or test smaller
regions. An isolated crop of the lead story's first body column is the next
local check; its coordinates are `(300, 280, 500, 820)` within
`KPUR_2013_02_20_p1_tile3.png`. The crop has cut boundaries and is not a complete
story or transcription gold.

The crop trial also failed to complete promptly: it generated over 6,000 tokens
in more than three minutes without producing a result and was stopped. No
transcription accuracy claim can be made from either local attempt. The crop
log is `tmp/pilot/surya-crop.log`. Investigate generation/stopping behavior on a
small fixed crop before increasing context or processing the remaining issues;
merely enlarging the context may prolong unproductive generation.
