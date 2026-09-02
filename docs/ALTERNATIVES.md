# Cheaper extraction approaches

Start with the [layout-only findings](../experiments/layout/RESULTS.md).
American Stories and Paddle's standalone layout detector have now been tested
on nine pages at two resolutions. Boundary and role errors remain, so choosing
an OCR engine does not yet produce reliable articles. Recognition alternatives
below should be evaluated separately once page-specific regions are available.

For just 50 pages, engineering time can exceed a few dollars of API usage.
For a reusable pipeline, the diagnostic value is knowing which stage fails.
Local models still require download, compute, and review time.

| Approach | Marginal API cost | Useful output | Main work still needed |
|---|---|---|---|
| PDF text + font mapping | $0 | Characters, native coordinates, font sizes | Correct per-font decoding and column/story association |
| Tesseract Nepali/English | $0 locally | Text and word boxes | Region detection, reading order, story association |
| PaddleOCR PP-OCRv5 | $0 locally | Detection and Devanagari recognition | Install/evaluate locally; join regions into stories |
| Surya | $0 locally | OCR, layout labels, reading order | Diagnose local generation/context behavior before scaling |
| Dell's American Stories / EffOCR | $0 locally after setup | Newspaper layout and article association architecture | Transfer and validate models for Nepali fonts/layouts |
| Local OCR + selective Claude | Paid only for selected requests | Repair/association on difficult regions | Validate routing against independently reviewed errors |

Local routes still use storage, electricity, and possibly rented compute.
Their installation/training effort is not represented by a $0 API price.

## Tesseract: recognition baseline

Tesseract provides a Nepali `nep` model and word-level TSV coordinates. Its
`fast` and `best` model families offer different speed/accuracy tradeoffs;
recognizer confidence alone is not an error probability.
[Official model documentation](https://tesseract-ocr.github.io/tessdoc/Data-Files.html).

On one fixed crop from the February Kantipur lead, installed Tesseract 5.5.2
returned readable Nepali at 150 and 300 DPI in approximately 0.6–0.7 seconds.
The outputs differ by one inserted vowel sign: the 150-DPI version has
`निर्वाचन गर्ने नसके`, while 300 DPI has `निर्वाचन गर्न नसके` on that line.
The crop, raw text, word boxes, exact command, hashes, and timing are in
`experiments/local_ocr/results/`. This is an inspected example, not a measured
corpus error rate. Agreement at two resolutions can preserve shared errors.

A full-page check with `nep+eng` and automatic segmentation also completed:
20 seconds at 150 DPI and 35 seconds at 300 DPI, producing 7,797 and 8,633
characters respectively. More output is not an accuracy score; full-page
reading order and omissions remain to be reviewed. The flat 300-DPI output
inserts masthead text into the first story, demonstrating why region
association is still necessary.

Next compare a few complete story regions, captions, and small headlines from
both papers. Use `nep` for Nepali, `eng` for English, and compare mixed-language
settings only where the source mixes scripts. Avoid treating full-page OCR
reading order as story association. Keep paragraph/word boxes for later joins.

## Melissa Dell's pipeline: borrow the structure

American Stories explicitly separates layout detection, legibility, OCR, and
association of article text across boxes. This addresses the same structural
problem our text-layer heuristic gets wrong. Its released models and pipeline
were developed for historical U.S. newspapers.
[Official American Stories repository](https://github.com/dell-research-harvard/AmericanStories).

EffOCR recognizes localized glyphs through image retrieval/metric learning.
The released framework defaults to English and Japanese; other languages can
require modifying the code and training suitable models. Do not assume an
English checkpoint will read Devanagari conjuncts. A Nepali adaptation could
use rendered font samples plus manually reviewed real crops, but that is a
training project rather than a cheap plug-in for these three issues.
[Official EffOCR repository](https://github.com/dell-research-harvard/effocr).

Recommendation: reuse the region/association design first. Consider adapting
models only if a much larger corpus justifies annotation and training costs.

## PaddleOCR: layout tested; recognition remains separate

PP-OCRv5 has a Devanagari mobile recognizer whose documented languages include
Nepali and English. It is a more direct Nepali recognition candidate than an
English-only newspaper checkpoint. Its recognition scores do not establish
article grouping quality. The recognition model has not been run here; PP-DocLayoutV3 was tested separately.
[Official multilingual documentation](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html).

## Surya: diagnose before enlarging the job

The local Surya 0.22.1/llama.cpp full-page trial exhausted a 16,384-token context
after about 7.4 minutes. A small crop then generated over 6,000 tokens without
completing and was stopped. Neither produced a usable final transcription.
See [the pilot log](PILOT.md). This could reflect generation/configuration
problems; it is not a benchmark of Surya's Nepali accuracy.

Surya's current framework supplies OCR, region labels, and reading order.
These capabilities are relevant, but a bounded crop must finish and be checked
before another whole-issue run. [Official Surya repository](https://github.com/datalab-to/surya).

## Hybrid: spend on difficult regions

Use local text/OCR and geometry to propose items, then ask Claude to resolve
uncertain story boundaries or unreadable crops. Retain original local output
and the revised output with their respective provenance. Don't send every word
to a model again just to reformat it; full transcription output dominates the
small pilot's projected token bill.

Build a small human-reviewed set of regions before selecting a routing rule.
Measure both errors caught and correct regions unnecessarily escalated, using
labels independent of the routing signals. Keep interior and continuation
pages held out from the front-page diagnosis. A populated field or agreement
between two recognizers is not evidence of completeness.
