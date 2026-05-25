from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .dependencies import find_dependency
from .errors import CmakexError


def probe_dependency(root: Path, name: str, build_dir: Path) -> list[str]:
    find_dependency(root, name)
    build_path = build_dir if build_dir.is_absolute() else root / build_dir
    query_path = build_path / ".cmake" / "api" / "v1" / "query"
    query_path.mkdir(parents=True, exist_ok=True)
    (query_path / "codemodel-v2").write_text("", encoding="utf-8")

    command = [
        "cmake",
        "-S",
        str(root),
        "-B",
        str(build_path),
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise CmakexError("cmake executable not found") from exc

    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise CmakexError(f"cmake configure failed while probing {name}:\n{output.strip()}")

    return read_file_api_targets(build_path, name)


def read_file_api_targets(build_path: Path, dependency_name: str) -> list[str]:
    reply_path = build_path / ".cmake" / "api" / "v1" / "reply"
    indexes = sorted(reply_path.glob("index-*.json"))
    if not indexes:
        raise CmakexError("CMake File API reply was not generated")

    index = json.loads(indexes[-1].read_text(encoding="utf-8"))
    codemodel_reply = index.get("reply", {}).get("codemodel-v2", {})
    codemodel_ref = codemodel_reply.get("jsonFile")
    if not codemodel_ref:
        raise CmakexError("CMake File API codemodel reply was not generated")

    codemodel = json.loads((reply_path / codemodel_ref).read_text(encoding="utf-8"))
    target_names: set[str] = set()
    fallback_names: set[str] = set()
    source_marker = f"_deps/{dependency_name.lower()}-src"
    build_marker = f"_deps/{dependency_name.lower()}-build"

    for configuration in codemodel.get("configurations", []):
        directories = configuration.get("directories", [])
        for target in configuration.get("targets", []):
            name = target.get("name")
            if not name:
                continue
            fallback_names.add(name)
            directory_index = target.get("directoryIndex")
            directory = {}
            if isinstance(directory_index, int) and directory_index < len(directories):
                directory = directories[directory_index]
            source_dir = directory.get("source", target.get("sourceDirectory", ""))
            build_dir = directory.get("build", target.get("buildDirectory", ""))
            normalized_source = source_dir.replace("\\", "/").lower()
            normalized_build = build_dir.replace("\\", "/").lower()
            if source_marker in normalized_source or build_marker in normalized_build:
                target_names.add(name)

    return sorted(target_names or fallback_names)
