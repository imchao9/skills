#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


JAVA_EXTENSIONS = {".java", ".kt"}
SQL_EXTENSIONS = {".xml", ".sql"}
RELEVANT_EXTENSIONS = JAVA_EXTENSIONS | SQL_EXTENSIONS
IGNORED_DIRS = {".git", ".gradle", ".idea", ".cursor", "build", "out", "target"}
CONTROL_WORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "throw",
    "new",
    "super",
    "this",
    "when",
    "try",
    "synchronized",
    "assert",
    "typeof",
    "sizeof",
}
GENERIC_METHOD_NAMES = {
    "add",
    "delete",
    "execute",
    "get",
    "getId",
    "list",
    "remove",
    "save",
    "set",
    "setId",
    "setUpdateTime",
    "toString",
    "update",
    "updateById",
}
METHOD_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
MR_URL_RE = re.compile(r"/-/merge_requests/(\d+)")
JAVA_METHOD_RE = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:public|protected|private)?\s*(?:static\s+)?"
    r"(?:final\s+)?(?:synchronized\s+)?(?:default\s+)?(?:<[^>]+>\s*)?"
    r"[\w\[\]<>?,.@]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*(?:throws\s+[^{]+)?\{"
)
KOTLIN_METHOD_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|open|override|suspend|inline|tailrec|"
    r"operator|infix|abstract|final|sealed|data|external|actual|expect)\s+)*fun\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\("
)
JAVA_METHOD_HEADER_RE = re.compile(
    r"(?:public|protected|private|static|final|synchronized|default|\s)+"
    r"(?:<[^>]+>\s*)?[\w\[\]<>?,.@]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*(?:throws\s+[^{]+)?\{"
)
KOTLIN_METHOD_HEADER_RE = re.compile(
    r"(?:(?:public|private|protected|internal|open|override|suspend|inline|tailrec|operator|infix|"
    r"abstract|final|sealed|data|external|actual|expect)\s+)*fun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\).*?\{"
)
CLASS_RE = re.compile(r"\b(class|interface|object|enum\s+class)\s+([A-Za-z_][A-Za-z0-9_]*)")
XML_BLOCK_RE = re.compile(r'<(select|insert|update|delete)\b[^>]*\bid\s*=\s*"([^"]+)"', re.IGNORECASE)
DIFF_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
NULLABILITY_GOTCHAS = [
    {
        "rule_id": "NULL-001",
        "title": "Collectors.toMap nullable value",
        "patterns": [re.compile(r"Collectors\.toMap\s*\(")],
    },
    {
        "rule_id": "NULL-002",
        "title": "Optional.get or findFirst().get",
        "patterns": [
            re.compile(r"\.findFirst\(\)\.get\(\)"),
            re.compile(r"\.findAny\(\)\.get\(\)"),
            re.compile(r"Optional<"),
        ],
    },
    {
        "rule_id": "NULL-003",
        "title": "Map.get chained call",
        "patterns": [re.compile(r"\.get\([^)]*\)\s*\.[A-Za-z_][A-Za-z0-9_]*\s*\(")],
    },
    {
        "rule_id": "NULL-004",
        "title": "Nullable collection stream",
        "patterns": [re.compile(r"\.[A-Za-z_][A-Za-z0-9_]*\(\)\.stream\(\)")],
    },
    {
        "rule_id": "NULL-005",
        "title": "Wrapper auto-unboxing",
        "patterns": [
            re.compile(r"\.(?:intValue|longValue|booleanValue|doubleValue|floatValue)\(\)"),
        ],
    },
    {
        "rule_id": "NULL-006",
        "title": "list.get(0) without emptiness check",
        "patterns": [re.compile(r"\.get\(0\)")],
    },
    {
        "rule_id": "NULL-007",
        "title": "Kotlin non-null assertion",
        "patterns": [re.compile(r"!!")],
    },
    {
        "rule_id": "NULL-008",
        "title": "Nullable method chain",
        "patterns": [re.compile(r"\.[A-Za-z_][A-Za-z0-9_]*\(\)\.[A-Za-z_][A-Za-z0-9_]*\(\)\.[A-Za-z_][A-Za-z0-9_]*\(")],
    },
    {
        "rule_id": "NULL-009",
        "title": "Stream map may emit null",
        "patterns": [re.compile(r"\.stream\(\).*?\.map\(", re.DOTALL)],
    },
    {
        "rule_id": "NULL-010",
        "title": "BeanUtils.copyProperties nullable source",
        "patterns": [re.compile(r"BeanUtils\.copyProperties\s*\(")],
    },
]


class CommandError(RuntimeError):
    pass


@dataclass
class Symbol:
    name: str
    kind: str
    rel_path: str
    start_line: int
    end_line: int
    language: str
    signature: str
    enclosing_class: Optional[str] = None

    def to_dict(self, root: Path) -> dict:
        path = root / self.rel_path
        return {
            "name": self.name,
            "kind": self.kind,
            "path": self.rel_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "signature": self.signature,
            "enclosing_class": self.enclosing_class,
            "snippet": read_snippet(path, self.start_line, self.end_line),
        }


def run(cmd: Sequence[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            list(cmd),
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        binary = cmd[0] if cmd else "<unknown>"
        hint = {
            "glab": "缺少命令 glab。MR 模式依赖 GitLab CLI，请先安装并完成 `glab auth login`，或者改用 `--base` / `--head` 进行本地 commit range 审查。",
            "git": "缺少命令 git。请先安装 Git 并确保它在 PATH 中。",
        }.get(binary, f"缺少命令 {binary}。请先安装并确保它在 PATH 中。")
        raise CommandError(hint) from exc
    if check and result.returncode != 0:
        raise CommandError(f"{' '.join(cmd)} failed: {result.stderr.strip()}")
    return result


def read_snippet(path: Path, start_line: int, end_line: int) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(start_line - 1, 0)
    end = min(end_line, len(lines))
    return "\n".join(lines[start:end])


def repo_root(start: Path) -> Path:
    return Path(run(["git", "rev-parse", "--show-toplevel"], start).stdout.strip())


def current_branch(root: Path) -> str:
    return run(["git", "branch", "--show-current"], root).stdout.strip()


def repo_identity(root: Path) -> dict:
    remote = run(["git", "config", "--get", "remote.origin.url"], root, check=False).stdout.strip()
    repo_key = remote or str(root)
    repo_label = root.name
    return {
        "key": repo_key,
        "label": repo_label,
        "remote_url": remote or None,
    }


def parse_mr_token(token: str) -> str:
    if token.isdigit():
        return token
    match = MR_URL_RE.search(token)
    if match:
        return match.group(1)
    if token.startswith("!"):
        return token[1:]
    return token


def resolve_mr(root: Path, mr: Optional[str]) -> Optional[dict]:
    has_glab = shutil.which("glab") is not None
    if mr:
        if not has_glab:
            raise CommandError("`--mr` 模式需要 glab。请先安装并完成 `glab auth login`，或者改用 `--base` / `--head`。")
        token = parse_mr_token(mr)
        return json.loads(run(["glab", "mr", "view", token, "-F", "json"], root).stdout)

    if not has_glab:
        return None
    branch = current_branch(root)
    try:
        result = run(
            ["glab", "api", f"projects/:fullpath/merge_requests?state=opened&source_branch={branch}"],
            root,
        )
    except CommandError:
        return None
    merge_requests = json.loads(result.stdout or "[]")
    if not merge_requests:
        return None
    merge_requests.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    token = str(merge_requests[0]["iid"])
    return json.loads(run(["glab", "mr", "view", token, "-F", "json"], root).stdout)


def ensure_git_ref(root: Path, ref: str) -> None:
    try:
        run(["git", "cat-file", "-e", f"{ref}^{{commit}}"], root)
    except CommandError:
        run(["git", "fetch", "origin", ref], root)


def fetch_mr_refs(root: Path, mr_data: dict) -> None:
    source = mr_data["source_branch"]
    target = mr_data["target_branch"]
    run(["git", "fetch", "origin", source, target], root)
    for ref in (mr_data.get("sha"), mr_data.get("diff_refs", {}).get("base_sha"), mr_data.get("diff_refs", {}).get("head_sha")):
        if ref:
            ensure_git_ref(root, ref)


def create_worktree(root: Path, ref: str) -> Tuple[Path, str]:
    temp_dir = Path(tempfile.mkdtemp(prefix="codex-review-worktree-"))
    run(["git", "worktree", "add", "--detach", str(temp_dir), ref], root)
    cleanup = f"git -C {root} worktree remove {temp_dir} && rm -rf {temp_dir}"
    return temp_dir, cleanup


def untracked_file_diff(root: Path) -> str:
    result = run(["git", "ls-files", "--others", "--exclude-standard"], root)
    chunks: List[str] = []
    for rel_path in result.stdout.splitlines():
        path = root / rel_path
        if not path.is_file():
            continue
        diff = subprocess.run(
            ["git", "diff", "--no-index", "--unified=3", "--no-color", "/dev/null", str(path)],
            cwd=str(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if diff.stdout:
            chunks.append(diff.stdout)
    return "\n".join(chunks)


def unified_diff(root: Path, mode: str, base: Optional[str], head: Optional[str], mr_iid: Optional[str]) -> str:
    if mode == "merge_request" and mr_iid:
        try:
            return run(["glab", "mr", "diff", mr_iid, "--raw", "--color=never"], root).stdout
        except CommandError:
            if base and head:
                return run(["git", "diff", "--unified=3", "--no-color", base, head], root).stdout
            raise
    if mode == "commit_range" and base and head:
        return run(["git", "diff", "--unified=3", "--no-color", base, head], root).stdout
    tracked = run(["git", "diff", "HEAD", "--unified=3", "--no-color"], root).stdout
    untracked = untracked_file_diff(root)
    return "\n".join(part for part in [tracked, untracked] if part)


def parse_diff(diff_text: str) -> List[dict]:
    files: List[dict] = []
    current: Optional[dict] = None
    hunk: Optional[dict] = None
    new_line = 0
    old_line = 0

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("diff --git "):
            if current:
                files.append(current)
            current = {"path": None, "hunks": []}
            hunk = None
            continue
        if current is None:
            continue
        if raw_line.startswith("+++ "):
            path = raw_line[4:]
            current["path"] = path[2:] if path.startswith("b/") else path
            continue
        if raw_line.startswith("@@ "):
            match = DIFF_HUNK_RE.match(raw_line)
            if not match:
                continue
            old_line = int(match.group(1))
            new_line = int(match.group(2))
            hunk = {
                "header": raw_line,
                "changed_new_lines": [],
                "changed_old_lines": [],
                "lines": [],
            }
            current["hunks"].append(hunk)
            continue
        if hunk is None:
            continue
        hunk["lines"].append(raw_line)
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            hunk["changed_new_lines"].append(new_line)
            new_line += 1
            continue
        if raw_line.startswith("-") and not raw_line.startswith("---"):
            hunk["changed_old_lines"].append(old_line)
            old_line += 1
            continue
        if raw_line.startswith("\\"):
            continue
        old_line += 1
        new_line += 1

    if current:
        files.append(current)
    return [item for item in files if item.get("path")]


def discover_source_root(workspace: Path) -> Path:
    candidates = [
        workspace / "internal-account-service" / "src" / "main",
        workspace / "src" / "main",
        workspace,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return workspace


def iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in RELEVANT_EXTENSIONS:
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        yield path


def parse_code_symbols(path: Path, rel_path: str) -> List[Symbol]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    symbols: List[Symbol] = []
    class_stack: List[Tuple[str, int, int]] = []
    for index, line in enumerate(lines, start=1):
        class_match = CLASS_RE.search(line)
        if class_match and "{" in line:
            end = find_block_end(lines, index)
            class_name = class_match.group(2)
            class_stack.append((class_name, index, end))
            symbols.append(Symbol(class_name, "class", rel_path, index, end, path.suffix[1:], line.strip()))
        enclosing_class = None
        for class_name, start, end in reversed(class_stack):
            if start <= index <= end:
                enclosing_class = class_name
                break

        java_match = JAVA_METHOD_RE.match(line)
        if java_match and java_match.group(1) not in CONTROL_WORDS:
            end = find_block_end(lines, index)
            symbols.append(
                Symbol(
                    java_match.group(1),
                    "method",
                    rel_path,
                    index,
                    end,
                    path.suffix[1:],
                    line.strip(),
                    enclosing_class=enclosing_class,
                )
            )
            continue

        kotlin_match = KOTLIN_METHOD_RE.match(line)
        if kotlin_match and "{" in line and kotlin_match.group(1) not in CONTROL_WORDS:
            end = find_block_end(lines, index)
            symbols.append(
                Symbol(
                    kotlin_match.group(1),
                    "method",
                    rel_path,
                    index,
                    end,
                    path.suffix[1:],
                    line.strip(),
                    enclosing_class=enclosing_class,
                )
            )
    return symbols


def parse_xml_symbols(path: Path, rel_path: str) -> List[Symbol]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    symbols: List[Symbol] = []
    for index, line in enumerate(lines, start=1):
        match = XML_BLOCK_RE.search(line)
        if not match:
            continue
        block_type, block_name = match.groups()
        closing = f"</{block_type}>"
        end = index
        for probe in range(index, len(lines) + 1):
            if closing in lines[probe - 1]:
                end = probe
                break
        symbols.append(Symbol(block_name, block_type.lower(), rel_path, index, end, "xml", line.strip()))
    return symbols


def find_block_end(lines: List[str], start_line: int) -> int:
    balance = 0
    started = False
    for index in range(start_line, len(lines) + 1):
        line = lines[index - 1]
        balance += line.count("{")
        balance -= line.count("}")
        if "{" in line:
            started = True
        if started and balance <= 0:
            return index
    return len(lines)


def looks_like_declaration_start(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    first_token = stripped.split()[0]
    if first_token in CONTROL_WORDS:
        return False
    if stripped.startswith("@"):
        return True
    return (
        "fun " in stripped
        or first_token in {"public", "protected", "private", "internal", "open", "override", "suspend", "static", "final", "default"}
    )


def infer_symbol_from_line(path: Path, rel_path: str, line_no: int) -> Optional[Symbol]:
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        return None
    line_no = min(line_no, len(lines))
    lower_bound = max(line_no - 200, 0)
    if path.suffix == ".xml":
        for start in range(line_no, lower_bound, -1):
            match = XML_BLOCK_RE.search(lines[start - 1])
            if not match:
                continue
            block_type, block_name = match.groups()
            closing = f"</{block_type}>"
            end = start
            for probe in range(start, len(lines) + 1):
                if closing in lines[probe - 1]:
                    end = probe
                    break
            return Symbol(block_name, block_type.lower(), rel_path, start, end, "xml", lines[start - 1].strip())

    for start in range(line_no, lower_bound, -1):
        if not looks_like_declaration_start(lines[start - 1]):
            continue
        header = " ".join(part.strip() for part in lines[start - 1 : min(start + 8, len(lines))]).strip()
        java_match = JAVA_METHOD_HEADER_RE.search(header)
        if java_match and java_match.group(1) not in CONTROL_WORDS:
            brace_line = next(
                (probe for probe in range(start, min(start + 8, len(lines)) + 1) if "{" in lines[probe - 1]),
                None,
            )
            if brace_line is None or brace_line > line_no:
                continue
            return Symbol(
                java_match.group(1),
                "method",
                rel_path,
                start,
                find_block_end(lines, start),
                path.suffix[1:],
                header[:200],
            )
        kotlin_match = KOTLIN_METHOD_HEADER_RE.search(header)
        if kotlin_match and kotlin_match.group(1) not in CONTROL_WORDS:
            brace_line = next(
                (probe for probe in range(start, min(start + 8, len(lines)) + 1) if "{" in lines[probe - 1]),
                None,
            )
            if brace_line is None or brace_line > line_no:
                continue
            return Symbol(
                kotlin_match.group(1),
                "method",
                rel_path,
                start,
                find_block_end(lines, start),
                path.suffix[1:],
                header[:200],
            )
    return None


def index_repository(root: Path) -> Tuple[Dict[str, List[Symbol]], Dict[str, List[Symbol]]]:
    by_file: Dict[str, List[Symbol]] = {}
    by_name: Dict[str, List[Symbol]] = {}
    for path in iter_source_files(root):
        rel_path = str(path.relative_to(root))
        if path.suffix in JAVA_EXTENSIONS:
            symbols = parse_code_symbols(path, rel_path)
        else:
            symbols = parse_xml_symbols(path, rel_path)
        if not symbols:
            continue
        by_file[rel_path] = symbols
        for symbol in symbols:
            by_name.setdefault(symbol.name, []).append(symbol)
    return by_file, by_name


def select_changed_symbols(changed_file: dict, symbols: List[Symbol], root: Path) -> List[dict]:
    selected: List[dict] = []
    seen = set()
    file_path = root / changed_file["path"]
    for hunk in changed_file["hunks"]:
        line_candidates = hunk["changed_new_lines"] or hunk["changed_old_lines"]
        if not line_candidates:
            continue
        for line in line_candidates:
            matched_symbol: Optional[Symbol] = None
            for symbol in symbols:
                if symbol.start_line <= line <= symbol.end_line:
                    matched_symbol = symbol
                    break
            if matched_symbol is None:
                matched_symbol = infer_symbol_from_line(file_path, changed_file["path"], line)
            if matched_symbol is None:
                continue
            key = (matched_symbol.name, matched_symbol.start_line, matched_symbol.rel_path)
            if key in seen:
                continue
            seen.add(key)
            record = matched_symbol.to_dict(root)
            record["reason"] = "changed_hunk"
            selected.append(record)
    return selected


def extract_calls(snippet: str) -> List[str]:
    calls: List[str] = []
    seen = set()
    body_lines = snippet.splitlines()[1:]
    for line in body_lines:
        stripped = line.strip()
        if stripped.startswith("@"):
            continue
        for match in METHOD_CALL_RE.finditer(line):
            name = match.group(1)
            if name in CONTROL_WORDS or name in seen:
                continue
            seen.add(name)
            calls.append(name)
    return calls


def resolve_related_symbols(
    changed_symbols: List[dict],
    by_name: Dict[str, List[Symbol]],
    root: Path,
    max_depth: int,
) -> Tuple[List[dict], List[dict]]:
    related: List[dict] = []
    unresolved: List[dict] = []
    queue: List[Tuple[dict, int]] = [(symbol, 1) for symbol in changed_symbols if symbol["kind"] == "method"]
    visited = {(symbol["path"], symbol["start_line"], symbol["name"]) for symbol in changed_symbols}

    while queue:
        current, depth = queue.pop(0)
        if depth > max_depth:
            continue
        calls = extract_calls(current.get("snippet", ""))
        current_file = current["path"]
        current_class = current.get("enclosing_class")
        for call in calls:
            candidates = by_name.get(call, [])
            if not candidates:
                continue
            same_file = [item for item in candidates if item.rel_path == current_file]
            same_class = [item for item in candidates if current_class and item.enclosing_class == current_class]
            resolved: Optional[Symbol] = None
            ambiguous_candidates = candidates
            if call in GENERIC_METHOD_NAMES and not same_file and not same_class:
                continue
            if len(same_file) == 1:
                resolved = same_file[0]
            elif len(same_class) == 1:
                resolved = same_class[0]
            elif len(candidates) == 1:
                resolved = candidates[0]

            if not resolved:
                unresolved.append(
                    {
                        "call": call,
                        "from": {"path": current_file, "name": current["name"]},
                        "candidates": [
                            {"path": item.rel_path, "start_line": item.start_line, "kind": item.kind}
                            for item in ambiguous_candidates[:5]
                        ],
                        "reason": "ambiguous_symbol",
                    }
                )
                continue

            key = (resolved.rel_path, resolved.start_line, resolved.name)
            if key in visited:
                continue
            visited.add(key)
            record = resolved.to_dict(root)
            record["reason"] = f"callee_depth_{depth}"
            related.append(record)
            if resolved.kind == "method" and depth < max_depth:
                queue.append((record, depth + 1))
    return related, unresolved


def detect_nullability_gotchas(texts: List[str]) -> List[dict]:
    corpus = "\n".join(text for text in texts if text)
    hits: List[dict] = []
    for gotcha in NULLABILITY_GOTCHAS:
        matched = False
        for pattern in gotcha["patterns"]:
            if pattern.search(corpus):
                matched = True
                break
        if matched:
            hits.append(
                {
                    "rule_id": gotcha["rule_id"],
                    "title": gotcha["title"],
                    "reference": "references/nullability-gotchas.md",
                }
            )
    return hits


def build_context(args: argparse.Namespace) -> dict:
    root = repo_root(Path.cwd())
    repo = repo_identity(root)
    mr_data = resolve_mr(root, args.mr)
    mode = "working_tree"
    base = args.base
    head = args.head
    worktree_path = None
    cleanup_command = None
    mr_iid = None
    start = None

    if mr_data:
        mode = "merge_request"
        mr_iid = str(mr_data["iid"])
        fetch_mr_refs(root, mr_data)
        diff_refs = mr_data.get("diff_refs", {})
        base = diff_refs.get("base_sha") or mr_data.get("target_branch")
        start = diff_refs.get("start_sha") or base
        head = diff_refs.get("head_sha") or mr_data.get("sha")
        if not args.no_worktree and head:
            worktree_root, cleanup_command = create_worktree(root, head)
            worktree_path = str(worktree_root)
    elif base and head:
        mode = "commit_range"
        ensure_git_ref(root, base)
        ensure_git_ref(root, head)
        if not args.no_worktree:
            worktree_root, cleanup_command = create_worktree(root, head)
            worktree_path = str(worktree_root)

    diff_text = unified_diff(root, mode, base, head, mr_iid)
    changed_files = parse_diff(diff_text)
    workspace = Path(worktree_path) if worktree_path else root
    source_root = discover_source_root(workspace)
    by_file, by_name = index_repository(workspace)

    change_records = []
    changed_symbols: List[dict] = []
    for changed_file in changed_files:
        path = changed_file["path"]
        ext = Path(path).suffix
        symbols = by_file.get(path, []) if ext in RELEVANT_EXTENSIONS else []
        selected = select_changed_symbols(changed_file, symbols, workspace) if symbols else []
        changed_symbols.extend(selected)
        change_records.append(
            {
                "path": path,
                "language": ext.lstrip("."),
                "hunks": changed_file["hunks"],
                "changed_symbols": selected,
            }
        )

    related_symbols, unresolved = resolve_related_symbols(
        changed_symbols, by_name, workspace, args.depth
    )
    gotcha_texts = [diff_text]
    gotcha_texts.extend(symbol.get("snippet", "") for symbol in changed_symbols)
    gotcha_texts.extend(symbol.get("snippet", "") for symbol in related_symbols)
    nullability_hits = detect_nullability_gotchas(gotcha_texts)

    notes = []
    if not mr_data:
        notes.append("未检测到可用 MR，已降级为本地 diff 或显式 commit range 审查。")
    if not worktree_path and mode != "working_tree":
        notes.append("未创建临时 worktree，后续读取将基于当前仓库。")
    notes.append("数据库MCP状态: 离线（脚本未集成数据库 MCP，仅提供静态上下文）。")
    if nullability_hits:
        notes.append("命中空值风险专项规则，review 时应额外读取 references/nullability-gotchas.md。")

    return {
        "review_mode": mode,
        "repo_root": str(root),
        "workspace_root": worktree_path or str(root),
        "source_root": str(source_root),
        "repo": repo,
        "cleanup_command": cleanup_command,
        "input": {
            "mr": args.mr,
            "base": base,
            "start": start,
            "head": head,
            "depth": args.depth,
        },
        "mr": {
            "iid": mr_data.get("iid"),
            "title": mr_data.get("title"),
            "description": mr_data.get("description"),
            "source_branch": mr_data.get("source_branch"),
            "target_branch": mr_data.get("target_branch"),
            "web_url": mr_data.get("web_url"),
        } if mr_data else None,
        "db_mcp_status": "offline",
        "raw_diff": diff_text,
        "changes": change_records,
        "related_symbols": related_symbols,
        "nullability_gotchas_hits": nullability_hits,
        "unresolved_symbols": unresolved,
        "notes": notes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="采集 Java 后端代码审查所需的 MR、分支差异或本地 diff 上下文。"
    )
    parser.add_argument("--mr", help="MR IID、!IID 或 GitLab MR URL。")
    parser.add_argument("--base", help="commit range 审查的 base 引用。")
    parser.add_argument("--head", help="commit range 审查的 head 引用。")
    parser.add_argument("--depth", type=int, default=2, choices=[1, 2], help="相关方法扩展深度。")
    parser.add_argument("--no-worktree", action="store_true", help="不创建临时 detached worktree。")
    parser.add_argument("--output", help="把 JSON 输出写入文件，而不是 stdout。")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        context = build_context(args)
    except CommandError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = json.dumps(context, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
