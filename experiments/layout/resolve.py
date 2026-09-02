"""Run a bounded, local Qwen diagnostic on layout ambiguities and controls."""

import argparse
import importlib.metadata
import json
import subprocess
import sys
import time

from PIL import Image, ImageDraw
from run import RESULTS, ROOT, WORK, digest, save, to_pdf

OUT = RESULTS / "agreement/qwen"
MODEL = {
    "repo": "mlx-community/Qwen3.5-4B-4bit",
    "revision": "0e7ffd5c629ef7719d4cbc04069232580bfa9d9c",
}
CASES = [
    ("fashion_ad", "TKP_2009_01_08_p1", "r015", "shared_error", "advertisement"),
    ("english_quote", "TKP_2009_01_08_p1", "r013", "shared_error", "pull_quote"),
    ("nepali_quote", "KPUR_2013_02_20_p3", "r031", "shared_error", "pull_quote"),
    ("main_story", "KPUR_2013_07_31_p1", "r014", "disagreement", "editorial_group"),
    (
        "merged_headlines",
        "TKP_2009_01_08_p3",
        "r013",
        "disagreement",
        "multiple_headlines",
    ),
    ("photo_control", "KPUR_2013_02_20_p3", "r000", "control", "photograph"),
    ("headline_control", "TKP_2009_01_08_p3", "r015", "control", "headline"),
    ("body_control", "KPUR_2013_02_20_p7", "r007", "control", "body_text"),
]
PROMPT = """The two images show a newspaper page overview and a detail crop.
The thin red rectangle identifies the target region; it is a machine overlay.
Determine the target's role in the newspaper using its contents AND context.
Choose exactly one decision: advertisement, public_notice, pull_quote,
headline, multiple_headlines, body_text, photograph, editorial_group, uncertain.
Use advertisement when a pictured person belongs to a commercial advertisement.
Use pull_quote for a quotation displayed inside a story, not a new story title.
Use multiple_headlines if the target merges headlines of distinct stories.
Use editorial_group if it encloses an editorial story and/or sidebar with
headline and body components. Use uncertain if the images are insufficient.
Return only JSON with keys decision and evidence; evidence must be one short
sentence describing visible evidence. Do not transcribe the article or invent
coordinates. No detector labels or reference answers are provided."""


def prepare():
    records = []
    for case_id, page_id, region_id, stratum, expected in CASES:
        result = json.loads((RESULTS / f"american_{page_id}_150.json").read_text())
        region = next(r for r in result["regions"] if r["region_id"] == region_id)
        source = Image.open(ROOT / result["image"]).convert("RGB")
        box = region["bbox_pixels"]
        context = [
            max(0, int(box[0] - 80)),
            max(0, int(box[1] - 80)),
            min(source.width, int(box[2] + 80)),
            min(source.height, int(box[3] + 80)),
        ]
        overview = source.copy()
        overview.thumbnail((800, 1100))
        ImageDraw.Draw(overview).rectangle(
            to_pdf(box, source.size, overview.size), outline="red", width=2
        )
        detail = source.crop(context)
        ImageDraw.Draw(detail).rectangle(
            [
                box[0] - context[0],
                box[1] - context[1],
                box[2] - context[0],
                box[3] - context[1],
            ],
            outline="red",
            width=3,
        )
        detail.thumbnail((1200, 1400))
        images = []
        for label, image in [("overview", overview), ("detail", detail)]:
            path = OUT / f"{case_id}_{label}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(path, quality=90)
            images.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": digest(path),
                    "size": list(image.size),
                }
            )
        records.append(
            {
                "case_id": case_id,
                "page_id": page_id,
                "region_id": region_id,
                "stratum": stratum,
                "expected": expected,
                "reference_status": "provisional assistant visual judgment",
                "images": images,
                "prompt": PROMPT,
            }
        )
    save(OUT / "cases.json", records)


def parse_response(text):
    decoder = json.JSONDecoder()
    for i, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "decision" in value and "evidence" in value:
            return value
    return None


def run():
    records = json.loads((OUT / "cases.json").read_text())
    model = WORK / "qwen/model"
    for record in records:
        path = OUT / f'{record["case_id"]}.json'
        if path.exists():
            continue
        command = [
            sys.executable,
            "-m",
            "mlx_vlm.generate",
            "--model",
            str(model),
            "--image",
            *[str(ROOT / im["path"]) for im in record["images"]],
            "--prompt",
            record["prompt"],
            "--max-tokens",
            "192",
            "--temperature",
            "0",
            "--thinking-mode",
            "disabled",
            "--no-verbose",
        ]
        started = time.monotonic()
        try:
            result = subprocess.run(command, capture_output=True, timeout=90, cwd=WORK)
            status = "completed" if result.returncode == 0 else "failed"
            stdout, stderr = result.stdout.decode(), result.stderr.decode()
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            stdout = (exc.stdout or b"").decode(errors="replace")
            stderr = (exc.stderr or b"").decode(errors="replace")
        answer = parse_response(stdout) if status == "completed" else None
        save(
            path,
            {
                **record,
                "model": MODEL,
                "status": status,
                "elapsed_seconds": time.monotonic() - started,
                "max_tokens": 192,
                "thinking": "disabled",
                "temperature": 0,
                "stdout": stdout,
                "stderr": stderr,
                "parsed": answer,
                "matches_provisional_reference": (
                    answer["decision"] == record["expected"] if answer else None
                ),
                "versions": {
                    p: importlib.metadata.version(p)
                    for p in ["mlx", "mlx-vlm", "transformers", "pillow"]
                },
            },
        )
        print(record["case_id"], status, answer, flush=True)
        if status != "completed":
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "run"])
    args = parser.parse_args()
    prepare() if args.action == "prepare" else run()
