# Detector agreement and local adjudication

The method is useful for prioritizing review, but this pilot does not justify
accepting agreement as truth. Raising the threshold helps boundary agreement;
it does not fix shared semantic errors. Local Qwen corrected some shared errors
and missed others. No automatic acceptance, model training, or paid API calls
were enabled.

Open the [interactive threshold comparison](results/agreement/index.html).
The [audit JSON](results/agreement/audit.json) retains every proposal and the
Paddle regions outside selected matches.

## Experiment

We reused both detectors on nine pages at two resolutions. All these pages had
already been inspected. The development/evaluation labels in the original
results are retained for traceability, but this is a diagnostic experiment,
not a new held-out evaluation. References are provisional assistant annotations,
not independently validated human labels.

Each valid Paddle box is assigned to the overlapping American Stories box with
highest IoU, with deterministic ties. For each American box, we compare its best
single match against the exact union of assigned Paddle boxes that have at least
80% of their area inside it. The higher-overlap alternative wins. This allows
paragraph fragments to match a column without filling the gaps between them or
counting overlaps twice. Ownership is exclusive. This asymmetric heuristic favors
American Stories' coarser regions; it is not a globally optimal segmentation.

Candidate agreement also requires compatible mapped roles and no contained,
assigned conflicting-role fragment outside the selected match. Ads/graphics and
unknown roles cannot qualify. Invalid geometry is excluded from matching but
retained in source results. Unselected valid Paddle regions remain review items.
No model confidence score is treated as a calibrated probability.

### Threshold sweep

Counts below cover all nine pages at 150 DPI: 331 valid American Stories regions
and 651 valid Paddle regions. One-to-one is a geometry-only maximum matching;
the grouped columns additionally require compatible roles.

| IoU threshold | One-to-one geometry matches | Grouped/role-compatible candidates | Of these, one-to-many | Candidates disagreeing with reference |
|---|---:|---:|---:|---:|
| 0.5 | 194 | 203 | 100 | 33 |
| 0.7 | 148 | 196 | 99 | 28 |
| 0.8 | 128 | 186 | 98 | 22 |
| 0.9 | 72 | 149 | 93 | 9 |

At 300 DPI, the candidate counts were 203, 195, 187, and 152 respectively;
reference disagreements were 35, 28, 27, and 11. Higher render resolution did
not eliminate the problem. Both detectors resize their inputs internally.

Reference disagreement means the American box lacks a same-role reference with
IoU ≥ 0.8. It is not an adjudicated error rate: caption credits and other
annotation-granularity choices account for some disagreements. Nevertheless,
visual examples establish real shared mistakes even above 0.9:

- TKP page 1, r015: both treat a fashion advertisement as an image/photo.
- TKP page 1, r013: both treat a displayed quotation as a headline.
- February Kantipur page 3, r031: both treat a Nepali pull quote as a headline.

Thus 0.9 is a reasonable starting point for a high-agreement review stratum,
not an empirically calibrated safety threshold. Keeping 0.5 for permissive
candidate correspondence is a separate choice from accepting output.

## Local Qwen pilot

Eight cases were chosen deliberately: three shared errors, two disagreements,
and three correct controls. Expected answers were recorded before inference and
were not sent to the model. Inputs were a page overview and a contextual crop
with the target outlined in red. The prompt requested a role and a short visible
evidence statement; it supplied neither detector labels nor reference answers.

We used the community 4-bit conversion of Qwen3.5-4B with MLX on Apple Silicon,
temperature zero, thinking disabled, a 192-token output cap and a 90-second
per-case timeout. Model revision, package versions, image hashes, prompt, raw
output, and timing are recorded in each result.

| Target (linked image) | Provisional reference | Qwen decision |
|---|---|---|
| [Fashion advertisement](results/agreement/qwen/fashion_ad_detail.jpg) | advertisement | advertisement |
| [English quotation](results/agreement/qwen/english_quote_detail.jpg) | pull quote | pull quote |
| [Nepali quotation](results/agreement/qwen/nepali_quote_detail.jpg) | pull quote | **public notice** |
| [Main story and sidebar](results/agreement/qwen/main_story_detail.jpg) | editorial group | editorial group |
| [Three merged headlines](results/agreement/qwen/merged_headlines_detail.jpg) | multiple headlines | **headline** |
| [Photo control](results/agreement/qwen/photo_control_detail.jpg) | photograph | photograph |
| [Headline control](results/agreement/qwen/headline_control_detail.jpg) | headline | headline |
| [Body control](results/agreement/qwen/body_control_detail.jpg) | body text | body text |

Six of eight decisions matched the provisional labels. This handpicked sample
cannot estimate population accuracy. The Nepali failure cited the red border as
evidence despite the prompt identifying it as an overlay. That suggests an
annotation-overlay sensitivity worth testing, without establishing its cause.
Some correct labels had inaccurate explanations of scope (calling a region
full-page). A plausible explanation is therefore not itself a credible quality
signal. Qwen also missed the merged-headline defect we specifically need to catch.

The eight completed processes took 172 seconds total, including repeated model
loading. API expense was **$0**; this excludes local electricity and hardware.
The initial model download was roughly 3 GB. Initial attempts failed before
generation because Jinja2 was missing; their logs are preserved in
`results/agreement/qwen/setup_failures/`, and the dependency is now pinned.

## What published pipelines suggest

[Soft Teacher (ICCV 2021)](https://arxiv.org/abs/2106.09018) separates selection
for classification and box regression, using box jitter to assess localization
stability. [Double-Check Soft Teacher (IJCAI 2022)](https://www.ijcai.org/proceedings/2022/199)
addresses localization inconsistency and uncertain background labels. These are
semi-supervised object-detection methods, not validations on Nepali newspapers.
Their relevant lesson is to assess location and semantic confidence separately.

[Weighted Boxes Fusion](https://arxiv.org/abs/1910.13302) combines overlapping
predictions from detectors. Our inference is that averaging boxes here should
wait until correspondence and region granularity are resolved: a paragraph and
a column are not interchangeable detections, and neither model's confidence is
calibrated on these pages.

The [official Qwen3.5-4B model](https://huggingface.co/Qwen/Qwen3.5-4B) and
[MLX-VLM implementation](https://github.com/Blaizzy/mlx-vlm) make local visual
adjudication practical. This pilot used a
[community quantization](https://huggingface.co/mlx-community/Qwen3.5-4B-4bit),
so its results should not be generalized to all Qwen configurations.

The next useful step is a small human-reviewed sample stratified across high
agreement, lower agreement, splits/merges, and unmatched regions, on fresh pages.
Record boundary quality, role, and article membership separately. Include both
languages and ads, quotes, captions, and narrow columns. Then measure how often
each stratum is wrong and whether Qwen's proposed corrections help or harm.
Keep Qwen as a review suggestion until that evidence exists. Train a small
resolver only after recurring failure classes and independently checked labels
justify it. Transcription and reading order remain separate downstream tasks.

## Reproduce

The agreement audit needs only the committed detector/reference records and the
base environment:

```bash
python experiments/layout/agreement.py
make check
```

For local Qwen, use a separate Apple Silicon environment with
`requirements-qwen.txt`. Download the pinned conversion:

```bash
hf download mlx-community/Qwen3.5-4B-4bit \
  --revision 0e7ffd5c629ef7719d4cbc04069232580bfa9d9c \
  --local-dir tmp/layout/qwen/model
python experiments/layout/resolve.py run
```

Committed case images suffice for inference. To regenerate images, first render
the source pages using `run.py prepare`, then use `resolve.py prepare`. Existing
result JSON files are skipped; archive completed results before a deliberate
rerun. A failed invocation stops the runner. Model files and full renders remain
ignored under `tmp/`.
