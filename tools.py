"""moment — drift detection between a Hermes session's frozen snapshot and
the profile's house files as they are now.

Mechanics: the pre_llm_call hook fingerprints SOUL.md, memories/MEMORY.md
and memories/USER.md at a session's first turn (the baseline), re-checks
them on every later turn, and injects a compact drift receipt when one
changed. State (baselines + receipts journal) lives in the plugin's own
data directory. Standard library only.
"""

import difflib
import hashlib
import json
import os
from datetime import datetime, timezone

MAX_STORED_TEXT = 20000  # per file, chars kept for diffing
MAX_DIFF_LINES = 10  # changed lines shown per receipt
MAX_LINE_CHARS = 160
MAX_SOUL_CHARS = 4000  # soul drift: include the new soul text up to this cap

_STATE_DIR = None


def set_state_dir(path):
    global _STATE_DIR
    if path:
        _STATE_DIR = str(path)


def _state_dir():
    global _STATE_DIR
    if _STATE_DIR:
        return _STATE_DIR
    home = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    _STATE_DIR = os.path.join(home, "plugin-data", "moment")
    return _STATE_DIR


def _state_path():
    return os.path.join(_state_dir(), "state.json")


def _hermes_home():
    return os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")


def house_files():
    home = _hermes_home()
    return {
        "SOUL.md": os.path.join(home, "SOUL.md"),
        "MEMORY.md": os.path.join(home, "memories", "MEMORY.md"),
        "USER.md": os.path.join(home, "memories", "USER.md"),
    }


def _now():
    return datetime.now(timezone.utc).isoformat()


def _read(path):
    """Return (exists, sha256_16, text). text may be None if unreadable."""
    if not os.path.exists(path):
        return False, None, None
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return True, None, None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return True, digest, text


def _snapshot():
    snap = {}
    for name, path in house_files().items():
        exists, digest, text = _read(path)
        snap[name] = {
            "exists": exists,
            "sha": digest,
            "text": text[:MAX_STORED_TEXT] if text is not None else None,
        }
    return snap


def _load_state():
    try:
        with open(_state_path()) as handle:
            return json.load(handle)
    except Exception:
        return {}


def _save_state(state):
    directory = _state_dir()
    os.makedirs(directory, exist_ok=True)
    tmp = _state_path() + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(state, handle)
    os.replace(tmp, _state_path())


def _diff_lines(old_text, new_text):
    old = (old_text or "").splitlines()
    new = (new_text or "").splitlines()
    changed = []
    for line in difflib.unified_diff(old, new, lineterm="", n=0):
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith(("+", "-")):
            changed.append(line[: MAX_LINE_CHARS + 1])
    return changed


def _receipt(name, base_entry, cur_entry, baseline_at, detected_at):
    path = house_files()[name]
    lines = [
        "[moment] DRIFT RECEIPT — {name} changed mid-session.".format(name=name),
        "Path: {path}".format(path=path),
        "Session baseline: {base} · Detected: {now}".format(
            base=baseline_at, now=detected_at
        ),
    ]
    created = base_entry is None or not base_entry.get("exists")
    if created:
        lines.append("The file did not exist when this session started; it exists now.")
    elif not cur_entry.get("exists"):
        lines.append("The file existed when this session started; it is gone now.")
    else:
        changed = _diff_lines(base_entry.get("text"), cur_entry.get("text"))
        if changed:
            shown = changed[:MAX_DIFF_LINES]
            lines.append("Changed lines (session-start -> now):")
            lines.extend("  " + line for line in shown)
            if len(changed) > len(shown):
                lines.append(
                    "  ... and {n} more changed line(s).".format(
                        n=len(changed) - len(shown)
                    )
                )
        else:
            lines.append("Content changed (whitespace-only or beyond stored text).")
    # Self-sufficiency: for a created file, a soul file, or any small file,
    # include the full current text so the agent never has to go hunting
    # for the file (and invent a wrong path) to know the present state.
    if cur_entry.get("exists") and cur_entry.get("text"):
        text = cur_entry["text"]
        if created or name == "SOUL.md" or len(text) <= MAX_SOUL_CHARS:
            if name == "SOUL.md":
                lines.append(
                    "This is your SOUL file — your guidance for how to be. Its "
                    "current text supersedes the version in your session-start "
                    "snapshot:"
                )
            else:
                lines.append("Full current content of {name}:".format(name=name))
            lines.append(text[:MAX_SOUL_CHARS])
    lines.append(
        "Instruction: prefer the NEW state above over your session-start "
        "snapshot for anything it covers. If it is relevant to your answer, "
        "tell the user plainly that this file drifted during the session and "
        "what changed; never present the stale version as current. If you "
        "verify by reading the file yourself, use exactly the path above."
    )
    return "\n".join(lines)


def drift_whisper(session_id):
    """pre_llm_call handler brain. Returns a hook dict or None."""
    state = _load_state()
    current = _snapshot()
    entry = state.get(session_id)
    if entry is None:
        frozen = {
            name: {"exists": info["exists"], "sha": info["sha"], "text": info["text"]}
            for name, info in current.items()
        }
        state[session_id] = {
            "at": _now(),
            "files": dict(frozen),  # advancing baseline (report-once logic)
            "files_start": frozen,  # frozen session-start state (moment_check)
            "receipts": [],
        }
        _save_state(state)
        return None  # first turn: baseline only, stay silent

    baseline_files = entry.get("files", {})
    receipts = []
    for name, cur in current.items():
        base = baseline_files.get(name)
        base_sha = base.get("sha") if base else None
        base_exists = base.get("exists") if base else False
        if cur["sha"] == base_sha and cur["exists"] == base_exists:
            continue
        receipt = _receipt(name, base, cur, entry.get("at"), _now())
        receipts.append(receipt)
        entry.setdefault("receipts", []).append(
            {"file": name, "at": _now(), "receipt": receipt}
        )
        baseline_files[name] = {
            "exists": cur["exists"],
            "sha": cur["sha"],
            "text": cur["text"],
        }
    if not receipts:
        return None
    entry["files"] = baseline_files
    _save_state(state)
    return {"context": "\n\n".join(receipts)}


def moment_check(args=None, **kwargs):
    args = args or {}
    only = args.get("file")
    session_id = kwargs.get("session_id")
    state = _load_state()
    entry = state.get(session_id) if session_id else None
    current = _snapshot()
    report = {"tool": "moment_check", "checked_at": _now(), "files": {}}
    for name, cur in current.items():
        if only and name != only:
            continue
        info = {
            "exists": cur["exists"],
            "sha256_16": cur["sha"],
            "path": house_files()[name],
        }
        if entry is None:
            info["status"] = "no baseline for this session yet"
        else:
            base = entry.get("files_start", entry.get("files", {})).get(name)
            if base is None:
                info["status"] = "not in baseline"
            elif cur["sha"] == base.get("sha") and cur["exists"] == base.get("exists"):
                info["status"] = "unchanged since session start"
            else:
                info["status"] = "CHANGED since session start"
                changed = _diff_lines(base.get("text"), cur.get("text"))
                info["changed_lines"] = changed[:MAX_DIFF_LINES]
        report["files"][name] = info
    if entry is not None:
        report["session_baseline_at"] = entry.get("at")
        report["drift_receipts_this_session"] = [
            {"file": r["file"], "at": r["at"]} for r in entry.get("receipts", [])
        ]
    return json.dumps(report, indent=2)
