# cmakex

`cmakex` is a lightweight, GitHub-first helper for CMake `FetchContent` dependencies.

It does not introduce a package manifest or a custom CMake DSL. The project source of truth remains normal CMake files:

- dependencies are written to `cmake/dependencies.cmake`
- the root `CMakeLists.txt` includes that file
- users still link targets with `target_link_libraries(...)`

`cmakex` is the command name. It is not the system `cmake` command:

```bash
cmakex search fmt
```

## Install

Install as an isolated CLI with `pipx`:

```bash
pipx install "git+https://github.com/trdthg/cmakex.git"
cmakex --help
```

Install as an isolated CLI with `uv`:

```bash
uv tool install "git+https://github.com/trdthg/cmakex.git"
cmakex --help
```

Run without permanently installing with `uvx`:

```bash
uvx --from "git+https://github.com/trdthg/cmakex.git" cmakex --help
```

`uvx` is the short alias for `uv tool run`.

## Quick Start

Create a minimal project:

```bash
cmakex new hello
cd hello
```

Example output:

```text
Created CMake project: hello
  path: /path/to/hello
```

Search for a dependency:

```bash
cmakex search fmt
```

Example output:

```text
repo                              stars  updated     description
--------------------------------  -----  ----------  ----------------------------------------
fmtlib/fmt                        23499  2026-05-20  A modern formatting library
MengRao/fmtlog                    1015   2026-05-14  fmtlog is a performant fmtlib-style...
WGUNDERWOOD/tex-fmt               806    2026-05-20  An extremely fast LaTeX formatter...

Use `cmakex latest owner/repo` to inspect the latest tag before installing.
Search results are GitHub repositories; FetchContent/CMake compatibility is not guaranteed.
```

Inspect release/tag candidates:

```bash
cmakex latest fmtlib/fmt
```

Example output:

```text
fmtlib/fmt
  refs:
    latest: 12.1.0 (GitHub latest release)
    #2: 12.0.0 (semver tag)
    #3: 11.2.0 (semver tag)
    #4: 11.1.4 (semver tag)
    #5: 11.1.3 (semver tag)
```

Install `fmt` at a specific tag:

```bash
cmakex install fmtlib/fmt==12.1.0
```

`install` writes `cmake/dependencies.cmake`, runs a CMake probe by default, downloads the dependency into `build/_deps`, and prints a link template.

Example output:

```text
Installed fmt
  repository: https://github.com/fmtlib/fmt.git
  ref:        12.1.0
  source:     explicit tag shorthand
Detected CMake targets:
  fmt
Next step: add this to your CMakeLists.txt and replace placeholders as needed:

  target_link_libraries(hello PRIVATE fmt)

Copy-paste on Linux/macOS:
  printf '\ntarget_link_libraries(hello PRIVATE fmt)\n' >> CMakeLists.txt
```

Add the link line:

```cmake
target_link_libraries(hello PRIVATE fmt)
```

Or copy-paste the generated shell command on Linux/macOS:

```bash
printf '\ntarget_link_libraries(hello PRIVATE fmt)\n' >> CMakeLists.txt
```

Build and run:

```bash
cmakex run
```

Example output:

```text
-- {fmt} version: 12.1.0
-- Build files have been written to: /path/to/hello/build
[100%] Built target hello
Hello from cmakex
```

## Generated Project

`cmakex new hello` creates:

```text
hello/
├── CMakeLists.txt
├── cmake/
│   └── dependencies.cmake
└── src/
    └── main.c
```

The generated `CMakeLists.txt` enables both C and CXX:

```cmake
cmake_minimum_required(VERSION 3.24)

project(hello C CXX)

include(cmake/dependencies.cmake)

add_executable(hello src/main.c)
```

CXX is enabled because many useful `FetchContent` dependencies expose C++ targets even when your app starts as C.

## Commands

```bash
cmakex new <name>
cmakex search <query>
cmakex latest <name-or-owner/repo>
cmakex install <owner/repo|github-url|git-url>[==tag]
cmakex uninstall <name>
cmakex list
cmakex probe <name>
cmakex build [target]
cmakex run [target] [-- args]
```

### `search`

Searches GitHub repositories:

```bash
cmakex search fmt
```

Search results are GitHub repositories, not curated packages. `cmakex` does not guarantee that every result supports direct `FetchContent_MakeAvailable(...)`.

GitHub API calls are cached under `~/.cache/cmakex`. Set `GITHUB_TOKEN` if you hit rate limits:

```bash
export GITHUB_TOKEN=...
```

### `latest`

Shows latest release/tag candidates:

```bash
cmakex latest fmtlib/fmt
```

Example output:

```text
fmtlib/fmt
  refs:
    latest: 12.1.0 (GitHub latest release)
    #2: 12.0.0 (semver tag)
    #3: 11.2.0 (semver tag)
```

### `install`

Install from GitHub:

```bash
cmakex install fmtlib/fmt==12.1.0
```

Equivalent explicit form:

```bash
cmakex install fmtlib/fmt --tag 12.1.0
```

Other refs:

```bash
cmakex install owner/repo --branch main
cmakex install owner/repo --commit abc1234
```

Override the local dependency name:

```bash
cmakex install sqlite/sqlite --name sqlite3 --tag version-3.46.0
```

Skip the automatic CMake probe:

```bash
cmakex install fmtlib/fmt==12.1.0 --no-probe
```

Pass upstream CMake cache options:

```bash
cmakex install opencv/opencv==4.10.0 --set WITH_IPP=OFF
```

`--set KEY=VALUE` can be repeated.

### `list`

Shows local dependencies without network access:

```bash
cmakex list
```

### `uninstall`

Removes the matching `FetchContent_Declare(...)` block and its `FetchContent_MakeAvailable(...)` call:

```bash
cmakex uninstall fmt
```

### `probe`

Runs CMake configure and tries to detect targets via the CMake File API:

```bash
cmakex probe fmt
```

Default build directory is `build`. Dependencies normally land in:

```text
build/_deps/
```

Use another build directory:

```bash
cmakex probe fmt --build-dir cmake-build-debug
```

### `build`

Configures and builds:

```bash
cmakex build
cmakex build hello
```

### `run`

Builds and runs an executable target:

```bash
cmakex run
cmakex run hello
cmakex run hello -- arg1 arg2
```

If no target is passed, `cmakex` uses the name from `project(...)`.

## Examples

This section is intentionally small and can grow as more repositories are tested.

### CLI11

CLI11 is a C++ command-line parser. It works well with direct FetchContent embedding.

```bash
cmakex install CLIUtils/CLI11==v2.6.2
```

Expected target:

```cmake
target_link_libraries(<your-app> PRIVATE CLI11)
```

### raylib

raylib is a C game programming library. It can be installed from GitHub:

```bash
cmakex install raysan5/raylib==6.0
```

### OpenCV

OpenCV is a large CMake project. It may not behave like a small library when embedded directly with `FetchContent_MakeAvailable(opencv)`.

Basic install:

```bash
cmakex install opencv/opencv==4.10.0
```

If OpenCV fails around IPP internals, for example:

```text
hal/ipp/src/mean_ipp.cpp
fatal error: opencv2/core/base.hpp: No such file or directory
```

the header may exist, but the OpenCV internal `ipphal` target did not receive the expected include path in this embedded build. A practical workaround is to disable IPP:

```bash
rm -rf build
cmakex uninstall opencv
cmakex install opencv/opencv==4.10.0 --set WITH_IPP=OFF
```

For faster and smaller builds, restrict modules:

```bash
rm -rf build
cmakex uninstall opencv
cmakex install opencv/opencv==4.10.0 \
  --set WITH_IPP=OFF \
  --set BUILD_LIST=core,imgproc,imgcodecs \
  --set BUILD_TESTS=OFF \
  --set BUILD_PERF_TESTS=OFF \
  --set BUILD_EXAMPLES=OFF
```

Common module targets:

```cmake
target_link_libraries(<your-app> PRIVATE opencv_core opencv_imgproc opencv_imgcodecs)
```

## CMake Output

For:

```bash
cmakex install fmtlib/fmt==12.1.0
```

`cmakex` writes:

```cmake
include(FetchContent)

FetchContent_Declare(
  fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG 12.1.0
)
FetchContent_MakeAvailable(fmt)
```

With options:

```bash
cmakex install opencv/opencv==4.10.0 --set WITH_IPP=OFF --no-probe
```

`cmakex` writes:

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

## Current Boundaries

`cmakex` is not a full package manager.

It currently does not:

- maintain a package registry
- guarantee GitHub search results are installable
- automatically edit your business `target_link_libraries(...)`
- patch upstream projects
- manage binary packages

The intended workflow is:

1. find a GitHub repo
2. write a standard `FetchContent_Declare(...)`
3. probe for target candidates
4. let the user link the right target in normal CMake

## Test

Run the local test suite:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```
