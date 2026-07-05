"""Graph store — the in-repo knowledge graph.

The graph lives at .graphcoding/graph.jsonl: one JSON object per line, sorted
by node name. Sorted JSONL keeps diffs small and merges sane — a node edit
touches one line, and two branches adding different nodes rarely conflict.

Node shape:
    {
      "name":     "src/app.py"           # repo-relative path, or "path::Symbol"
      "type":     "CodeFile",            # see NODE_TYPES
      "status":   "ok",                  # ok | planned | needs-analysis | to-be-deleted
      "language": "python",
      "summary":  "One line: what this file is for.",
      "edges":    [{"to": "src/db.py", "type": "IMPORTS"}, ...]
    }

Edges are stored on the source node. Edge targets may name nodes that do not
exist yet — a link to a planned node is work to do, by design.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

NODE_TYPES = [
    "CodeFile", "CodeFunction", "CodeClass", "CodeModule",
    "Component", "Hook", "TypeDef", "ServiceDef", "ConfigFile", "Doc",
]

EDGE_TYPES = [
    "IMPORTS", "CALLS", "CONTAINS", "INHERITS", "IMPLEMENTS",
    "REFERENCES", "DEPENDS_ON", "RELATED_TO",
]

STATUSES = ["ok", "planned", "needs-analysis", "to-be-deleted"]

GRAPH_DIR = ".graphcoding"
GRAPH_FILE = "graph.jsonl"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "track_extensions": [
        ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".rb", ".java",
        ".kt", ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".swift",
        ".css", ".scss", ".sql", ".sh", ".html", ".vue", ".svelte",
        ".json", ".yaml", ".yml", ".toml", ".md",
    ],
    "ignore_segments": [
        "node_modules", ".git", ".venv", "venv", "dist", "build", "target",
        "__pycache__", ".next", ".nuxt", "coverage", "vendor", ".graphcoding",
    ],
    "ignore_tests": True,
    "scan_symbols": False,
}

# The classification is OPEN and binary: a node is either CODE (a repo-relative
# file path — scanned, drift-gated) or ANOTHER SYSTEM (any "scheme:" name —
# declared, never expected on disk). Invent whatever schemes fit your world:
# db:orders, mcp:router::search, svc:gateway, erp:sap::orders, team:payments,
# sensor:plant-7. The scheme is yours; the lifecycle and edges are the same.
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9_.+-]*:(?!//)")


def is_external(name: str, cfg: dict | None = None) -> bool:
    """True for 'scheme:...' names (non-file architecture). File paths never
    carry a scheme; URLs (scheme://) are also treated as external."""
    return bool(_SCHEME.match(name)) or "://" in name


@dataclass
class Node:
    name: str
    type: str = "CodeFile"
    status: str = "ok"
    language: str = ""
    summary: str = ""
    edges: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"name": self.name, "type": self.type, "status": self.status}
        if self.language:
            d["language"] = self.language
        if self.summary:
            d["summary"] = self.summary
        if self.edges:
            d["edges"] = sorted(self.edges, key=lambda e: (e["type"], e["to"]))
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Node":
        return cls(
            name=d["name"],
            type=d.get("type", "CodeFile"),
            status=d.get("status", "ok"),
            language=d.get("language", ""),
            summary=d.get("summary", ""),
            edges=list(d.get("edges", [])),
        )

    def add_edge(self, to: str, etype: str) -> bool:
        for e in self.edges:
            if e["to"] == to and e["type"] == etype:
                return False
        self.edges.append({"to": to, "type": etype})
        return True


class Graph:
    """The whole graph, loaded in memory; save() rewrites the sorted JSONL."""

    def __init__(self, root: str):
        self.root = root
        self.path = os.path.join(root, GRAPH_DIR, GRAPH_FILE)
        self.nodes: dict[str, Node] = {}

    # -- persistence -----------------------------------------------------
    @classmethod
    def load(cls, root: str) -> "Graph":
        g = cls(root)
        if os.path.exists(g.path):
            with open(g.path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    n = Node.from_dict(json.loads(line))
                    g.nodes[n.name] = n
        return g

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            for name in sorted(self.nodes):
                f.write(json.dumps(self.nodes[name].to_dict(),
                                   ensure_ascii=False, sort_keys=True) + "\n")

    # -- ops ---------------------------------------------------------------
    def upsert(self, node: Node) -> Node:
        existing = self.nodes.get(node.name)
        if existing:
            existing.type = node.type or existing.type
            existing.language = node.language or existing.language
            if node.summary:
                existing.summary = node.summary
            existing.status = node.status
            if node.edges:
                for e in node.edges:
                    existing.add_edge(e["to"], e["type"])
            return existing
        self.nodes[node.name] = node
        return node

    def delete(self, name: str) -> bool:
        """Remove a node and every edge pointing at it."""
        found = self.nodes.pop(name, None) is not None
        for n in self.nodes.values():
            n.edges = [e for e in n.edges if e["to"] != name]
        return found

    def incoming(self, name: str) -> list[tuple[str, str]]:
        """Who points at this node — the blast radius. [(source, edge_type)]"""
        out = []
        for n in self.nodes.values():
            for e in n.edges:
                if e["to"] == name:
                    out.append((n.name, e["type"]))
        return sorted(out)

    def file_nodes(self) -> dict[str, Node]:
        """Nodes that represent files (no ::symbol suffix)."""
        return {k: v for k, v in self.nodes.items() if "::" not in k}

    def with_status(self, status: str) -> list[Node]:
        return sorted((n for n in self.nodes.values() if n.status == status),
                      key=lambda n: n.name)

    def search(self, terms: list[str], limit: int = 20) -> list[tuple[float, Node]]:
        """Rank nodes by token overlap across name + summary. No server needed."""
        terms = [t.lower() for t in terms if t]
        scored = []
        for n in self.nodes.values():
            hay = (n.name + " " + n.summary).lower()
            score = sum(2.0 if t in n.name.lower() else 1.0
                        for t in terms if t in hay)
            if score > 0:
                scored.append((score, n))
        scored.sort(key=lambda s: (-s[0], s[1].name))
        return scored[:limit]


# -- config -----------------------------------------------------------------
def config_path(root: str) -> str:
    return os.path.join(root, GRAPH_DIR, CONFIG_FILE)


def load_config(root: str) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    p = config_path(root)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def find_root(start: str | None = None) -> str | None:
    """Walk up from start (or cwd) to the directory containing .graphcoding/."""
    d = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(d, GRAPH_DIR)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
