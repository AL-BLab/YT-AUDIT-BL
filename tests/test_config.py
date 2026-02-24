import os
import unittest

from web.config import AppConfig


class ConfigTests(unittest.TestCase):
    def test_default_retention_days(self):
        previous = os.environ.get("RETENTION_DAYS")
        if "RETENTION_DAYS" in os.environ:
            del os.environ["RETENTION_DAYS"]
        try:
            config = AppConfig.from_env()
            self.assertEqual(config.retention_days, 180)
        finally:
            if previous is not None:
                os.environ["RETENTION_DAYS"] = previous


if __name__ == "__main__":
    unittest.main()
