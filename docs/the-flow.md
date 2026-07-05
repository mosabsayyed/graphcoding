# The whole system on one page

Four artifacts. Two tool families. One flow. If this page isn't enough to run the method, the method is too complicated — file an issue.

## The four artifacts

| Artifact | Holds | Size discipline |
|---|---|---|
| **Constitution** (CLAUDE.md / AGENTS.md) | statusless law: identity, non-negotiables, pointers | fits on one screen, forever |
| **Context graph** (your memory index, graphed in place) | facts, decisions, references, rules — and *intentions* — each with status + relations | one JSON line per item |
| **Code graph** (`.graphcoding/graph.jsonl`) | what the system is and should become: files, systems (`db:` `mcp:` …), environments (`env:`), planned + doomed | one line per node |
| **Skills** (procedure files) | verbs: how to do X, loaded only when doing X | one file per procedure |

## The two tool families

|  | SETUP — once per repo/agent | MAINTAIN — the daily verbs |
|---|---|---|
| **Code** | `init` (scan the repo into a graph, install the gate) | `query` `show` · `plan` `link` · `sync` · `drift` |
| **Context** | `ctx cleanse` (agent-led monolith audit) + graph your memory index in place | `ctx add` · `ctx done` `ctx retire` · `ctx query` `ctx show` · `ctx boot` · `ctx health` |

Setup happens once and is allowed to be a project. Maintenance must be so cheap it's cheaper than not doing it — one verb per event, always the same verb.

## The session flow — how the pieces feed each other

```
        ┌──────────────────────────────────────────────────────────┐
        │  BOOT        ctx boot [--role --task]                    │
        │              1 who I am + the law        (constitution)  │
        │              2 what I must know now      (hooks)         │
        │              3 how I behave              (rules)         │
        │              4 what I intended           (active work)   │
        │              5 what I can do             (skills/tools,  │
        │                                          as triggers)    │
        └───────────────┬──────────────────────────────────────────┘
                        │  intent points at code
        ┌───────────────▼──────────────────────────────────────────┐
        │  HANDOFF     the moment a task touches the repo,         │
        │              GraphCode takes over:                       │
        │              status → show (blast radius) → plan →       │
        │              code → sync → drift gate                    │
        └───────────────┬──────────────────────────────────────────┘
                        │  outcomes flow BACK
        ┌───────────────▼──────────────────────────────────────────┐
        │  CLOSE       code graph clean (DRIFT=NONE), then:        │
        │              ctx done  <the intention that drove this>   │
        │              ctx add   <anything learned worth keeping>  │
        │              → the NEXT session's boot is already true   │
        └──────────────────────────────────────────────────────────┘
```

Three properties make the circle seamless rather than three separate chores:

1. **One grammar.** Context and code speak the same verbs (query/show, add/plan, done/sync, health/drift) over the same file format. Learning one half is learning both.
2. **The future is data in both.** An intention in the context graph (`status: active`) and a planned file in the code graph (`status: planned`) are the same idea at two altitudes — and each session descends from one to the other and climbs back.
3. **Truth flows in one direction per phase.** At boot, graphs feed the mind. While working, the mind feeds the graphs (sync as you go). At close, outcomes reconcile both. Nothing is ever "documented later" — later is where truth goes to die.

## The handoff rule (worth stating alone)

Context answers *"what should I be doing and what must I know?"* — then **gets out of the way**. The moment work touches code, the code graph is the only authority on structure; the agent doesn't carry context-graph impressions of the code into the edit, it queries blast radii fresh. Symmetrically, the code loop never records *why* — decisions, lessons, and closures climb back up to the context graph at CLOSE. Each graph owns its altitude; the flow is the two handoffs between them.
