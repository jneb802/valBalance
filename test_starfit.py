import unittest

from starfit import closest_stars


class StarFitTests(unittest.TestCase):
    def test_nearest_health_and_tie(self):
        self.assertEqual(closest_stars(150, 3472)["stars"], 22)
        self.assertEqual(closest_stars(100, 150)["stars"], 0)

    def test_clamps_to_supported_range(self):
        self.assertEqual(closest_stars(100, 50)["stars"], 0)
        self.assertEqual(closest_stars(100, 10000, max_stars=2)["stars"], 2)

    def test_zero_health_rejected(self):
        with self.assertRaises(ValueError):
            closest_stars(0, 100)
