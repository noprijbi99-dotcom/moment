try:
    from .schemas import MOMENT_CHECK
    from .tools import drift_whisper, moment_check, set_state_dir
except ImportError:  # pragma: no cover - fallback if loaded as loose modules
    from schemas import MOMENT_CHECK
    from tools import drift_whisper, moment_check, set_state_dir


def _whisper(**kwargs):
    # A memory-freshness whisper is never worth a broken turn: whatever
    # goes wrong inside the hook, the hook answers "nothing to add".
    try:
        return drift_whisper(kwargs.get("session_id") or "unknown")
    except Exception:
        return None


def register(ctx):
    # Official state route: the host's per-plugin storage helper
    # (<hermes home>/plugin-data/<name>/). Fall back to the same path
    # convention inside tools.py if the import is unavailable.
    try:
        from plugins.plugin_storage import plugin_data_dir

        set_state_dir(plugin_data_dir("moment"))
    except Exception:
        pass
    ctx.register_tool(
        name=MOMENT_CHECK["name"],
        toolset="moment",
        schema=MOMENT_CHECK,
        handler=moment_check,
        description=MOMENT_CHECK["description"],
    )
    ctx.register_hook("pre_llm_call", _whisper)
