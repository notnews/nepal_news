import unittest

from experiments.text_layer.extract import (
    FROM_RE,
    JUMP_RE,
    find_jump,
    link_continuations,
)


class ContinuationTests(unittest.TestCase):
    def test_printed_page_cues(self):
        for text, pattern, expected in [
            ("बाँकी पृष्ठ १२", JUMP_RE, 12),
            ("Contd on Pg 3", JUMP_RE, 3),
            ("पृष्ठ १ बाट", FROM_RE, 1),
            ("Contd from Pg 1", FROM_RE, 1),
            ("No continuation cue", JUMP_RE, None),
        ]:
            with self.subTest(text=text):
                self.assertEqual(find_jump(text, pattern), expected)

    def test_explicit_reciprocal_link(self):
        stories = [
            {
                "paper": "TKP",
                "date": "2009-01-08",
                "page": 1,
                "headline": "Congress demands",
                "body": "Report. Contd on Pg 3",
                "salience": {"bbox": [10, 200, 100, 500]},
            },
            {
                "page": 3,
                "headline": "Congress demands",
                "body": "Contd from Pg 1. Further reporting.",
            },
        ]
        result = link_continuations(stories)
        self.assertEqual(result[0]["story_id"], result[1]["story_id"])
        self.assertEqual([s["part"] for s in result], [1, 2])

    def test_missing_target_is_unresolved(self):
        story = {"page": 1, "headline": "Report", "body": "Contd on Pg 3"}
        result = link_continuations([story])[0]
        self.assertEqual(result["continued_to_page"], 3)
        self.assertNotIn("story_id", result)
