import unittest

from ipad_hybrid_control.operations import hid_point


class CoordinateTests(unittest.TestCase):
    def test_hid_corners(self):
        cases = [
            ("portrait", (0, 0), (1640, 2360), (0, 0)),
            ("portrait", (1639, 2359), (1640, 2360), (65535, 65535)),
            ("portraitUpsideDown", (0, 0), (1640, 2360), (65535, 65535)),
            ("landscapeLeft", (0, 0), (2360, 1640), (65535, 0)),
            ("landscapeRight", (0, 0), (2360, 1640), (0, 65535)),
        ]
        for orientation, point, size, expected in cases:
            with self.subTest(orientation=orientation, point=point):
                self.assertEqual(hid_point(orientation, *point, *size), expected)

    def test_rejects_out_of_bounds_coordinate(self):
        with self.assertRaises(ValueError):
            hid_point("portrait", 2000, 10, 1640, 2360)


if __name__ == "__main__":
    unittest.main()
