MOMENT_CHECK = {
    "name": "moment_check",
    "description": (
        "Check whether this session's memory has drifted. Compares the "
        "profile's house files (SOUL.md, memories/MEMORY.md, "
        "memories/USER.md) against the fingerprints taken at this session's "
        "first turn, and returns per-file status (unchanged / changed / "
        "created / deleted / no baseline), the drift receipts recorded this "
        "session, and each file's current fingerprint. Use it when the user "
        "asks whether your memory is still fresh, or before relying on a "
        "remembered fact in a long session."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file": {
                "type": "string",
                "enum": ["SOUL.md", "MEMORY.md", "USER.md"],
                "description": "Optional: limit the report to one house file.",
            }
        },
    },
}
