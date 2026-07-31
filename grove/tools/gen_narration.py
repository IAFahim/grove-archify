#!/usr/bin/env python3
"""Generate Inflect WAVs for Grove lesson narration.

Uses the warm ReadAloud Inflect worker over a Unix socket (same protocol as ReadAloud).

  python3 grove/tools/gen_narration.py
  python3 grove/tools/gen_narration.py --track fun --lesson 01
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # grove/
SCRIPTS = ROOT / "narrate" / "scripts"
AUDIO = ROOT / "narrate" / "audio"
MANIFEST = ROOT / "narrate" / "manifest.json"
MANIFEST_JS = ROOT / "narrate" / "manifest.js"

SOCK = Path(os.environ.get("READALOUD_INFLECT_SOCK")
            or Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "readaloud-inflect.sock")


def speak(text: str, out: Path, *, speed: float = 1.0, variation: float = 0.45, seed: int = 7) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".partial.wav")
    if tmp.exists():
        tmp.unlink()
    req = {
        "text": text.strip(),
        "output": str(tmp.resolve()),
        "speed": speed,
        "variation": variation,
        "seed": seed,
    }
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(180)
    try:
        s.connect(str(SOCK))
        s.sendall((json.dumps(req) + "\n").encode("utf-8"))
        resp = s.recv(8192).decode("utf-8", errors="replace").strip()
    finally:
        s.close()
    if not resp.startswith("ok"):
        raise RuntimeError(f"Inflect failed for {out.name}: {resp}")
    if not tmp.exists() or tmp.stat().st_size < 44:
        raise RuntimeError(f"missing wav {tmp}")
    tmp.replace(out)


def load_script(track: str, lesson: str) -> dict:
    path = SCRIPTS / track / f"{lesson}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def clips_for(script: dict) -> list[tuple[str, str]]:
    """Return (clip_id, text) pairs."""
    out: list[tuple[str, str]] = []
    for ch in script["chapters"]:
        out.append((f"ch-{ch['id']}", ch["text"]))
    for nid, text in (script.get("nodes") or {}).items():
        out.append((f"node-{nid}", text))
    return out


def gen_lesson(track: str, lesson: str, *, force: bool = False, speed: float = 1.0) -> list[str]:
    script = load_script(track, lesson)
    wrote: list[str] = []
    for clip_id, text in clips_for(script):
        dest = AUDIO / track / lesson / f"{clip_id}.wav"
        if dest.exists() and not force and dest.stat().st_size > 44:
            continue
        print(f"  synth {track}/{lesson}/{clip_id} ({len(text)} chars)…", flush=True)
        t0 = time.time()
        speak(text, dest, speed=speed)
        print(f"    → {dest.stat().st_size} bytes in {time.time()-t0:.1f}s", flush=True)
        wrote.append(str(dest.relative_to(ROOT)))
    return wrote


def build_manifest() -> dict:
    lessons = []
    for track in ("fun", "serious"):
        for path in sorted((SCRIPTS / track).glob("*.json")):
            script = json.loads(path.read_text(encoding="utf-8"))
            lesson_id = path.stem
            chapters = []
            for ch in script["chapters"]:
                wav = f"audio/{track}/{lesson_id}/ch-{ch['id']}.wav"
                chapters.append({
                    "id": ch["id"],
                    "title": ch.get("title") or ch["id"],
                    "view": ch.get("view"),
                    "text": ch["text"],
                    "audio": wav if (ROOT / "narrate" / wav).exists() else None,
                })
            nodes = {}
            for nid, text in (script.get("nodes") or {}).items():
                wav = f"audio/{track}/{lesson_id}/node-{nid}.wav"
                nodes[nid] = {
                    "text": text,
                    "audio": wav if (ROOT / "narrate" / wav).exists() else None,
                }
            lessons.append({
                "track": track,
                "id": lesson_id,
                "title": script["title"],
                "map": script["map"],
                "chapters": chapters,
                "nodes": nodes,
            })
    return {
        "version": 1,
        "voice": "Inflect-Micro-v2",
        "lessons": lessons,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", choices=["fun", "serious", "all"], default="all")
    ap.add_argument("--lesson", default="all", help="01..07 or all")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--manifest-only", action="store_true")
    args = ap.parse_args()

    if not args.manifest_only and not SOCK.exists():
        print(f"Inflect socket missing: {SOCK}", file=sys.stderr)
        print("Start ReadAloud Inflect worker, or run with env READALOUD_INFLECT_* set.", file=sys.stderr)
        return 2

    tracks = ["fun", "serious"] if args.track == "all" else [args.track]
    if not args.manifest_only:
        for track in tracks:
            lessons = sorted(p.stem for p in (SCRIPTS / track).glob("*.json"))
            if args.lesson != "all":
                lessons = [args.lesson]
            for lesson in lessons:
                print(f"== {track} / {lesson} ==")
                gen_lesson(track, lesson, force=args.force, speed=args.speed)

    # always write manifest under narrate/
    # JSON for tooling; JS for file:// playback (script tags are not CORS-blocked).
    man = build_manifest()
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    MANIFEST_JS.write_text(
        "// Generated by tools/gen_narration.py — do not edit by hand.\n"
        "window.GROVE_NARRATE_MANIFEST = "
        + json.dumps(man, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {MANIFEST} + {MANIFEST_JS.name} ({len(man['lessons'])} lesson tracks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
