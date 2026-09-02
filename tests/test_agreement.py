import sys
import unittest
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1] / "experiments/layout"
sys.path.insert(0, str(DIRECTORY))
import agreement  # noqa: E402


def region(name, box, label):
    return {"region_id": name, "bbox": box, "label": label}


class AgreementTests(unittest.TestCase):
    def test_union_does_not_fill_gap(self):
        target = [0, 0, 10, 10]
        pieces = [[0, 0, 2, 10], [8, 0, 10, 10]]
        self.assertAlmostEqual(agreement.union_iou(target, pieces), 0.4)

    def test_union_does_not_double_count_overlap(self):
        self.assertEqual(agreement.union_area([[0, 0, 8, 10], [2, 0, 10, 10]]), 100)

    def test_grouping_preserves_exclusive_ownership(self):
        american = [
            region("a", [0, 0, 10, 10], "article"),
            region("b", [0, 0, 20, 10], "article"),
        ]
        paddle = [
            region("p1", [0, 0, 5, 10], "text"),
            region("p2", [5, 0, 10, 10], "text"),
        ]
        output = agreement.proposals(american, paddle, [20, 10])
        a = output[0]
        self.assertEqual(a["union_iou"], 1)
        self.assertEqual(a["match_type"], "group")
        self.assertTrue(agreement.accepts(a, 0.9))
        self.assertFalse(agreement.accepts(output[1], 0.9))

    def test_identical_geometry_with_wrong_role_is_not_agreement(self):
        output = agreement.proposals(
            [region("a", [0, 0, 10, 10], "headline")],
            [region("p", [0, 0, 10, 10], "image")],
            [10, 10],
        )[0]
        self.assertEqual(output["union_iou"], 1)
        self.assertFalse(agreement.accepts(output, 0.8))

    def test_contained_conflicting_role_blocks_acceptance(self):
        output = agreement.proposals(
            [region("a", [0, 0, 10, 10], "article")],
            [
                region("p", [0, 0, 10, 10], "text"),
                region("q", [2, 2, 4, 4], "paragraph_title"),
            ],
            [10, 10],
        )[0]
        self.assertEqual(output["internal_role_conflicts"], ["q"])
        self.assertFalse(agreement.accepts(output, 0.8))

    def test_zero_width_detection_is_excluded(self):
        output = agreement.proposals(
            [region("a", [10, 0, 10, 10], "article")], [], [10, 10]
        )
        self.assertEqual(output, [])


if __name__ == "__main__":
    unittest.main()
