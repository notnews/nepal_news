"""Reproduce the bounded layout-only comparison using released model components."""

import argparse
import hashlib
import importlib.metadata
import json
import math
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "tmp/layout"
RESULTS = ROOT / "experiments/layout/results"
PADDLE_REVISION = "97d101e6db2642e162a1d05392d1b0231c91033e"
AMERICAN_REVISION = "f307e5cec224fed5977b080c4f170d89c93ae3ba"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def to_pdf(box, pixels, points):
    return [float(v) * points[i % 2] / pixels[i % 2] for i, v in enumerate(box)]


def geometry_flags(box, size):
    flags = []
    if len(box) != 4 or not all(math.isfinite(v) for v in box):
        return ["invalid_coordinates"]
    if box[2] <= box[0] or box[3] <= box[1]:
        flags.append("degenerate_bbox")
    if box[0] < 0 or box[1] < 0 or box[2] > size[0] or box[3] > size[1]:
        flags.append("out_of_page_bbox")
    return flags


def prepare():
    import pdfplumber

    entries = []
    for pdf in sorted((ROOT / "pdfs").glob("*.pdf")):
        with pdfplumber.open(pdf) as document:
            for number in [1, 3, 7]:
                page = document.pages[number - 1]
                page_id = f"{pdf.stem}_p{number}"
                native = {
                    "page_id": page_id,
                    "width_pt": page.width,
                    "height_pt": page.height,
                    "chars": [
                        {
                            k: c.get(k)
                            for k in ["x0", "top", "x1", "bottom", "fontname", "size"]
                        }
                        for c in page.chars
                    ],
                    "rules": [
                        {k: c.get(k) for k in ["x0", "top", "x1", "bottom"]}
                        for c in page.lines + page.rects
                    ],
                }
                save(WORK / "native" / f"{page_id}.json", native)
                for dpi in [150, 300]:
                    stem = WORK / "images" / f"{page_id}_{dpi}"
                    stem.parent.mkdir(parents=True, exist_ok=True)
                    image = stem.with_suffix(".png")
                    if not image.exists():
                        subprocess.run(
                            [
                                "pdftoppm",
                                "-f",
                                str(number),
                                "-l",
                                str(number),
                                "-r",
                                str(dpi),
                                "-singlefile",
                                "-png",
                                str(pdf),
                                str(stem),
                            ],
                            check=True,
                        )
                    with Image.open(image) as im:
                        size = list(im.size)
                    entries.append(
                        {
                            "page_id": page_id,
                            "page_index": number,
                            "split": "evaluation" if number == 7 else "development",
                            "source": str(pdf.relative_to(ROOT)),
                            "source_sha256": digest(pdf),
                            "dpi": dpi,
                            "image": str(image.relative_to(ROOT)),
                            "image_sha256": digest(image),
                            "image_size": size,
                            "page_size_pt": [page.width, page.height],
                            "native_char_count": len(page.chars),
                            "native_rule_count": len(page.lines) + len(page.rects),
                        }
                    )
    save(RESULTS / "manifest.json", entries)


def infer(model_name, entry):
    import numpy as np
    import torch

    torch.set_num_threads(4)
    image = Image.open(ROOT / entry["image"]).convert("RGB")
    start = time.monotonic()
    if model_name == "paddle":
        from transformers import AutoImageProcessor, AutoModelForObjectDetection

        location = WORK / "models/paddle"
        processor = AutoImageProcessor.from_pretrained(location, local_files_only=True)
        model = AutoModelForObjectDetection.from_pretrained(
            location, local_files_only=True
        ).eval()
        inputs = processor(images=image, return_tensors="pt")
        tensor_size = list(inputs["pixel_values"].shape[-2:])
        with torch.inference_mode():
            outputs = model(**inputs)
        raw_path = WORK / "raw" / f"paddle_{entry['page_id']}_{entry['dpi']}.npz"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            raw_path,
            **{
                k: v.detach().cpu().numpy()
                for k, v in outputs.items()
                if isinstance(v, torch.Tensor)
            },
        )
        output = processor.post_process_object_detection(
            outputs, target_sizes=[image.size[::-1]], threshold=0.5
        )[0]
        regions = []
        for i, (score, label, box, polygon) in enumerate(
            zip(
                output["scores"],
                output["labels"],
                output["boxes"],
                output["polygon_points"],
            )
        ):
            regions.append(
                {
                    "region_id": f"r{i:03d}",
                    "label": model.config.id2label[int(label)],
                    "score": float(score),
                    "bbox_pixels": box.tolist(),
                    "polygon_pixels": np.asarray(polygon).tolist(),
                    "order": i,
                }
            )
        checkpoint = location / "model.safetensors"
        settings = {"revision": PADDLE_REVISION, "threshold": 0.5}
    else:
        import onnxruntime as ort
        from ultralytics.data.augment import LetterBox
        from ultralytics.utils.nms import non_max_suppression
        from ultralytics.utils.ops import scale_boxes

        checkpoint = WORK / "models/layout_model_new.onnx"
        labels = json.loads((WORK / "models/american_labels.json").read_text())
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4
        session = ort.InferenceSession(
            str(checkpoint), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        array = LetterBox(new_shape=(1280, 1280), auto=False)(image=np.array(image))
        # PIL supplies RGB; upstream reverses cv2 BGR to the same channel order.
        tensor = np.ascontiguousarray(array.transpose(2, 0, 1))[None]
        tensor = tensor.astype(np.float32) / 255.0
        tensor_size = list(tensor.shape[-2:])
        output = session.run(None, {session.get_inputs()[0].name: tensor})[0]
        raw_path = WORK / "raw" / f"american_{entry['page_id']}_{entry['dpi']}.npz"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(raw_path, output=output)
        predictions = non_max_suppression(
            torch.from_numpy(output),
            conf_thres=0.01,
            iou_thres=0.1,
            agnostic=True,
            max_det=2000,
        )[0]
        # Upstream coordinate scaling clips detections to the source image.
        predictions[:, :4] = scale_boxes(
            (1280, 1280),
            predictions[:, :4],
            image.size[::-1],
        )
        regions = [
            {
                "region_id": f"r{i:03d}",
                "label": labels[str(int(row[5]))],
                "score": float(row[4]),
                "bbox_pixels": row[:4].tolist(),
                "order": None,
            }
            for i, row in enumerate(predictions)
        ]
        settings = {
            "revision": AMERICAN_REVISION,
            "confidence": 0.01,
            "iou": 0.1,
            "agnostic_nms": True,
            "max_det": 2000,
            "coordinate_postprocessing": "ultralytics scale_boxes (clips to image)",
        }
    for region in regions:
        region["bbox"] = to_pdf(
            region["bbox_pixels"], entry["image_size"], entry["page_size_pt"]
        )
        region["quality_flags"] = geometry_flags(region["bbox"], entry["page_size_pt"])
        region["transcription"] = None
        region["article_id"] = None
    return {
        **entry,
        "model": model_name,
        "status": "ok",
        "settings": settings,
        "checkpoint_sha256": digest(checkpoint),
        "input_tensor_hw": tensor_size,
        "inference_and_load_seconds": time.monotonic() - start,
        "raw_tensors": str(raw_path.relative_to(ROOT)),
        "regions": regions,
        "versions": {
            p: importlib.metadata.version(p)
            for p in ["torch", "transformers", "onnxruntime", "ultralytics", "pillow"]
        },
    }


def overlay(result, target):
    image = Image.open(ROOT / result["image"]).convert("RGB")
    image.thumbnail((1200, 1800))
    draw = ImageDraw.Draw(image)
    colors = ["#ff0000", "#008800", "#0000ff", "#a000a0", "#cc6600"]
    for i, region in enumerate(result["regions"]):
        box = to_pdf(region["bbox_pixels"], result["image_size"], image.size)
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        color = colors[i % len(colors)]
        draw.rectangle(box, outline=color, width=2)
        draw.text(
            (box[0], box[1]),
            f"{region['region_id']} {region['label']}",
            fill="white",
            stroke_width=2,
            stroke_fill=color,
        )
    image.save(target)


def run(args):
    entries = json.loads((RESULTS / "manifest.json").read_text())
    for entry in entries:
        if entry["split"] != args.split:
            continue
        for name in ["american", "paddle"]:
            key = f"{name}_{entry['page_id']}_{entry['dpi']}"
            target = RESULTS / f"{key}.json"
            if target.exists():
                continue
            cmd = [
                sys.executable,
                str(Path(__file__).resolve()),
                "worker",
                "--model",
                name,
                "--page-id",
                entry["page_id"],
                "--dpi",
                str(entry["dpi"]),
            ]
            start = time.monotonic()
            try:
                completed = subprocess.run(
                    cmd, capture_output=True, timeout=120, cwd=WORK
                )
                status = "ok" if completed.returncode == 0 else "failed"
                log = completed.stdout + completed.stderr
            except subprocess.TimeoutExpired as exc:
                status = "timeout"
                log = (exc.stdout or b"") + (exc.stderr or b"")
            (RESULTS / f"{key}.log").write_bytes(log)
            if status != "ok":
                save(
                    target,
                    {
                        **entry,
                        "model": name,
                        "status": status,
                        "elapsed_seconds": time.monotonic() - start,
                        "regions": [],
                    },
                )
            print(key, status, round(time.monotonic() - start, 2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "run", "worker"])
    parser.add_argument(
        "--split", choices=["development", "evaluation"], default="development"
    )
    parser.add_argument("--model", choices=["american", "paddle"])
    parser.add_argument("--page-id")
    parser.add_argument("--dpi", type=int, choices=[150, 300])
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "run":
        run(args)
    else:
        entries = json.loads((RESULTS / "manifest.json").read_text())
        entry = next(
            e for e in entries if e["page_id"] == args.page_id and e["dpi"] == args.dpi
        )
        result = infer(args.model, entry)
        key = f"{args.model}_{args.page_id}_{args.dpi}"
        overlay(result, RESULTS / f"{key}.jpg")
        save(RESULTS / f"{key}.json", result)


if __name__ == "__main__":
    main()
