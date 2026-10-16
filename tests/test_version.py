import re
import unittest
from pathlib import Path

import gzw_data

ROOT = Path(__file__).resolve().parent.parent


class VersionTests(unittest.TestCase):
    def test_package_and_pyproject_versions_match(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(gzw_data.__version__, match.group(1))

    def test_user_agent_carries_the_version(self):
        source = (ROOT / "gzw_data" / "client.py").read_text(encoding="utf-8")
        match = re.search(r'user_agent: str = "gzw-data-python/([^"]+)"', source)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), gzw_data.__version__)


if __name__ == "__main__":
    unittest.main()
