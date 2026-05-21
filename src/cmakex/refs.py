from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import CmakexError


GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GITHUB_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
SEMVER_RE = re.compile(
    r"^(?P<prefix>v)?(?P<version>\d+(?:\.\d+){1,3})(?:[-+._][0-9A-Za-z.-]+)?$"
)


@dataclass(frozen=True)
class RepoSpec:
    repository: str
    dependency_name: str
    owner: str | None = None
    repo: str | None = None
    shorthand_tag: str | None = None


def split_shorthand_tag(value: str) -> tuple[str, str | None]:
    if "==" not in value:
        return value, None
    repo, tag = value.split("==", 1)
    if not repo or not tag:
        raise CmakexError("version shorthand must look like owner/repo==tag")
    return repo, tag


def parse_repo_spec(value: str, name: str | None = None) -> RepoSpec:
    raw_repo, shorthand_tag = split_shorthand_tag(value)
    raw_repo = raw_repo.strip()

    if GITHUB_REPO_RE.match(raw_repo):
        owner, repo = raw_repo.split("/", 1)
        dep_name = name or normalize_dependency_name(repo)
        return RepoSpec(
            repository=f"https://github.com/{owner}/{repo}.git",
            dependency_name=dep_name,
            owner=owner,
            repo=repo,
            shorthand_tag=shorthand_tag,
        )

    match = GITHUB_URL_RE.match(raw_repo)
    if match:
        owner = match.group("owner")
        repo = match.group("repo")
        dep_name = name or normalize_dependency_name(repo)
        return RepoSpec(
            repository=f"https://github.com/{owner}/{repo}.git",
            dependency_name=dep_name,
            owner=owner,
            repo=repo,
            shorthand_tag=shorthand_tag,
        )

    if (
        raw_repo.startswith("http://")
        or raw_repo.startswith("https://")
        or raw_repo.startswith("git@")
        or raw_repo.startswith("file://")
    ):
        dep_name = name
        if dep_name is None:
            dep_name = infer_name_from_url(raw_repo)
        return RepoSpec(repository=raw_repo, dependency_name=dep_name, shorthand_tag=shorthand_tag)

    raise CmakexError("repository must be owner/repo, a GitHub URL, or a git URL")


def normalize_dependency_name(repo: str) -> str:
    if repo.endswith(".git"):
        repo = repo[:-4]
    return re.sub(r"[^A-Za-z0-9_]", "_", repo)


def infer_name_from_url(url: str) -> str:
    repo = url.rstrip("/").rsplit("/", 1)[-1]
    repo = repo[:-4] if repo.endswith(".git") else repo
    name = normalize_dependency_name(repo)
    if not name:
        raise CmakexError("could not infer dependency name; pass --name")
    return name


def selected_ref(args) -> tuple[str | None, str | None]:
    values = [
        ("tag", getattr(args, "tag", None)),
        ("commit", getattr(args, "commit", None)),
        ("branch", getattr(args, "branch", None)),
    ]
    selected = [(kind, value) for kind, value in values if value]
    if len(selected) > 1:
        raise CmakexError("--tag, --commit, and --branch are mutually exclusive")
    return selected[0] if selected else (None, None)


def semver_sort_key(tag: str) -> tuple[int, ...] | None:
    normalized = tag
    if normalized.endswith("^{}"):
        normalized = normalized[:-3]
    normalized = normalized.rsplit("/", 1)[-1]
    match = SEMVER_RE.match(normalized)
    if not match:
        return None
    parts = tuple(int(part) for part in match.group("version").split("."))
    return parts + (0,) * (4 - len(parts))


def pick_latest_semver_tag(tags: list[str]) -> str | None:
    candidates: list[tuple[tuple[int, ...], str]] = []
    for tag in tags:
        key = semver_sort_key(tag)
        if key is not None:
            candidates.append((key, tag))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def sort_semver_tags(tags: list[str]) -> list[str]:
    candidates: list[tuple[tuple[int, ...], str]] = []
    for tag in tags:
        key = semver_sort_key(tag)
        if key is not None:
            candidates.append((key, tag))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [tag for _, tag in candidates]
