from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .errors import CmakexError


DEPENDENCIES_PATH = Path("cmake") / "dependencies.cmake"
DECLARE_RE = re.compile(
    r"(?P<prefix>(?:#[^\n]*\n)*)"
    r"FetchContent_Declare\s*\(\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?P<body>.*?)"
    r"^\)",
    re.MULTILINE | re.DOTALL,
)
MAKE_AVAILABLE_RE_TEMPLATE = (
    r"\n?(?:set\s*\([^\n]*\)\s*\n)*FetchContent_MakeAvailable\s*\(\s*{name}\s*\)\s*\n?"
)
FIELD_RE_TEMPLATE = r"\b{field}\s+([^\s\)]+)"
TARGET_COMMENT_RE = re.compile(r"^#\s*cmakex:\s*targets\s+(?P<targets>.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Dependency:
    name: str
    repository: str | None
    ref: str | None
    targets: tuple[str, ...] = ()
    options: tuple[str, ...] = ()


def dependencies_path(root: Path = Path(".")) -> Path:
    return root / DEPENDENCIES_PATH


def ensure_dependencies_file(root: Path = Path(".")) -> Path:
    path = dependencies_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("include(FetchContent)\n", encoding="utf-8")
    return path


def read_dependencies(root: Path = Path(".")) -> list[Dependency]:
    path = dependencies_path(root)
    if not path.exists():
        return []
    return parse_dependencies(path.read_text(encoding="utf-8"))


def parse_dependencies(text: str) -> list[Dependency]:
    dependencies: list[Dependency] = []
    for match in DECLARE_RE.finditer(text):
        name = match.group("name")
        prefix = match.group("prefix")
        body = match.group("body")
        repository = read_field(body, "GIT_REPOSITORY")
        ref = read_field(body, "GIT_TAG")
        targets = read_targets(prefix)
        options = read_options(prefix)
        dependencies.append(Dependency(name=name, repository=repository, ref=ref, targets=targets, options=options))
    return dependencies


def find_dependency(root: Path, name: str) -> Dependency:
    for dependency in read_dependencies(root):
        if dependency.name == name:
            return dependency
    raise CmakexError(f"dependency not found: {name}")


def read_field(body: str, field: str) -> str | None:
    match = re.search(FIELD_RE_TEMPLATE.format(field=re.escape(field)), body)
    return match.group(1) if match else None


def read_targets(prefix: str) -> tuple[str, ...]:
    match = TARGET_COMMENT_RE.search(prefix)
    if not match:
        return ()
    return tuple(target.strip() for target in match.group("targets").split(";") if target.strip())


def read_options(prefix: str) -> tuple[str, ...]:
    options: list[str] = []
    for line in prefix.splitlines():
        if line.startswith("# cmakex: option "):
            options.append(line.split("# cmakex: option ", 1)[1].strip())
    return tuple(options)


def upsert_dependency(
    root: Path,
    name: str,
    repository: str,
    ref: str,
    targets: list[str] | tuple[str, ...] = (),
    options: list[str] | tuple[str, ...] = (),
) -> str:
    path = ensure_dependencies_file(root)
    text = path.read_text(encoding="utf-8")
    block = render_dependency_block(name, repository, ref, targets, options)

    existing = find_declare_match(text, name)
    action = "installed"
    if existing:
        start, end = existing.span()
        end = consume_following_make_available(text, end, name)
        text = text[:start].rstrip() + "\n\n" + block + text[end:].lstrip("\n")
        action = "updated"
    else:
        text = text.rstrip() + "\n\n" + block

    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return action


def uninstall_dependency(root: Path, name: str) -> None:
    path = dependencies_path(root)
    if not path.exists():
        raise CmakexError("cmake/dependencies.cmake does not exist")
    text = path.read_text(encoding="utf-8")
    existing = find_declare_match(text, name)
    if not existing:
        raise CmakexError(f"dependency not found: {name}")
    start, end = existing.span()
    end = consume_following_make_available(text, end, name)
    updated = text[:start].rstrip() + "\n\n" + text[end:].lstrip("\n")
    path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def find_declare_match(text: str, name: str) -> re.Match[str] | None:
    for match in DECLARE_RE.finditer(text):
        if match.group("name") == name:
            return match
    return None


def consume_following_make_available(text: str, start: int, name: str) -> int:
    pattern = re.compile(MAKE_AVAILABLE_RE_TEMPLATE.format(name=re.escape(name)))
    match = pattern.match(text, start)
    return match.end() if match else start


def render_dependency_block(
    name: str,
    repository: str,
    ref: str,
    targets: list[str] | tuple[str, ...] = (),
    options: list[str] | tuple[str, ...] = (),
) -> str:
    lines: list[str] = []
    if targets:
        lines.append(f"# cmakex: targets {'; '.join(targets)}")
    option_lines: list[str] = []
    for option in options:
        key, value = parse_option(option)
        cache_type = "BOOL" if value in {"ON", "OFF", "TRUE", "FALSE"} else "STRING"
        lines.append(f"# cmakex: option {key}={value}")
        option_lines.append(f"set({key} {cmake_quote(value)} CACHE {cache_type} \"cmakex option for {name}\" FORCE)")
    lines.extend(
        [
            "FetchContent_Declare(",
            f"  {name}",
            f"  GIT_REPOSITORY {repository}",
            f"  GIT_TAG {ref}",
            ")",
        ]
    )
    lines.extend(option_lines)
    lines.append(f"FetchContent_MakeAvailable({name})")
    return "\n".join(lines)


def parse_option(option: str) -> tuple[str, str]:
    if "=" not in option:
        raise CmakexError("CMake options must look like KEY=VALUE")
    key, value = option.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        raise CmakexError(f"invalid CMake option name: {key}")
    if not value:
        raise CmakexError(f"empty value for CMake option: {key}")
    return key, value


def cmake_quote(value: str) -> str:
    if re.match(r"^[A-Za-z0-9_./:+,-]+$", value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
