# The GraphCoding Manifesto

## The problem is not that AI writes bad code

The problem is that AI writes code **without a durable model of the system it is changing.**

A human senior engineer carries a mental graph: *this service talks to that queue; those three handlers all assume the session object has a tenant id; deleting this helper breaks the export job nobody has touched since March.* That graph — not typing speed — is what makes them safe to let loose on a codebase.

An LLM agent has no such graph. It has a context window. Every session it re-derives a partial, slightly different model of your system from grep results and open files, acts on that model, and throws it away. The failure modes are so consistent they have names on every team that ships with agents:

- **Blind edits.** The agent changes a function's contract after reading 3 of its 14 call sites — the 3 that fit in context.
- **Drift.** Monday's plan said "split the service in three." Wednesday's code did half of it. Thursday's agent, seeing no trace of the plan, "cleans up" the half. The design now exists nowhere.
- **Amnesia.** The hard-won knowledge — *why* the retry lives in the client, *which* module is deprecated, *what* the frontend actually calls on the backend — evaporates when the session ends.
- **Confident restatement.** Asked about architecture, the agent describes what the code *probably* does. Convincingly. Sometimes correctly.

Better prompts don't fix this. Bigger context windows don't fix this — a 10M-token window still starts empty tomorrow and still can't see that an HTTP call in one repo lands on a route in another. The missing piece is not intelligence. It is **shared, persistent, enforced memory of structure and intent.**

## The move

Keep a knowledge graph of the codebase **in the repo**, and make three commitments about it:

**1. The graph is queried before code is touched.**
Not "should be." Is. Before an edit, you ask the graph what the file is for and who depends on it. The blast radius is a query result, not an impression. An agent that queries before editing is categorically safer than one that greps — because the graph returns *all* incoming edges, not the ones that happened to match a search string.

**2. The graph is written before the code is written.**
Design is not prose in a ticket; it is `planned` nodes and edges projected onto the graph. "Add invoicing" becomes: a planned `invoices.py` with a summary, an `IMPORTS` edge to `payments.py`, a planned edge from the checkout route. The plan and the codebase now live in the same coordinate system. What's left to build is a query (`status`), not a memory. A dangling edge to a node that doesn't exist yet isn't an error — it's the todo list.

**3. Code and graph move in the same commit, or the commit doesn't move.**
Every methodology dies at the moment of "I'll update the docs later." GraphCoding removes that moment: a pre-commit gate and a CI check compare the working tree to the graph, and drift blocks the commit that caused it. Sync isn't a virtue; it's a mechanical consequence.

## Why in the repo, why plain text

Because everything else has been tried and rots:

- **Wikis and architecture docs** rot because they live outside the change process. Nothing fails when they're wrong.
- **Graph databases on a server** rot differently: they're unversioned, unbranchable, invisible in review, and one more thing to run. (They're a fine *accelerator* — see [scaling](scaling.md) — but a terrible source of truth.)
- **"The code is the documentation"** is true only for structure, and only if you can hold the whole structure in your head. Code cannot document intent (*planned*, *to-be-deleted*, *why*), and it cannot document edges that no static analyzer sees.

A sorted JSONL file in the repo has none of these failure modes. It branches when the code branches. It merges line-by-line. It shows up in the PR diff, so a reviewer sees the *intended* shape of a change next to its implementation. And it costs nothing to adopt: no server, no daemon, no account.

## What the graph holds that nothing else can

A scanner can rebuild the import edges any time — those are cheap. The graph earns its keep with what **cannot be regenerated from the files**:

- **Intent**: one-line summaries in human language; `planned` nodes for what should exist; `to-be-deleted` marks for what shouldn't.
- **Invisible edges**: the frontend service that calls a backend route over HTTP. The cron job that assumes a table schema. The two modules that must change together for reasons the compiler will never know. No import statement reveals these; an engineer (or an agent, once told) records them once, and every future session inherits them.
- **Negative space**: zero incoming edges is evidence a thing is safe to delete. You cannot grep for the absence of callers.

## What GraphCoding is not

- **Not documentation.** Documentation describes; the graph *constrains*. Docs can be stale; the graph mechanically cannot.
- **Not a type system or a build graph.** Those verify what code *is*. GraphCoding also tracks what code *should become* and *should stop being* — the dimension every drift lives in.
- **Not tied to a vendor, model, or IDE.** It is a file format, a loop, and a gate. The reference CLI is ~1,000 lines of dependency-free Python. Replace any part of it and the methodology survives.

## The bet

Software teams are becoming one human directing several agents. The bottleneck of that arrangement is not code generation — it is **coherence**: keeping many fast, forgetful workers building the same system instead of five slightly different ones.

Coherence needs a shared world model that outlives every session, sits under version control with the code it describes, and is enforced rather than trusted.

That is the whole idea. The graph is the contract. Code to it.
