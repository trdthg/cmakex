import unittest

from cmakex.refs import parse_repo_spec, pick_latest_semver_tag, sort_semver_tags


class RefTests(unittest.TestCase):
    def test_parse_owner_repo_with_shorthand_tag(self):
        spec = parse_repo_spec("fmtlib/fmt==11.0.2")

        self.assertEqual(spec.repository, "https://github.com/fmtlib/fmt.git")
        self.assertEqual(spec.dependency_name, "fmt")
        self.assertEqual(spec.owner, "fmtlib")
        self.assertEqual(spec.repo, "fmt")
        self.assertEqual(spec.shorthand_tag, "11.0.2")

    def test_parse_github_url(self):
        spec = parse_repo_spec("https://github.com/sqlite/sqlite.git", name="sqlite3")

        self.assertEqual(spec.repository, "https://github.com/sqlite/sqlite.git")
        self.assertEqual(spec.dependency_name, "sqlite3")
        self.assertEqual(spec.owner, "sqlite")
        self.assertEqual(spec.repo, "sqlite")

    def test_parse_file_url(self):
        spec = parse_repo_spec("file:///tmp/localdep", name="localdep")

        self.assertEqual(spec.repository, "file:///tmp/localdep")
        self.assertEqual(spec.dependency_name, "localdep")
        self.assertIsNone(spec.owner)
        self.assertIsNone(spec.repo)

    def test_pick_latest_semver_tag(self):
        self.assertEqual(pick_latest_semver_tag(["v1.9.0", "v1.10.0", "nightly"]), "v1.10.0")

    def test_sort_semver_tags(self):
        self.assertEqual(sort_semver_tags(["v1.9.0", "nightly", "v2.0.0", "v1.10.0"]), ["v2.0.0", "v1.10.0", "v1.9.0"])
