import unittest

from experiments.claude.validate import valid_bbox, validate


class GeometryTests(unittest.TestCase):
    def test_rejects_observed_coordinate_failure(self):
        self.assertFalse(valid_bbox([299, 762, 735, 1123]))

    def test_nonfinite_degenerate_and_boolean_coordinates(self):
        for box in ([0, 0, float("nan"), 10], [0, 0, 0, 10], [False, 0, 1, 1]):
            with self.subTest(box=box):
                self.assertFalse(valid_bbox(box))

    def test_accepts_page_boundary(self):
        self.assertTrue(valid_bbox([0, 0, 1000, 1000]))

    def test_complete_flag_does_not_bypass_missing_fields(self):
        errors = validate(
            {
                "page_complete": True,
                "items": [
                    {"id": "a", "type": "story", "regions": [], "quality_flags": []}
                ],
                "unreadable_regions": [],
            }
        )
        self.assertTrue(any("continuation_marker" in error for error in errors))
