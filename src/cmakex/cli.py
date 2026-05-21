from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import build_project, run_project
from .dependencies import find_dependency, read_dependencies, uninstall_dependency, upsert_dependency
from .errors import CmakexError
from .github import GitHubClient
from .probe import probe_dependency
from .refs import parse_repo_spec, selected_ref
from .templates import create_project


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CmakexError as exc:
        print(f"cmakex: error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cmakex")
    parser.add_argument("--root", default=".", help=argparse.SUPPRESS)
    subcommands = parser.add_subparsers(dest="command", required=True)

    new = subcommands.add_parser("new", help="create a minimal CMake project")
    new.add_argument("name", help="project name")
    new.set_defaults(func=cmd_new)

    search = subcommands.add_parser("search", help="search GitHub repositories")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.set_defaults(func=cmd_search)

    install = subcommands.add_parser("install", help="install or update a FetchContent dependency")
    install.add_argument("repository", help="owner/repo, GitHub URL, git URL, or owner/repo==tag")
    install.add_argument("--name", help="local FetchContent dependency name")
    ref_group = install.add_mutually_exclusive_group()
    ref_group.add_argument("--tag", help="git tag to write to GIT_TAG")
    ref_group.add_argument("--commit", help="commit hash to write to GIT_TAG")
    ref_group.add_argument("--branch", help="branch name to write to GIT_TAG")
    install.add_argument("--target", action="append", default=[], help="record an upstream target hint")
    install.add_argument(
        "--set",
        dest="cmake_options",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="set a CMake cache option before FetchContent_MakeAvailable",
    )
    install.add_argument("--no-probe", action="store_true", help="write dependencies.cmake without running cmake")
    install.add_argument("--build-dir", default="build", help="build directory for automatic probe")
    install.set_defaults(func=cmd_install)

    uninstall = subcommands.add_parser("uninstall", help="remove a dependency")
    uninstall.add_argument("name")
    uninstall.set_defaults(func=cmd_uninstall)

    list_cmd = subcommands.add_parser("list", help="list local dependencies")
    list_cmd.set_defaults(func=cmd_list)

    latest = subcommands.add_parser("latest", help="show latest GitHub release/tag for a dependency or repo")
    latest.add_argument("target", help="installed dependency name or owner/repo")
    latest.set_defaults(func=cmd_latest)

    probe = subcommands.add_parser("probe", help="configure the project and detect CMake targets")
    probe.add_argument("name")
    probe.add_argument("--build-dir", default="build")
    probe.set_defaults(func=cmd_probe)

    build = subcommands.add_parser("build", help="configure and build the project")
    build.add_argument("target", nargs="?", help="optional target to build")
    build.add_argument("--build-dir", default="build")
    build.add_argument("--config", help="CMake multi-config configuration")
    build.set_defaults(func=cmd_build)

    run = subcommands.add_parser("run", help="build and run an executable target")
    run.add_argument("target", nargs="?", help="target to run; defaults to project name")
    run.add_argument("--build-dir", default="build")
    run.add_argument("--config", help="CMake multi-config configuration")
    run.add_argument("program_args", nargs=argparse.REMAINDER, help="arguments passed after --")
    run.set_defaults(func=cmd_run)

    return parser


def cmd_new(args) -> int:
    root = Path(args.root).resolve()
    project_root = create_project(root, args.name)
    print(f"Created CMake project: {args.name}")
    print(f"  path: {project_root}")
    return 0


def cmd_search(args) -> int:
    client = GitHubClient()
    results = client.search(args.query, limit=args.limit)
    if not results:
        print("No repositories found.")
        return 0
    rows = [
        (result.full_name, str(result.stars), result.updated_at, shorten(result.description, 96))
        for result in results
    ]
    print_table(("repo", "stars", "updated", "description"), rows)
    print("\nUse `cmakex latest owner/repo` to inspect the latest tag before installing.")
    print("Search results are GitHub repositories; FetchContent/CMake compatibility is not guaranteed.")
    return 0


def cmd_install(args) -> int:
    root = Path(args.root).resolve()
    spec = parse_repo_spec(args.repository, args.name)
    ref_kind, explicit_ref = selected_ref(args)
    if spec.shorthand_tag and explicit_ref:
        raise CmakexError("use either owner/repo==tag or --tag/--commit/--branch, not both")

    ref = spec.shorthand_tag or explicit_ref
    ref_source = "explicit tag shorthand" if spec.shorthand_tag else f"explicit {ref_kind}" if ref_kind else None

    if ref is None:
        if not spec.owner or not spec.repo:
            raise CmakexError("non-GitHub repositories require --tag, --commit, or --branch")
        latest = GitHubClient().latest_ref(spec.owner, spec.repo)
        ref = latest.ref
        ref_source = latest.source

    action = upsert_dependency(
        root,
        spec.dependency_name,
        spec.repository,
        ref,
        tuple(args.target),
        tuple(args.cmake_options),
    )
    print(f"{action.capitalize()} {spec.dependency_name}")
    print(f"  repository: {spec.repository}")
    print(f"  ref:        {ref}")
    if ref_source:
        print(f"  source:     {ref_source}")

    if ref_source == "default branch":
        print("  note:       default branch refs are moving targets; prefer --tag or --commit for reproducibility")

    if args.no_probe:
        print_link_template(root, [])
        return 0

    targets = probe_dependency(root, spec.dependency_name, Path(args.build_dir))
    print_targets(root, targets)
    return 0


def cmd_uninstall(args) -> int:
    root = Path(args.root).resolve()
    uninstall_dependency(root, args.name)
    print(f"Uninstalled {args.name}")
    return 0


def cmd_list(args) -> int:
    dependencies = read_dependencies(Path(args.root).resolve())
    if not dependencies:
        print("No dependencies found.")
        return 0
    rows = [
        (
            dependency.name,
            dependency.repository or "-",
            dependency.ref or "-",
            "; ".join(dependency.targets) if dependency.targets else "-",
            "; ".join(dependency.options) if dependency.options else "-",
        )
        for dependency in dependencies
    ]
    print_table(("name", "repository", "ref", "targets", "options"), rows)
    return 0


def cmd_latest(args) -> int:
    root = Path(args.root).resolve()
    target = args.target
    owner: str | None = None
    repo: str | None = None
    current_ref: str | None = None

    if "/" in target and not target.startswith(("http://", "https://", "git@")):
        spec = parse_repo_spec(target)
        owner, repo = spec.owner, spec.repo
    else:
        dependency = find_dependency(root, target)
        current_ref = dependency.ref
        spec = parse_repo_spec(dependency.repository or "", dependency.name)
        owner, repo = spec.owner, spec.repo

    if not owner or not repo:
        raise CmakexError("latest only supports GitHub repositories")

    latest_refs = GitHubClient().latest_refs(owner, repo)
    print(f"{owner}/{repo}")
    if current_ref:
        print(f"  current: {current_ref}")
    print("  refs:")
    for index, latest in enumerate(latest_refs, start=1):
        label = "latest" if index == 1 else f"#{index}"
        print(f"    {label}: {latest.ref} ({latest.source})")
    return 0


def cmd_probe(args) -> int:
    root = Path(args.root).resolve()
    targets = probe_dependency(root, args.name, Path(args.build_dir))
    print_targets(root, targets)
    return 0


def cmd_build(args) -> int:
    root = Path(args.root).resolve()
    build_project(root, Path(args.build_dir), target=args.target, config=args.config)
    return 0


def cmd_run(args) -> int:
    root = Path(args.root).resolve()
    program_args = args.program_args
    if program_args and program_args[0] == "--":
        program_args = program_args[1:]
    return run_project(
        root,
        Path(args.build_dir),
        target=args.target,
        config=args.config,
        program_args=program_args,
    )


def print_targets(root: Path, targets: list[str]) -> None:
    if not targets:
        print("No CMake targets detected.")
        print_link_template(root, [])
        return
    print("Detected CMake targets:")
    for target in targets:
        print(f"  {target}")
    print_link_template(root, targets)


def print_link_template(root: Path, targets: list[str]) -> None:
    project_target = infer_link_target(root)
    upstream_target = targets[0] if targets else "<upstream-target>"
    print("Next step: add this to your CMakeLists.txt and replace placeholders as needed:")
    print()
    print(f"  target_link_libraries({project_target} PRIVATE {upstream_target})")
    if can_print_append_command(project_target, upstream_target):
        print()
        print("Copy-paste on Linux/macOS:")
        print(f"  printf '\\ntarget_link_libraries({project_target} PRIVATE {upstream_target})\\n' >> CMakeLists.txt")


def infer_link_target(root: Path) -> str:
    try:
        from .build import infer_project_name

        return infer_project_name(root)
    except CmakexError:
        return "<your-target>"


def can_print_append_command(project_target: str, upstream_target: str) -> bool:
    if sys.platform not in {"linux", "linux2", "darwin"}:
        return False
    return "<" not in project_target and "<" not in upstream_target


def print_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def shorten(value: str, max_length: int) -> str:
    value = " ".join(value.split())
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."
