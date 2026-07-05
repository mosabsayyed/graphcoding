# Scaling up — semantic search, embeddings, graph databases

The JSONL file + token search covers repos into the tens of thousands of files. Scale up **only when you feel a specific limit**, and keep the file as the source of truth when you do — accelerators are derived views, rebuilt from the file at will.

## The ladder

| Rung | What | When you need it |
|---|---|---|
| 0 | `graph.jsonl` + `graphcoding query` (token match) | default; most repos, forever |
| 1 | + embeddings sidecar (semantic search) | "query misses things phrased differently than the summary" |
| 2 | + graph database mirror (Neo4j etc.) | multi-hop queries, multi-repo federation, org-wide views |

**The invariant across all rungs:** the JSONL in the repo remains canonical. Embeddings and databases are caches. They can be deleted and rebuilt from the file; the file can never be rebuilt from them (they don't carry your git history, branches, or review trail).

## Rung 1 — embeddings sidecar

Token search fails when vocabulary diverges: `query login` won't find a node summarized "session issuance and refresh." Fix with an embeddings index:

- Embed `name + " " + summary` per node (this exact formula, kept identical between indexing and querying, is what makes results stable).
- Store as a sidecar keyed by a content hash of that string — **gitignored**, since it's derived and often produced by a paid API:

```
.graphcoding/embeddings.jsonl        # {"name": ..., "hash": ..., "vector": [...]}
```

- On query: embed the query, cosine-rank, blend with token scores. On sync: re-embed only nodes whose hash changed (a handful per commit — cost is effectively zero after the initial pass).

Any embedding model works; small ones (e.g. 1536-dim text-embedding class, or a local sentence-transformer for the API-averse) are plenty — you are ranking one-line summaries, not documents. This is deliberately out of the zero-dependency core; it's a ~100-line wrapper around the CLI that teams write to taste, and a reference implementation is on the roadmap.

## Rung 2 — graph database mirror

When you outgrow single-hop queries — *"every route transitively reachable from this model"*, *"orphan clusters across our 9 repos"* — mirror into a real graph engine:

```
node  -> (:GraphNode {name, type, status, language, summary})
edge  -> (a)-[:IMPORTS|CALLS|...]->(b)
```

Load is a 40-line script (JSONL → batched MERGE); refresh from CI on merge to main, per-repo namespaced (`repoA:src/...`). Then:

```cypher
// blast radius, transitive, depth 4
MATCH (n {name:'repoA:src/db/models.py'})<-[:IMPORTS|CALLS*1..4]-(caller)
RETURN DISTINCT caller.name

// cross-repo: what breaks everywhere if this API changes?
MATCH (api {name:'repoB:app/routes/auth.py'})<-[:CALLS]-(client)
RETURN client.name
```

With a vector index on the mirror (Neo4j and friends support this natively), rungs 1 and 2 merge: semantic search *and* multi-hop traversal against one live view — this is the configuration GraphCoding's parent project runs, exposed to agents as MCP tools so the model queries memory the way it queries any tool.

What stays in the repo regardless: the file, the gate, the loop. Developers and CI never depend on the database being up; it accelerates queries, it never arbitrates truth.

## Performance envelope of rung 0 (measured expectations)

- 10k nodes ≈ 3–5 MB JSONL, parse < 100 ms, `drift` over a full tree well under a second — comfortably inside pre-commit budget.
- `git ls-files`-based tracking means scan cost scales with tracked files, not repo history.
- Sorted output keeps `git diff` on the graph proportional to the *change*, not the graph.

If you hit real limits before 50k nodes, file an issue with numbers — that's a bug, not a ceiling.

## Multi-repo federation pattern

One graph per repo (each gated in its own CI), plus rung-2 mirror as the federation layer:

1. Each repo's CI pushes its JSONL to the mirror under its namespace on merge to main.
2. Cross-repo `CALLS` edges live in the **calling** repo's graph (it owns the knowledge of what it calls), target names carry the foreign namespace (`repoB:app/routes/auth.py`) and show as dangling locally — truthfully: the target is outside this graph's world. The mirror resolves them.
3. Org-wide questions (dead APIs, change-impact across teams, service coupling) become Cypher one-liners over the mirror.

Federation without the mirror also works at small scale: a script that concatenates namespaced JSONLs answers most cross-repo questions with `jq`.
