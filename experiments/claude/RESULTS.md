# Claude pilot findings

Two requests on the February Kantipur front page cost $0.135283 in total.
Both returned parseable JSON without truncation, but both failed geometry and
transcription checks. The remaining four approved requests were not submitted:
we stopped after the paired diagnostic failure rather than scale this prompt.

| Measure | Overview + six crops | Overview only |
|---|---:|---:|
| Input tokens | 13,595 | 4,598 |
| Output tokens, including reasoning | 9,383 | 14,035 |
| Thinking tokens, already included above | 274 | 6,361 |
| Cost at reported batch tier | $0.060510 | $0.074773 |
| Batch elapsed time, including queue | 233 seconds | 572 seconds |
| Items returned | 13 | 13 |
| Out-of-range boxes / all boxes | 17 / 36 | 21 / 32 |
| Missing nullable continuation fields | 9 | 4 |

Both responses identify `claude-sonnet-5`, `service_tier: batch`, global
inference, and `stop_reason: end_turn`. Costs use the provider's recorded
input/output usage at $1/$5 per million tokens. Reasoning is not added a second
time. Neither response used prompt caching.

Fewer image tokens did not mean a cheaper request here: the overview-only
request spent more output tokens on reasoning. This is one paired example,
not a general comparison of model efficiency.

## Text and grouping failures

The lead headline and byline match the inspected page, and its body is populated
where the original baseline was empty. But the tiled response changes visible
source text: `जेठभित्र` becomes `जेठमिनु`, and `समझदारी` becomes `समभदारी`.
The printed `नेतृत्व लिन सक्ने` becomes `नेतृत्व लिने`, changing the wording.
Tesseract's small 300-DPI crop retained these source forms.

The overview response has additional wording errors, including `विषय संशोधन
नगरिकन मात्र` where the inspected crop reads `विषय संशोधन भएपछि मात्रै`.
Its lead body also absorbs a line from the neighboring boxed story. Both
responses mark `page_complete: true`, with no unreadable regions. That flag is
not trustworthy without source checks.

The tiled result retains a separate `story-videshik-cont` body while flagging it
as duplicated/merged. The overview instead separates a death/visa brief from
the Brazil story. Matching item counts therefore do not establish matching
story boundaries. No corpus transcription accuracy or detection recall has
been measured.

## Geometry and schema failures

Coordinates exceed the required 0–1000 frame in both variants. Even boxes that
fall within the range have not been shown to align with their source regions.
We have not silently rescaled or clipped them; an inconsistent frame cannot
be repaired by assuming a scale factor.

The contract checker in `validate.py` rejects these records. A future strict
JSON schema could prevent missing fields and some malformed values, but it
would not prevent altered wording, omitted text, or plausible wrong boxes.

## Next experiment

Use local OCR/native text and measured region boxes as evidence. Give Claude
fixed region IDs and ask it to assign roles and associate regions into stories,
without generating coordinates or retranscribing every word. Compare against
manually checked regions, including an interior page, before expanding.

The paid trial does not establish that this hybrid will succeed. It identifies
what should change and provides a small comparison dataset. See
[other low-cost approaches](../../docs/ALTERNATIVES.md).

Raw responses, extracted JSON, token counts, and contract failures are under
`results/tiles/` and `results/overview/`. `results/summary.json` records spending
and the stop decision; `results/input_manifest.json` records the source hashes
and prepared image inputs. Large base64 request files remain under ignored
`tmp/pilot/` and can be recreated with `prepare.py`.
