"""Filesystem tools: list, read, write, precise replace."""

from __future__ import annotations

from ..security.policy import PolicyError
from .base import ToolContext, ToolError, ToolSpec


def list_files(context: ToolContext, args: dict) -> dict:
    base = args.get("relative_path", ".")
    pattern = args.get("glob", "**/*")
    limit = min(int(args.get("max_results", 200)), 1000)
    entries = list(context.policy.iter_files(base, pattern, limit + 1))
    truncated = len(entries) > limit
    entries = entries[:limit]
    return {
        "ok": True,
        "summary": f"列出 {len(entries)} 个文件" + ("（已截断）" if truncated else ""),
        "relative_path": base,
        "glob": pattern,
        "count": len(entries),
        "truncated": truncated,
        "entries": entries,
    }


def read_file(context: ToolContext, args: dict) -> dict:
    path = args["path"]
    start = max(1, int(args.get("start_line", 1)))
    end = int(args.get("end_line", 0)) or start + 399
    end = max(start, end)
    text, target = context.policy.read_text(path, max_chars=context.config.max_read_chars * 4)
    lines = text.splitlines()
    total = len(lines)
    if total == 0:
        return {"ok": True, "summary": f"{path} 为空文件", "path": context.policy.relative(target),
                "total_lines": 0, "content": "", "start_line": start, "end_line": 0}
    if start > total:
        raise ToolError("line_out_of_range", f"起始行 {start} 超出文件总行数 {total}。")
    end = min(end, total)
    chunk = "\n".join(lines[start - 1:end])
    truncated = len(chunk) > context.config.max_read_chars
    if truncated:
        chunk = chunk[: context.config.max_read_chars] + "\n...[内容已截断]"
    return {
        "ok": True,
        "summary": f"读取 {context.policy.relative(target)} 第 {start}-{end} 行（共 {total} 行）",
        "path": context.policy.relative(target),
        "start_line": start,
        "end_line": end,
        "total_lines": total,
        "truncated": truncated,
        "content": chunk,
    }


def write_file(context: ToolContext, args: dict) -> dict:
    path = args["path"]
    content = args["content"]
    overwrite = bool(args.get("overwrite", False))
    result = context.policy.write_text_atomic(path, content, overwrite=overwrite,
                                              max_bytes=context.config.max_file_bytes)
    record = context.files.record(result, "write_file", context.step)
    record.requirement_ids = list(args.get("requirement_ids", []) or [])
    context.notify("file", f"已写入 {result['path']}", path=result["path"],
                   bytes=result["bytes"], sha256=result["sha256"], created=result["created"])
    return {
        "ok": True,
        "summary": f"写入 {result['path']}（{result['bytes']} 字节，sha256={result['sha256'][:12]}）",
        **result,
    }


def replace_in_file(context: ToolContext, args: dict) -> dict:
    path = args["path"]
    old_text = args["old_text"]
    new_text = args["new_text"]
    if not old_text:
        raise ToolError("invalid_arguments", "old_text 不能为空。")
    text, target = context.policy.read_text(path, max_chars=10_000_000)
    occurrences = text.count(old_text)
    if occurrences == 0:
        raise ToolError("not_found", f"在 {path} 中未找到 old_text，未做修改。",
                        {"path": path, "hint": "请先 read_file 获取精确文本。"})
    if occurrences > 1:
        raise ToolError("not_unique", f"old_text 在 {path} 中出现 {occurrences} 次，必须唯一匹配。",
                        {"path": path, "occurrences": occurrences})
    updated = text.replace(old_text, new_text, 1)
    result = context.policy.write_text_atomic(path, updated, overwrite=True,
                                              max_bytes=context.config.max_file_bytes)
    record = context.files.record(result, "replace_in_file", context.step)
    record.requirement_ids = list(args.get("requirement_ids", []) or [])
    context.notify("file", f"已修改 {result['path']}", path=result["path"],
                   bytes=result["bytes"], sha256=result["sha256"])
    return {
        "ok": True,
        "summary": f"修改 {result['path']}（1 处替换，sha256={result['sha256'][:12]}）",
        "replacements": 1,
        **result,
    }


SPECS = [
    ToolSpec(
        name="list_files",
        description="List files inside the output workspace. Use this before creating a project tree.",
        parameters={
            "type": "object",
            "properties": {
                "relative_path": {"type": "string", "description": "Directory relative to workspace root."},
                "glob": {"type": "string", "description": "Glob such as **/* or src/**/*.js."},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=list_files,
    ),
    ToolSpec(
        name="read_file",
        description="Read a UTF-8 text file with line ranges. Always read a file before editing it.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=read_file,
    ),
    ToolSpec(
        name="write_file",
        description="Create a text file atomically. Existing files are protected unless overwrite=true.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path using forward slashes."},
                "content": {"type": "string"},
                "overwrite": {"type": "boolean"},
                "requirement_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        handler=write_file,
    ),
    ToolSpec(
        name="replace_in_file",
        description="Replace one unique occurrence of old_text with new_text. Fails if not unique.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
                "requirement_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["path", "old_text", "new_text"],
            "additionalProperties": False,
        },
        handler=replace_in_file,
    ),
]
