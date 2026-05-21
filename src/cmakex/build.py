from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .errors import CmakexError


PROJECT_RE = re.compile(r"^\s*project\s*\(\s*([A-Za-z_][A-Za-z0-9_-]*)", re.MULTILINE)


def configure_project(root: Path, build_dir: Path) -> None:
    build_path = resolve_build_dir(root, build_dir)
    command = ["cmake", "-S", str(root), "-B", str(build_path)]
    run_command(command, "cmake configure failed")


def build_project(root: Path, build_dir: Path, target: str | None = None, config: str | None = None) -> None:
    build_path = resolve_build_dir(root, build_dir)
    configure_project(root, build_dir)
    command = ["cmake", "--build", str(build_path)]
    if target:
        command.extend(["--target", target])
    if config:
        command.extend(["--config", config])
    run_command(command, "cmake build failed")


def run_project(
    root: Path,
    build_dir: Path,
    target: str | None = None,
    config: str | None = None,
    program_args: list[str] | None = None,
) -> int:
    target = target or infer_project_name(root)
    build_project(root, build_dir, target=target, config=config)
    executable = find_executable(resolve_build_dir(root, build_dir), target, config)
    result = subprocess.run([str(executable), *(program_args or [])], check=False)
    return result.returncode


def infer_project_name(root: Path) -> str:
    cmakelists = root / "CMakeLists.txt"
    if not cmakelists.exists():
        raise CmakexError("CMakeLists.txt not found; run `cmakex new <name>` first")
    text = cmakelists.read_text(encoding="utf-8")
    match = PROJECT_RE.search(text)
    if not match:
        raise CmakexError("could not infer run target; pass it explicitly")
    return match.group(1)


def find_executable(build_path: Path, target: str, config: str | None = None) -> Path:
    names = [target, f"{target}.exe"]
    search_roots = [build_path]
    if config:
        search_roots.insert(0, build_path / config)

    for root in search_roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate

    matches = [
        path
        for name in names
        for path in build_path.rglob(name)
        if path.is_file() and not any(part.startswith(".") for part in path.parts)
    ]
    if matches:
        return sorted(matches, key=lambda path: len(path.parts))[0]

    raise CmakexError(f"built target `{target}`, but executable was not found under {build_path}")


def resolve_build_dir(root: Path, build_dir: Path) -> Path:
    return build_dir if build_dir.is_absolute() else root / build_dir


def run_command(command: list[str], error_message: str) -> None:
    try:
        result = subprocess.run(command, check=False)
    except FileNotFoundError as exc:
        raise CmakexError("cmake executable not found") from exc
    if result.returncode != 0:
        raise CmakexError(error_message)
