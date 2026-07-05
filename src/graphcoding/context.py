"""GraphContext — the agent's boot context as a graph with lifecycle.

GraphCode governs what the system IS; GraphContext governs what a fresh agent
session must KNOW, in what order. A monolithic CLAUDE.md/AGENTS.md competes
with the graph for authority and rots the same way docs do. Here, context is
nodes with status (active|done|retired), typed edges, and load rules — and a
session boot is a QUERY over that graph, not a recital of a monolith.

The context graph file is JSONL-in-markdown: any non-JSON lines (a human
header) are preserved verbatim; every line starting with '{' is a node:

    {"name": "...", "type": "rule|project|reference|user|note|skill|trigger",
     "status": "active|done|retired", "hook": "one-line recall cue",
     "load": "always" | "role=architect" | "task=frontend" | "demand",
     "cornerstone": true, "edges": [{"to": "...", "type": "..."}]}

`load` defaults to "demand". `cornerstone: true` implies always + load first.
An edge to a node that doesn't exist = a memory owed (prospective memory).
"""
from __future__ import annotations

import json
import os
import re

CTX_STATUSES = ["active", "done", "retired"]
CTX_TYPES = ["rule", "project", "reference", "user", "note", "skill", "trigger"]


class ContextGraph:
    def __init__(self, path: str):
        self.path = path
        self.header: list[str] = []
        self.nodes: dict[str, dict] = {}

    @classmethod
    def load(cls, path: str) -> "ContextGraph":
        g = cls(path)
        if os.path.exists(path):
            for line in open(path, encoding="utf-8"):
                s = line.rstrip("\n")
                if s.strip().startswith("{"):
                    d = json.loads(s)
                    g.nodes[d["name"]] = d
                elif not g.nodes:  # header = every non-node line before nodes
                    g.header.append(s)
        return g

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            for h in self.header:
                f.write(h + "\n")
            if self.header and self.header[-1].strip():
                f.write("\n")
            for name in sorted(self.nodes):
                f.write(json.dumps(self.nodes[name], ensure_ascii=False,
                                   sort_keys=True) + "\n")

    # -- ops -----------------------------------------------------------------
    def incoming(self, name: str) -> list[tuple[str, str]]:
        out = []
        for n in self.nodes.values():
            for e in n.get("edges", []):
                if e["to"] == name:
                    out.append((n["name"], e["type"]))
        return sorted(out)

    def owed(self) -> dict[str, list[str]]:
        """Edges pointing at nodes that don't exist: memories owed."""
        res: dict[str, list[str]] = {}
        for n in self.nodes.values():
            for e in n.get("edges", []):
                if e["to"] not in self.nodes:
                    res.setdefault(e["to"], []).append(n["name"])
        return res

    def search(self, terms: list[str], limit: int = 20) -> list[dict]:
        terms = [t.lower() for t in terms if t]
        scored = []
        for n in self.nodes.values():
            hay = (n["name"] + " " + n.get("hook", "")).lower()
            score = sum(2.0 if t in n["name"].lower() else 1.0
                        for t in terms if t in hay)
            if score:
                scored.append((score, n))
        scored.sort(key=lambda s: (-s[0], s[1]["name"]))
        return [n for _, n in scored[:limit]]

    # -- boot: the walker ------------------------------------------------
    def boot(self, role: str = "", task: str = "") -> str:
        """Assemble a session's starting context: a few hundred tokens of
        hooks + pointers instead of a monolith. Retired never loads."""
        live = [n for n in self.nodes.values() if n.get("status") != "retired"]

        def matches(n: dict) -> bool:
            load = n.get("load", "demand")
            if n.get("cornerstone") or load == "always":
                return True
            if load.startswith("role=") and role:
                return load[5:] == role
            if load.startswith("task=") and task:
                return load[5:] == task
            return False

        corner = sorted((n for n in live if n.get("cornerstone")),
                        key=lambda n: n["name"])
        always = sorted((n for n in live if not n.get("cornerstone")
                         and n.get("load") == "always"), key=lambda n: n["name"])
        scoped = sorted((n for n in live if not n.get("cornerstone")
                         and n.get("load", "demand") not in ("always", "demand")
                         and matches(n)), key=lambda n: n["name"])
        work = sorted((n for n in live if n.get("type") == "project"
                       and n.get("status") == "active"
                       and not n.get("cornerstone")), key=lambda n: n["name"])
        trig = sorted((n for n in live if n.get("type") == "trigger"),
                      key=lambda n: n["name"])

        out = [f"=== CONTEXT BOOT (role={role or '-'}, task={task or '-'}) ==="]

        def block(title: str, ns: list[dict]) -> None:
            if not ns:
                return
            out.append(f"-- {title} --")
            for n in ns:
                out.append(f"  {n['name']}: {n.get('hook', '')}")
        block("cornerstone (read first)", corner)
        block("always", always)
        block(f"loaded for this session", scoped)
        block("active work (the future layer)", work)
        block("triggers (load on match, not now)", trig)
        owed = self.owed()
        if owed:
            out.append(f"-- owed ({len(owed)} cited, unwritten) --")
            for t, srcs in sorted(owed.items())[:8]:
                out.append(f"  {t}  <- {len(srcs)} citation(s)")
        out.append("detail on demand: `ctx show <name>` or read <name>.md — "
                   "never rely on this summary for specifics")
        return "\n".join(out)

    # -- health ---------------------------------------------------------
    def health(self) -> str:
        live = [n for n in self.nodes.values() if n.get("status") != "retired"]
        incoming: dict[str, int] = {}
        for n in self.nodes.values():
            for e in n.get("edges", []):
                incoming[e["to"]] = incoming.get(e["to"], 0) + 1
        orphans = [n["name"] for n in live
                   if not n.get("edges") and not incoming.get(n["name"])]
        no_hook = [n["name"] for n in live if not n.get("hook")]
        done_cited = [n["name"] for n in self.nodes.values()
                      if n.get("status") in ("done", "retired")
                      and incoming.get(n["name"], 0) > 0]
        out = [f"context health: {len(self.nodes)} nodes "
               f"({sum(1 for n in self.nodes.values() if n.get('status')=='active')} active, "
               f"{sum(1 for n in self.nodes.values() if n.get('status')=='done')} done, "
               f"{sum(1 for n in self.nodes.values() if n.get('status')=='retired')} retired)"]
        if no_hook:
            out.append(f"no hook — invisible to boot ({len(no_hook)}): " + ", ".join(no_hook[:6]))
        if orphans:
            out.append(f"orphans — no relations ({len(orphans)}): " + ", ".join(orphans[:6])
                       + ("…" if len(orphans) > 6 else ""))
        owed = self.owed()
        if owed:
            out.append(f"owed — cited but unwritten ({len(owed)}): " + ", ".join(sorted(owed)[:6]))
        if done_cited:
            out.append(f"closed-but-load-bearing ({len(done_cited)}) — fine, history has edges")
        return "\n".join(out)


# -- monolith cleanser: SCAFFOLDING ONLY --------------------------------------
# Classifying a context block (constitution vs state vs procedure vs trigger)
# is SEMANTIC JUDGMENT — it is the LLM agent's job and cannot be encoded as
# patterns without silently fraudulent results on unfamiliar files. This tool
# therefore only: splits blocks, surfaces mechanical SIGNALS as hints, and
# prints the rubric. The agent running the cleanse decides each block and
# records decisions with `ctx add` / by editing the constitution file.
_DATE_RE = re.compile(r"20\d\d-\d\d")
_CAPS_STATUS_RE = re.compile(r"\b(DONE|SHELVED|RETIRED|IN-FLIGHT|BUILT|DEPLOYED|LOCKED)\b")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|.*\|")
_NUM_STEP_RE = re.compile(r"^\s*\d+[.)]\s")

RUBRIC = """RUBRIC (decide EACH block yourself — signals are hints, not verdicts):
  CONSTITUTION  statusless law, true year-round, violating it corrupts the rest
                -> stays in the monolith
  STATE         has a lifecycle (can become done/stale/superseded)
                -> ctx add <name> -t project|reference --hook "..."
  TRIGGER       'when X, load/do Y' dispatch knowledge
                -> ctx add <name> -t trigger --hook "when X -> Y"
  PROCEDURE     a verb: steps followed while doing a task
                -> move to a skill file, loaded on demand
A block can mix kinds — split it. When unsure, it is NOT constitution."""


def cleanse(md_path: str) -> str:
    """Prepare a monolith for agent-led cleansing: blocks + signals + rubric.
    Deliberately renders NO verdicts — see RUBRIC and the skill workflow."""
    text = open(md_path, encoding="utf-8").read()
    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    out = [f"=== cleanse work-order: {md_path} — {len(blocks)} blocks ===",
           "Classification is LLM work. Read each block, judge per rubric,",
           "record STATE/TRIGGER via `ctx add`, move PROCEDURE to skills,",
           "leave only CONSTITUTION in the file.", "", RUBRIC, ""]
    for i, b in enumerate(blocks, 1):
        lines = b.splitlines()
        first = next((l.strip() for l in lines if l.strip()), "")[:76]
        signals = []
        if any(_TABLE_ROW_RE.match(l) for l in lines):
            signals.append("table")
        if sum(1 for l in lines if _NUM_STEP_RE.match(l)) >= 3:
            signals.append("numbered-steps")
        if _DATE_RE.search(b):
            signals.append("dates")
        if _CAPS_STATUS_RE.search(b):
            signals.append("status-words")
        out.append(f"[{i:02d}] {first}")
        out.append(f"     signals: {', '.join(signals) or 'none'}   "
                   f"({len(lines)} lines)")
    return "\n".join(out)
