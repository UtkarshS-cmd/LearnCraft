import pathlib
import unittest


class AppStructureTests(unittest.TestCase):
    def test_expected_directories_exist(self):
        # File lives at backend/tests/unit/; project root is three levels up
        # (repo layout keeps frontend/ at the project root, not backend/).
        root = pathlib.Path(__file__).resolve().parents[3]
        backend = root / "backend"
        required = [
            backend / "app",
            backend / "app" / "api",
            backend / "app" / "core",
            backend / "app" / "database",
            backend / "app" / "models",
            backend / "app" / "repositories",
            backend / "app" / "services",
            root / "frontend",
            backend / "docs",
            backend / "scripts",
            backend / "tests",
        ]
        for directory in required:
            self.assertTrue(directory.exists(), f"Missing directory: {directory}")


if __name__ == "__main__":
    unittest.main()
