# Local OCR diagnostics

The Tesseract comparison uses the same cropped body column at 150 and 300 DPI.
`results/tesseract_run.json` records the commands, image hashes, and elapsed
times. Images, text, and TSV word boxes are retained beside it. The crop is not
a complete article and has cut boundaries; it is not transcription gold.

```bash
tesseract experiments/local_ocr/results/body_150dpi.png \
  experiments/local_ocr/results/tesseract_nep_150dpi \
  -l nep --oem 1 --psm 6 txt tsv
```

Surya's failed full-page/crop trials are documented in
[the pilot assessment](../../docs/PILOT.md). No custom Surya wrapper is retained:
the recorded standard CLI commands are sufficient to reproduce the trials.

The full February Kantipur front page was also run with `nep+eng`, automatic
page segmentation (`--psm 3`), at both resolutions. See `results/fullpage_run.json`
for exact commands and timings, and `kantipur_frontpage_*` for text/word boxes.
The 150-DPI pass took 20 seconds; 300 DPI took 35 seconds on this machine.
These are single-run timings, not a throughput benchmark. Neither flat OCR
output is automatically a set of correctly associated stories.
