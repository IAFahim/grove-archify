#!/usr/bin/env python3
"""Generate narration for Grove maps — same pipeline as two-capsules.

Speaks scripts through the ReadAloud Inflect worker, writes:
  narrate/audio/<lesson>/<clip>.wav
  narrate/manifest.json
  narrate/manifest.js   (file:// safe)

    python3 tools/gen_narration.py
    python3 tools/gen_narration.py --lesson 02 --force
    python3 tools/gen_narration.py --manifest-only
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "narrate" / "scripts"
AUDIO = ROOT / "narrate" / "audio"
MANIFEST = ROOT / "narrate" / "manifest.json"
MANIFEST_JS = ROOT / "narrate" / "manifest.js"

SOCK = Path(
    os.environ.get("READALOUD_INFLECT_SOCK")
    or Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "readaloud-inflect.sock"
)


def speak(text: str, out: Path, *, speed: float = 1.0, variation: float = 0.4, seed: int = 11) -> None:
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
    s.settimeout(240)
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


def clips_for(script: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for c in script["chapters"]:
        out.append((f"ch-{c['id']}", c["text"]))
        if c.get("deep"):
            out.append((f"ch-{c['id']}-deep", c["deep"]))
    for k, v in (script.get("nodes") or {}).items():
        if isinstance(v, str):
            out.append((f"node-{k}-short", v))
        else:
            out.append((f"node-{k}-short", v["short"]))
            if v.get("deep"):
                out.append((f"node-{k}-deep", v["deep"]))
    return out


def try_migrate(lesson: str, clip_id: str, dest: Path) -> bool:
    """Reuse older fun/serious layout if present."""
    candidates = []
    # old: audio/fun/01/node-users.wav  /  audio/fun/01/ch-intro.wav
    if clip_id.startswith("node-") and clip_id.endswith("-short"):
        nid = clip_id[len("node-") : -len("-short")]
        candidates += [
            AUDIO / "fun" / lesson / f"node-{nid}.wav",
            AUDIO / lesson / f"node-{nid}.wav",
        ]
    if clip_id.startswith("node-") and clip_id.endswith("-deep"):
        nid = clip_id[len("node-") : -len("-deep")]
        candidates += [
            AUDIO / "serious" / lesson / f"node-{nid}.wav",
        ]
    if clip_id.startswith("ch-") and not clip_id.endswith("-deep"):
        candidates += [
            AUDIO / "fun" / lesson / f"{clip_id}.wav",
            AUDIO / "serious" / lesson / f"{clip_id}.wav",
        ]
    for src in candidates:
        if src.exists() and src.stat().st_size > 44:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            return True
    return False


def gen(path: Path, *, force: bool, speed: float) -> int:
    script = json.loads(path.read_text(encoding="utf-8"))
    lesson = script["id"]
    made = 0
    for clip_id, text in clips_for(script):
        dest = AUDIO / lesson / f"{clip_id}.wav"
        if dest.exists() and not force and dest.stat().st_size > 44:
            continue
        if not force and try_migrate(lesson, clip_id, dest):
            print(f"  reuse {lesson}/{clip_id}", flush=True)
            made += 1
            continue
        print(f"  synth {lesson}/{clip_id}  ({len(text)} chars)", flush=True)
        t0 = time.time()
        speak(text, dest, speed=speed)
        print(f"    -> {dest.stat().st_size:,} bytes in {time.time() - t0:.1f}s", flush=True)
        made += 1
    return made


def build_manifest() -> dict:
    lessons = []
    for path in sorted(SCRIPTS.glob("*.json")):
        # skip legacy fun/serious folders if any remain as files only at top level
        if path.parent != SCRIPTS:
            continue
        script = json.loads(path.read_text(encoding="utf-8"))
        lesson = script["id"]

        def audio_for(clip_id: str):
            rel = f"audio/{lesson}/{clip_id}.wav"
            return rel if (ROOT / "narrate" / rel).exists() else None

        nodes = {}
        for k, v in (script.get("nodes") or {}).items():
            if isinstance(v, str):
                nodes[k] = {"short": v, "audio": audio_for(f"node-{k}-short")}
            else:
                entry = {
                    "short": v["short"],
                    "deep": v.get("deep"),
                    "audio": audio_for(f"node-{k}-short"),
                    "audioDeep": audio_for(f"node-{k}-deep") if v.get("deep") else None,
                }
                if v.get("label"):
                    entry["label"] = v["label"]
                nodes[k] = entry

        chapters = []
        for c in script["chapters"]:
            chapters.append({
                "id": c["id"],
                "title": c["title"],
                "focus": c.get("focus"),
                "text": c["text"],
                "audio": audio_for(f"ch-{c['id']}"),
            })

        lessons.append({
            "id": lesson,
            "title": script["title"],
            "blurb": script.get("blurb", ""),
            "map": script["map"],
            "chapters": chapters,
            "nodes": nodes,
        })

    return {
        "version": 2,
        "voice": "ReadAloud Inflect",
        "lessons": lessons,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lesson", default="all")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--manifest-only", action="store_true")
    args = ap.parse_args()

    paths = sorted(p for p in SCRIPTS.glob("*.json") if p.parent == SCRIPTS)
    if args.lesson != "all":
        paths = [p for p in paths if p.stem == args.lesson]

    if not args.manifest_only:
        if not SOCK.exists():
            print(f"Inflect socket missing: {SOCK}", file=sys.stderr)
            return 2
        for path in paths:
            print(f"== {path.stem} ==")
            gen(path, force=args.force, speed=args.speed)

    man = build_manifest()
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    MANIFEST_JS.write_text(
        "// Generated by tools/gen_narration.py — do not edit by hand.\n"
        "window.GROVE_NARRATE_MANIFEST = "
        + json.dumps(man, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {MANIFEST.name} + {MANIFEST_JS.name} ({len(man['lessons'])} lessons)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
