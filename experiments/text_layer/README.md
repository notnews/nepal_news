# Text-layer baseline

`extract.py` is the existing pdfplumber/npttf2utf experiment. Its checked-in
`results/` contain the 383 original candidates, including 164 empty bodies.
See [the assessment](../../docs/ASSESSMENT.md) for demonstrated segmentation and
font-mapping problems. Keeping this baseline allows comparisons against the
new experiments; it is not an endorsed extraction method.

```bash
python experiments/text_layer/extract.py pdfs/*.pdf --out-dir tmp/text-layer
```

Paths in commands are relative to the repository root.
