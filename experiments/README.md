# Experiments

| Directory | Purpose | Status |
|---|---|---|
| `layout/` | Separate page layout from OCR and article assembly | Nine-page comparison |
| `claude/` | Prepare and run a small, explicitly budgeted vision comparison | Pilot |
| `text_layer/` | Legacy-font conversion and layout heuristic, with saved results | Known segmentation failures; comparison baseline |
| `local_ocr/` | Small Tesseract comparison and Surya observations | Diagnostic only |
| `legacy/` | Original LayoutParser notebook and CSV | Historical artifacts, not active code |

Source issues live in `../pdfs/`. Generated images and large request payloads go
in ignored `../tmp/`. Keep small, informative results beside their experiment;
do not retain abandoned wrapper scripts. None of these experiments is a
validated production pipeline.
