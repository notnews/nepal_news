# Proposed extraction schema

Status: design proposal, not the format emitted by `experiments/text_layer/extract.py`.

The pipeline has three separate stages: page-specific layout detection, text
recognition, and article assembly. Layout proposals can be revised when they
merge stories or fragment content. No fixed page template or column count is
assumed. See the [layout comparison](../experiments/layout/README.md).

Use one JSONL record per issue. Pages own detected regions independently of
assembled items; items reference regions. Preserve every region, including
unassigned, uncertain, and non-editorial regions. A story can occupy several
columns or pages, so a single rectangle cannot represent its occupied area.
Page reading order is distinct from order within each article.

The first Claude pilot returned out-of-range geometry and altered source words.
See [the results](../experiments/claude/RESULTS.md). An association model may
reference detected region IDs, but it must be able to flag missing, merged, or
split regions for layout revision. Valid JSON does not establish accuracy.

## What transfers from TOI

Consulted `../toi_stories/docs/SCHEMA.md` and `scripts/extract_v2.py` on
2026-09-05 (`../toi` was absent). Borrow typed items, copy-or-null attribution,
verbatim body text, continuation cues, images with captions and credits, and
extraction provenance. TOI's schema document proposes some fields that its
extractor does not yet emit; it is not itself evidence of implementation.

TOI starts with vendor-segmented clippings. Nepal starts with whole issues:
layout segmentation, item association, page coverage, and reading order must
be evaluated here. TOI's English clipping evaluation does not validate Nepali
font conversion or full-page extraction.

## Record contract

| Level | Fields and meaning |
|---|---|
| Issue | `schema_version`, `issue_id`, `paper_code`, `newspaper_name`, `edition`, `language`, `date_iso`, `date_printed`, `date_calendar`, `date_source`, `source_pdf`, `source_sha256`, `pages`, `story_links`, `extraction` |
| Page | `page_id`, `pdf_page_index` (1-based), `page_printed` (string or null), `section`, `width_pt`, `height_pt`, `rotation`, `status`, `regions`, `items`, `quality_flags` |
| Item | `item_id`, `item_type`, `parent_item_id`, `language`, `kicker`, `headline`, `subhead`, `byline`, `dateline_city`, `dateline_date`, `body`, `ordered_region_ids`, `images`, `continuation`, `salience`, `quality` |
| Region | `region_id`, `role`, `bbox`, `polygon`, `page_reading_order`, `text_raw`, `text_unicode`, `font_runs`, `method`, `layout_run_id`, `quality_flags` |
| Image | `image_id`, `region_id`, `kind`, `caption_region_ids`, `credit_region_ids` |
| Story link | `from_item_id`, `to_item_id`, `relation`, `evidence`, `status` |
| Extraction | `run_id`, `code_revision`, `config`, `dependency_versions`, `started_at`, `duration_seconds`, `font_mappings`, `model`, `model_digest`, `prompt_version`, `render_dpi` |

`item_type`: story, brief, ad, listing, graphic, caption, furniture, or unknown.
`role`: kicker, headline, subhead, byline, dateline, body, caption, credit,
pull_quote, image, continuation_marker, or other. A sidebar is a separate
item with `parent_item_id`; captions and pull quotes must not duplicate body.
Standalone photos/graphics remain items even without an associated story.

Use explicit null for absent or unresolved scalar fields and empty arrays for
no observed members. Preserve unreadable text with a quality flag and region
reference; do not silently substitute invented text. `quality.field_status`
distinguishes absent, extracted, unreadable, and not_processed. Do not equate
an empty body with an empty printed item. Language permits `ne`, `en`, `mixed`,
and `und`; printed dates remain verbatim, including Bikram Sambat dates.
Filename dates are metadata claims until checked against the masthead.

## Geometry and identity

Coordinates are PDF points, `[x0, top, x1, bottom]`, top-left origin, on the
rotation-applied page. Store the rendering transform if a model returns pixel
coordinates. Require finite, ordered bounds within page dimensions; record
and inspect out-of-page source objects rather than silently clipping them.

Use source SHA-256 as document identity, page index for page identity, and
persisted region/item identifiers within an extraction run. IDs must be unique
within the issue. A new segmentation can change items: preserve run identity
and explicit cross-run matches instead of promising stable IDs from rounded
vertical position. Links must resolve to existing items in the same issue.

`ordered_region_ids` supplies article-specific order and resolves to page-owned
regions. A region may remain unassigned; article association must not discard it.
`body` joins only body regions in that explicit order, retaining paragraph
breaks. Keep legacy text and font names so decoding can be audited and revised.
For each mapping retain the embedded font, chosen mapping, method, and review
status; a high Devanagari share is not a confidence probability.

## Continuations

Keep `starts_midstream`, verbatim `marker_text`, `to_page_printed`, and
`from_page_printed` separately from inferred links. Printed pages may include
section labels; they are not PDF indices. Link status is proposed, verified,
or rejected, with cue/region evidence. Permit unresolved and ambiguous links.
Only verified links enter the assembled-story export. Validate against cycles,
conflicting destinations, and duplicate body regions; support more than two
parts and retain the page-level items after assembly.

## Salience measures

Store measured features, not a single importance score:

- `headline_font_max_pt`, `body_font_median_pt`, and their ratio, nullable for OCR.
- `headline_width_fraction`: headline width / page width. This is not a count
  of columns. `column_count` stays null until actual columns are detected.
- `text_area_share` and `image_area_share`: unions of their respective region
  rectangles divided by full page area. `item_area_share` uses their combined
  union to avoid double counting; it remains a geometric proxy.
- `headline_top_fraction`, `headline_above_midpoint`, and
  `area_above_midpoint_fraction`. The page midpoint is a stated fold proxy,
  not an observed physical fold.
- PDF page index, printed page label, and verified front-page status.

All area denominators use the full page, including ads and margins. An
editorial-area denominator would be a separate measure requiring reliable
item classification. None of these features establishes readership or impact.

## Validation before adoption

Validate types, enums, dates, ID uniqueness, reference integrity, coordinate
bounds, area fractions in [0, 1], and deterministic body reconstruction.
Every source page must appear with status complete, partial, or failed;
no-text pages must not disappear. Syntax checks do not establish accuracy.

Build manually checked page/region gold covering both languages, multicolumn
stories, sidebars, advertisements, photographs, and continuation pages. Keep
held-out pages separate from development. Measure item detection precision
and recall, region overlap, reading order, body completeness, transcription
character error, attribution accuracy, and continuation-link precision/recall.
Report each by paper and content type, with denominators. Ask a fluent Nepali
reader to verify font conversion against crops before claiming text accuracy.

Start with the three front pages for diagnosis and a separate selection of
interior pages for evaluation. Compare layout-aware text-layer extraction with
selective OCR/vision on failing regions. TOI's local vision approach is a
candidate fallback, requiring its own Nepali evaluation. Do not bulk-process
or assign substantive topic/sentiment outcomes until extraction is assessed.
