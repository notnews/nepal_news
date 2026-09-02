"""Render three front pages and prepare six image requests without submitting."""

import base64
import hashlib
import json
import math
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tmp" / "pilot"
MODEL = "anthropic/claude-sonnet-5"
MAX_TOKENS = 32768
PROMPT = """Transcribe this newspaper page into JSON. Images show ONE page: an
 overview followed, when supplied, by overlapping detail crops. Each image is
 labelled with its bounds on the page in normalized 0..1000 coordinates.
 Use crops for legibility and the overview for article association. Deduplicate
 overlap. Never invent missing text or complete a story using general knowledge.
 Read Nepali as Nepali Unicode and English as English; do not translate.
 Return {\"page_complete\":bool,\"items\":[{\"id\":str,\"type\":
 \"story|brief|ad|listing|graphic|caption|furniture|unknown\",\"headline\":str|null,
 \"byline\":str|null,\"body\":str|null,\"continuation_marker\":str|null,
 \"regions\":[{\"role\":\"headline|byline|body|caption|image|other\",
 \"bbox\":[x0,y0,x1,y1],\"order\":int}],\"quality_flags\":[str]}],
 \"unreadable_regions\":[[x0,y0,x1,y1]]}.
 Coordinates refer to the FULL page, normalized to 0..1000, top-left origin.
 Keep separate stories distinct, follow columns, preserve body paragraph breaks,
 and exclude bylines/captions/pull quotes from body. Retain ads and furniture as
 their own items. Copy attribution exactly or use null. Report unreadable or
 incomplete material explicitly. Transcribe each item once. Return JSON only.
"""


def tile_boxes(width, height):
    """Cover the page with a 2 by 3 grid and 5% margin on each tile edge."""
    dx, dy = math.ceil(width / 40), math.ceil(height / 60)
    return [
        (
            max(0, col * width // 2 - dx),
            max(0, row * height // 3 - dy),
            min(width, (col + 1) * width // 2 + dx),
            min(height, (row + 1) * height // 3 + dy),
        )
        for row in range(3)
        for col in range(2)
    ]


def image_block(path):
    return {
        "type": "image_url",
        "image_url": {
            "url": "data:image/png;base64,"
            + base64.b64encode(path.read_bytes()).decode()
        },
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, manifest = [], []
    for pdf in sorted((ROOT / "pdfs").glob("*.pdf")):
        prefix = OUT / f"{pdf.stem}_p1_150dpi"
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                "1",
                "-singlefile",
                "-r",
                "150",
                "-png",
                str(pdf),
                str(prefix),
            ],
            check=True,
        )
        with Image.open(prefix.with_suffix(".png")) as source:
            width, height = source.size
            overview = source.copy()
            overview.thumbnail((2240, 2240), Image.Resampling.LANCZOS)
            overview_path = OUT / f"{pdf.stem}_p1_overview.png"
            overview.save(overview_path)
            images = [(overview_path, [0, 0, 1000, 1000])]
            for i, box in enumerate(tile_boxes(width, height)):
                path = OUT / f"{pdf.stem}_p1_tile{i + 1}.png"
                source.crop(box).save(path)
                bounds = [
                    round(1000 * value / dimension, 2)
                    for value, dimension in zip(box, (width, height, width, height))
                ]
                images.append((path, bounds))
        for variant, selected in [("overview", images[:1]), ("tiles", images)]:
            content = [{"type": "text", "text": PROMPT}]
            visual_tokens = 0
            for path, bounds in selected:
                with Image.open(path) as im:
                    tokens = math.ceil(im.width / 28) * math.ceil(im.height / 28)
                    assert max(im.size) <= 2576 and tokens <= 4784
                    visual_tokens += tokens
                content.extend(
                    [
                        {"type": "text", "text": f"Image page bounds: {bounds}"},
                        image_block(path),
                    ]
                )
            custom_id = f"{pdf.stem}_p1_{variant}"
            rows.append(
                {
                    "custom_id": custom_id,
                    "model": MODEL,
                    "messages": [{"role": "user", "content": content}],
                    "params": {"max_tokens": MAX_TOKENS},
                }
            )
            manifest.append(
                {
                    "custom_id": custom_id,
                    "source_pdf": str(pdf.relative_to(ROOT)),
                    "source_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                    "pdf_page_index": 1,
                    "render_dpi": 150,
                    "variant": variant,
                    "images": [
                        {"path": str(p.relative_to(ROOT)), "bounds": b}
                        for p, b in selected
                    ],
                    "visual_tokens": visual_tokens,
                    "max_output_tokens": MAX_TOKENS,
                }
            )
    assert len(rows) == 6, "This pilot is restricted to the three source PDFs."
    (OUT / "requests.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Prepared {len(rows)} requests; no API calls made.")
    print(f"Visual tokens: {sum(r['visual_tokens'] for r in manifest):,}")


if __name__ == "__main__":
    main()
