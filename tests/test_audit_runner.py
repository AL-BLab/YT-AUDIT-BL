import unittest

from web.services.audit_runner import (
    extract_summary_metrics,
    normalize_channel_url,
    validate_channel_url,
)


class AuditRunnerTests(unittest.TestCase):
    def test_normalize_channel_url_forces_https(self):
        self.assertEqual(
            normalize_channel_url("http://youtube.com/@ChrisCappy/"),
            "https://youtube.com/@ChrisCappy",
        )

    def test_validate_channel_url(self):
        self.assertTrue(validate_channel_url("https://youtube.com/@channelname"))
        self.assertTrue(validate_channel_url("https://youtube.com/channel/UCabcdefghijk"))
        self.assertFalse(validate_channel_url("https://example.com/not-youtube"))

    def test_extract_summary_metrics(self):
        analysis = {
            "channelHealthScore": 72,
            "summary": {
                "highPriority": 1,
                "mediumPriority": 2,
                "lowPriority": 3,
                "videosAnalyzed": 30,
            },
        }
        metrics = extract_summary_metrics(analysis)
        self.assertEqual(metrics["summary_health_score"], 72)
        self.assertEqual(metrics["summary_high_priority"], 1)
        self.assertEqual(metrics["summary_medium_priority"], 2)
        self.assertEqual(metrics["summary_low_priority"], 3)


if __name__ == "__main__":
    unittest.main()
