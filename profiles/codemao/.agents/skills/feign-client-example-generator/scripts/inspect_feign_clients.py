#!/usr/bin/env python3
"""Inspect FeignClient declarations and map them to controller implementations."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


GENERIC_SOURCE_PATTERNS = [
    "src/main/kotlin/**/*.kt",
    "src/main/java/**/*.java",
    "*/src/main/kotlin/**/*.kt",
    "*/src/main/java/**/*.java",
]

MAPPING_METHODS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}

THIRD_PARTY_KEYWORDS = [
    "third",
    "thirdparty",
    "external",
    "openapi",
    "resttemplate",
    "webclient",
    "okhttp",
    "retrofit",
    "sdk",
    "http://",
    "https://",
    "dingtalk",
    "beisen",
    "didi",
    "lbk",
]


@dataclass
class Endpoint:
    http_method: str
    sub_path: str
    signature: str
    line: int


@dataclass
class FeignClientDef:
    fqcn: str
    name: str
    module: str
    file: str
    line: int
    base_path: str
    endpoints: List[Endpoint] = field(default_factory=list)


@dataclass
class ControllerDef:
    fqcn: str
    file: str
    class_base_path: str
    endpoints: List[Endpoint] = field(default_factory=list)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def rel_path(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def normalize_path(path: str) -> str:
    if not path:
        return "/"
    path = path.strip().strip('"').strip("'")
    if not path.startswith("/"):
        path = "/" + path
    path = re.sub(r"/+", "/", path)
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path or "/"


def resolve_constant_path(raw_path: str, constants: Dict[str, str]) -> str:
    key = raw_path.strip().strip('"').strip("'")
    if key in constants:
        return normalize_path(constants[key])
    if key.startswith("/"):
        stripped = key[1:]
        if stripped in constants:
            return normalize_path(constants[stripped])
        if stripped.startswith("Services.") and stripped in constants:
            return normalize_path(constants[stripped])
        return normalize_path(key)
    if key.startswith("Services.") and key in constants:
        return normalize_path(constants[key])
    return normalize_path(key)


def join_paths(a: str, b: str) -> str:
    if b == "/":
        return normalize_path(a)
    if a == "/":
        return normalize_path(b)
    return normalize_path(f"{a}/{b.lstrip('/')}")


def extract_package(text: str) -> str:
    match = re.search(r"^\s*package\s+([a-zA-Z0-9_.]+)", text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def extract_class_name(text: str) -> Optional[Tuple[str, int]]:
    for pattern in [
        r"^\s*(?:public\s+)?(?:abstract\s+)?(?:class|interface)\s+([A-Za-z0-9_]+)",
        r"^\s*(?:open\s+)?(?:class|interface|object)\s+([A-Za-z0-9_]+)",
    ]:
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match:
            line = text[: match.start()].count("\n") + 1
            return match.group(1), line
    return None


def extract_annotation_path(annotation: str) -> str:
    for key in ["path", "value"]:
        match = re.search(rf"{key}\s*=\s*([^\s,)]+)", annotation)
        if match:
            return match.group(1).strip()
    match = re.search(r"\(([^)]*)\)", annotation)
    if not match:
        return "/"
    arg = match.group(1).strip()
    if not arg:
        return "/"
    if "=" in arg:
        return "/"
    return arg.split(",")[0].strip()


def parse_request_mapping(annotation: str) -> Tuple[str, str]:
    method = "ANY"
    method_match = re.search(r"RequestMethod\.([A-Z]+)", annotation)
    if method_match:
        method = method_match.group(1)
    return method, extract_annotation_path(annotation)


def collect_constant_values(root: Path, pattern_candidates: List[str]) -> Dict[str, str]:
    constants: Dict[str, str] = {}
    for pattern in pattern_candidates:
        for path in root.glob(pattern):
            text = read_text(path)
            class_info = extract_class_name(text)
            class_name = class_info[0] if class_info else None

            for match in re.finditer(r"const\s+val\s+([A-Z0-9_]+)\s*=\s*\"([^\"]+)\"", text):
                key, value = match.group(1), match.group(2)
                constants[key] = value
                if class_name:
                    constants[f"{class_name}.{key}"] = value
            for match in re.finditer(
                r"public\s+static\s+final\s+String\s+([A-Z0-9_]+)\s*=\s*\"([^\"]+)\"",
                text,
            ):
                key, value = match.group(1), match.group(2)
                constants[key] = value
                if class_name:
                    constants[f"{class_name}.{key}"] = value
    return constants


def collect_endpoints(text: str, constants: Dict[str, str]) -> List[Endpoint]:
    lines = text.splitlines()
    endpoints: List[Endpoint] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        mapping_match = re.search(
            r"@(?P<anno>GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\s*(?P<args>\([^)]*\))?",
            line,
        )
        if not mapping_match:
            idx += 1
            continue

        anno = mapping_match.group("anno")
        args = mapping_match.group("args") or "()"
        if anno == "RequestMapping":
            http_method, sub_path = parse_request_mapping(args)
        else:
            http_method = MAPPING_METHODS[anno]
            sub_path = extract_annotation_path(args)
        sub_path = resolve_constant_path(sub_path, constants)

        signature = ""
        sig_line = idx + 1
        for j in range(idx + 1, min(idx + 8, len(lines))):
            candidate = lines[j].strip()
            if re.search(r"\b(fun|public|private|protected)\b", candidate) and "(" in candidate:
                signature = candidate
                sig_line = j + 1
                break
            if re.search(r"\b[A-Za-z0-9_<>,\[\]\?]+\s+[A-Za-z0-9_]+\s*\(", candidate):
                signature = candidate
                sig_line = j + 1
                break

        endpoints.append(
            Endpoint(
                http_method=http_method,
                sub_path=sub_path,
                signature=signature or "<signature-not-found>",
                line=sig_line,
            )
        )
        idx += 1
    return endpoints


def parse_feign_clients(root: Path, constants: Dict[str, str], feign_patterns: List[str]) -> List[FeignClientDef]:
    clients: List[FeignClientDef] = []
    for pattern in feign_patterns:
        for path in root.glob(pattern):
            text = read_text(path)
            match = re.search(r"@FeignClient\s*\(([^)]*)\)", text, flags=re.DOTALL)
            if not match:
                continue
            package = extract_package(text)
            class_info = extract_class_name(text)
            if not class_info:
                continue
            class_name, class_line = class_info
            base_path = resolve_constant_path(extract_annotation_path(match.group(1)), constants)
            module = rel_path(root, path).split("/", 1)[0]
            fqcn = f"{package}.{class_name}" if package else class_name
            endpoints = collect_endpoints(text, constants)
            clients.append(
                FeignClientDef(
                    fqcn=fqcn,
                    name=class_name,
                    module=module,
                    file=rel_path(root, path),
                    line=class_line,
                    base_path=base_path,
                    endpoints=endpoints,
                )
            )
    clients.sort(key=lambda c: (c.name, c.module, c.file))
    return clients


def parse_controllers(root: Path, constants: Dict[str, str], service_patterns: List[str]) -> List[ControllerDef]:
    controllers: List[ControllerDef] = []
    for pattern in service_patterns:
        for path in root.glob(pattern):
            text = read_text(path)
            if "Mapping" not in text:
                continue
            package = extract_package(text)
            class_info = extract_class_name(text)
            if not class_info:
                continue
            class_name, _ = class_info
            class_mapping_match = re.search(r"@RequestMapping\s*(\([^)]*\))", text)
            class_base_path = (
                resolve_constant_path(extract_annotation_path(class_mapping_match.group(1)), constants)
                if class_mapping_match
                else "/"
            )
            endpoints = collect_endpoints(text, constants)
            if not endpoints:
                continue
            controllers.append(
                ControllerDef(
                    fqcn=f"{package}.{class_name}" if package else class_name,
                    file=rel_path(root, path),
                    class_base_path=class_base_path,
                    endpoints=endpoints,
                )
            )
    controllers.sort(key=lambda c: c.file)
    return controllers


def discover_patterns(root: Path) -> Tuple[List[str], List[str]]:
    """Discover feign/implementation source patterns from current project modules."""
    feign_patterns: List[str] = []
    impl_patterns: List[str] = []
    impl_tokens = ("service", "api", "web", "server", "backend", "core")

    for child in root.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if name.startswith("."):
            continue
        if not (child / "src" / "main").exists():
            continue

        lower_name = name.lower()
        if "client" in lower_name:
            feign_patterns.extend(
                [
                    f"{name}/src/main/kotlin/**/*.kt",
                    f"{name}/src/main/java/**/*.java",
                ]
            )
        if any(token in lower_name for token in impl_tokens):
            impl_patterns.extend(
                [
                    f"{name}/src/main/kotlin/**/*.kt",
                    f"{name}/src/main/java/**/*.java",
                ]
            )

    if not feign_patterns:
        feign_patterns = list(GENERIC_SOURCE_PATTERNS)
    if not impl_patterns:
        impl_patterns = list(GENERIC_SOURCE_PATTERNS)
    return feign_patterns, impl_patterns


def parse_glob_args(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    globs: List[str] = []
    for value in values:
        for part in value.split(","):
            item = part.strip()
            if item:
                globs.append(item)
    return globs


def detect_third_party(path: Path, lines: Iterable[str]) -> List[str]:
    hits: List[str] = []
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip().lower()
        if not line:
            continue
        for keyword in THIRD_PARTY_KEYWORDS:
            if keyword in line:
                hits.append(f"{path}:{idx}: {raw.strip()}")
                if len(hits) >= 12:
                    return hits
                break
    return hits


def extract_import_fqcns(text: str) -> List[str]:
    return re.findall(r"^\s*import\s+([a-zA-Z0-9_.]+)", text, flags=re.MULTILINE)


def extract_dependency_type_names(text: str) -> List[str]:
    names = set()
    for match in re.finditer(r"\b([A-Z][A-Za-z0-9_]+)\s+[a-zA-Z_][A-Za-z0-9_]*\s*[;=,)]", text):
        names.add(match.group(1))
    for match in re.finditer(r"\b(?:val|var)\s+[a-zA-Z_][A-Za-z0-9_]*\s*:\s*([A-Z][A-Za-z0-9_]+)", text):
        names.add(match.group(1))
    return list(names)


def is_impl_chain_name(name: str) -> bool:
    suffixes = ("Controller", "Facade", "Service", "Manager", "Repository", "Store", "Client")
    return name.endswith(suffixes)


def build_source_indices(
    root: Path, service_patterns: List[str]
) -> Tuple[Dict[str, Path], Dict[str, Dict[str, List[Path]]]]:
    fqcn_to_path: Dict[str, Path] = {}
    module_to_class_paths: Dict[str, Dict[str, List[Path]]] = {}
    seen: set[Path] = set()

    for pattern in service_patterns:
        for path in root.glob(pattern):
            if path in seen:
                continue
            seen.add(path)
            text = read_text(path)
            package = extract_package(text)
            class_info = extract_class_name(text)
            if not class_info:
                continue
            class_name = class_info[0]
            if package:
                fqcn_to_path[f"{package}.{class_name}"] = path
            rel = rel_path(root, path)
            module = rel.split("/", 1)[0] if "/" in rel else "."
            module_to_class_paths.setdefault(module, {}).setdefault(class_name, []).append(path)

    return fqcn_to_path, module_to_class_paths


def collect_impl_chain_files(
    root: Path,
    controller_file: str,
    fqcn_to_path: Dict[str, Path],
    module_to_class_paths: Dict[str, Dict[str, List[Path]]],
    max_depth: int = 2,
) -> List[Path]:
    controller_path = root / controller_file
    module = controller_file.split("/", 1)[0] if "/" in controller_file else "."
    class_map = module_to_class_paths.get(module, {})

    visited = {controller_path}
    queue: List[Tuple[Path, int]] = [(controller_path, 0)]
    collected: List[Path] = []

    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        text = read_text(current)
        candidates: List[Path] = []

        for fqcn in extract_import_fqcns(text):
            simple = fqcn.rsplit(".", 1)[-1]
            if is_impl_chain_name(simple):
                path = fqcn_to_path.get(fqcn)
                if path:
                    candidates.append(path)
                candidates.extend(class_map.get(f"{simple}Impl", []))

        for type_name in extract_dependency_type_names(text):
            if not is_impl_chain_name(type_name):
                continue
            candidates.extend(class_map.get(type_name, []))
            candidates.extend(class_map.get(f"{type_name}Impl", []))

        for nxt in candidates:
            if nxt in visited:
                continue
            visited.add(nxt)
            collected.append(nxt)
            queue.append((nxt, depth + 1))

    return collected


def match_implementation(
    root: Path,
    client: FeignClientDef,
    controllers: List[ControllerDef],
    fqcn_to_path: Dict[str, Path],
    module_to_class_paths: Dict[str, Dict[str, List[Path]]],
) -> Tuple[List[Dict[str, object]], List[str]]:
    matches: List[Dict[str, object]] = []
    third_party_hits: List[str] = []
    third_party_seen = set()
    for endpoint in client.endpoints:
        full_path = join_paths(client.base_path, endpoint.sub_path)
        endpoint_matches: List[Dict[str, object]] = []
        for controller in controllers:
            for ctrl_ep in controller.endpoints:
                ctrl_full_path = join_paths(controller.class_base_path, ctrl_ep.sub_path)
                if normalize_path(full_path) != normalize_path(ctrl_full_path):
                    continue
                if endpoint.http_method != "ANY" and ctrl_ep.http_method != "ANY" and endpoint.http_method != ctrl_ep.http_method:
                    continue
                endpoint_matches.append(
                    {
                        "controller": controller.fqcn,
                        "controllerFile": controller.file,
                        "controllerLine": ctrl_ep.line,
                        "controllerMethod": ctrl_ep.signature,
                        "controllerHttpMethod": ctrl_ep.http_method,
                        "controllerPath": ctrl_full_path,
                    }
                )
                impl_files = [root / controller.file] + collect_impl_chain_files(
                    root=root,
                    controller_file=controller.file,
                    fqcn_to_path=fqcn_to_path,
                    module_to_class_paths=module_to_class_paths,
                    max_depth=2,
                )
                for impl_path in impl_files:
                    key = str(impl_path)
                    if key in third_party_seen:
                        continue
                    text = read_text(impl_path).splitlines()
                    hits = detect_third_party(impl_path, text)
                    if hits:
                        third_party_hits.extend(hits)
                    third_party_seen.add(key)
        matches.append(
            {
                "clientMethod": endpoint.signature,
                "clientHttpMethod": endpoint.http_method,
                "clientSubPath": endpoint.sub_path,
                "clientFullPath": full_path,
                "clientLine": endpoint.line,
                "implementations": endpoint_matches,
            }
        )
    return matches, third_party_hits


def find_client(clients: List[FeignClientDef], query: str) -> Optional[FeignClientDef]:
    lowered = query.lower()
    candidates = [
        c
        for c in clients
        if lowered in c.fqcn.lower()
        or lowered == c.name.lower()
        or lowered in c.file.lower()
    ]
    if not candidates:
        return None
    exact = [c for c in candidates if lowered == c.fqcn.lower() or lowered == c.name.lower()]
    return exact[0] if exact else candidates[0]


def print_list_text(clients: List[FeignClientDef]) -> None:
    print("Found FeignClients:")
    for idx, client in enumerate(clients, start=1):
        print(
            f"{idx:>2}. {client.name} | {client.fqcn} | module={client.module} | "
            f"basePath={client.base_path} | methods={len(client.endpoints)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--mode", choices=["list", "inspect"], default="list")
    parser.add_argument("--client", help="Client name/FQCN/file segment for inspect mode")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--feign-glob",
        action="append",
        default=[],
        help="Glob(s) for Feign source scan. Repeatable or comma-separated.",
    )
    parser.add_argument(
        "--service-glob",
        action="append",
        default=[],
        help="Glob(s) for implementation source scan (controller/facade/service). Repeatable or comma-separated.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    auto_feign_patterns, auto_service_patterns = discover_patterns(root)
    feign_patterns = parse_glob_args(args.feign_glob) or auto_feign_patterns
    service_patterns = parse_glob_args(args.service_glob) or auto_service_patterns

    constants = collect_constant_values(root, feign_patterns + service_patterns)
    clients = parse_feign_clients(root, constants, feign_patterns)
    controllers = parse_controllers(root, constants, service_patterns)
    fqcn_to_path, module_to_class_paths = build_source_indices(root, service_patterns)

    if args.mode == "list":
        if args.format == "json":
            payload = [
                {
                    "name": c.name,
                    "fqcn": c.fqcn,
                    "module": c.module,
                    "file": c.file,
                    "line": c.line,
                    "basePath": c.base_path,
                    "methodCount": len(c.endpoints),
                }
                for c in clients
            ]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print_list_text(clients)
        return

    if not args.client:
        raise SystemExit("--client is required when --mode=inspect")

    client = find_client(clients, args.client)
    if not client:
        raise SystemExit(f"Client not found: {args.client}")

    matches, third_party_hits = match_implementation(
        root,
        client,
        controllers,
        fqcn_to_path,
        module_to_class_paths,
    )
    payload = {
        "client": {
            "name": client.name,
            "fqcn": client.fqcn,
            "module": client.module,
            "file": client.file,
            "line": client.line,
            "basePath": client.base_path,
        },
        "endpointMappings": matches,
        "thirdPartyInvolved": bool(third_party_hits),
        "thirdPartyEvidence": third_party_hits,
    }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"Client: {client.name} ({client.fqcn})")
    print(f"File: {client.file}:{client.line}")
    print(f"BasePath: {client.base_path}")
    print("")
    for item in matches:
        print(
            f"- {item['clientHttpMethod']} {item['clientFullPath']} | "
            f"{item['clientMethod']} (line {item['clientLine']})"
        )
        impls = item["implementations"]
        if not impls:
            print("  -> No implementation match found")
            continue
        for impl in impls:
            print(
                "  -> "
                f"{impl['controllerHttpMethod']} {impl['controllerPath']} | "
                f"{impl['controller']} @ {impl['controllerFile']}:{impl['controllerLine']}"
            )
    print("")
    print(f"Third-party involved: {'YES' if third_party_hits else 'NO'}")
    if third_party_hits:
        for hit in third_party_hits[:10]:
            print(f"  * {hit}")


if __name__ == "__main__":
    main()
