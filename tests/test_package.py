import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_validator", ROOT / "scripts" / "validate_package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class PackageTest(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in package.REQUIRED:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}" if path.suffix == ".json" else "content\n", encoding="utf-8")
        (root / "SKILL.md").write_text(
            '---\nname: agent-orchestrator\ndescription: "test skill"\n---\nBody.\n', encoding="utf-8")
        return root

    def test_package_files_and_links(self):
        self.assertEqual([], package.validate(ROOT))

    def test_missing_required_file_is_detected(self):
        root = self.fixture()
        (root / "references" / "ledger.md").unlink()
        self.assertTrue(any("Missing required" in e for e in package.validate(root)))

    def test_broken_link_is_detected(self):
        root = self.fixture()
        (root / "README.md").write_text("[missing](missing.md)", encoding="utf-8")
        self.assertTrue(any("Broken/escaping" in e for e in package.validate(root)))

    def test_link_cannot_escape_package(self):
        root = self.fixture()
        (root / "README.md").write_text("[outside](../)", encoding="utf-8")
        self.assertTrue(any("Broken/escaping" in e for e in package.validate(root)))

    def test_private_path_is_detected(self):
        root = self.fixture()
        (root / "README.md").write_text("Local path: /Users/example/private", encoding="utf-8")
        self.assertTrue(any("Private path" in e for e in package.validate(root)))

    def test_invalid_json_is_detected(self):
        root = self.fixture()
        (root / "examples" / "accepted-run.json").write_text("broken json", encoding="utf-8")
        self.assertTrue(any("Invalid JSON" in e for e in package.validate(root)))


if __name__ == "__main__":
    unittest.main()
