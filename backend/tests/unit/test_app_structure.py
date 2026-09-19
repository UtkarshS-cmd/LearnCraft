import pathlib
import unittest


class AppStructureTests(unittest.TestCase):
    def test_expected_directories_exist(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        required = [
            root / "app",
            root / "app" / "api",
            root / "app" / "core",
            root / "app" / "database",
            root / "app" / "models",
            root / "app" / "repositories",
            root / "app" / "services",
            root / "frontend",
            root / "docs",
            root / "scripts",
            root / "tests",
        ]
        for directory in required:
            self.assertTrue(directory.exists(), f"Missing directory: {directory}")


if __name__ == "__main__":
    unittest.main()
