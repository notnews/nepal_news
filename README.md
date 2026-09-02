# Nepal News

Experiments in extracting complete stories and page layout from three newspaper
PDFs: two Kantipur issues and one Kathmandu Post issue, 50 pages in total.
There is no validated production extractor yet.

The original text-layer baseline has demonstrated segmentation failures.
A paired Claude test cost $0.1353 and failed geometry/transcription checks;
see [the measured findings](experiments/claude/RESULTS.md). Local Tesseract
produced useful crop text, but whole-page story association remains unresolved. Start with the [layout comparison](experiments/layout/README.md),
[Claude pilot](docs/PILOT.md),
[cheaper alternatives](docs/ALTERNATIVES.md), and [proposed schema](docs/SCHEMA.md).

## Repository layout

| Path | Contents |
|---|---|
| `pdfs/` | Original newspaper issues |
| `experiments/layout/` | Page-specific detector comparison, overlays, and references |
| `experiments/claude/` | Image preparation and budgeted batch pilot |
| `experiments/text_layer/` | Existing extraction heuristic and original results |
| `experiments/local_ocr/` | Small local OCR comparisons and results |
| `experiments/legacy/` | Historical notebook and CSV, not active entry points |
| `docs/` | Assessment, schema, experiment design, and findings |
| `tests/` | Behavioral checks |
| `tmp/` | Ignored renders, large request payloads, and working files |

The obsolete PyPDF2 scripts have been deleted. Python entry points live with
their experiments; no notebook or Python script lives in the repository root.

## Local setup and checks

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
make check
```

`make check` runs black, isort, flake8, and unit tests. `make format` formats
experiment code. `make ci-docker` runs the checks in a standard Python 3.14
image and requires a running Docker daemon.

For the Claude experiment, install the sibling checkout with
`pip install ../batchlane`; see its [instructions](experiments/claude/README.md).
Poppler supplies image rendering; Tesseract and Surya are separate local tools.
API keys are read from the environment or a hidden prompt and must not be
stored in this repository.

## Current evidence

The original baseline contains 383 candidates with 164 empty bodies, including
prominent stories whose text is visible in the PDF. See the
[assessment](docs/ASSESSMENT.md). Its `column_span` is a width fraction, its
area measure is a bounding rectangle, and Devanagari share is not transcription
accuracy. The proposed schema preserves ordered regions and source evidence.

The companion [TOI project](https://github.com/notnews/toi_stories) supplies useful
item types and provenance conventions, but its vendor-segmented English
clippings do not validate extraction from full Nepali newspaper pages.
