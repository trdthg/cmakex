from pathlib import Path
import tempfile
import unittest

from cmakex.build import infer_project_name
from cmakex.templates import init_project


class BuildTests(unittest.TestCase):
    def test_infer_project_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, "demo")

            self.assertEqual(infer_project_name(root), "demo")
