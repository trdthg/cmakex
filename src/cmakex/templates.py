from __future__ import annotations

from pathlib import Path

from .errors import CmakexError


def create_project(parent: Path, name: str) -> Path:
    if name in {"", ".", ".."} or "/" in name or "\\" in name:
        raise CmakexError("project name must be a plain directory name")
    root = parent / name
    if root.exists() and any(root.iterdir()):
        raise CmakexError(f"refusing to initialize non-empty directory: {name}")
    root.mkdir(parents=True, exist_ok=True)
    init_project(root, name)
    return root


def init_project(root: Path, name: str) -> None:
    cmakelists = root / "CMakeLists.txt"
    dependencies = root / "cmake" / "dependencies.cmake"
    main_c = root / "src" / "main.c"
    existing = [path for path in (cmakelists, dependencies, main_c) if path.exists()]
    if existing:
        paths = ", ".join(str(path.relative_to(root)) for path in existing)
        raise CmakexError(f"refusing to overwrite existing files: {paths}")

    dependencies.parent.mkdir(parents=True, exist_ok=True)
    main_c.parent.mkdir(parents=True, exist_ok=True)

    cmakelists.write_text(
        "\n".join(
            [
                "cmake_minimum_required(VERSION 3.24)",
                "",
                f"project({name} C CXX)",
                "",
                "include(cmake/dependencies.cmake)",
                "",
                f"add_executable({name} src/main.c)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    dependencies.write_text("include(FetchContent)\n", encoding="utf-8")
    main_c.write_text(
        "\n".join(
            [
                "#include <stdio.h>",
                "",
                "int main(void) {",
                '    puts("Hello from cmakex");',
                "    return 0;",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
