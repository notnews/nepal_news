#!/usr/bin/env python3
"""Story-level extraction from Nepali newspaper PDFs with salience metadata.

These are print-production PDFs with a text layer in legacy ASCII-mapped
Nepali fonts (Preeti/Kantipur family), so extraction is encoding conversion
plus layout clustering, not OCR. pdfplumber supplies per-character font
name, size, and position; npttf2utf converts each font's text to Unicode
(the mapping per embedded font is chosen empirically by valid-Devanagari
share); headlines are lines set much larger than the page's modal body
size, and a story is a headline plus the body lines below it that share
its column span, until the next headline.

Every story record carries the salience fields the layout gives us free:
headline font size, bounding box, share of page area, column span, page
number, above/below fold. In the spirit of the layout metadata kept by
Dell et al.'s American Stories pipeline.

Usage:
  python experiments/text_layer/extract.py pdfs/KPUR_2013_02_20.pdf
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import npttf2utf
import pdfplumber
from npttf2utf import FontMapper

MAP_JSON = os.path.join(os.path.dirname(npttf2utf.__file__), "map.json")
CANDIDATE_FONTS = [
    "Kantipur",
    "Preeti",
    "Sagarmatha",
    "FONTASY_HIMALI_TT",
    "PCS NEPALI",
]
HEADLINE_RATIO = 1.5  # a line this much larger than modal body size is a headline


def devanagari_share(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if "ऀ" <= c <= "ॿ") / len(letters)


def detect_mappings(pages) -> dict:
    """Choose a legacy->Unicode mapping per embedded font, empirically."""
    fm = FontMapper(MAP_JSON)
    samples = defaultdict(str)
    for page in pages:
        for ch in page.chars:
            if len(samples[ch["fontname"]]) < 400:
                samples[ch["fontname"]] += ch["text"]
    try:
        with open("/usr/share/dict/words", encoding="utf-8") as dictionary:
            english_words = {w.strip().lower() for w in dictionary if len(w) > 3}
    except FileNotFoundError:
        english_words = set()

    def looks_english(text: str) -> bool:
        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        if len(words) < 2:
            return False
        return sum(w in english_words for w in words) / len(words) >= 0.4

    mapping = {}
    for font, sample in samples.items():
        if devanagari_share(sample) > 0.5:
            mapping[font] = None  # already Unicode
            continue
        # ASCII maps to SOME Devanagari under every legacy mapping, so the
        # output score cannot identify true-Latin fonts; check the input.
        if looks_english(sample):
            mapping[font] = None
            continue
        best, best_score = None, 0.35  # below this, treat as Latin passthrough
        for cand in CANDIDATE_FONTS:
            try:
                score = devanagari_share(fm.map_to_unicode(sample, from_font=cand))
            except Exception:
                continue
            if score > best_score:
                best, best_score = cand, score
        mapping[font] = best  # None => passthrough (Helvetica, numerals)
    return mapping


def convert(fm: FontMapper, mapping: dict, font: str, text: str) -> str:
    m = mapping.get(font)
    if not m:
        return text
    try:
        return fm.map_to_unicode(text, from_font=m)
    except Exception:
        return text


def lines_from_chars(chars):
    """Group chars into visual lines per (rounded top); keep font info."""
    rows = defaultdict(list)
    for ch in chars:
        rows[round(ch["top"] / 3) * 3].append(ch)
    lines = []
    for top, chs in sorted(rows.items()):
        chs.sort(key=lambda c: c["x0"])
        sizes = [round(c["size"], 1) for c in chs]
        fonts = Counter(c["fontname"] for c in chs)
        lines.append(
            {
                "top": min(c["top"] for c in chs),
                "bottom": max(c["bottom"] for c in chs),
                "x0": min(c["x0"] for c in chs),
                "x1": max(c["x1"] for c in chs),
                "size": max(sizes),
                "font": fonts.most_common(1)[0][0],
                "chars": chs,
            }
        )
    return lines


def line_text(fm, mapping, line) -> str:
    """Convert a line's chars font-run by font-run, inserting spaces on gaps."""
    out, run, run_font, prev_x1 = [], "", None, None
    for ch in line["chars"]:
        if prev_x1 is not None and ch["x0"] - prev_x1 > ch["size"] * 0.4:
            run += " "
        if run_font is None or ch["fontname"] == run_font:
            run += ch["text"]
        else:
            out.append(convert(fm, mapping, run_font, run))
            run = ch["text"]
        run_font = ch["fontname"]
        prev_x1 = ch["x1"]
    if run:
        out.append(convert(fm, mapping, run_font, run))
    return re.sub(r"\s+", " ", "".join(out)).strip()


JUMP_RE = re.compile(
    r"(?:बाँकी\s*(?:पृष्ठ|पेज)\s*([०-९0-9]+))|(?:contd\.?\s*on\s*pg\.?\s*(\d+))",
    re.IGNORECASE,
)
FROM_RE = re.compile(
    r"(?:पृष्ठ\s*([०-९0-9]+)\s*(?:बाट|को\s*बाँकी))|(?:contd\.?\s*from\s*pg\.?\s*(\d+))",
    re.IGNORECASE,
)
NEP_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def find_jump(text, pattern):
    m = pattern.search(text)
    if not m:
        return None
    d = next(g for g in m.groups() if g)
    return int(d.translate(NEP_DIGITS))


def story_components(
    page, head_lines, body, x0, x1, htop, bottom, body_size, fm, mapping
):
    """Decompose the story region: byline, photos, captions, insets."""
    comp = {}
    byline_lines = []
    for ln in body[:2]:
        txt = line_text(fm, mapping, ln)
        marker = any(w in txt for w in ("संवाददाता", "एजेन्सी", "Post Report"))
        distinct = ln["font"] != (body[2]["font"] if len(body) > 2 else None)
        if len(txt) <= 45 and (marker or (distinct and ln is body[0])):
            byline_lines.append((ln, txt))
        else:
            break
    if byline_lines:
        comp["byline"] = {
            "text": " ".join(t for _, t in byline_lines),
            "bbox": [
                round(v, 1)
                for v in (
                    min(ln["x0"] for ln, _ in byline_lines),
                    min(ln["top"] for ln, _ in byline_lines),
                    max(ln["x1"] for ln, _ in byline_lines),
                    max(ln["bottom"] for ln, _ in byline_lines),
                )
            ],
        }
    photos = []
    for im in page.images:
        cx = (im["x0"] + im["x1"]) / 2
        cy = (im["top"] + im["bottom"]) / 2
        if x0 - 5 <= cx <= x1 + 5 and htop - 5 <= cy <= bottom + 5:
            if (im["x1"] - im["x0"]) * (im["bottom"] - im["top"]) < 400:
                continue
            photo = {
                "bbox": [
                    round(im["x0"], 1),
                    round(im["top"], 1),
                    round(im["x1"], 1),
                    round(im["bottom"], 1),
                ],
                "area_share": round(
                    (im["x1"] - im["x0"])
                    * (im["bottom"] - im["top"])
                    / (page.width * page.height),
                    4,
                ),
            }
            caps = [
                ln
                for ln in body
                if 0 <= ln["top"] - im["bottom"] < 3 * body_size
                and ln["x0"] >= im["x0"] - 15
                and ln["x1"] <= im["x1"] + 15
                and ln["size"] <= body_size
            ]
            if caps:
                photo["caption"] = {
                    "text": " ".join(line_text(fm, mapping, ln) for ln in caps),
                    "bbox": [
                        round(v, 1)
                        for v in (
                            min(ln["x0"] for ln in caps),
                            min(ln["top"] for ln in caps),
                            max(ln["x1"] for ln in caps),
                            max(ln["bottom"] for ln in caps),
                        )
                    ],
                }
            photos.append(photo)
    if photos:
        comp["photos"] = photos
    insets = []
    for rc in page.rects:
        w, h = rc["x1"] - rc["x0"], rc["bottom"] - rc["top"]
        if w < 60 or h < 40:
            continue
        cx, cy = (rc["x0"] + rc["x1"]) / 2, (rc["top"] + rc["bottom"]) / 2
        if not (x0 <= cx <= x1 and htop <= cy <= bottom):
            continue
        inside = [
            ln
            for ln in body
            if rc["x0"] - 3 <= ln["x0"]
            and ln["x1"] <= rc["x1"] + 3
            and rc["top"] - 3 <= ln["top"]
            and ln["bottom"] <= rc["bottom"] + 3
        ]
        if inside:
            insets.append(
                {
                    "bbox": [
                        round(rc["x0"], 1),
                        round(rc["top"], 1),
                        round(rc["x1"], 1),
                        round(rc["bottom"], 1),
                    ],
                    "text": " ".join(line_text(fm, mapping, ln) for ln in inside)[:300],
                }
            )
    if insets:
        comp["insets"] = insets[:4]
    return comp


def link_continuations(stories):
    """Join jump-marked stories to their continuations within an issue."""
    for st in stories:
        st["continued_to_page"] = find_jump(st["body"][-120:], JUMP_RE)
        st["continued_from_page"] = find_jump(
            st["headline"] + " " + st["body"][:120], FROM_RE
        )
    for st in stories:
        tgt = st.get("continued_to_page")
        if not tgt:
            continue
        head_tokens = set(st["headline"].split())
        best, best_ov = None, 1
        for c in stories:
            if c["page"] != tgt or c is st:
                continue
            ov = len(head_tokens & set((c["headline"] + " " + c["body"][:150]).split()))
            if c.get("continued_from_page") == st["page"]:
                ov += 3
            if ov > best_ov:
                best, best_ov = c, ov
        if best is not None:
            sid = (
                f'{st["paper"]}_{st["date"]}_p{st["page"]}_'
                f'{round(st["salience"]["bbox"][1])}'
            )
            st["story_id"] = best["story_id"] = sid
            st["part"], best["part"] = 1, 2
    return stories


def extract_issue(pdf_path: Path):
    paper, y, m, d = pdf_path.stem.split("_")
    fm = FontMapper(MAP_JSON)
    stories = []
    with pdfplumber.open(pdf_path) as pdf:
        mapping = detect_mappings(pdf.pages)
        for pageno, page in enumerate(pdf.pages, start=1):
            lines = lines_from_chars(page.chars)
            if not lines:
                continue
            body_size = statistics.mode(
                [ln["size"] for ln in lines for _ in range(len(ln["chars"]))]
            )
            heads = [
                i
                for i, ln in enumerate(lines)
                if ln["size"] >= body_size * HEADLINE_RATIO and len(ln["chars"]) >= 3
            ]
            # merge headline lines that are vertically adjacent, similar in
            # size, and horizontally overlapping (multi-line headlines)
            groups = []
            for i in heads:
                cur = lines[i]
                merged = False
                for g in groups:
                    prev = lines[g[-1]]
                    close = 0 <= cur["top"] - prev["bottom"] < cur["size"] * 0.9 or (
                        cur["top"] < prev["bottom"] and cur["top"] > prev["top"]
                    )
                    similar = abs(cur["size"] - prev["size"]) < 2
                    overlap = min(cur["x1"], prev["x1"]) - max(cur["x0"], prev["x0"])
                    if close and similar and overlap > 0.3 * (cur["x1"] - cur["x0"]):
                        g.append(i)
                        merged = True
                        break
                if not merged:
                    groups.append([i])
            for gi, g in enumerate(groups):
                head_lines = [lines[i] for i in g]
                hx0 = min(ln["x0"] for ln in head_lines)
                hx1 = max(ln["x1"] for ln in head_lines)
                htop = min(ln["top"] for ln in head_lines)
                next_top = (
                    min(lines[i]["top"] for i in groups[gi + 1])
                    if gi + 1 < len(groups)
                    else page.height
                )
                body = [
                    ln
                    for ln in lines
                    if htop < ln["top"] < next_top
                    and ln not in head_lines
                    and ln["x1"] > hx0 - 5
                    and ln["x0"] < hx1 + 5
                    and ln["size"] < body_size * HEADLINE_RATIO
                ]
                headline = " ".join(line_text(fm, mapping, ln) for ln in head_lines)
                body_text = " ".join(line_text(fm, mapping, ln) for ln in body)
                x0 = min([hx0] + [ln["x0"] for ln in body])
                x1 = max([hx1] + [ln["x1"] for ln in body])
                bottom = max([ln["bottom"] for ln in head_lines + body])
                stories.append(
                    {
                        "paper": paper,
                        "date": f"{y}-{m}-{d}",
                        "page": pageno,
                        "headline": headline,
                        "body": body_text,
                        "n_body_lines": len(body),
                        "salience": {
                            "headline_font_pt": round(
                                max(ln["size"] for ln in head_lines), 1
                            ),
                            "body_font_pt": round(body_size, 1),
                            "bbox": [round(v, 1) for v in (x0, htop, x1, bottom)],
                            "page_area_share": round(
                                (x1 - x0)
                                * (bottom - htop)
                                / (page.width * page.height),
                                4,
                            ),
                            "column_span": round((hx1 - hx0) / page.width, 3),
                            "above_fold": htop < page.height / 2,
                        },
                        "components": story_components(
                            page,
                            head_lines,
                            body,
                            x0,
                            x1,
                            htop,
                            bottom,
                            body_size,
                            fm,
                            mapping,
                        ),
                        "extraction": {
                            "engine": "pdfplumber+npttf2utf",
                            "font_mappings": {k: v for k, v in mapping.items() if v},
                            "prompt_version": None,
                            "timestamp": datetime.now(timezone.utc).isoformat(
                                timespec="seconds"
                            ),
                        },
                    }
                )
    return link_continuations(stories)


def main() -> None:
    parser = argparse.ArgumentParser(description="Nepali newspaper story extraction")
    parser.add_argument("pdfs", nargs="+")
    parser.add_argument("--out-dir", default="tmp/text-layer")
    args = parser.parse_args()
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    for p in args.pdfs:
        p = Path(p)
        stories = extract_issue(p)
        out = Path(args.out_dir) / (p.stem + "_stories.jsonl")
        with open(out, "w", encoding="utf-8") as f:
            for s in stories:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        dev = (
            statistics.mean(
                devanagari_share(s["headline"] + s["body"]) for s in stories
            )
            if stories
            else 0
        )
        print(
            f"{p.name}: {len(stories)} stories, "
            f"mean Devanagari share {dev:.2f} -> {out}"
        )


if __name__ == "__main__":
    main()
