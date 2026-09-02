# Layout-only findings

Both released detectors ran successfully on all nine pages at both resolutions:
36 local runs, 1,938 detected regions, and **$0 in paid API calls**. American
Stories is a useful newspaper-layout baseline. It usually preserves column
regions, but it can merge headlines and mistake prominent editorial content
for advertisements. Paddle often supplies finer text blocks, leaving more
work to recover newspaper regions and distinguish advertising.

[Open the page-by-page visual comparison](results/index.html).
[Machine-readable metrics](results/metrics.json) retain page-level counts.

## Region matching and text coverage

References contain 284 visually annotated regions: 187 on six development
pages and 97 on three evaluation pages. They were drawn by the assistant before
viewing model outputs, in editable LabelMe format. **They are provisional,
not independently human-validated ground truth.** The same frozen detector
settings were used on evaluation pages; neither detector was fine-tuned.

| Model | DPI | Split | Matched / predicted / reference regions | Precision | Recall | Editorial area covered by text regions |
|---|---:|---|---:|---:|---:|---:|
| American Stories | 150 | Development | 149 / 227 / 187 | 65.6% | 79.7% | 93.1% |
| American Stories | 300 | Development | 150 / 219 / 187 | 68.5% | 80.2% | 93.0% |
| Paddle V3 | 150 | Development | 105 / 422 / 187 | 24.9% | 56.1% | 94.9% |
| Paddle V3 | 300 | Development | 104 / 415 / 187 | 25.1% | 55.6% | 94.6% |
| American Stories | 150 | Evaluation | 80 / 105 / 97 | 76.2% | 82.5% | 98.9% |
| American Stories | 300 | Evaluation | 81 / 101 / 97 | 80.2% | 83.5% | 98.7% |
| Paddle V3 | 150 | Evaluation | 66 / 230 / 97 | 28.7% | 68.0% | 96.2% |
| Paddle V3 | 300 | Evaluation | 64 / 219 / 97 | 29.2% | 66.0% | 94.1% |

Matching is class-agnostic, one-to-one, at IoU ≥ 0.5. References use body-column
runs and whole advertisements; Paddle's finer paragraph-style segmentation is
penalized by this metric even where it captures text. Area coverage complements
region matching, but measures rectangle area, not character recall. Neither
measure establishes correct labels, reading order, or complete articles.
Evaluation pages are only three pages from the same issues; better scores there
do not establish generalization to new dates or newspapers.

There is no consistent 300-DPI benefit. American Stories letterboxes both
resolutions to 1280×1280; Paddle resizes both to 800×800. Increasing render DPI
alone does not preserve additional model input pixels. On these runs, 150 DPI
is a reasonable starting setting for subsequent layout diagnosis, pending a
larger independent evaluation.

## Specific failures visible in the overlays

- **Merged headlines:** American Stories, TKP page 3 at 150 DPI, `r013`, combines
  “Govt told to end Kamlari practice,” “Hope for refugees,” and “SKorea dispels
  employment buzz.” Their bodies remain separate. The automated body-merge
  diagnostic misses this headline error; a zero body-merge count is insufficient.
- **Editorial content classified as an advertisement:** American Stories, July
  Kantipur front page, `r014` at 150 DPI, encloses the main story and sidebar
  as `cartoon_or_advertisement`. Several nested text regions survive, but a
  pipeline that blindly removes advertising would lose editorial content.
- **Advertisements classified as editorial text:** American Stories calls much
  of the TKP page 3 tender notice (`r020`) and Oxfam recruitment notice (`r026`)
  article text. Paddle also detects their internal text without enclosing them
  in an advertisement category.
- **Wrong region roles:** American Stories calls the large bottom headline on
  February Kantipur page 3 `newspaper_header` (`r032`). The box alone looks useful;
  filtering by its predicted role would discard a headline.
- **Granularity and missing headlines:** Paddle often splits column runs into
  several blocks. On TKP page 7 at 300 DPI it misses the “Inflation reached
  14.1pc in Mangsir” headline while detecting its body columns. That failure
  remains visible despite high overall text-area coverage.
- **Invalid geometry:** American Stories returns a zero-width edge box on July
  Kantipur page 7 at 150 DPI (`r035`); Paddle returns a slightly negative left
  edge on July Kantipur page 3 at 150 DPI (`r029`). Both records are retained
  with explicit quality flags. American Stories' upstream scaling clips boxes;
  raw inference tensors are retained in ignored scratch storage.

Across the development pages, roughly 18–20% of annotated advertisement area
is covered by predicted text regions for either model. On the evaluation
pages, Paddle covers about 49–50% versus 0.3–2.6% for American Stories. These
are area diagnostics, not advertisement-classification accuracy. The evaluation
advertisements are all on TKP page 7, so this comparison has a narrow basis.

## Native PDF geometry

All nine pages contain native character geometry: 3,276–23,404 character objects
per page. The gallery overlays characters in blue and drawing objects in red.
For example, the three TKP page 3 headlines that American Stories merges have
separate native character runs and visible gaps. That is useful evidence for
splitting a proposed region without first solving OCR.

Native geometry is not a complete layout solution: letters, vector outlines,
images, and rules have different representations, and embedded text may be
incorrectly encoded. It can complement a visual detector on these production
PDFs; it does not replace a detector for scanned newspapers.

## Runtime, reproducibility, and next decision

Median measured model-load/inference/postprocessing time was 3.5 seconds for
American Stories and 12.3 seconds for Paddle. The first American Stories run
was 32.3 seconds, illustrating startup effects. Worker startup, image loading,
and overlay generation add overhead; all 36 workers completed below the
120-second wall-clock cap. These sequential runs are diagnostic timings, not
a controlled throughput benchmark. No rental compute or API inference was used.

The next bottleneck is **region boundaries and roles**, especially headline
separation and editorial-versus-advertisement classification. Keep American
Stories as a starting proposal generator and Paddle as an alternative source
of finer regions. Test repairs using native geometry where available, and
validate them against a human-reviewed reference set plus new issues. Do not
filter out content solely because either model calls it an advertisement.

Transcription, within-article ordering, and continuation linking remain separate
experiments. No OCR, article assembly, or Surya retry was performed in this
comparison. The schema now stores page-owned regions and ordered article
references, so unassigned and questionable regions remain available for review.

[Reproduction instructions and metric definitions](README.md).
