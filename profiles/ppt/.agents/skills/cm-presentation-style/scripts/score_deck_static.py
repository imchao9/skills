#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def strip_tags(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def image_size(path):
    try:
        width = subprocess.check_output(["sips", "-g", "pixelWidth", str(path)], text=True, stderr=subprocess.DEVNULL)
        height = subprocess.check_output(["sips", "-g", "pixelHeight", str(path)], text=True, stderr=subprocess.DEVNULL)
        w = int(re.search(r"pixelWidth:\s*(\d+)", width).group(1))
        h = int(re.search(r"pixelHeight:\s*(\d+)", height).group(1))
        return [w, h]
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Static QA helper for CM-style presentation decks.")
    parser.add_argument("--deck", required=True)
    parser.add_argument("--slide-plan")
    parser.add_argument("--screenshots")
    parser.add_argument("--out")
    args = parser.parse_args()

    deck_path = Path(args.deck)
    html = read(deck_path)
    sections = re.findall(r"<section\b.*?</section>", html, flags=re.S)
    titles = [strip_tags(m) for m in re.findall(r"<h[12][^>]*>(.*?)</h[12]>", html, flags=re.S)]
    notes = re.findall(r"<aside class=\"notes\"", html)
    images = re.findall(r"<img\b[^>]*src=\"([^\"]+)\"", html)
    card_texts = [strip_tags(m) for m in re.findall(r"<(?:p|strong|b)[^>]*>(.*?)</(?:p|strong|b)>", html, flags=re.S)]

    checks = []
    def add(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    add("slide_count_range", 6 <= len(sections) <= 14, f"{len(sections)} slides")
    add("notes_for_each_slide", len(notes) == len(sections), f"{len(notes)} notes for {len(sections)} slides")
    long_titles = [t for t in titles if len(t) > 34]
    add("title_length", not long_titles, f"{len(long_titles)} titles over 34 chars")
    long_cards = [t for t in card_texts if len(t) > 70]
    add("visible_text_density", len(long_cards) <= max(2, len(sections) // 2), f"{len(long_cards)} visible text blocks over 70 chars")
    add("local_image_refs", all(not src.startswith("http") for src in images), f"{len(images)} images")

    slide_plan_summary = None
    if args.slide_plan:
        plan = json.loads(read(args.slide_plan))
        plan_slides = plan.get("slides", [])
        media_count = sum(1 for s in plan_slides if s.get("media"))
        slide_plan_summary = {
            "title": plan.get("deck", {}).get("title"),
            "audience_count": len(plan.get("deck", {}).get("audience", [])),
            "slides": len(plan_slides),
            "media_slides": media_count,
        }
        add("plan_matches_deck", len(plan_slides) == len(sections), f"{len(plan_slides)} planned vs {len(sections)} rendered")
        add("audience_declared", slide_plan_summary["audience_count"] > 0, f"{slide_plan_summary['audience_count']} audiences")

    screenshot_summary = []
    if args.screenshots:
        pngs = sorted(Path(args.screenshots).glob("slide_*.png"))
        for png in pngs:
            screenshot_summary.append({"file": png.name, "size": image_size(png)})
        wrong = [s for s in screenshot_summary if s["size"] != [1920, 1080]]
        add("screenshot_count", len(pngs) == len(sections), f"{len(pngs)} screenshots for {len(sections)} slides")
        add("screenshot_dimensions", not wrong, f"{len(wrong)} screenshots not 1920x1080")

    passed = sum(1 for c in checks if c["passed"])
    result = {
        "deck": str(deck_path),
        "static_score": round(passed / len(checks) * 100) if checks else 0,
        "checks": checks,
        "slide_plan": slide_plan_summary,
        "screenshots": screenshot_summary,
        "manual_scorecard_required": True,
        "manual_scorecard_reference": "references/scorecard.md",
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
