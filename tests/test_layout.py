import importlib.util
import sys
import unittest
from pathlib import Path

LAYOUT = Path(__file__).resolve().parents[1] / "experiments/layout"
spec = importlib.util.spec_from_file_location("run", LAYOUT / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
sys.modules["run"] = run
spec = importlib.util.spec_from_file_location("layout_evaluate", LAYOUT / "evaluate.py")
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


class LayoutTests(unittest.TestCase):
    def test_pixel_point_roundtrip(self):
        box = [30, 60, 210, 330]
        points = run.to_pdf(box, [900, 1200], [450, 600])
        self.assertEqual(points, [15, 30, 105, 165])
        self.assertEqual(run.to_pdf(points, [450, 600], [900, 1200]), box)

    def test_observed_geometry_failures_are_flagged(self):
        self.assertEqual(
            run.geometry_flags([946, 75, 946, 1125], [946, 1488]), ["degenerate_bbox"]
        )
        self.assertEqual(
            run.geometry_flags([-0.76, 693, 945, 1453], [946, 1488]),
            ["out_of_page_bbox"],
        )
        self.assertEqual(run.geometry_flags([0, 0, 946, 1488], [946, 1488]), [])

    def test_matching_does_not_reuse_reference(self):
        box = [0, 0, 10, 10]
        self.assertEqual(len(evaluate.match([box, box], [box])), 1)

    def test_matching_avoids_greedy_loss(self):
        predicted = [[0, 0, 15, 10], [0, 0, 10, 10]]
        reference = [[0, 0, 10, 10], [5, 0, 15, 10]]
        self.assertEqual(len(evaluate.match(predicted, reference)), 2)

    def test_cross_story_merge_and_unassigned_region(self):
        result = {
            "regions": [
                {
                    "region_id": "r0",
                    "bbox": [0, 0, 30, 10],
                    "label": "text",
                    "article_id": None,
                }
            ]
        }
        reference = [
            {"label": "body", "article_id": 1, "bbox": [0, 0, 10, 10]},
            {"label": "body", "article_id": 2, "bbox": [20, 0, 30, 10]},
        ]
        score = evaluate.score(result, reference)
        self.assertEqual(score["cross_article_merge_candidates"], ["r0"])
        self.assertEqual(score["unmatched_editorial_regions"], 2)
        self.assertIsNone(result["regions"][0]["article_id"])

    def test_coverage_deduplicates_and_accepts_fragments(self):
        target = [0, 0, 10, 10]
        boxes = [[0, 0, 5, 10], [5, 0, 10, 10], [0, 0, 5, 10]]
        self.assertEqual(evaluate.covered_area(target, boxes), 100)
        self.assertEqual(evaluate.covered_area(target, [[20, 0, 30, 10]]), 0)

    def test_empty_detector_is_not_perfect_precision(self):
        score = evaluate.score(
            {"regions": []},
            [{"label": "body", "article_id": 1, "bbox": [0, 0, 10, 10]}],
        )
        self.assertEqual(score["precision_iou50"], 0)
        self.assertEqual(score["recall_iou50"], 0)


if __name__ == "__main__":
    unittest.main()
