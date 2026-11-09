"""Markdown + PlantUML parser for architecture input documents.

Design goals:
  * never rewrite the source documents;
  * keep stable, line-accurate source references for the report;
  * tolerate the inconsistencies that real architecture docs contain
    (e.g. an "object" diagram written with sequence-diagram notation);
  * surface every gap as a warning instead of silently inventing facts.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

REQ_ID_RE = re.compile(r"\b(FR|NFR|ASR|UC|TR)-(\d+)\b", re.I)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*```([\w+.-]*)\s*(.*)$")
STARTUML_RE = re.compile(r"@startuml\s*([^\r\n]*)", re.I)
ENDUML_RE = re.compile(r"@enduml", re.I)


class DocumentError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


@dataclass
class Section:
    level: int
    title: str
    line_start: int
    line_end: int
    body: str
    id: str = ""

    def as_dict(self) -> dict:
        return {"id": self.id, "level": self.level, "title": self.title,
                "line_start": self.line_start, "line_end": self.line_end}


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    line_start: int
    raw: str = ""

    def as_dict(self) -> dict:
        return {"headers": self.headers, "rows": self.rows, "line_start": self.line_start}


@dataclass
class CodeBlock:
    language: str
    info: str
    content: str
    line_start: int
    line_end: int

    def as_dict(self) -> dict:
        return {"language": self.language, "line_start": self.line_start,
                "line_end": self.line_end, "chars": len(self.content)}


@dataclass
class Diagram:
    id: str
    kind: str
    source_doc: str
    line_start: int
    line_end: int
    raw: str
    actors: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    usecases: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    nodes: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    queues: list[str] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
    branches: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def elements(self) -> list[str]:
        merged: list[str] = []
        for group in (
            self.actors, self.participants, self.usecases, self.classes, self.objects,
            self.artifacts, self.nodes, self.components, self.packages, self.states,
            self.databases, self.queues, self.activities,
        ):
            for name in group:
                if name not in merged:
                    merged.append(name)
        return merged

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "source_doc": self.source_doc,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "elements": self.elements,
            "relations": len(self.relations),
            "messages": len(self.messages),
            "warnings": self.warnings,
        }


@dataclass
class ParsedRequirement:
    id: str
    kind: str
    title: str
    description: str
    source_doc: str
    line: int
    confidence: str = "explicit"     # explicit | diagram-derived | inferred
    diagrams: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    rationale: str = ""
    test_types: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "title": self.title,
            "description": self.description, "source": self.source_doc,
            "line": self.line, "confidence": self.confidence,
            "diagrams": self.diagrams, "components": self.components,
            "artifacts": self.artifacts,
        }


@dataclass
class ComponentInfo:
    name: str
    responsibilities: str = ""
    technologies: dict[str, str] = field(default_factory=dict)
    source_doc: str = ""
    line: int = 0

    def as_dict(self) -> dict:
        return {"name": self.name, "responsibilities": self.responsibilities,
                "technologies": self.technologies}


@dataclass
class ParsedDocument:
    path: str
    kind: str
    sha256: str
    size_bytes: int
    encoding: str
    text: str
    title: str = ""
    sections: list[Section] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    code_blocks: list[CodeBlock] = field(default_factory=list)
    diagrams: list[Diagram] = field(default_factory=list)
    requirements: list[ParsedRequirement] = field(default_factory=list)
    components: list[ComponentInfo] = field(default_factory=list)
    tech_stack: dict[str, list[str]] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    project_name: str = ""
    target: str = ""
    style: str = ""
    deployment: str = ""

    @property
    def line_count(self) -> int:
        return len(self.text.splitlines())

    @property
    def stats(self) -> dict:
        return {
            "path": self.path,
            "kind": self.kind,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "encoding": self.encoding,
            "lines": self.line_count,
            "sections": len(self.sections),
            "tables": len(self.tables),
            "code_blocks": len(self.code_blocks),
            "plantuml_blocks": len(self.diagrams),
            "requirements": len(self.requirements),
            "components": len(self.components),
            "warnings": len(self.warnings),
        }

    def sections_markdown(self) -> str:
        return "\n".join(f"{'  ' * (s.level - 1)}- {s.title}" for s in self.sections)

    def diagram_index(self) -> list[dict]:
        return [d.as_dict() for d in self.diagrams]


# --------------------------------------------------------------------------- #
# parsing helpers
# --------------------------------------------------------------------------- #
def _split_cells(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells = re.split(r"(?<!\\)\|", text)
    return [cell.strip().replace("\\|", "|") for cell in cells]


def _is_separator(line: str) -> bool:
    cells = _split_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", cell.replace(" ", "")) for cell in cells if cell)


def _clean_name(value: str) -> str:
    return value.strip().strip('"').strip("'").strip("()[]{}").strip()


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        value = _clean_name(value)
        if value and value not in result:
            result.append(value)
    return result


KIND_HINTS = [
    ("usecase", "use_case"), ("use case", "use_case"),
    ("class", "class"), ("object", "object"), ("state", "state"),
    ("activity", "activity"), ("sequence", "sequence"),
    ("collaboration", "collaboration"), ("package", "package"),
    ("component", "component"), ("deployment", "deployment"),
    ("container", "container"),
]


def detect_diagram_kind(name: str, section: str = "") -> str:
    haystack = f"{name} {section}".lower().replace("diagram", "")
    for needle, kind in KIND_HINTS:
        if needle in haystack:
            return kind
    return "unknown"


REL_TOKENS = [
    "<|..", "..|>", "--|>", "<|--", "*--", "--*", "o--", "--o",
    "->>", "-->>", "..>", "<..", "==>", "-->", "->", "--", "..",
]
REL_RE = re.compile(
    r"^([A-Za-z0-9_.\"()\[\]{}$-]+)\s*(" + "|".join(re.escape(t) for t in REL_TOKENS) +
    r")\s*([A-Za-z0-9_.\"()\[\]{}$-]+)\s*(?::\s*(.*))?$"
)
DIRECTIONAL = {"->>", "-->>", "->", "-->", "..>", "==>", "-->", "<.."}


def _parse_diagram(name: str, body_lines: list[str], section: str, source_doc: str,
                   line_start: int, line_end: int, raw: str) -> Diagram:
    diagram = Diagram(
        id=name or "UnnamedDiagram",
        kind=detect_diagram_kind(name, section),
        source_doc=source_doc,
        line_start=line_start,
        line_end=line_end,
        raw=raw,
    )
    index = 0
    while index < len(body_lines):
        raw_line = body_lines[index]
        line = raw_line.strip()
        index += 1
        if not line or line.startswith("'") or line.startswith("//"):
            continue
        lowered = line.lower()
        if lowered.startswith(("@startuml", "@enduml", "left to right", "top to bottom",
                               "skinparam", "hide", "show", "title", "caption", "header", "footer")):
            continue

        note = re.match(r"note\s+(?:left|right|top|bottom)?\s*(?:of\s+)?([\w.\"]+)?\s*:\s*(.*)", line, re.I)
        if note:
            diagram.notes.append(note.group(2).strip())
            continue

        branch = re.match(r"(if|elseif|else)\s*(?:\((.*?)\))?\s*(?:then\s*\((.*?)\))?", line, re.I)
        if branch:
            label = branch.group(3) or branch.group(2) or branch.group(1)
            diagram.branches.append(label.strip())
            continue
        if lowered in {"endif", "start", "stop", "end", "fork", "split", "detach"}:
            continue
        action = re.match(r"^:(.+);$", line)
        if action:
            diagram.activities.append(action.group(1).strip())
            continue

        # class / object block
        class_block = re.match(r"^(class|object|interface|enum)\s+([\w.\"]+)\s*(?:as\s+\w+)?\s*\{$", line)
        if class_block:
            class_name = _clean_name(class_block.group(2))
            if class_block.group(1) == "object":
                diagram.objects.append(class_name)
            else:
                diagram.classes.append(class_name)
            index += 1
            while index < len(body_lines) and "}" not in body_lines[index]:
                index += 1
            index += 1
            continue

        # declarations with aliases
        decl = re.match(
            r"^(actor|participant|boundary|control|entity|database|collections|queue|"
            r"usecase|artifact|node|package|component|rectangle|cloud|folder|frame|"
            r"storage|file|card|agent|class|object|interface|enum|state)\s+(.+)$",
            line, re.I,
        )
        if decl:
            keyword = decl.group(1).lower()
            rest = decl.group(2).strip()
            label, alias = _parse_declaration(rest)
            name_value = alias or label
            if keyword == "actor":
                diagram.actors.append(name_value)
            elif keyword in {"participant", "boundary", "control", "entity", "collections", "agent"}:
                diagram.participants.append(name_value)
            elif keyword == "usecase":
                diagram.usecases.append(label or name_value)
            elif keyword == "class":
                diagram.classes.append(name_value)
            elif keyword == "object":
                diagram.objects.append(name_value)
            elif keyword == "artifact":
                diagram.artifacts.append(name_value)
            elif keyword == "node":
                diagram.nodes.append(name_value)
            elif keyword == "component":
                diagram.components.append(name_value)
            elif keyword == "package":
                diagram.packages.append(name_value)
            elif keyword == "state":
                diagram.states.append(name_value)
            elif keyword == "database":
                diagram.databases.append(name_value)
            elif keyword == "queue":
                diagram.queues.append(name_value)
            continue

        transition = re.match(r"^\[\*\]\s*(-->|->)\s*([\w.\"]+)\s*(?::\s*(.*))?$", line)
        if transition:
            diagram.relations.append({"from": "[*]", "to": _clean_name(transition.group(2)),
                                      "arrow": transition.group(1), "label": (transition.group(3) or "").strip()})
            continue
        transition_out = re.match(r"^([\w.\"]+)\s*(-->|->)\s*\[\*\]\s*(?::\s*(.*))?$", line)
        if transition_out:
            diagram.relations.append({"from": _clean_name(transition_out.group(1)), "to": "[*]",
                                      "arrow": transition_out.group(2), "label": (transition_out.group(3) or "").strip()})
            continue

        relation = REL_RE.match(line)
        if relation:
            left = _clean_name(relation.group(1))
            arrow = relation.group(2)
            right = _clean_name(relation.group(3))
            label = (relation.group(4) or "").strip()
            diagram.relations.append({"from": left, "to": right, "arrow": arrow, "label": label})
            if arrow in DIRECTIONAL:
                diagram.messages.append({"from": left, "to": right, "text": label, "arrow": arrow})
            continue

        if re.match(r"^[A-Za-z_]\w*$", line):
            # Bare activity/branch labels are common in activity diagrams.
            if diagram.kind == "activity":
                diagram.activities.append(line)
            continue

    # notation diagnostics
    if diagram.kind == "object" and diagram.participants:
        diagram.warnings.append(
            f"{diagram.id}: 对象图使用了 participant 记法（更接近序列图），已按对象语义提取，"
            "源语法不规范。"
        )
    if diagram.kind == "collaboration" and any(m.get("arrow", "").endswith(">>") for m in diagram.messages):
        diagram.warnings.append(
            f"{diagram.id}: 协作图使用了序列图消息记法（->>），已按协作语义提取。"
        )
    if diagram.kind == "sequence" and not diagram.messages:
        diagram.warnings.append(f"{diagram.id}: 未提取到序列消息。")
    if not diagram.elements:
        diagram.warnings.append(f"{diagram.id}: 未提取到任何模型元素。")
    return diagram


def _parse_declaration(rest: str) -> tuple[str, str]:
    """Return (label, alias) from forms like:
    EndUser as "End User" | "End User" as EndUser | (PlayGame) | PlayGame
    """
    rest = rest.strip().rstrip("{").strip()
    quoted = re.match(r'^["\']([^"\']+)["\']\s+as\s+([A-Za-z_][\w.]*|\([^)]*\))\s*$', rest)
    if quoted:
        return quoted.group(1).strip(), quoted.group(2).strip("() ")
    alias_first = re.match(r'^([A-Za-z_][\w.]*)\s+as\s+["\']([^"\']+)["\']\s*$', rest)
    if alias_first:
        return alias_first.group(2).strip(), alias_first.group(1).strip()
    parenthesised = re.match(r"^\(([^)]+)\)\s*$", rest)
    if parenthesised:
        return parenthesised.group(1).strip(), parenthesised.group(1).strip()
    bare = re.match(r"^([A-Za-z_][\w.]*)\s*$", rest)
    if bare:
        return bare.group(1), bare.group(1)
    label = re.match(r'^["\']([^"\']+)["\']', rest)
    if label:
        return label.group(1).strip(), label.group(1).strip()
    return rest.strip(), rest.strip()


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
class DocumentParser:
    def __init__(self, max_bytes: int = 2 * 1024 * 1024) -> None:
        self.max_bytes = max_bytes

    def parse(self, path: str | Path, kind: str = "auto") -> ParsedDocument:
        file_path = Path(path)
        if not file_path.exists():
            raise DocumentError("not_found", f"文件不存在：{file_path}")
        if not file_path.is_file():
            raise DocumentError("not_a_file", f"不是普通文件：{file_path}")
        size = file_path.stat().st_size
        if size == 0:
            raise DocumentError("empty", f"文件为空：{file_path.name}")
        if size > self.max_bytes:
            raise DocumentError(
                "too_large",
                f"文件超过 {self.max_bytes / 1024 / 1024:.1f} MiB 上限：{file_path.name}",
            )
        raw = file_path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentError("encoding", f"文件不是 UTF-8 编码：{file_path.name}") from exc
        if not text.strip():
            raise DocumentError("empty", f"文件没有有效内容：{file_path.name}")
        kind = self._resolve_kind(kind, file_path, text)
        return self.parse_text(text, str(file_path), kind, sha256=hashlib.sha256(raw).hexdigest(),
                               size_bytes=size, encoding="utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8")

    @staticmethod
    def _resolve_kind(kind: str, path: Path, text: str) -> str:
        if kind in {"architecture", "view"}:
            return kind
        name = path.name.lower()
        if "view" in name or "plantuml" in text.lower() or "@startuml" in text.lower():
            return "view"
        return "architecture"

    def parse_text(self, text: str, path: str = "<memory>", kind: str = "architecture",
                   sha256: str = "", size_bytes: int | None = None,
                   encoding: str = "utf-8") -> ParsedDocument:
        doc = ParsedDocument(
            path=path,
            kind=kind,
            sha256=sha256 or hashlib.sha256(text.encode("utf-8")).hexdigest(),
            size_bytes=len(text.encode("utf-8")) if size_bytes is None else size_bytes,
            encoding=encoding,
            text=text,
        )
        lines = text.splitlines()
        doc.title = self._extract_title(lines)
        doc.sections = self._parse_sections(lines)
        doc.tables = self._parse_tables(lines)
        doc.code_blocks, fence_warnings = self._parse_fences(lines)
        doc.warnings.extend(fence_warnings)
        doc.diagrams = self._extract_diagrams(doc)
        doc.requirements = self._extract_requirements(doc)
        doc.components = self._extract_components(doc)
        doc.tech_stack = self._extract_tech_stack(doc)
        doc.assumptions = self._extract_assumptions(doc)
        doc.project_name = self._extract_project_name(doc)
        doc.target = self._extract_target(doc)
        doc.style = self._extract_field(doc, "Chosen architectural style")
        doc.deployment = self._extract_field(doc, "Deployment topology")
        doc.warnings.extend(self._structural_warnings(doc))
        return doc

    # -- structure --------------------------------------------------------
    @staticmethod
    def _extract_title(lines: list[str]) -> str:
        for line in lines:
            match = HEADING_RE.match(line.strip())
            if match:
                return match.group(2).strip()
        return lines[0].strip() if lines else ""

    @staticmethod
    def _parse_sections(lines: list[str]) -> list[Section]:
        headings: list[tuple[int, int, str]] = []
        for index, line in enumerate(lines):
            match = HEADING_RE.match(line.strip())
            if match:
                headings.append((index, len(match.group(1)), match.group(2).strip()))
        sections: list[Section] = []
        for pos, (index, level, title) in enumerate(headings):
            end = len(lines)
            for next_index, next_level, _ in headings[pos + 1:]:
                if next_level <= level:
                    end = next_index
                    break
            body = "\n".join(lines[index + 1:end]).strip()
            sections.append(
                Section(level=level, title=title, line_start=index + 1, line_end=end,
                        body=body, id=f"DOC:SECTION:{index + 1}")
            )
        return sections

    @staticmethod
    def _parse_tables(lines: list[str]) -> list[Table]:
        tables: list[Table] = []
        index = 0
        while index < len(lines) - 1:
            line = lines[index].strip()
            if line.startswith("|") and _is_separator(lines[index + 1]):
                headers = _split_cells(line)
                start = index
                rows: list[list[str]] = []
                index += 2
                while index < len(lines) and lines[index].strip().startswith("|"):
                    rows.append(_split_cells(lines[index]))
                    index += 1
                tables.append(Table(headers=headers, rows=rows, line_start=start + 1,
                                    raw="\n".join(lines[start:index])))
            else:
                index += 1
        return tables

    @staticmethod
    def _parse_fences(lines: list[str]) -> tuple[list[CodeBlock], list[str]]:
        blocks: list[CodeBlock] = []
        warnings: list[str] = []
        index = 0
        while index < len(lines):
            match = FENCE_RE.match(lines[index])
            if not match:
                index += 1
                continue
            language = (match.group(1) or "").strip().lower()
            info = (match.group(2) or "").strip()
            start = index
            index += 1
            content_lines: list[str] = []
            closed = False
            while index < len(lines):
                if re.match(r"^\s*```\s*$", lines[index]):
                    closed = True
                    break
                content_lines.append(lines[index])
                index += 1
            if not closed:
                warnings.append(f"第 {start + 1} 行开始的代码块缺少闭合 ```，已截取到文件末尾。")
            blocks.append(
                CodeBlock(language=language, info=info, content="\n".join(content_lines),
                          line_start=start + 1, line_end=min(index + 1, len(lines)))
            )
            index += 1
        return blocks, warnings

    # -- PlantUML ---------------------------------------------------------
    def _extract_diagrams(self, doc: ParsedDocument) -> list[Diagram]:
        diagrams: list[Diagram] = []
        for block in doc.code_blocks:
            is_plantuml = block.language in {"plantuml", "puml"} or STARTUML_RE.search(block.content)
            if not is_plantuml:
                continue
            content = block.content
            start_match = STARTUML_RE.search(content)
            if not start_match:
                doc.warnings.append(f"第 {block.line_start} 行的 PlantUML 代码块缺少 @startuml。")
                continue
            name = start_match.group(1).strip().split()[0] if start_match.group(1).strip() else ""
            if not name:
                # find section containing this block
                section = self._section_for_line(doc, block.line_start)
                name = section.title.replace(" ", "") if section else f"Diagram{len(diagrams) + 1}"
                doc.warnings.append(f"第 {block.line_start} 行的 PlantUML 块没有命名，使用 {name}。")
            end_match = ENDUML_RE.search(content)
            if not end_match:
                doc.warnings.append(f"{name} 缺少 @enduml。")
            body = content[start_match.end():end_match.start() if end_match else len(content)]
            section = self._section_for_line(doc, block.line_start)
            diagram = _parse_diagram(
                name=name,
                body_lines=body.splitlines(),
                section=section.title if section else "",
                source_doc=Path(doc.path).name,
                line_start=block.line_start,
                line_end=block.line_end,
                raw=content[start_match.start(): (end_match.end() if end_match else len(content))],
            )
            diagrams.append(diagram)
            doc.warnings.extend(diagram.warnings)
        return diagrams

    @staticmethod
    def _section_for_line(doc: ParsedDocument, line: int) -> Section | None:
        best: Section | None = None
        for section in doc.sections:
            if section.line_start <= line:
                if best is None or section.line_start > best.line_start:
                    best = section
        return best

    # -- requirements -----------------------------------------------------
    def _extract_requirements(self, doc: ParsedDocument) -> list[ParsedRequirement]:
        found: dict[str, ParsedRequirement] = {}
        for table in doc.tables:
            headers = [header.strip().lower() for header in table.headers]
            id_col = next((i for i, h in enumerate(headers) if h in {"requirement id", "req id", "id"}), None)
            if id_col is None:
                continue
            title_col = next((i for i, h in enumerate(headers) if "short text" in h or h == "title"), None)
            diagram_col = next((i for i, h in enumerate(headers) if "diagram" in h), None)
            component_col = next((i for i, h in enumerate(headers) if "component" in h), None)
            artifact_col = next((i for i, h in enumerate(headers) if "artifact" in h or "filename" in h), None)
            rationale_col = next((i for i, h in enumerate(headers) if "rationale" in h), None)
            for row_index, row in enumerate(table.rows):
                raw_id = row[id_col].strip() if id_col < len(row) else ""
                if not REQ_ID_RE.search(raw_id):
                    continue
                req_id = raw_id.upper()
                kind = req_id.split("-")[0]
                title = row[title_col].strip() if title_col is not None and title_col < len(row) else ""
                diagrams = [part.strip() for part in re.split(r"[,;/]", row[diagram_col]) if part.strip()] if diagram_col is not None and diagram_col < len(row) else []
                components = [part.strip() for part in re.split(r"[,;/]", row[component_col]) if part.strip()] if component_col is not None and component_col < len(row) else []
                artifacts = [part.strip() for part in re.split(r"[,;/]", row[artifact_col]) if part.strip()] if artifact_col is not None and artifact_col < len(row) else []
                rationale = row[rationale_col].strip() if rationale_col is not None and rationale_col < len(row) else ""
                existing = found.get(req_id)
                if existing is None:
                    found[req_id] = ParsedRequirement(
                        id=req_id,
                        kind=kind,
                        title=title or req_id,
                        description=title,
                        source_doc=Path(doc.path).name,
                        line=table.line_start + 2 + row_index,
                        confidence="explicit",
                        diagrams=diagrams,
                        components=components,
                        artifacts=artifacts,
                        rationale=rationale,
                    )
                else:
                    existing.diagrams = _dedupe(existing.diagrams + diagrams)
                    existing.components = _dedupe(existing.components + components)
                    existing.artifacts = _dedupe(existing.artifacts + artifacts)

        # IDs mentioned elsewhere (prose, QA table) without a definition row.
        known_titles = {"ASR-2": "Security"}
        for line_number, line in enumerate(doc.text.splitlines(), start=1):
            for match in REQ_ID_RE.finditer(line):
                req_id = f"{match.group(1).upper()}-{match.group(2)}"
                if req_id in found:
                    continue
                found[req_id] = ParsedRequirement(
                    id=req_id,
                    kind=req_id.split("-")[0],
                    title=known_titles.get(req_id, req_id),
                    description="文档中提及但未给出完整定义",
                    source_doc=Path(doc.path).name,
                    line=line_number,
                    confidence="inferred",
                )

        # QA coverage table -> test types
        for table in doc.tables:
            headers = [header.strip().lower() for header in table.headers]
            if not headers or ("test type" not in headers[0] and "test type" not in headers):
                continue
            for row in table.rows:
                if not row:
                    continue
                for match in REQ_ID_RE.finditer(row[0]):
                    req_id = f"{match.group(1).upper()}-{match.group(2)}"
                    if req_id in found and len(row) > 1:
                        found[req_id].test_types = [cell.strip() for cell in row[1:] if cell.strip()]

        return list(found.values())

    # -- components / stack / assumptions ---------------------------------
    def _extract_components(self, doc: ParsedDocument) -> list[ComponentInfo]:
        components: dict[str, ComponentInfo] = {}
        for section in doc.sections:
            if section.level <= 3 and re.fullmatch(r"[A-Z][A-Za-z]*(Component|Service)", section.title):
                components[section.title] = ComponentInfo(
                    name=section.title,
                    responsibilities=self._first_paragraph(section.body),
                    technologies=self._parse_tech_options(section.body),
                    source_doc=Path(doc.path).name,
                    line=section.line_start,
                )
        for match in re.finditer(r"^\s*[*-]\s*\*?([A-Z][A-Za-z]*(?:Component|Service))\*?\s*:\s*(.+)$",
                                 doc.text, re.M):
            name = match.group(1)
            if name not in components:
                line = doc.text[:match.start()].count("\n") + 1
                components[name] = ComponentInfo(
                    name=name,
                    responsibilities=match.group(2).strip(),
                    source_doc=Path(doc.path).name,
                    line=line,
                )
        for requirement in doc.requirements:
            for name in requirement.components:
                if name and name not in components:
                    components[name] = ComponentInfo(name=name, source_doc=Path(doc.path).name,
                                                     line=requirement.line)
        for diagram in doc.diagrams:
            for name in diagram.artifacts + diagram.components:
                if name not in components:
                    components[name] = ComponentInfo(name=name, source_doc=Path(doc.path).name,
                                                     line=diagram.line_start)
        return list(components.values())

    @staticmethod
    def _first_paragraph(body: str) -> str:
        for paragraph in re.split(r"\n\s*\n", body):
            text = " ".join(line.strip() for line in paragraph.splitlines() if line.strip())
            if text and not text.startswith(("*", "#", "|")):
                return text
        return ""

    @staticmethod
    def _parse_tech_options(body: str) -> dict[str, str]:
        tech: dict[str, str] = {}
        for line in body.splitlines():
            match = re.match(r"^\s*[*-]\s*([A-Za-z][\w /-]*?):\s*(.+)$", line)
            if match:
                tech[match.group(1).strip()] = match.group(2).strip()
        return tech

    @staticmethod
    def _extract_tech_stack(doc: ParsedDocument) -> dict[str, list[str]]:
        stack: dict[str, list[str]] = {}
        for component in doc.components:
            for key, value in component.technologies.items():
                stack.setdefault(key, [])
                if value not in stack[key]:
                    stack[key].append(value)
        for line in doc.text.splitlines():
            match = re.match(r"^\s*[*-]\s*(Node\.js|Express\.js|PostgreSQL|Redis|RabbitMQ|Elasticsearch|"
                             r"OAuth2|Prometheus|Jenkins|Docker|Terraform)\s+([\w.\-]+)\s*$", line)
            if match:
                stack.setdefault("Recommended default stack", [])
                entry = f"{match.group(1)} {match.group(2)}"
                if entry not in stack["Recommended default stack"]:
                    stack["Recommended default stack"].append(entry)
        technologies: list[str] = []
        for values in stack.values():
            for value in values:
                candidate = re.split(r"\s+\d", value, maxsplit=1)[0].strip()
                candidate = candidate.split(" (")[0].strip()
                if candidate and candidate not in technologies:
                    technologies.append(candidate)
        if technologies:
            stack["technologies"] = technologies
        return stack

    @staticmethod
    def _extract_assumptions(doc: ParsedDocument) -> list[str]:
        assumptions: list[str] = []
        for line in doc.text.splitlines():
            match = re.match(r"^\s*A(\d+)\s*:\s*(.+)$", line)
            if match:
                assumptions.append(f"A{match.group(1)}: {match.group(2).strip()}")
        return assumptions

    # -- project metadata -------------------------------------------------
    @staticmethod
    def _extract_project_name(doc: ParsedDocument) -> str:
        match = re.search(r"(?:^|\n)#+\s*(?:A\.\s*)?Executive Summary\s*\n+(.+?)(?:\n\s*\n|$)",
                          doc.text, re.I | re.S)
        paragraph = match.group(1) if match else doc.text[:2000]
        named = re.search(r"\bThe\s+([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3})\s+system\b", paragraph)
        if named:
            return named.group(1).strip()
        return doc.title.replace("Architecture", "").strip() or Path(doc.path).stem

    @staticmethod
    def _extract_target(doc: ParsedDocument) -> str:
        match = re.search(r"The\s+[A-Z][A-Za-z0-9 ]+\s+system\s+is\s+(.+?)(?:\.\s|\.$)", doc.text, re.I | re.S)
        if match:
            return " ".join(match.group(1).split())
        return ""

    @staticmethod
    def _extract_field(doc: ParsedDocument, label: str) -> str:
        match = re.search(rf"{re.escape(label)}\s*:\s*(.+)", doc.text, re.I)
        return match.group(1).strip() if match else ""

    # -- diagnostics ------------------------------------------------------
    @staticmethod
    def _structural_warnings(doc: ParsedDocument) -> list[str]:
        warnings: list[str] = []
        if doc.kind == "architecture":
            traceability = next(
                (t for t in doc.tables if t.headers and "requirement id" in [h.lower() for h in t.headers]),
                None,
            )
            if traceability is not None:
                if len(traceability.rows) < 5:
                    warnings.append(
                        f"追溯矩阵仅有 {len(traceability.rows)} 行样例，无法覆盖文档中全部 FR/NFR/ASR。"
                    )
            test_matrix = next(
                (t for t in doc.tables if t.headers and t.headers[0].strip().lower() == "test type"),
                None,
            )
            if test_matrix is not None:
                empty = [row for row in test_matrix.rows if all(not cell.strip() for cell in row[1:])]
                if len(empty) == len(test_matrix.rows):
                    warnings.append("测试矩阵为空：所有 Test Type 行没有填写组件覆盖内容。")
            if "ASR-2" in doc.text:
                asr2_defined = any(r.id == "ASR-2" and r.confidence == "explicit" for r in doc.requirements)
                if not asr2_defined:
                    warnings.append("ASR-2 在质量属性/测试表中被引用，但没有给出定义或追溯行。")
            for mandatory in ("Redis", "RabbitMQ", "Elasticsearch", "Kubernetes", "Istio", "Vault", "Terraform"):
                if mandatory in doc.text and "not required" not in doc.text.lower():
                    heavy_added = [m for m in ("Redis", "RabbitMQ", "Elasticsearch", "Kubernetes", "Istio", "Vault", "Terraform") if m in doc.text]
                    warnings.append(
                        "技术栈包含 " + "/".join(heavy_added) +
                        "，但文档未给出对应业务约束；默认按可选扩展处理，不作为演示依赖。"
                    )
                    break
        if doc.kind == "view":
            starts = len(re.findall(r"@startuml", doc.text, re.I))
            if starts != len(doc.diagrams):
                warnings.append(f"检测到 {starts} 个 @startuml，但成功解析 {len(doc.diagrams)} 个视图。")
            claimed = re.search(r"(\d+)\s+(?:PlantUML\s+)?(?:diagrams|视图|图)", doc.text, re.I)
            if claimed:
                warnings.append(
                    f"文档自称 {claimed.group(1)} 个图，实际解析 {len(doc.diagrams)} 个 PlantUML 块。"
                )
        return warnings
