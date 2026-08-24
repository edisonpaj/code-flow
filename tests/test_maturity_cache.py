import tempfile
import unittest
from pathlib import Path

from backend.analyzer.maturity_cache import MaturityCache


class MaturityCacheTest(unittest.TestCase):
    def test_saves_and_recovers_latest_report(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = MaturityCache(Path(temp))
            report = {"score": 73, "context": {"project_path": "C:/labs/client", "project_name": "client"}, "dimensions": [{"dimension_id": "SOLID"}]}
            saved = cache.save(report)
            latest = cache.latest()
            project = cache.latest("C:/labs/client")
            self.assertTrue(saved["cached"])
            self.assertEqual(latest["score"], 73)
            self.assertEqual(project["context"]["project_name"], "client")
            self.assertEqual(latest["cache_version"], "1.0")


if __name__ == "__main__": unittest.main()
