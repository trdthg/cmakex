# cmakex Design

`cmakex` is a lightweight, non-invasive helper for CMake projects that use `FetchContent`.

The project follows a simple principle: keep CMake as the source of truth. `cmakex` should help users discover source dependencies, write standard CMake snippets, probe targets, and run common build commands without introducing a package manifest or a custom CMake DSL.

## Goals

- Keep dependency declarations in normal CMake.
- Avoid project-local manifests such as `cmakex.json`.
- Avoid custom CMake macros.
- Use `FetchContent_Declare(...)` and `FetchContent_MakeAvailable(...)`.
- Leave application linking in the user's `CMakeLists.txt`.
- Make common workflows fast: create, search, install, list, build, run.
- Prefer explicit behavior over hidden mutation.

## Non-Goals

`cmakex` is not a full package manager.

It does not currently:

- maintain a package registry
- guarantee GitHub search results are installable
- patch upstream projects
- manage binary packages
- rewrite arbitrary CMake projects
- automatically edit business `target_link_libraries(...)`

## Project Contract

`cmakex` manages one dependency file:

```text
cmake/dependencies.cmake
```

The root `CMakeLists.txt` includes it:

```cmake
include(cmake/dependencies.cmake)
```

Application code links upstream targets manually:

```cmake
target_link_libraries(my_app PRIVATE fmt)
```

## Generated Project

`cmakex new hello` creates:

```text
hello/
|-- CMakeLists.txt
|-- cmake/
|   `-- dependencies.cmake
`-- src/
    `-- main.c
```

The generated `CMakeLists.txt` is intentionally small:

```cmake
cmake_minimum_required(VERSION 3.24)

project(hello C CXX)

include(cmake/dependencies.cmake)

add_executable(hello src/main.c)
```

Both C and CXX are enabled because many useful `FetchContent` dependencies expose C++ CMake targets even when the user's starter app is C.

## Dependency File Format

Base file:

```cmake
include(FetchContent)
```

Installed dependency:

```cmake
FetchContent_Declare(
  fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG 12.1.0
)
FetchContent_MakeAvailable(fmt)
```

Installed dependency with options:

```cmake
# cmakex: option WITH_IPP=OFF
FetchContent_Declare(
  opencv
  GIT_REPOSITORY https://github.com/opencv/opencv.git
  GIT_TAG 4.10.0
)
set(WITH_IPP OFF CACHE BOOL "cmakex option for opencv" FORCE)
FetchContent_MakeAvailable(opencv)
```

Target hints may be recorded as comments:

```cmake
# cmakex: targets fmt::fmt; fmt
FetchContent_Declare(
  fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG 12.1.0
)
FetchContent_MakeAvailable(fmt)
```

Comments are metadata only. The CMake file remains valid without `cmakex`.

## GitHub-First Discovery

The MVP does not maintain its own registry. GitHub is used as the remote discovery source.

Supported repository inputs:

```bash
fmtlib/fmt
https://github.com/fmtlib/fmt.git
https://example.com/custom/repo.git
git@example.com:owner/repo.git
file:///local/repo
```

For GitHub repositories, `cmakex` can:

- search repositories
- resolve `owner/repo` into a clone URL
- query latest release tags
- list semver-like tags
- fall back to the default branch when no release/tag is available

GitHub API responses are cached under:

```text
~/.cache/cmakex
```

Users can set `GITHUB_TOKEN` to improve rate limits.

## Commands

### `cmakex new <name>`

Creates a new project directory, similar to `cargo new`.

Behavior:

- creates `<name>/`
- refuses non-empty target directories
- writes `CMakeLists.txt`
- writes `cmake/dependencies.cmake`
- writes `src/main.c`
- does not provide `--force`

### `cmakex search <query>`

Searches GitHub repositories by name and description.

Search does not query latest versions by default. This avoids turning one search into many GitHub API calls.

Search results are candidates only. They do not guarantee that a repository supports direct `FetchContent_MakeAvailable(...)`.

### `cmakex latest <name-or-owner/repo>`

Queries GitHub for release/tag candidates.

Resolution order:

1. latest GitHub release
2. semver-like tags
3. default branch

The command prints up to five candidates by default.

### `cmakex install <repo-or-url>[==tag]`

Adds or updates a dependency block in `cmake/dependencies.cmake`.

Supported ref selectors:

```bash
cmakex install fmtlib/fmt==12.1.0
cmakex install fmtlib/fmt --tag 12.1.0
cmakex install owner/repo --branch main
cmakex install owner/repo --commit abc1234
```

`--tag`, `--branch`, and `--commit` are mutually exclusive. CMake stores all of them in `GIT_TAG`, because `FetchContent` accepts tags, branches, and commits in that field.

If no ref is passed for a GitHub repository, `cmakex` chooses:

1. latest GitHub release tag
2. latest semver-like tag
3. default branch

Non-GitHub repositories require an explicit `--tag`, `--branch`, or `--commit`.

By default, `install` runs a probe after writing the dependency file. Use `--no-probe` to only edit CMake.

### `cmakex install --set KEY=VALUE`

`--set` writes CMake cache options before `FetchContent_MakeAvailable(...)`.

Example:

```bash
cmakex install opencv/opencv==4.10.0 --set WITH_IPP=OFF
```

Generated CMake:

```cmake
set(WITH_IPP OFF CACHE BOOL "cmakex option for opencv" FORCE)
FetchContent_MakeAvailable(opencv)
```

`--set` can be repeated.

### `cmakex uninstall <name>`

Removes the matching `FetchContent_Declare(...)` block, generated `set(...)` option lines, and the following `FetchContent_MakeAvailable(name)` call.

### `cmakex list`

Reads local dependencies from `cmake/dependencies.cmake`.

This command is offline. It does not query GitHub.

### `cmakex probe <name>`

Runs CMake configure and uses the CMake File API to inspect generated targets.

Default configure command:

```bash
cmake -S . -B build
```

Dependencies normally land in:

```text
build/_deps/
```

Target detection is best-effort. Some projects expose many internal targets, alias targets can be hard to enumerate, and large projects may require custom options.

### `cmakex build [target]`

Runs:

```bash
cmake -S . -B build
cmake --build build
```

If a target is passed, it is forwarded as:

```bash
cmake --build build --target <target>
```

### `cmakex run [target] [-- args]`

Builds and runs an executable target.

If no target is passed, `cmakex` reads the target name from `project(...)`.

## Link Strategy

`cmakex` does not edit the user's main `CMakeLists.txt` automatically.

Reason: GitHub-first discovery cannot reliably infer the target users should link. Examples:

```cmake
fmt
fmt::fmt
opencv_core
SQLite::SQLite3
zlibstatic
```

Instead, `install` and `probe` print a copyable template:

```cmake
target_link_libraries(hello PRIVATE fmt)
```

On Linux/macOS, when both names are known, they also print:

```bash
printf '\ntarget_link_libraries(hello PRIVATE fmt)\n' >> CMakeLists.txt
```

## Parsing Strategy

`cmakex` intentionally avoids a full CMake AST.

It uses a constrained text parser for standard blocks:

```cmake
FetchContent_Declare(
  name
  GIT_REPOSITORY url
  GIT_TAG ref
)
FetchContent_MakeAvailable(name)
```

The parser is scoped to `cmake/dependencies.cmake`. It is not intended to understand arbitrary CMake metaprogramming.

If users hand-write complex dependency logic, the safest behavior is to leave it alone or require manual maintenance.

## Heavy Projects

Large projects such as OpenCV may not behave like small libraries when embedded through `FetchContent_MakeAvailable(...)`.

Known risk areas:

- internal targets
- optional acceleration backends
- module selection
- platform detection
- long configure/build times
- assumptions made by upstream CMake

For OpenCV, users may need options such as:

```bash
cmakex install opencv/opencv==4.10.0 \
  --set WITH_IPP=OFF \
  --set BUILD_LIST=core,imgproc,imgcodecs \
  --set BUILD_TESTS=OFF \
  --set BUILD_PERF_TESTS=OFF \
  --set BUILD_EXAMPLES=OFF
```

For production OpenCV usage, an installed OpenCV plus `find_package(OpenCV CONFIG REQUIRED)` may be more reliable than direct FetchContent embedding.

## Future Work

Possible next steps:

- curated package hints for common repositories
- known target hints
- package-specific presets, for example OpenCV
- `check` command for Modern CMake linting
- better target ranking after probe
- optional registry provider
- private/local source providers

The central design constraint should remain: standard CMake stays the source of truth.
