from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import ssl

from .errors import CmakexError
from .refs import pick_latest_semver_tag, sort_semver_tags


API_ROOT = "https://api.github.com"
CACHE_DIR = Path.home() / ".cache" / "cmakex"
CACHE_TTL_SECONDS = 6 * 60 * 60


@dataclass(frozen=True)
class SearchResult:
    full_name: str
    stars: int
    updated_at: str
    description: str
    clone_url: str


@dataclass(frozen=True)
class LatestRef:
    ref: str
    source: str


class GitHubClient:
    def __init__(self, token: str | None = None, cache_dir: Path = CACHE_DIR):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.cache_dir = cache_dir

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        github_query = f"{query} in:name,description"
        data = self._get_json(
            "/search/repositories",
            {"q": github_query, "sort": "stars", "order": "desc", "per_page": str(limit)},
            cache=True,
        )
        results: list[SearchResult] = []
        for item in data.get("items", []):
            results.append(
                SearchResult(
                    full_name=item.get("full_name", ""),
                    stars=int(item.get("stargazers_count", 0)),
                    updated_at=item.get("updated_at", "")[:10],
                    description=item.get("description") or "",
                    clone_url=item.get("clone_url", ""),
                )
            )
        return results

    def repo_default_branch(self, owner: str, repo: str) -> str:
        data = self._get_json(f"/repos/{owner}/{repo}", cache=True)
        return data.get("default_branch") or "main"

    def latest_ref(self, owner: str, repo: str) -> LatestRef:
        release = self.latest_release_tag(owner, repo)
        if release:
            return LatestRef(release, "GitHub latest release")
        tags = self.tags(owner, repo)
        semver = pick_latest_semver_tag(tags)
        if semver:
            return LatestRef(semver, "latest semver tag")
        branch = self.repo_default_branch(owner, repo)
        return LatestRef(branch, "default branch")

    def latest_refs(self, owner: str, repo: str, limit: int = 5) -> list[LatestRef]:
        refs: list[LatestRef] = []
        release = self.latest_release_tag(owner, repo)
        if release:
            refs.append(LatestRef(release, "GitHub latest release"))

        for tag in self.semver_tags(owner, repo):
            if tag != release:
                refs.append(LatestRef(tag, "semver tag"))
            if len(refs) >= limit:
                return refs

        if refs:
            return refs

        branch = self.repo_default_branch(owner, repo)
        return [LatestRef(branch, "default branch")]

    def latest_release_tag(self, owner: str, repo: str) -> str | None:
        try:
            data = self._get_json(f"/repos/{owner}/{repo}/releases/latest", cache=True)
        except CmakexError as exc:
            if "404" in str(exc):
                return None
            raise
        return data.get("tag_name")

    def tags(self, owner: str, repo: str, limit: int = 100) -> list[str]:
        data = self._get_json(
            f"/repos/{owner}/{repo}/tags",
            {"per_page": str(limit)},
            cache=True,
        )
        return [item["name"] for item in data if "name" in item]

    def semver_tags(self, owner: str, repo: str, limit: int = 100) -> list[str]:
        tags = self.tags(owner, repo, limit=limit)
        return sort_semver_tags(tags)

    def _get_json(
        self,
        path: str,
        params: dict[str, str] | None = None,
        cache: bool = False,
    ):
        params = params or {}
        url = f"{API_ROOT}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"

        cache_path = self._cache_path(url)
        if cache and cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if time.time() - cached["time"] < CACHE_TTL_SECONDS:
                return cached["data"]

        request = Request(url, headers=self._headers())
        data = self._open_json(request)

        if cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({"time": time.time(), "data": data}), encoding="utf-8")
        return data

    def _open_json(self, request: Request):
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urlopen(request, timeout=20) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body)
            except HTTPError as exc:
                message = exc.read().decode("utf-8", errors="replace")
                rate = exc.headers.get("x-ratelimit-remaining")
                reset = exc.headers.get("x-ratelimit-reset")
                suffix = ""
                if rate == "0" and reset:
                    suffix = f" GitHub rate limit exceeded; set GITHUB_TOKEN or retry after {reset}."
                raise CmakexError(f"GitHub API error {exc.code}: {message}{suffix}") from exc
            except (URLError, ssl.SSLError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
        if isinstance(last_error, URLError):
            raise CmakexError(f"GitHub API request failed: {last_error.reason}") from last_error
        raise CmakexError(f"GitHub API request failed: {last_error}") from last_error

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "cmakex",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _cache_path(self, url: str) -> Path:
        safe = "".join(ch if ch.isalnum() else "_" for ch in url)
        return self.cache_dir / f"{safe}.json"
