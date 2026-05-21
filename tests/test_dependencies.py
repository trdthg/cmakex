from pathlib import Path
import tempfile
import unittest

from cmakex.dependencies import (
    parse_dependencies,
    read_dependencies,
    uninstall_dependency,
    upsert_dependency,
)


class DependencyTests(unittest.TestCase):
    def test_parse_dependencies_with_targets(self):
        text = """include(FetchContent)

# cmakex: targets fmt::fmt; fmt
FetchContent_Declare(
  fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG 11.0.2
)
FetchContent_MakeAvailable(fmt)
"""

        dependencies = parse_dependencies(text)

        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependencies[0].name, "fmt")
        self.assertEqual(dependencies[0].repository, "https://github.com/fmtlib/fmt.git")
        self.assertEqual(dependencies[0].ref, "11.0.2")
        self.assertEqual(dependencies[0].targets, ("fmt::fmt", "fmt"))

    def test_parse_dependencies_with_options(self):
        text = """include(FetchContent)

# cmakex: option BUILD_TESTS=OFF
FetchContent_Declare(
  fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG 11.0.2
)
set(BUILD_TESTS OFF CACHE BOOL "cmakex option for fmt" FORCE)
FetchContent_MakeAvailable(fmt)
"""

        dependencies = parse_dependencies(text)

        self.assertEqual(dependencies[0].options, ("BUILD_TESTS=OFF",))

    def test_upsert_dependency_creates_file(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            action = upsert_dependency(
                tmp_path,
                "fmt",
                "https://github.com/fmtlib/fmt.git",
                "11.0.2",
                options=("BUILD_TESTS=OFF",),
            )

            self.assertEqual(action, "installed")
            dependencies = read_dependencies(tmp_path)
            self.assertEqual(dependencies[0].name, "fmt")
            self.assertEqual(dependencies[0].ref, "11.0.2")
            self.assertEqual(dependencies[0].options, ("BUILD_TESTS=OFF",))

    def test_upsert_dependency_updates_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            upsert_dependency(tmp_path, "fmt", "https://github.com/fmtlib/fmt.git", "11.0.2")
            action = upsert_dependency(tmp_path, "fmt", "https://github.com/fmtlib/fmt.git", "11.1.0")

            self.assertEqual(action, "updated")
            dependencies = read_dependencies(tmp_path)
            self.assertEqual(len(dependencies), 1)
            self.assertEqual(dependencies[0].ref, "11.1.0")

    def test_uninstall_dependency_removes_declare_and_make_available(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            upsert_dependency(
                tmp_path,
                "fmt",
                "https://github.com/fmtlib/fmt.git",
                "11.0.2",
                options=("BUILD_TESTS=OFF",),
            )

            uninstall_dependency(tmp_path, "fmt")

            text = (tmp_path / "cmake" / "dependencies.cmake").read_text(encoding="utf-8")
            self.assertNotIn("FetchContent_Declare", text)
            self.assertNotIn("FetchContent_MakeAvailable", text)
            self.assertNotIn("set(BUILD_TESTS", text)
