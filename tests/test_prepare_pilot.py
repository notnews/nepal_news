import unittest

from experiments.claude.prepare import tile_boxes


class TileTests(unittest.TestCase):
    def test_odd_dimensions_have_complete_coverage(self):
        width, height = 17, 23
        boxes = tile_boxes(width, height)
        self.assertEqual(len(boxes), 6)
        for x0, y0, x1, y1 in boxes:
            self.assertTrue(0 <= x0 < x1 <= width)
            self.assertTrue(0 <= y0 < y1 <= height)
        for x in range(width):
            for y in range(height):
                self.assertTrue(
                    any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in boxes)
                )

    def test_adjacent_tiles_overlap(self):
        boxes = tile_boxes(1971, 3100)
        self.assertGreater(boxes[0][2], boxes[1][0])
        self.assertGreater(boxes[0][3], boxes[2][1])
