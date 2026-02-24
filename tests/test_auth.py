import unittest

from web.auth import parse_iap_email


class AuthTests(unittest.TestCase):
    def test_parse_iap_email_with_provider_prefix(self):
        self.assertEqual(
            parse_iap_email("accounts.google.com:person@brainlabsdigital.com"),
            "person@brainlabsdigital.com",
        )

    def test_parse_iap_email_plain_value(self):
        self.assertEqual(
            parse_iap_email("person@brainlabsdigital.com"),
            "person@brainlabsdigital.com",
        )


if __name__ == "__main__":
    unittest.main()
