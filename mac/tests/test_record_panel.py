import unittest

from record_panel import clamp_origin

VISIBLE = (54.0, 0.0, 1458.0, 949.0)  # x, y, width, height
SIZE = (168.0, 52.0)


class ClampOriginTests(unittest.TestCase):
    def test_origin_inside_visible_frame_is_unchanged(self):
        self.assertEqual(clamp_origin((300.0, 200.0), SIZE, VISIBLE), (300.0, 200.0))

    def test_origin_past_right_edge_is_pulled_back(self):
        # Reproduces the dragged-to-the-corner case: only a sliver was visible.
        self.assertEqual(
            clamp_origin((1500.0, 897.0), SIZE, VISIBLE),
            (54.0 + 1458.0 - 168.0, 897.0),
        )

    def test_origin_past_top_edge_is_pulled_down(self):
        self.assertEqual(
            clamp_origin((300.0, 940.0), SIZE, VISIBLE),
            (300.0, 949.0 - 52.0),
        )

    def test_origin_left_of_or_below_visible_frame_is_pulled_in(self):
        self.assertEqual(clamp_origin((-500.0, -80.0), SIZE, VISIBLE), (54.0, 0.0))

    def test_panel_larger_than_screen_is_pinned_to_origin(self):
        self.assertEqual(
            clamp_origin((10.0, 10.0), (5000.0, 5000.0), VISIBLE),
            (54.0, 0.0),
        )
