"""Score geometry against provisional LabelMe references and build a review gallery."""

import json
from collections import defaultdict

from PIL import Image, ImageDraw
from run import RESULTS, ROOT, WORK, overlay, save, to_pdf

REFERENCE = ROOT / "experiments/layout/reference"
EDITORIAL = {"body", "headline", "byline", "caption", "pull_quote"}


def area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def intersection(a, b):
    return area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def iou(a, b):
    overlap = intersection(a, b)
    union = area(a) + area(b) - overlap
    return overlap / union if union else 0.0


def covered_area(target, boxes):
    """Area of the union of rectangles intersected with a target rectangle."""
    clipped = [
        [
            max(target[0], b[0]),
            max(target[1], b[1]),
            min(target[2], b[2]),
            min(target[3], b[3]),
        ]
        for b in boxes
        if intersection(target, b) > 0
    ]
    xs = sorted({v for b in clipped for v in [b[0], b[2]]})
    total = 0.0
    for left, right in zip(xs, xs[1:]):
        intervals = sorted(
            (b[1], b[3]) for b in clipped if b[0] <= left and b[2] >= right
        )
        end, length = float("-inf"), 0.0
        for low, high in intervals:
            length += max(0, high - max(low, end))
            end = max(end, high)
        total += (right - left) * length
    return total


def match(predicted, reference, threshold=0.5):
    """Maximum-cardinality one-to-one matching; prefer higher IoU per search."""
    edges = [
        sorted(
            [j for j, target in enumerate(reference) if iou(box, target) >= threshold],
            key=lambda j: (-iou(box, reference[j]), j),
        )
        for box in predicted
    ]
    owner = {}

    def augment(i, visited):
        for j in edges[i]:
            if j in visited:
                continue
            visited.add(j)
            if j not in owner or augment(owner[j], visited):
                owner[j] = i
                return True
        return False

    for i in range(len(predicted)):
        augment(i, set())
    return sorted((i, j) for j, i in owner.items())


def reference_regions(page_id, points):
    data = json.loads((REFERENCE / f"{page_id}.json").read_text())
    regions = []
    for shape in data["shapes"]:
        a, b = shape["points"]
        regions.append(
            {
                "label": shape["label"],
                "article_id": shape["group_id"],
                "bbox": to_pdf(
                    a + b, [data["imageWidth"], data["imageHeight"]], points
                ),
            }
        )
    return regions


def score(result, reference):
    boxes = [r["bbox"] for r in result["regions"]]
    gold = [r["bbox"] for r in reference]
    pairs = match(boxes, gold)
    matched = {j for _, j in pairs}
    merges = []
    for i, box in enumerate(boxes):
        stories = {
            r["article_id"]
            for r in reference
            if r["label"] == "body"
            and r["article_id"] is not None
            and intersection(box, r["bbox"]) / area(r["bbox"]) >= 0.5
        }
        if len(stories) > 1:
            merges.append(result["regions"][i]["region_id"])
    fragmented = [
        j
        for j, box in enumerate(gold)
        if sum(intersection(box, p) / area(p) >= 0.5 for p in boxes if area(p)) > 1
    ]
    text_labels = {
        "article",
        "author",
        "headline",
        "image_caption",
        "text",
        "doc_title",
        "paragraph_title",
        "vision_footnote",
        "aside_text",
    }
    text_boxes = [r["bbox"] for r in result["regions"] if r["label"] in text_labels]
    editorial = [r["bbox"] for r in reference if r["label"] in EDITORIAL]
    ads = [r["bbox"] for r in reference if r["label"] == "ad"]
    return {
        "editorial_reference_area": sum(map(area, editorial)),
        "editorial_area_covered_by_text": sum(
            covered_area(b, text_boxes) for b in editorial
        ),
        "ad_reference_area": sum(map(area, ads)),
        "ad_area_labeled_as_text": sum(covered_area(b, text_boxes) for b in ads),
        "editorial_regions_below_10pct_coverage": sum(
            covered_area(b, text_boxes) / area(b) < 0.1 for b in editorial
        ),
        "predictions": len(boxes),
        "reference_regions": len(gold),
        "matches_iou50": len(pairs),
        "precision_iou50": len(pairs) / len(boxes) if boxes else 0.0,
        "recall_iou50": len(pairs) / len(gold) if gold else None,
        "matched_ious": [iou(boxes[i], gold[j]) for i, j in pairs],
        "unmatched_reference_indices": [
            j for j in range(len(gold)) if j not in matched
        ],
        "unmatched_editorial_regions": sum(
            r["label"] in EDITORIAL and j not in matched
            for j, r in enumerate(reference)
        ),
        "cross_article_merge_candidates": merges,
        "fragmentation_candidates": fragmented,
        "matched_labels": [
            [result["regions"][i]["label"], reference[j]["label"]] for i, j in pairs
        ],
    }


def gallery(results):
    parts = [
        '<!doctype html><meta charset="utf-8"><title>Layout comparison</title>',
        "<style>body{font:16px system-ui;margin:24px} "
        ".row{display:flex;overflow-x:auto;gap:12px} "
        "figure{margin:0;flex:0 0 550px}img{width:550px} "
        "h2{margin-top:40px}a{color:#0755aa}</style>",
        "<h1>Newspaper layout comparison</h1>",
        "<p>References are provisional assistant annotations, drawn before "
        "viewing model outputs. Geometry scores are class-agnostic. "
        "Boxes are page-specific. No OCR or article assembly was run.</p>",
    ]
    pages = sorted({r["page_id"] for r in results})
    for page in pages:
        sample = next(r for r in results if r["page_id"] == page)
        refs = reference_regions(page, sample["page_size_pt"])
        reference_result = {
            **sample,
            "regions": [
                {
                    **r,
                    "region_id": f"g{i:03d}",
                    "bbox_pixels": to_pdf(
                        r["bbox"], sample["page_size_pt"], sample["image_size"]
                    ),
                }
                for i, r in enumerate(refs)
            ],
        }
        overlay(reference_result, RESULTS / f"{page}_reference.jpg")
        native = json.loads((WORK / "native" / f"{page}.json").read_text())
        image = Image.open(ROOT / sample["image"]).convert("RGB")
        image.thumbnail((1200, 1800))
        draw = ImageDraw.Draw(image)
        for group, color in [("chars", "#0000aa"), ("rules", "#ff0000")]:
            for obj in native[group]:
                box = [obj[k] for k in ["x0", "top", "x1", "bottom"]]
                if all(v is not None for v in box):
                    draw.rectangle(
                        to_pdf(box, sample["page_size_pt"], image.size),
                        outline=color,
                        width=1,
                    )
        image.save(RESULTS / f"{page}_native.jpg")
        parts.append(f'<h2>{page} — {sample["split"]}</h2><div class="row">')
        for label, file in [
            ("Source", f"../reference/{page}.jpg"),
            ("Provisional reference", f"{page}_reference.jpg"),
            ("Native characters and rules", f"{page}_native.jpg"),
        ]:
            parts.append(
                f"<figure><figcaption>{label}</figcaption>"
                f'<a href="{file}"><img src="{file}"></a></figure>'
            )
        for r in sorted(
            [r for r in results if r["page_id"] == page],
            key=lambda r: (r["dpi"], r["model"]),
        ):
            key = f'{r["model"]}_{page}_{r["dpi"]}'
            parts.append(
                f'<figure><figcaption>{r["model"]} {r["dpi"]} DPI '
                f'— {r["status"]} — <a href="{key}.json">JSON</a>'
                "</figcaption>"
            )
            if r["status"] == "ok":
                parts.append(f'<a href="{key}.jpg"><img src="{key}.jpg"></a>')
            parts.append("</figure>")
        parts.append("</div>")
    (RESULTS / "index.html").write_text("\n".join(parts) + "\n")


def main():
    records, totals = [], defaultdict(lambda: defaultdict(float))
    for path in sorted(RESULTS.glob("*.json")):
        result = json.loads(path.read_text())
        if not isinstance(result, dict) or "model" not in result:
            continue
        reference = reference_regions(result["page_id"], result["page_size_pt"])
        metrics = score(result, reference)
        records.append(
            {k: result[k] for k in ["page_id", "model", "dpi", "split", "status"]}
            | metrics
        )
        key = f'{result["model"]}_{result["dpi"]}_{result["split"]}'
        total = totals[key]
        total["runs"] += 1
        total["failed_runs"] += result["status"] != "ok"
        for field in [
            "predictions",
            "reference_regions",
            "matches_iou50",
            "unmatched_editorial_regions",
            "editorial_reference_area",
            "editorial_area_covered_by_text",
            "ad_reference_area",
            "ad_area_labeled_as_text",
            "editorial_regions_below_10pct_coverage",
        ]:
            total[field] += metrics[field]
        total["cross_article_merge_candidates"] += len(
            metrics["cross_article_merge_candidates"]
        )
    for total in totals.values():
        total["editorial_text_area_coverage"] = total[
            "editorial_area_covered_by_text"
        ] / max(1, total["editorial_reference_area"])
        total["ad_text_area_fraction"] = total["ad_area_labeled_as_text"] / max(
            1, total["ad_reference_area"]
        )
        total["precision_iou50"] = total["matches_iou50"] / max(1, total["predictions"])
        total["recall_iou50"] = total["matches_iou50"] / total["reference_regions"]
    save(
        RESULTS / "metrics.json",
        {
            "reference_status": (
                "provisional assistant visual annotations, not human gold"
            ),
            "matching": "class-agnostic maximum-cardinality matching at IoU >= 0.5",
            "warning": (
                "Unmatched regions can be boundary/granularity errors, not omissions."
            ),
            "totals": dict(totals),
            "pages": records,
        },
    )
    results = [json.loads(p.read_text()) for p in RESULTS.glob("*.json")]
    gallery([r for r in results if isinstance(r, dict) and "model" in r])


if __name__ == "__main__":
    main()
