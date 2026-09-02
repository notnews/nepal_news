# Initial assessment, 2026-09-05

The repository contains 50 PDF pages: two 19-page Kantipur issues and one
12-page Kathmandu Post issue. All three front pages were rendered and inspected;
this was a layout review, not a character-level audit of all pages.

| Saved output | Records | Empty bodies |
|---|---:|---:|
| KPUR 2013-02-20 | 132 | 56 |
| KPUR 2013-07-31 | 123 | 56 |
| TKP 2009-01-08 | 128 | 52 |

Counts come from parsing the checked-in `experiments/text_layer/results/*_stories.jsonl`. None of these
383 records has a `story_id`. Empty bodies alone do not prove failure for every
record: teasers and furniture can lack bodies. But the February Kantipur lead
and the Kathmandu Post's Pashupati lead have empty extracted bodies despite
visible body text, establishing specific segmentation failures.

The front pages contain adjacent columns, wrapped text around images, boxed
sidebars, standalone captioned images, advertisements, and masthead teasers.
The current algorithm groups all characters at similar vertical positions
before distinguishing columns. It then stops body collection at the next
headline in page order, even when that headline belongs to another column.
The output can merge unrelated text and truncate real stories. A font-size
threshold also picks up advertising and misses small headlines.

Additional limitations found in the code:

- Font detection depends on `/usr/share/dict/words`; machines without that file
  take a different path and can map English text into Devanagari.
- Devanagari character share does not distinguish correct words from incorrect
  mappings. The README's earlier character-exact claim lacked checked-in gold.
- `column_span` is a width fraction, and bounding-box area includes whitespace
  and potentially unrelated material.
- Continuation matching handles pairs heuristically; IDs are assigned only
  to matches and derive from rounded vertical positions.
- Byline, caption, and inset detection does not remove their text from body.
- Pages without text silently disappear from the story output.

The next implementation should preserve page regions and raw font runs first,
then recover column reading order and classify/associate items. Review these
against gold before rebuilding the story export. The proposed schema in
[SCHEMA.md](SCHEMA.md) supports that work without treating current candidates
as validated stories. Existing outputs remain unchanged as a baseline.

## Cleanup verification

Local black, isort, flake8, and three continuation unit tests passed. The initial archive was checked byte-for-byte. Subsequent cleanup deleted the
two obsolete PyPDF2 scripts and retained the notebook/CSV under
`experiments/legacy/`.
A full three-issue smoke run was stopped after about five minutes without a
completed issue; its interrupt trace was in npttf2utf conversion during inset
extraction. This does not establish a hang or a completed extraction test.
Docker checks could not start because no Docker daemon was available.
A bounded integration check using the actual TKP first page passed: the
extractor returned 12 candidates, all on PDF page 1, including the Pashupati
headline. This checks execution and metadata, not transcription or segmentation
accuracy.
