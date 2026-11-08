try:
    from .schemas import MOMENT_CHECK
    from .tools import drift_whisper, moment_check
except ImportError:  # pragma: no cover - fallback if loaded as loose modules
    from schemas import MOMENT_CHECK
    from tools import drift_whisper, moment_check


def _whisper(**kwargs):
    # A memory-freshness whisper is never worth a broken turn: whatever
    # goes wrong inside the hook, the hook answers "nothing to add".
    try:
        return drift_whisper(kwargs.get("session_id") or "unknown")
    except Exception:
        return None


def register(ctx):
    # Nothing profile-specific is resolved or cached here: one Hermes
    # process can serve several profiles, so the hook and the tool
    # resolve the active profile's home and this plugin's data directory
    # fresh on every call (see tools.py).
    ctx.register_tool(
        name=MOMENT_CHECK["name"],
        toolset="moment",
        schema=MOMENT_CHECK,
        handler=moment_check,
        description=MOMENT_CHECK["description"],
    )
    ctx.register_hook("pre_llm_call", _whisper)
