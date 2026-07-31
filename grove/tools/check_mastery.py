#!/usr/bin/env python3
"""Mastery curriculum gates for grove-archify/grove.

Writes:
  - coverage TSV (topic → lesson evidence)
  - id-consistency log
  - truth-spotcheck log (stale API strings)

Exit 0 only if all gates pass.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(
    __import__("os").environ.get(
        "GROVE_MASTERY_SCRATCH",
        "/tmp/grok-goal-b3ff9c2c7050/implementer",
    )
)
SCRATCH.mkdir(parents=True, exist_ok=True)

TEMPLATE_IDS = {
    "cdn", "lb", "api", "users", "consent", "pii", "redis", "web",
    "mobile", "edge", "warehouse", "dashboard", "features", "model",
    "queued", "planning", "executing", "reviewing", "completed",
    "approval", "blocked", "failed", "cancelled", "expired",
    "chat", "planner", "router", "retry", "tool", "external", "store",
    "trace", "user", "final",
}
FORBIDDEN_TEMPLATE_EDGE = re.compile(
    r"jwt-verification|consent-boundary|verify-jwt|cache-read-through|api-sql"
)
FORBIDDEN_STALE = [
    "GetVariables()",
    "GetVariables",
    "GraphBakingSystem<TGraph, TAuth>",
    "authentication",
    "OAuth",
    "JWT",
]
# GetVariables in deep as "not GetVariables" is OK — we allow negation phrases
STALE_OK_IF = re.compile(r"not\s+GetVariables|no\s+GetVariables|never\s+GetVariables|≠.*login|not login|not authentication", re.I)

P0_P1_TOPICS = [
    ("three_artifacts", r"GroveAuthGraph|Auth graph|\.mygraph|GraphData"),
    ("auth_authoring_not_login", r"not login|authoring — not|Auth means authoring|not authentication"),
    ("boundary_variables", r"GraphInputData|GraphOutputData|Input|Output|Local|untyped"),
    ("root_rule", r"exactly one Input|Root"),
    ("untyped_skip", r"Untyped|untyped"),
    ("one_frame", r"GraphImpl|GraphExecution|SetChunk|GetExecution"),
    ("brick_blobptr", r"BlobPtr|no edge table|NodeUnion|GraphData"),
    ("source_gen", r"ExecuteNode|source.gen|door book|partial"),
    ("push_pull", r"Execute|Calculate"),
    ("grove_state", r"GroveState"),
    ("context_blocks", r"GroveContextAuth|GroveBlockAuth|Blocks"),
    ("selectors_qualifiers", r"Selector|Qualifier|Scorer"),
    ("state_machines", r"StateSet|StateIf|StateSelect"),
    ("variants_overrides", r"variant|override"),
    ("multi_graph", r"GraphAuthoringBuffer|RemoveGraphState|GraphId"),
    ("getstate", r"GetState|GraphStateUtil"),
    ("ecs_setup", r"IGraphReference|IGraphBaking|GraphAuthoring"),
    ("custom_node", r"GroveExecutionAuth|NodeType|Init"),
    ("debug_hooks", r"NodeDebug|debug-enabled|ExecuteNodeDebug"),
]


def load_scripts():
    out = {}
    for p in sorted((ROOT / "narrate" / "scripts").glob("*.json")):
        out[p.stem] = json.loads(p.read_text())
    return out


def map_ids(html_path: Path) -> set[str]:
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    return set(re.findall(r'data-node-id="([A-Za-z0-9_\-]+)"', html))


def all_text(script: dict) -> str:
    parts = [script.get("blurb", ""), script.get("title", "")]
    for c in script.get("chapters") or []:
        parts.append(c.get("text", ""))
        parts.append(c.get("deep", "") or "")
        parts.append(c.get("title", ""))
    for n in (script.get("nodes") or {}).values():
        if isinstance(n, dict):
            parts.append(n.get("short", ""))
            parts.append(n.get("deep", "") or "")
            parts.append(n.get("label", "") or "")
        else:
            parts.append(str(n))
    return "\n".join(parts)


def gate_product_honesty(scripts) -> list[str]:
    errs = []
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    explore = (ROOT / "explore.html").read_text(encoding="utf-8")
    for bad in ("Fun track", "Serious track", "Play lesson", "leave <b>Fun</b>", "{fun,serious}"):
        if bad in index:
            errs.append(f"index still has dual-track language: {bad!r}")
    if "nodeLabel" not in explore and "n.label" not in explore:
        errs.append("explore does not use node labels in rail/caption path")
    if "Auth = authoring" not in explore and "not login" not in explore.lower():
        # index has strong glossary — explore should at least hint
        if "not login" not in index.lower():
            errs.append("no Auth=authoring framing in index/explore")
    # template residue in shipped HTML maps
    for html in ROOT.glob("0*.html"):
        text = html.read_text(encoding="utf-8", errors="ignore")
        if FORBIDDEN_TEMPLATE_EDGE.search(text):
            errs.append(f"template edge residue in {html.name}")
        ids = map_ids(html)
        bad = ids & TEMPLATE_IDS
        if bad:
            errs.append(f"template node ids in {html.name}: {sorted(bad)}")
    return errs


def gate_id_consistency(scripts) -> tuple[list[str], str]:
    lines = []
    errs = []
    for stem, script in scripts.items():
        mp = ROOT / script["map"]
        if not mp.exists():
            errs.append(f"{stem}: missing map {script['map']}")
            lines.append(f"FAIL {stem} missing map")
            continue
        mids = map_ids(mp)
        nids = set((script.get("nodes") or {}).keys())
        missing = nids - mids
        extra = mids - nids
        status = "OK" if not missing and not extra else "FAIL"
        lines.append(f"{status} {stem} script={len(nids)} map={len(mids)} missing_in_map={sorted(missing)} missing_in_script={sorted(extra)}")
        if missing or extra:
            errs.append(f"{stem}: id mismatch {missing=} {extra=}")
        # labels required
        for k, v in (script.get("nodes") or {}).items():
            if isinstance(v, dict) and not v.get("label"):
                errs.append(f"{stem}: node {k} missing label")
    log = "\n".join(lines) + "\n"
    (SCRATCH / "id-consistency.log").write_text(log, encoding="utf-8")
    return errs, log


def gate_coverage(scripts) -> tuple[list[str], str]:
    blob = "\n\n".join(f"##{k}\n{all_text(v)}" for k, v in scripts.items())
    rows = ["topic\tlesson\tevidence"]
    errs = []
    for topic, pat in P0_P1_TOPICS:
        hits = []
        for lid, sc in scripts.items():
            t = all_text(sc)
            m = re.search(pat, t, re.I)
            if m:
                hits.append((lid, m.group(0)[:80]))
        if not hits:
            errs.append(f"coverage missing topic {topic}")
            rows.append(f"{topic}\t-\tMISSING")
        else:
            lid, ev = hits[0]
            rows.append(f"{topic}\t{lid}\t{ev}")
    tsv = "\n".join(rows) + "\n"
    (SCRATCH / "grove-mastery-coverage.tsv").write_text(tsv, encoding="utf-8")
    return errs, tsv


def gate_truth(scripts) -> tuple[list[str], str]:
    lines = []
    errs = []
    for lid, sc in scripts.items():
        t = all_text(sc)
        for bad in FORBIDDEN_STALE:
            if bad not in t:
                continue
            # allow educational negation
            for m in re.finditer(re.escape(bad), t):
                window = t[max(0, m.start() - 40) : m.end() + 40]
                if STALE_OK_IF.search(window) or "not login" in window.lower() or "not authentication" in window.lower() or "≠" in window:
                    lines.append(f"OK {lid} mentions {bad!r} in negation: {window!r}")
                elif bad in ("JWT", "OAuth", "authentication") and (
                    "not" in window.lower()
                    or "never" in window.lower()
                    or "zero" in window.lower()
                    or "no oauth" in window.lower()
                    or "no jwt" in window.lower()
                    or "there is no" in window.lower()
                ):
                    lines.append(f"OK {lid} anti-pattern mention {bad!r}")
                else:
                    errs.append(f"{lid}: stale/forbidden string {bad!r} near {window!r}")
                    lines.append(f"FAIL {lid} {bad}")
    # package spot-check: GraphData fields exist
    pkg = Path("/home/i/GitHub/vex-ee-3/Library/PackageCache")
    grove = next(pkg.glob("com.bovinelabs.grove@*"), None)
    if grove and (grove / "BovineLabs.Grove/GraphData.cs").exists():
        gd = (grove / "BovineLabs.Grove/GraphData.cs").read_text(encoding="utf-8")
        for need in ("BlobPtr<ExecutionHeader> Root", "BlobArray<GraphInputData>", "NodeUnion"):
            if need in gd:
                lines.append(f"OK package GraphData has {need}")
            else:
                errs.append(f"package GraphData missing {need}")
                lines.append(f"FAIL package {need}")
    else:
        lines.append("WARN package path not found for spot-check")
    log = "\n".join(lines) + "\n"
    (SCRATCH / "truth-spotcheck.log").write_text(log, encoding="utf-8")
    return errs, log


def gate_manifest() -> list[str]:
    errs = []
    man_path = ROOT / "narrate" / "manifest.json"
    if not man_path.exists():
        return ["missing narrate/manifest.json — run gen_narration.py"]
    man = json.loads(man_path.read_text())
    scripts = {p.stem for p in (ROOT / "narrate" / "scripts").glob("*.json")}
    lids = {l["id"] for l in man.get("lessons") or []}
    if scripts - lids:
        errs.append(f"manifest missing lessons {sorted(scripts - lids)}")
    if lids - scripts:
        errs.append(f"manifest extra lessons {sorted(lids - scripts)}")
    # each node should have short
    for les in man["lessons"]:
        for k, n in (les.get("nodes") or {}).items():
            if not n.get("short"):
                errs.append(f"manifest {les['id']}.{k} missing short")
    return errs


def main() -> int:
    scripts = load_scripts()
    errs: list[str] = []
    errs += gate_product_honesty(scripts)
    e, _ = gate_id_consistency(scripts)
    errs += e
    e, _ = gate_coverage(scripts)
    errs += e
    e, _ = gate_truth(scripts)
    errs += e
    errs += gate_manifest()

    summary = SCRATCH / "mastery-gate-summary.txt"
    if errs:
        summary.write_text("FAIL\n" + "\n".join(errs) + "\n", encoding="utf-8")
        print("FAIL", len(errs), "issues")
        for e in errs[:40]:
            print(" -", e)
        return 1
    summary.write_text("PASS\n", encoding="utf-8")
    print("PASS mastery gates")
    print("wrote", SCRATCH / "grove-mastery-coverage.tsv")
    print("wrote", SCRATCH / "id-consistency.log")
    print("wrote", SCRATCH / "truth-spotcheck.log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
