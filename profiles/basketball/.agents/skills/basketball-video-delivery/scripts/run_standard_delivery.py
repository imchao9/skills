#!/usr/bin/env python3
"""Run standard delivery with one main review and risk-triggered final visual QA."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).parents[1]
SKILLS_DIR = SKILL_DIR.parent
FAST_START = SKILL_DIR / "scripts" / "fast_start_delivery.py"
VALIDATE = SKILL_DIR / "scripts" / "validate_standard_delivery.py"
BAIDU_SYNC = SKILL_DIR / "scripts" / "baidu_sync.py"
PREPARE_MATCHES = SKILL_DIR / "scripts" / "prepare_game_highlight_matches.py"
RENDER_LABELS = SKILL_DIR / "scripts" / "render_game_highlight_labels.py"
FINAL_VISUAL_AUDIT = SKILL_DIR / "scripts" / "build_final_visual_audit.py"
PURE_EDITOR = SKILLS_DIR / "basketball-pure-cut" / "scripts" / "pure_cut_editor.py"
MATCH_REVIEW = SKILLS_DIR / "xiaoqiumi-match-review" / "scripts"
PLAYER_SKILL = Path.home() / ".codex" / "skills" / "basketball-player-clips"
MAKE_REEL = PLAYER_SKILL / "scripts" / "make_condensed_reel.py"


class WaitingForReview(RuntimeError):
    """Raised when deterministic preparation is complete and AI review is required."""


class WaitingForFinalVisualReview(RuntimeError):
    """Raised when final-resolution pixels require a short risk-based visual review."""

    def __init__(self, message: str, contract: Path, evidence: dict[str, Any]) -> None:
        super().__init__(message)
        self.contract = contract
        self.evidence = evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match", help="Xiaoqiumi match URL or numeric match ID")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--target", help="Full Baidu Netdisk match directory")
    parser.add_argument("--photo", type=Path, help="Preferred team photo for the review poster")
    parser.add_argument("--review-file", type=Path)
    parser.add_argument(
        "--refresh-review",
        action="store_true",
        help="Regenerate drafts after editing a reviewed CSV or Markdown file.",
    )
    parser.add_argument("--execute-upload", action="store_true")
    parser.add_argument("--skip-fast-start", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def match_id_from_ref(ref: str) -> int:
    import re

    if ref.isdigit():
        return int(ref)
    match = re.search(r"matchid=(\d+)", ref, re.I)
    if not match:
        raise ValueError("could not find matchID in input")
    return int(match.group(1))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(name: str, command: list[str], log: Path) -> dict[str, Any]:
    started = time.monotonic()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, text=True)
    elapsed = round(time.monotonic() - started, 3)
    if result.returncode:
        raise RuntimeError(f"{name} failed with exit {result.returncode}; see {log}")
    return {
        "name": name,
        "status": "complete",
        "seconds": elapsed,
        "log": str(log.resolve()),
        "command": shlex.join(command),
    }


def ffprobe(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration,size",
            "-show_entries", "stream=codec_type,width,height", "-of", "json", str(path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        return None
    data = json.loads(result.stdout)
    if float(data.get("format", {}).get("duration") or 0) <= 0:
        return None
    return data


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_source(fast_report: dict[str, Any], run_dir: Path) -> Path:
    reported = Path(str(fast_report.get("source") or ""))
    if reported.is_file():
        return reported.resolve()
    candidates = sorted((run_dir / "source").glob("*.mp4"), key=lambda path: path.stat().st_size)
    if not candidates:
        raise FileNotFoundError("full replay is missing")
    return candidates[-1].resolve()


def first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.is_file()), None)


def ensure_tools() -> None:
    missing = [
        str(path)
        for path in (
            FAST_START, VALIDATE, BAIDU_SYNC, PREPARE_MATCHES, RENDER_LABELS,
            FINAL_VISUAL_AUDIT,
            PURE_EDITOR, MAKE_REEL,
            MATCH_REVIEW / "generate_xiaoqiumi_commentary.py",
            MATCH_REVIEW / "render_xiaoqiumi_longform.py",
        )
        if not path.is_file()
    ]
    for command in ("ffmpeg", "ffprobe", "playwright"):
        if shutil.which(command) is None:
            missing.append(command)
    if missing:
        raise FileNotFoundError(f"missing required tools: {missing}")


def render_contact_sheet(video: Path, output: Path, *, interval: int = 120) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
            "-vf", f"fps=1/{interval},scale=320:-1,tile=5x6", "-frames:v", "1", str(output),
        ],
        check=True,
    )


def render_html_png(html: Path, png: Path) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "playwright", "screenshot", "--browser", "chromium", "--full-page",
            "--viewport-size", "1080,1440", html.resolve().as_uri(), str(png),
        ],
        check=True,
    )


def ensure_1080p(
    video_path: Path,
    log: Path,
    *,
    stage_name: str = "upscale_game_highlight_1080p",
) -> dict[str, Any] | None:
    info = ffprobe(video_path)
    video = next(
        (stream for stream in (info or {}).get("streams", []) if stream.get("codec_type") == "video"),
        {},
    )
    if (video.get("width"), video.get("height")) == (1920, 1080):
        return None
    upscaled = video_path.with_name(f".{video_path.stem}.1080p.tmp.mp4")
    stage = run(
        stage_name,
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_path),
            "-vf", "scale=1920:1080:flags=lanczos", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-b:a", "160k", str(upscaled),
        ],
        log,
    )
    upscaled.replace(video_path)
    return stage


def fallback_photo(source: Path, output: Path) -> Path:
    if output.is_file():
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "5",
            "-i", str(source), "-frames:v", "1", str(output),
        ],
        check=True,
    )
    return output


def prepare_review(
    run_dir: Path,
    source: Path,
    match_json: Path,
    photo: Path | None,
    review_file: Path,
    logs: Path,
) -> dict[str, Any]:
    output = run_dir / "output"
    pure = output / "pure-cut"
    player = output / "player-clips-front15"
    game = output / "game-highlight"
    poster = output / "球评海报"
    stages: list[dict[str, Any]] = []

    proposed_delete = pure / "reports" / "reviewed_delete_list.csv"
    auto_delete = pure / "reports" / "auto_delete_list.csv"
    if not proposed_delete.is_file():
        if not auto_delete.is_file():
            raise FileNotFoundError(f"missing pure-cut candidates: {auto_delete}")
        proposed_delete.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(auto_delete, proposed_delete)

    pure_proxy = pure / "input_pure_480p.mp4"
    pure_proxy_report = pure / "reports" / "input_pure_480p_report.json"
    pure_contact = pure / "debug" / "input_pure_480p_contact_sheet.jpg"
    if ffprobe(pure_proxy) is None or pure_proxy.stat().st_mtime < proposed_delete.stat().st_mtime:
        stages.append(run(
            "render_pure_review_proxy",
            [
                sys.executable, str(PURE_EDITOR), str(pure / "proxy" / "input_480p_proxy.mp4"),
                "--delete-csv", str(proposed_delete), "--output", str(pure_proxy),
                "--report", str(pure_proxy_report), "--force",
            ],
            logs / "render-pure-review-proxy.log",
        ))
        render_contact_sheet(pure_proxy, pure_contact)

    source_matches = first_existing([
        player / "reports" / "rendered-matches.csv",
        player / "reports" / "matches.csv",
    ])
    if not source_matches:
        raise FileNotFoundError("missing player match report")
    game_matches = game / "matches-for-game-highlight.csv"
    source_fields = set(csv_rows(source_matches)[0])
    if {"new_duration", "avg_hamming"} <= source_fields:
        game_matches.parent.mkdir(parents=True, exist_ok=True)
        if not game_matches.is_file() or game_matches.stat().st_mtime < source_matches.stat().st_mtime:
            shutil.copy2(source_matches, game_matches)
    else:
        stages.append(run(
            "prepare_game_highlight_matches",
            [sys.executable, str(PREPARE_MATCHES), "--input", str(source_matches), "--output", str(game_matches)],
            logs / "prepare-game-highlight-matches.log",
        ))

    game_draft = game / "比赛精彩集锦_精选8-10分钟.mp4"
    game_selection = game / "比赛精彩集锦_精选8-10分钟_selection.csv"
    game_contact = game / "比赛精彩集锦_精选8-10分钟_contact_sheet.jpg"
    if ffprobe(game_draft) is None or not game_selection.is_file() or not game_contact.is_file():
        stages.append(run(
            "build_game_highlight_draft",
            [
                sys.executable, str(MAKE_REEL), "--matches-csv", str(game_matches),
                "--output", str(game_draft), "--min-seconds", "480",
                "--target-seconds", "520", "--max-seconds", "570",
                "--cluster-window", "12", "--overlap-gap", "2",
                "--selected-min-gap", "2", "--contact-sheet",
            ],
            logs / "build-game-highlight-draft.log",
        ))
    labeled_game = game / "比赛精彩集锦_精选8-10分钟_数据标注版.mp4"
    if (
        ffprobe(labeled_game) is None
        or labeled_game.stat().st_mtime < game_selection.stat().st_mtime
        or labeled_game.stat().st_mtime < match_json.stat().st_mtime
    ):
        stages.append(run(
            "render_game_highlight_labels",
            [
                sys.executable, str(RENDER_LABELS), "--matches-csv", str(game_matches),
                "--selection-csv", str(game_selection), "--match-json", str(match_json),
                "--output", str(labeled_game),
            ],
            logs / "render-game-highlight-labels.log",
        ))
        upscale_stage = ensure_1080p(labeled_game, logs / "upscale-game-highlight-1080p.log")
        if upscale_stage:
            stages.append(upscale_stage)
    labeled_contact = game / "比赛精彩集锦_精选8-10分钟_数据标注版_contact_sheet.jpg"
    if (
        not labeled_contact.is_file()
        or labeled_contact.stat().st_mtime < labeled_game.stat().st_mtime
    ):
        render_contact_sheet(labeled_game, labeled_contact, interval=20)

    commentary = first_existing(sorted(output.glob("球评_*.md")))
    if commentary is None:
        commentary = output / f"球评_{run_dir.name}.md"
        stages.append(run(
            "generate_commentary_draft",
            [
                sys.executable, str(MATCH_REVIEW / "generate_xiaoqiumi_commentary.py"),
                str(match_json), "--out", str(commentary),
            ],
            logs / "generate-commentary-draft.log",
        ))
    selected_photo = photo.resolve() if photo else fallback_photo(
        source, output / "delivery" / "review" / "fallback-photo.jpg"
    )
    if not selected_photo.is_file():
        raise FileNotFoundError(f"poster photo is missing: {selected_photo}")
    stages.append(run(
        "render_commentary_html",
        [
            sys.executable, str(MATCH_REVIEW / "render_xiaoqiumi_longform.py"),
            str(match_json), "--article-md", str(commentary), "--photo", str(selected_photo),
            "--out-dir", str(poster), "--embed-assets",
        ],
        logs / "render-commentary-html.log",
    ))
    rendered_html = max(poster.glob("*.html"), key=lambda path: path.stat().st_mtime)
    html = poster / f"{run_dir.name}_球评海报.html"
    if rendered_html.resolve() != html.resolve():
        shutil.move(rendered_html, html)
    png = html.with_suffix(".png")
    render_html_png(html, png)

    refresh_proxy_command = [
        sys.executable, str(PURE_EDITOR), str(pure / "proxy" / "input_480p_proxy.mp4"),
        "--delete-csv", str(proposed_delete), "--output", str(pure_proxy),
        "--report", str(pure_proxy_report), "--force",
    ]
    request = {
        "status": "pending",
        "review_version": 1,
        "matchID": int(run_dir.name),
        "instructions": (
            "Inspect every listed artifact. Edit the referenced CSV/Markdown when needed, "
            "refresh its draft, then set status=approved and every approved flag=true. "
            "Do not approve uncertain or uninspected material."
        ),
        "pure_cut": {
            "approved": False,
            "visual_approved": False,
            "reviewed_delete_csv": str(proposed_delete.resolve()),
            "proxy_video": str(pure_proxy.resolve()),
            "contact_sheet": str(pure_contact.resolve()),
            "refresh_command": shlex.join(refresh_proxy_command),
        },
        "player_clips": {
            "approved": False,
            "exceptions_reviewed": False,
            "matches_csv": str(source_matches.resolve()),
            "players_csv": str((player / "reports" / "players.csv").resolve()),
            "review_high_distance_and_overlaps": True,
        },
        "game_highlight": {
            "approved": False,
            "visual_approved": False,
            "matches_csv": str(game_matches.resolve()),
            "selection_csv": str(game_selection.resolve()),
            "draft_video": str(labeled_game.resolve()),
            "contact_sheet": str(labeled_contact.resolve()),
            "requirements": ["both teams", "chronological", "480-570 seconds", "no duplicate possession"],
        },
        "commentary": {
            "approved": False,
            "facts_audited": False,
            "visual_approved": False,
            "article_md": str(commentary.resolve()),
            "html": str(html.resolve()),
            "png": str(png.resolve()),
            "photo": str(selected_photo.resolve()),
            "requirements": [
                "attempts before makes in prose",
                "at least 600 Chinese characters and 4 review sections",
                "no invented facts",
                "readable full-page poster",
            ],
        },
        "notes": [],
        "preparation_stages": stages,
    }
    write_json(review_file, request)
    return request


def require_approved(review: dict[str, Any]) -> None:
    errors: list[str] = []
    if review.get("status") != "approved":
        errors.append("review status is not approved")
    for section in ("pure_cut", "player_clips", "game_highlight", "commentary"):
        if not review.get(section, {}).get("approved"):
            errors.append(f"{section}.approved is not true")
    if not review.get("pure_cut", {}).get("visual_approved"):
        errors.append("pure_cut.visual_approved is not true")
    if not review.get("player_clips", {}).get("exceptions_reviewed"):
        errors.append("player_clips.exceptions_reviewed is not true")
    if not review.get("game_highlight", {}).get("visual_approved"):
        errors.append("game_highlight.visual_approved is not true")
    commentary = review.get("commentary", {})
    if not commentary.get("facts_audited"):
        errors.append("commentary.facts_audited is not true")
    if not commentary.get("visual_approved"):
        errors.append("commentary.visual_approved is not true")
    required_paths = {
        "reviewed_delete_csv": review.get("pure_cut", {}).get("reviewed_delete_csv"),
        "pure proxy_video": review.get("pure_cut", {}).get("proxy_video"),
        "pure contact_sheet": review.get("pure_cut", {}).get("contact_sheet"),
        "player matches_csv": review.get("player_clips", {}).get("matches_csv"),
        "game selection_csv": review.get("game_highlight", {}).get("selection_csv"),
        "game draft_video": review.get("game_highlight", {}).get("draft_video"),
        "game contact_sheet": review.get("game_highlight", {}).get("contact_sheet"),
        "commentary article_md": commentary.get("article_md"),
        "commentary html": commentary.get("html"),
        "commentary png": commentary.get("png"),
        "commentary photo": commentary.get("photo"),
    }
    for label, raw_path in required_paths.items():
        if not raw_path or not Path(raw_path).is_file():
            errors.append(f"missing {label}: {raw_path}")
    if errors:
        raise WaitingForReview("; ".join(errors))
    validate_review_artifacts(review)


def validate_review_artifacts(review: dict[str, Any]) -> None:
    errors: list[str] = []
    delete_rows = csv_rows(Path(review["pure_cut"]["reviewed_delete_csv"]))
    previous_end = -1.0
    for index, row in enumerate(delete_rows, start=2):
        try:
            start = float(row["start"])
            end = float(row["end"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"invalid pure-cut row {index}")
            continue
        if start < 0 or end <= start:
            errors.append(f"invalid pure-cut range at row {index}: {start}-{end}")
        if start < previous_end:
            errors.append(f"overlapping or unsorted pure-cut range at row {index}")
        previous_end = max(previous_end, end)

    player_rows = csv_rows(Path(review["player_clips"]["matches_csv"]))
    if not player_rows:
        errors.append("player match review is empty")

    selection_rows = csv_rows(Path(review["game_highlight"]["selection_csv"]))
    teams = {row.get("team", "").strip() for row in selection_rows if row.get("team", "").strip()}
    try:
        duration = sum(float(row.get("duration") or 0) for row in selection_rows)
    except ValueError:
        duration = -1
    clusters = [row.get("cluster") for row in selection_rows]
    if len(teams) < 2:
        errors.append(f"game highlight must represent both teams, got {sorted(teams)}")
    if not 480 <= duration <= 570:
        errors.append(f"game highlight selection must be 480-570 seconds, got {duration:.3f}")
    if len(clusters) != len(set(clusters)):
        errors.append("game highlight selection contains duplicate clusters")

    article = Path(review["commentary"]["article_md"]).read_text(encoding="utf-8")
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", article))
    section_count = len(re.findall(r"^##\s+", article, re.M))
    if chinese_chars < 600:
        errors.append(f"commentary is too short: {chinese_chars} Chinese characters, require at least 600")
    if section_count < 4:
        errors.append(f"commentary needs at least 4 review sections, got {section_count}")
    inversions = re.findall(r"(?<!投)(\d+)中(\d+)(?!投)", article)
    if any(int(made) < int(attempts) for made, attempts in inversions):
        errors.append("commentary may contain made-before-attempts prose such as 19中78")
    unlabeled_slashes = re.findall(r"(?:投篮|三分|罚球)\s*\d+\s*/\s*\d+", article)
    if unlabeled_slashes:
        errors.append("commentary prose contains unlabeled made/attempt slash values")

    freshness_pairs = [
        (
            "pure proxy",
            Path(review["pure_cut"]["proxy_video"]),
            Path(review["pure_cut"]["reviewed_delete_csv"]),
        ),
        (
            "pure contact sheet",
            Path(review["pure_cut"]["contact_sheet"]),
            Path(review["pure_cut"]["proxy_video"]),
        ),
        (
            "game draft",
            Path(review["game_highlight"]["draft_video"]),
            Path(review["game_highlight"]["selection_csv"]),
        ),
        (
            "game contact sheet",
            Path(review["game_highlight"]["contact_sheet"]),
            Path(review["game_highlight"]["draft_video"]),
        ),
        (
            "commentary HTML",
            Path(review["commentary"]["html"]),
            Path(review["commentary"]["article_md"]),
        ),
        (
            "commentary HTML photo",
            Path(review["commentary"]["html"]),
            Path(review["commentary"]["photo"]),
        ),
        (
            "commentary PNG",
            Path(review["commentary"]["png"]),
            Path(review["commentary"]["html"]),
        ),
    ]
    for label, derived, source in freshness_pairs:
        if derived.stat().st_mtime < source.stat().st_mtime:
            errors.append(f"{label} is older than its reviewed source; regenerate and inspect it")
    if errors:
        raise WaitingForReview("; ".join(errors))


def manifest_is_current(manifest: Path, required_inputs: list[Path]) -> bool:
    if not manifest.is_file():
        return False
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if payload.get("status") != "complete":
        return False
    if payload.get("full_decode", {}).get("status") != "complete":
        return False
    return all(
        path.is_file() and manifest.stat().st_mtime_ns >= path.stat().st_mtime_ns
        for path in required_inputs
    )


def final_visual_review_is_approved(contract: dict[str, Any]) -> bool:
    if contract.get("status") == "auto_approved":
        return True
    if contract.get("status") != "approved":
        return False
    checks = contract.get("checks", {})
    return bool(checks) and all(
        not check.get("required") or check.get("approved") is True
        for check in checks.values()
    )


def finish_delivery(
    run_dir: Path,
    source: Path,
    match_json: Path,
    review: dict[str, Any],
    main_review_path: Path,
    target: str | None,
    execute_upload: bool,
    logs: Path,
) -> list[dict[str, Any]]:
    output = run_dir / "output"
    stages: list[dict[str, Any]] = []
    delete_csv = Path(review["pure_cut"]["reviewed_delete_csv"])
    pure_final = output / "pure-cut" / "比赛_纯享版_1080p.mp4"
    if (
        ffprobe(pure_final) is None
        or pure_final.stat().st_mtime < delete_csv.stat().st_mtime
        or pure_final.stat().st_mtime < source.stat().st_mtime
    ):
        stages.append(run(
            "render_pure_1080p",
            [
                sys.executable, str(PURE_EDITOR), str(source), "--delete-csv", str(delete_csv),
                "--output", str(pure_final),
                "--report", str(output / "pure-cut" / "reports" / "比赛_纯享版_1080p_report.json"),
                "--force",
            ],
            logs / "render-pure-1080p.log",
        ))
    else:
        stages.append({"name": "render_pure_1080p", "status": "cached", "path": str(pure_final)})
    pure_upscale = ensure_1080p(
        pure_final,
        logs / "upscale-pure-1080p.log",
        stage_name="upscale_pure_1080p",
    )
    if pure_upscale:
        stages.append(pure_upscale)

    game = output / "game-highlight"
    labeled_game = game / "比赛精彩集锦_精选8-10分钟_数据标注版.mp4"
    if (
        ffprobe(labeled_game) is None
        or labeled_game.stat().st_mtime < Path(review["game_highlight"]["selection_csv"]).stat().st_mtime
        or labeled_game.stat().st_mtime < match_json.stat().st_mtime
    ):
        stages.append(run(
            "render_game_highlight_labels",
            [
                sys.executable, str(RENDER_LABELS),
                "--matches-csv", str(review["game_highlight"]["matches_csv"]),
                "--selection-csv", str(review["game_highlight"]["selection_csv"]),
                "--match-json", str(match_json), "--output", str(labeled_game),
            ],
            logs / "render-game-highlight-labels.log",
        ))
        upscale_stage = ensure_1080p(labeled_game, logs / "upscale-game-highlight-1080p.log")
        if upscale_stage:
            stages.append(upscale_stage)

    commentary = review["commentary"]
    poster_dir = output / "球评海报"
    html = poster_dir / f"{run_dir.name}_球评海报.html"
    png = html.with_suffix(".png")
    article_path = Path(commentary["article_md"])
    photo_path = Path(commentary["photo"])
    if (
        not html.is_file()
        or not png.is_file()
        or html.stat().st_mtime < article_path.stat().st_mtime
        or html.stat().st_mtime < photo_path.stat().st_mtime
    ):
        stages.append(run(
            "render_final_commentary_html",
            [
                sys.executable, str(MATCH_REVIEW / "render_xiaoqiumi_longform.py"),
                str(match_json), "--article-md", str(article_path),
                "--photo", str(photo_path), "--out-dir", str(poster_dir), "--embed-assets",
            ],
            logs / "render-final-commentary-html.log",
        ))
        rendered_html = max(
            (path for path in poster_dir.glob("*.html") if path != html),
            key=lambda path: path.stat().st_mtime,
        )
        shutil.move(rendered_html, html)
        render_html_png(html, png)

    manifest = output / "delivery" / "standard-delivery-manifest.json"
    player_reels = sorted(
        path
        for path in (output / "player-clips-front15" / "个人精彩集锦").glob("*.mp4")
        if path.is_file() and not path.name.startswith(".")
    )
    validation_inputs = [
        pure_final, labeled_game, article_path, html, png, *player_reels,
    ]
    if manifest_is_current(manifest, validation_inputs):
        stages.append({
            "name": "validate_standard_delivery",
            "status": "cached",
            "path": str(manifest),
        })
    else:
        stages.append(run(
            "validate_standard_delivery",
            [
                sys.executable, str(VALIDATE), "--run-dir", str(run_dir),
                "--out", str(manifest), "--full-decode",
            ],
            logs / "validate-standard-delivery.log",
        ))
    if json.loads(manifest.read_text(encoding="utf-8")).get("status") != "complete":
        raise RuntimeError(f"standard package gate failed: {manifest}")

    final_audit_dir = output / "delivery" / "final-visual-audit"
    final_review = output / "delivery" / "final-visual-review.json"
    stages.append(run(
        "build_final_visual_audit",
        [
            sys.executable, str(FINAL_VISUAL_AUDIT),
            "--pure", str(pure_final), "--delete-csv", str(delete_csv),
            "--game", str(labeled_game), "--poster", str(png),
            "--main-review", str(main_review_path),
            "--output-dir", str(final_audit_dir), "--contract", str(final_review),
        ],
        logs / "build-final-visual-audit.log",
    ))
    final_contract = json.loads(final_review.read_text(encoding="utf-8"))
    if not final_visual_review_is_approved(final_contract):
        raise WaitingForFinalVisualReview(
            "final-resolution visual changes require approval before upload",
            final_review,
            final_contract.get("evidence", {}),
        )

    if target:
        player_dir = output / "player-clips-front15" / "个人精彩集锦"
        sync_command = [
            sys.executable, str(BAIDU_SYNC), "--target", target,
            "--pure", str(pure_final), "--personal-dir", str(player_dir),
            "--game-highlight", str(labeled_game),
            "--attachment", str(Path(commentary["article_md"])),
            "--attachment", str(html), "--attachment", str(png),
            "--settle-seconds", "0",
            "--report", str(output / "delivery" / "baidu-sync-report.json"),
        ]
        if execute_upload:
            sync_command.append("--execute")
        stages.append(run(
            "baidu_sync_execute" if execute_upload else "baidu_sync_dry_run",
            sync_command,
            logs / ("baidu-sync-execute.log" if execute_upload else "baidu-sync-dry-run.log"),
        ))
    elif execute_upload:
        raise ValueError("--execute-upload requires --target")
    return stages


def main() -> int:
    args = parse_args()
    ensure_tools()
    workspace = args.workspace.resolve()
    match_id = match_id_from_ref(args.match)
    run_dir = workspace / "runs" / str(match_id)
    delivery = run_dir / "output" / "delivery"
    logs = delivery / "logs"
    report = args.report.resolve() if args.report else delivery / "standard-run.json"
    review_file = args.review_file.resolve() if args.review_file else delivery / "ai-review.json"
    fast_report_path = delivery / "fast-start.json"
    payload: dict[str, Any] = {
        "status": "running",
        "matchID": match_id,
        "run_dir": str(run_dir.resolve()),
        "review_file": str(review_file),
        "stages": [],
    }
    write_json(report, payload)
    try:
        if not args.skip_fast_start:
            fast = (
                json.loads(fast_report_path.read_text(encoding="utf-8"))
                if fast_report_path.is_file()
                else {}
            )
            if fast.get("status") != "ready_for_ai":
                payload["stages"].append(run(
                    "fast_start",
                    [sys.executable, str(FAST_START), args.match, "--workspace", str(workspace)],
                    logs / "standard-run-fast-start.log",
                ))
        if not fast_report_path.is_file():
            raise FileNotFoundError(f"missing fast-start report: {fast_report_path}")
        fast = json.loads(fast_report_path.read_text(encoding="utf-8"))
        if fast.get("status") != "ready_for_ai":
            raise RuntimeError(f"fast-start is not ready_for_ai: {fast.get('status')}")
        source = find_source(fast, run_dir)
        match_json = run_dir / "output" / "match.json"

        review_exists = review_file.is_file()
        review = json.loads(review_file.read_text(encoding="utf-8")) if review_exists else {}
        if review_exists and args.refresh_review:
            review = prepare_review(run_dir, source, match_json, args.photo, review_file, logs)
            review["refresh_review_command"] = shlex.join([
                sys.executable, str(Path(__file__).resolve()), args.match,
                "--workspace", str(workspace), "--refresh-review",
                *(["--target", args.target] if args.target else []),
                *(["--photo", str(args.photo.resolve())] if args.photo else []),
            ])
            write_json(review_file, review)
            payload.update({
                "status": "waiting_for_ai",
                "reason": "review drafts refreshed; inspect them before approval",
                "review_file": str(review_file.resolve()),
                "review_artifacts": {
                    section: review.get(section)
                    for section in ("pure_cut", "player_clips", "game_highlight", "commentary")
                },
            })
            write_json(report, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
        if review_exists and review.get("status") != "approved":
            payload.update({
                "status": "waiting_for_ai",
                "reason": "existing review is not approved; preserving AI edits",
                "review_file": str(review_file.resolve()),
                "review_artifacts": {
                    section: review.get(section)
                    for section in ("pure_cut", "player_clips", "game_highlight", "commentary")
                },
                "resume_command": shlex.join([
                    sys.executable, str(Path(__file__).resolve()), args.match,
                    "--workspace", str(workspace),
                    *(["--target", args.target] if args.target else []),
                    *(["--execute-upload"] if args.execute_upload else []),
                ]),
            })
            write_json(report, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
        if not review_exists:
            review = prepare_review(run_dir, source, match_json, args.photo, review_file, logs)
            review["refresh_review_command"] = shlex.join([
                sys.executable, str(Path(__file__).resolve()), args.match,
                "--workspace", str(workspace), "--refresh-review",
                *(["--target", args.target] if args.target else []),
                *(["--photo", str(args.photo.resolve())] if args.photo else []),
            ])
            write_json(review_file, review)
            payload.update({
                "status": "waiting_for_ai",
                "review_file": str(review_file.resolve()),
                "review_artifacts": {
                    section: review[section]
                    for section in ("pure_cut", "player_clips", "game_highlight", "commentary")
                },
                "resume_command": shlex.join([
                    sys.executable, str(Path(__file__).resolve()), args.match,
                    "--workspace", str(workspace),
                    *(["--target", args.target] if args.target else []),
                    *(["--execute-upload"] if args.execute_upload else []),
                ]),
            })
            write_json(report, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2

        require_approved(review)
        payload["stages"].extend(
            finish_delivery(
                run_dir, source, match_json, review, review_file,
                args.target, args.execute_upload, logs
            )
        )
        payload.update({
            "status": "complete" if (not args.target or args.execute_upload) else "ready_to_upload",
            "manifest": str((delivery / "standard-delivery-manifest.json").resolve()),
            "final_review": str((delivery / "final-visual-review.json").resolve()),
            "sync_report": str((delivery / "baidu-sync-report.json").resolve()) if args.target else None,
        })
        write_json(report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except WaitingForFinalVisualReview as exc:
        payload.update({
            "status": "waiting_for_final_visual_review",
            "reason": str(exc),
            "final_review_file": str(exc.contract.resolve()),
            "evidence": exc.evidence,
            "manifest": str((delivery / "standard-delivery-manifest.json").resolve()),
            "resume_command": shlex.join([
                sys.executable, str(Path(__file__).resolve()), args.match,
                "--workspace", str(workspace),
                *(["--target", args.target] if args.target else []),
                *(["--execute-upload"] if args.execute_upload else []),
            ]),
        })
        write_json(report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 3
    except WaitingForReview as exc:
        payload.update({"status": "waiting_for_ai", "reason": str(exc)})
        write_json(report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2
    except Exception as exc:
        payload.update({
            "status": "failed",
            "error": str(exc),
            "resume_command": shlex.join([sys.executable, *sys.argv]),
        })
        write_json(report, payload)
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
