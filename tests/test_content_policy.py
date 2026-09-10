import unittest

from utility.content_policy import (
    validate_english_visual_query,
    validate_script,
    validate_topic,
)


class ContentPolicyTests(unittest.TestCase):
    def assert_rejected(self, validator, value):
        with self.assertRaises(ValueError):
            validator(value)

    def test_accepts_global_topics(self):
        for topic in (
            "History of Pakistan",
            "History of India",
            "Culture of Bangladesh",
            "The Eiffel Tower in France",
            "Russian space exploration",
            "German engineering",
            "Saudi Arabian architecture",
            "Modern cities in the UAE",
            "The United Kingdom coastline",
        ):
            validate_topic(topic)

    def test_accepts_mixed_country_topic(self):
        validate_topic("Comparing France and Germany landmarks")

    def test_rejects_empty_or_non_english_topic(self):
        self.assert_rejected(validate_topic, "")
        self.assert_rejected(validate_topic, "Paris skyline – travel")

    def test_rejects_non_english_script(self):
        self.assert_rejected(
            validate_script,
            "پاکستان has diverse landscapes.",
        )

    def test_accepts_global_visual_query(self):
        validate_english_visual_query("Paris skyline")
        validate_english_visual_query("Dhaka street market")

    def test_rejects_non_english_visual_query(self):
        self.assert_rejected(
            validate_english_visual_query,
            "Paris skyline – travel",
        )


if __name__ == "__main__":
    unittest.main()
