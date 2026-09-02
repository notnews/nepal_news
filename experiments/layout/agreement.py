"""Audit detector agreement using exclusive matches and exact rectangle unions."""

import json
from collections import Counter

from evaluate import area, covered_area, intersection, iou, match, reference_regions
from run import RESULTS, geometry_flags, save

OUT = RESULTS / "agreement"
THRESHOLDS = [0.5, 0.7, 0.8, 0.9]
FAMILIES = {
    "article": "body",
    "text": "body",
    "headline": "headline",
    "doc_title": "headline",
    "paragraph_title": "headline",
    "author": "byline",
    "image_caption": "caption",
    "vision_footnote": "caption",
    "figure_title": "caption",
    "photograph": "image",
    "image": "image",
    "table": "table",
    "newspaper_header": "furniture",
    "masthead": "furniture",
    "page_number": "furniture",
    "header": "furniture",
    "footer": "furniture",
    "number": "furniture",
    "cartoon_or_advertisement": "ad_or_graphic",
}


def union_area(boxes):
    if not boxes:
        return 0.0
    bounds = [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]
    return covered_area(bounds, boxes)


def union_iou(box, boxes):
    overlap = covered_area(box, boxes)
    denominator = area(box) + union_area(boxes) - overlap
    return overlap / denominator if denominator else 0.0


def proposals(american, paddle, size):
    """Assign each Paddle box once, then compare single and grouped matches."""
    a = [r for r in american if not geometry_flags(r["bbox"], size)]
    p = [r for r in paddle if not geometry_flags(r["bbox"], size)]
    owned = {r["region_id"]: [] for r in a}
    for candidate in p:
        ranked = sorted(
            a, key=lambda r: (-iou(r["bbox"], candidate["bbox"]), r["region_id"])
        )
        if ranked and intersection(ranked[0]["bbox"], candidate["bbox"]) > 0:
            owned[ranked[0]["region_id"]].append(candidate)
    output = []
    for region in a:
        box = region["bbox"]
        candidates = owned[region["region_id"]]
        singles = sorted(
            candidates, key=lambda r: (-iou(box, r["bbox"]), r["region_id"])
        )
        chosen = singles[:1]
        score = iou(box, chosen[0]["bbox"]) if chosen else 0.0
        contained = [
            r
            for r in candidates
            if intersection(box, r["bbox"]) / area(r["bbox"]) >= 0.8
        ]
        grouped_score = union_iou(box, [r["bbox"] for r in contained])
        if len(contained) > 1 and grouped_score > score:
            chosen, score = contained, grouped_score
        family = FAMILIES.get(region["label"], "unknown")
        roles = [FAMILIES.get(r["label"], "unknown") for r in chosen]
        compatible = bool(chosen) and family not in {"unknown", "ad_or_graphic"}
        compatible = compatible and all(role == family for role in roles)
        conflicts = [
            r["region_id"]
            for r in candidates
            if r not in chosen
            and intersection(box, r["bbox"]) / area(r["bbox"]) >= 0.8
            and FAMILIES.get(r["label"], "unknown") != family
        ]
        output.append(
            {
                "american_id": region["region_id"],
                "american_label": region["label"],
                "bbox": box,
                "paddle_ids": [r["region_id"] for r in chosen],
                "paddle_labels": [r["label"] for r in chosen],
                "paddle_boxes": [r["bbox"] for r in chosen],
                "match_type": "group" if len(chosen) > 1 else "single",
                "union_iou": score,
                "compatible_role": compatible,
                "role_family": family,
                "internal_role_conflicts": conflicts,
            }
        )
    used = [r for candidate in output for r in candidate["paddle_ids"]]
    assert len(used) == len(set(used))
    return output


def accepts(candidate, threshold):
    return (
        candidate["union_iou"] >= threshold
        and candidate["compatible_role"]
        and not candidate["internal_role_conflicts"]
    )


def audit(candidate, refs):
    ranked = sorted(
        enumerate(refs), key=lambda r: -iou(candidate["bbox"], r[1]["bbox"])
    )
    j, ref = ranked[0]
    overlap = iou(candidate["bbox"], ref["bbox"])
    return {
        "nearest_reference_index": j,
        "reference_iou": overlap,
        "reference_label": ref["label"],
        "reference_boundary_and_role_match": (
            overlap >= 0.8 and candidate["role_family"] == ref["label"]
        ),
    }


def gallery(pages):
    import html

    parts = [
        '<!doctype html><meta charset="utf-8"><title>Detector agreement</title>',
        "<style>body{font:16px system-ui;margin:24px;max-width:1100px}"
        "svg{width:100%;height:auto} .candidate{fill:none;stroke-width:2}"
        ".accept{stroke:#008000}.review{stroke:#d00000}</style>",
        "<h1>Detector agreement at 150 DPI</h1>"
        "<p>Green: candidate agreement; red: review. Hover for region details. "
        "Agreement is not accuracy. Human validation is pending.</p>"
        '<label>IoU threshold <select id="threshold">'
        "<option>0.5</option><option>0.7</option><option selected>0.8</option>"
        "<option>0.9</option></select></label>"
        '<p id="counts"></p>',
    ]
    for page in pages:
        if page["dpi"] != 150:
            continue
        width, height = page["page_size_pt"]
        name = page["page_id"]
        parts.append(
            f"<h2>{name}</h2><p>"
            f'{len(page["unmatched_paddle_ids"])} valid Paddle regions '
            "are outside selected matches and remain in the review pool.</p>"
        )
        parts.append(
            f'<svg viewBox="0 0 {width} {height}" '
            'xmlns="http://www.w3.org/2000/svg">'
            f'<image href="../../reference/{name}.jpg" '
            f'width="{width}" height="{height}"/>'
        )
        for c in page["candidates"]:
            x0, y0, x1, y1 = c["bbox"]
            eligible = int(c["compatible_role"] and not c["internal_role_conflicts"])
            label = html.escape(
                f'{c["american_id"]} {c["american_label"]}; '
                f'Paddle {c["paddle_ids"]}; union IoU {c["union_iou"]:.3f}; '
                f'compatible roles: {c["compatible_role"]}'
            )
            parts.append(
                f'<rect class="candidate" x="{x0}" y="{y0}" '
                f'width="{x1-x0}" height="{y1-y0}" '
                f'data-iou="{c["union_iou"]}" data-eligible="{eligible}">'
                f"<title>{label}</title></rect>"
            )
        parts.append("</svg>")
    parts.append("""<script>
const select = document.getElementById('threshold');
function update() {
  let accepted = 0, total = 0;
  document.querySelectorAll('.candidate').forEach(box => {
    const ok = +box.dataset.iou >= +select.value && +box.dataset.eligible === 1;
    box.classList.toggle('accept', ok); box.classList.toggle('review', !ok);
    accepted += +ok; total++;
  });
  document.getElementById('counts').textContent =
    `${accepted} / ${total} American Stories regions are candidate agreements.`;
}
select.addEventListener('change', update); update();
</script>""")
    (OUT / "index.html").write_text("\n".join(parts) + "\n")


def main():
    pages, counters = [], {}
    for path in sorted(RESULTS.glob("american_*.json")):
        a = json.loads(path.read_text())
        p = json.loads(
            path.with_name(path.name.replace("american_", "paddle_", 1)).read_text()
        )
        refs = reference_regions(a["page_id"], a["page_size_pt"])
        candidates = proposals(a["regions"], p["regions"], a["page_size_pt"])
        for c in candidates:
            c.update(audit(c, refs))
        valid_a = [
            r["bbox"]
            for r in a["regions"]
            if not geometry_flags(r["bbox"], a["page_size_pt"])
        ]
        valid_p = [
            r["bbox"]
            for r in p["regions"]
            if not geometry_flags(r["bbox"], p["page_size_pt"])
        ]
        for threshold in THRESHOLDS:
            key = f'{a["dpi"]}_{a["split"]}_{threshold}'
            totals = counters.setdefault(key, Counter())
            accepted = [c for c in candidates if accepts(c, threshold)]
            totals.update(
                {
                    "pages": 1,
                    "american_valid_regions": len(valid_a),
                    "paddle_valid_regions": len(valid_p),
                    "one_to_one_geometry_matches": len(
                        match(valid_a, valid_p, threshold)
                    ),
                    "union_geometry_matches": sum(
                        c["union_iou"] >= threshold for c in candidates
                    ),
                    "candidate_accepts": len(accepted),
                    "group_accepts": sum(c["match_type"] == "group" for c in accepted),
                    "reference_boundary_role_matches": sum(
                        c["reference_boundary_and_role_match"] for c in accepted
                    ),
                    "reference_boundary_role_mismatches": sum(
                        not c["reference_boundary_and_role_match"] for c in accepted
                    ),
                }
            )
        pages.append(
            {
                "page_id": a["page_id"],
                "dpi": a["dpi"],
                "split": a["split"],
                "american_source": path.name,
                "page_size_pt": a["page_size_pt"],
                "unmatched_paddle_ids": [
                    r["region_id"]
                    for r in p["regions"]
                    if not geometry_flags(r["bbox"], p["page_size_pt"])
                    and r["region_id"]
                    not in {rid for c in candidates for rid in c["paddle_ids"]}
                ],
                "candidates": candidates,
            }
        )
    save(
        OUT / "audit.json",
        {
            "thresholds": THRESHOLDS,
            "status": "diagnostic; no automatic acceptance enabled",
            "reference_status": (
                "provisional assistant annotations; previously inspected pages"
            ),
            "warning": (
                "Reference mismatch is not an adjudicated error. "
                "Agreement is not accuracy."
            ),
            "totals": {k: dict(v) for k, v in counters.items()},
            "pages": pages,
        },
    )
    gallery(pages)
    print(
        json.dumps(
            {k: dict(v) for k, v in counters.items() if k.startswith("150_")}, indent=2
        )
    )


if __name__ == "__main__":
    main()
