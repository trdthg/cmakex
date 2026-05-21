from pathlib import Path
import unittest


from cmakex.errors import CmakexError
from cmakex.templates import create_project, init_project


class InitProjectTests(unittest.TestCase):
    def test_init_project(self):
        with TemporaryDirectoryPath() as tmp_path:
            init_project(tmp_path, "demo")

            self.assertTrue((tmp_path / "CMakeLists.txt").exists())
            self.assertTrue((tmp_path / "cmake" / "dependencies.cmake").exists())
            self.assertTrue((tmp_path / "src" / "main.c").exists())
            cmakelists = (tmp_path / "CMakeLists.txt").read_text(encoding="utf-8")
            self.assertIn("project(demo C CXX)", cmakelists)

    def test_init_project_refuses_overwrite(self):
        with TemporaryDirectoryPath() as tmp_path:
            (tmp_path / "CMakeLists.txt").write_text("project(existing)\n", encoding="utf-8")

            with self.assertRaises(CmakexError):
                init_project(tmp_path, "demo")

    def test_create_project_creates_named_directory(self):
        with TemporaryDirectoryPath() as tmp_path:
            project_root = create_project(tmp_path, "demo")

            self.assertEqual(project_root, tmp_path / "demo")
            self.assertTrue((project_root / "CMakeLists.txt").exists())

    def test_create_project_refuses_non_empty_directory(self):
        with TemporaryDirectoryPath() as tmp_path:
            project_root = tmp_path / "demo"
            project_root.mkdir()
            (project_root / "README.md").write_text("exists\n", encoding="utf-8")

            with self.assertRaises(CmakexError):
                create_project(tmp_path, "demo")


class TemporaryDirectoryPath:
    def __enter__(self):
        import tempfile

        self._directory = tempfile.TemporaryDirectory()
        return Path(self._directory.name)

    def __exit__(self, exc_type, exc, traceback):
        self._directory.cleanup()
