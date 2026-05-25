import sys
import unittest
from unittest.mock import patch

from cmakex.cli import build_parser, can_print_append_command, infer_upstream_link_target


class CliTests(unittest.TestCase):
    def test_run_program_args_after_double_dash(self):
        args = build_parser().parse_args(["run", "--", "--name", "CLI11"])

        self.assertEqual(args.command, "run")
        self.assertEqual(args.target, "--name")
        self.assertEqual(args.program_args, ["CLI11"])

    def test_single_target_is_used_as_link_target(self):
        self.assertEqual(infer_upstream_link_target(["CLI11"]), "CLI11")

    def test_multiple_targets_use_placeholder(self):
        self.assertEqual(infer_upstream_link_target(["opencv_core", "opencv_imgproc"]), "<target>")

    def test_append_command_allows_upstream_placeholder(self):
        with patch.object(sys, "platform", "linux"):
            self.assertTrue(can_print_append_command("hello", "<target>"))
