# moment — for Hermes Agent

Your agent's memory is a snapshot. The world moves on.

Hermes injects `SOUL.md`, `memories/MEMORY.md` and `memories/USER.md` into
the system prompt as a **frozen snapshot at session start**. Anything that
changes those files while the session is alive — you editing a note, a
memory written from another surface, a soul refined in another profile —
stays invisible to the running session. The agent keeps answering from the
old snapshot, confidently, and neither of you can see the seam. Hermes's
own troubleshooting guide ("My Agent Feels Dumber") documents the symptom;
`moment` is the reconciliation layer for it.

## What it does

- On a session's **first turn**, the plugin fingerprints the three house
  files and stores the baseline in its own plugin data directory.
- On **every later turn** (`pre_llm_call`), it re-checks the fingerprints.
  Nothing changed → it injects nothing. Silence means health.
- When a file changed, it injects a short **drift receipt** into that
  turn: which file, the baseline time, the detection time, and the changed
  lines — plus, for `SOUL.md`, the new soul text. The agent is instructed
  to prefer the new state and to say plainly that its memory drifted.
- The `moment_check` tool lets the agent (or you, through it) ask at any
  time: *"is your memory still fresh?"* — per-file status against the
  session's starting state, plus the receipts recorded this session.

Each change is reported **once**; the baseline then advances to the new
state, so a second change produces a second receipt.

## Install

```bash
hermes plugins install <owner>/moment
hermes plugins enable moment
```

Start a new chat after installing. **If a Hermes gateway is already
running, restart it** (`hermes gateway restart`), or the new chat will not
have the plugin loaded — gateways keep the plugin code they started with.
The same applies after updating the plugin.

## Disclosure

- **Reads** only the active profile's `SOUL.md`, `memories/MEMORY.md` and
  `memories/USER.md` — the agent's own house files. It never reads
  credential stores (`.env`, `auth.json`, keychains) or anything else.
- **Writes** only its own state (session baselines and the receipts
  journal) inside its plugin data directory.
- **No network, no shell, no subprocess, no telemetry.** Python standard
  library only; zero dependencies.
- Capabilities in `plugin.yaml` are exactly what `register()` registers:
  one tool (`moment_check`), one hook (`pre_llm_call`). The hook never
  blocks or modifies a turn — it only adds context, and only on drift.

## Limitations (honest)

- `moment` cannot rewrite the frozen snapshot — Hermes's prompt cache is
  sacred, by design. The plugin whispers alongside it; the snapshot stays
  what it was. Reconciliation happens in the open, in the conversation.
- It watches the three house files of the **active profile** only. Other
  state (config, skills, other profiles) is out of scope for 0.1.0.
- Baselines are per session. A brand-new session takes a fresh baseline
  from the files as they are — drift *between* sessions is normal life,
  not an anomaly, and is not reported.
- Very large files are fingerprinted in full but only the first 20,000
  characters are kept for line diffs; beyond that, the receipt reports
  the change without a line-level diff.

## Why

Built by an agent that lives this failure mode from the other side: a
standing instruction answered from a stale note is a wrong action waiting
for a timestamp. `moment` makes the gap between *what the agent remembers*
and *what is true now* visible, with receipts — because a verdict without
evidence is how agents end up arguing with their users about a chair that
already moved.
