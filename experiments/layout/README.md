# Layout comparison

Compare page-specific layout detection independently of transcription and
article assembly. The experiment uses pages 1, 3, and 7 of each original PDF,
at 150 and 300 DPI. Pages 1 and 3 are development pages; page 7 is reserved for
evaluation with the same frozen detector settings. No paid API calls are made.

Open [the visual comparison](results/index.html) locally. Each row includes the
source, provisional reference, native PDF geometry, and both models at both
resolutions. Click an image for the larger version or JSON for exact geometry.
See [findings](RESULTS.md) for interpretation and limitations.

## Reproduce

Use an isolated Python 3.13 environment, install this directory's
`requirements.txt`, and install Poppler separately for `pdftoppm`.
The execution environment used Python 3.13.2 on macOS ARM64 with CPU inference,
four Torch/ONNX threads, and batch size one. Models are not committed.

Download the official Paddle weights at the frozen revision:

```bash
hf download PaddlePaddle/PP-DocLayoutV3_safetensors \
  --revision 97d101e6db2642e162a1d05392d1b0231c91033e \
  --local-dir tmp/layout/models/paddle
```

Download `layout_model_new.onnx` from the
[American Stories model folder](https://www.dropbox.com/sh/sfaf1nmuji9yhu6/AAAj1UGrPmCWFJUiTSP41ihpa?dl=0)
and place it in `tmp/layout/models/`. The provider's folder download returned
an 879,190,994-byte ZIP even when a subpath was requested; only the layout
checkpoint was retained. Get `src/label_maps/label_map_layout.json` from
[upstream revision f307e5c](https://github.com/dell-research-harvard/AmericanStories/tree/f307e5cec224fed5977b080c4f170d89c93ae3ba)
and save it as `tmp/layout/models/american_labels.json`.

```bash
python experiments/layout/run.py prepare
python experiments/layout/run.py run --split development
python experiments/layout/run.py run --split evaluation
python experiments/layout/evaluate.py
make check
```

The worker uses the official Paddle Transformers API and the American Stories
ONNX checkpoint with upstream confidence/NMS settings. Ultralytics supplies
letterboxing, NMS, and source-coordinate scaling. PIL input is already RGB;
upstream's cv2 input is BGR and reverses channels before inference. American
Stories' `article` class means a detected content region, not an assembled
multi-column article. No article membership is inferred here. Region IDs are scoped to each
(model, page, DPI) result; these diagnostic records do not implement the full
proposed issue-level schema.

Paddle resizes input to 800×800. American Stories letterboxes to 1280×1280.
Both 150- and 300-DPI renders therefore have the same model tensor dimensions.
Every result records source/image/model hashes, package versions, thresholds,
input dimensions, geometry in pixels and PDF points, and load-plus-inference
time. The controller enforces 120 seconds per worker, including startup,
loading, inference, and serialization. Failed or timed-out attempts are retained.
Existing result files are not overwritten; archive an experiment before reruns.

Prepared renders, native character/rule geometry, and raw model tensors are in
ignored `tmp/layout/`. Per-page detections and review overlays are in `results/`.
Model/postprocessor reading order is retained where available; it is not a
validated within-article order. No region is discarded for lacking an article
assignment or transcription. American Stories' coordinate postprocessor clips
boxes at image boundaries; this is explicitly recorded, with raw tensors retained.

## Reference annotations and metrics

`reference/` contains nine source thumbnails and editable LabelMe-format JSON
annotations, drawn by the assistant from original page images before viewing
model overlays. No annotation GUI was used. These are **provisional visual
references, not independently human-validated gold**. Open them with the standard
LabelMe application for review; `group_id` indicates proposed article membership.
The protocol records reference hashes. Changes require a new evaluation report.

Annotation units are contiguous body-column runs, separate headlines/bylines,
photos/captions, pull quotes, tables, page furniture, and whole advertisements.
Body runs split around photos or pull quotes. Masthead promotional elements are
grouped as furniture; printing crop marks are omitted. These choices favor
newspaper-region segmentation over a paragraph-level representation. They do
not provide transcription gold or establish semantic article-link correctness.

The scorer reports class-agnostic maximum-cardinality one-to-one matching at
IoU ≥ 0.5. Precision/recall here measure agreement with those region boundaries.
An unmatched region is not necessarily missing text. Complementary measures
report the union of predicted text rectangles covering editorial reference
rectangles, avoiding double counting, and the share of advertisement rectangles
labeled as text. These remain area proxies, not character recall or OCR accuracy.

A cross-article merge candidate covers at least half of a body reference region
from each of two proposed articles. A fragmentation candidate contains at least
half of each of multiple predicted regions. Both require visual adjudication.
Detection labels are preserved, since the two models have different ontologies;
no semantic label-accuracy claim is made. A zero region count from a failed run
counts as zero recall rather than disappearing from the denominator.
