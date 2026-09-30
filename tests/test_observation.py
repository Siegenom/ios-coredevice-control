import io
import unittest
from types import SimpleNamespace

from PIL import Image

from ipad_hybrid_control.operations import difference_score
from ipad_hybrid_control.semantic import caption_of


def png(color):
    buffer = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(buffer, "PNG")
    return buffer.getvalue()


class ObservationTests(unittest.TestCase):
    def test_identical_images_have_zero_change(self):
        image = png("white")
        self.assertEqual(difference_score(image, image), 0.0)

    def test_different_images_have_large_change(self):
        self.assertGreater(difference_score(png("black"), png("white")), 0.9)

    def test_caption_prefers_caption_and_falls_back_to_spoken_description(self):
        self.assertEqual(caption_of(SimpleNamespace(caption=" Wi-Fi ", spoken_description="other")), "Wi-Fi")
        self.assertEqual(caption_of(SimpleNamespace(caption="", spoken_description=" General ")), "General")


if __name__ == "__main__":
    unittest.main()
