"""Content search tool (regex / literal), confined and size-limited."""

from __future__ import annotations

import re

from ..security.policy import PolicyError
from .base import ToolContext, ToolError, ToolSpec


def search_in_files(context: ToolContext, args: dict) -> dict:
    pattern = args["pattern"]
    glob = args.get("glob", "**/*")
    use_regex = bool(args.get("regex", False))
    ignore_case = bool(args.get("ignore_case", True))
    max_results = min(int(args.get("max_results", 100)), 500)
    flags = re.IGNORECASE if ignore_case else 0
    try:
        compiled = re.compile(pattern if use_regex else re.escape(pattern), flags)
    except re.error as exc:
        raise ToolError("invalid_pattern", f"正则表达式无效：{exc}") from exc

    matches: list[dict] = []
    scanned = 0
    skipped = 0
    truncated = False
    for entry in context.policy.iter_files(".", glob, limit=5000):
        if context.cancel.is_set():
            break
        path = entry["path"]
        if entry["size"] > context.config.max_file_bytes:
            skipped += 1
            continue
        try:
            text, _ = context.policy.read_text(path, max_chars=2_000_000)
        except PolicyError:
            skipped += 1
            continue
        scanned += 1
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in compiled.finditer(line):
                if len(matches) >= max_results:
                    truncated = True
                    break
                matches.append({
                    "path": path,
                    "line": line_number,
                    "column": match.start() + 1,
                    "text": line.strip()[:240],
                })
            if truncated:
                break
        if truncated:
            break
    return {
        "ok": True,
        "summary": f"匹配 {len(matches)} 处（扫描 {scanned} 个文件）" + ("，结果已截断" if truncated else ""),
        "pattern": pattern,
        "glob": glob,
        "matches": matches,
        "scanned_files": scanned,
        "skipped_files": skipped,
        "truncated": truncated,
    }


SPECS = [
    ToolSpec(
        name="search_in_files",
        description="Search text across project files, returning path/line/column snippets.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "glob": {"type": "string"},
                "regex": {"type": "boolean"},
                "ignore_case": {"type": "boolean"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        handler=search_in_files,
        category="search",
    )
]
