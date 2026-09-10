import unittest
from unittest.mock import patch

from utility.render.render_engine import _find_imagemagick, download_file


class ImageMagickTests(unittest.TestCase):
    def test_rejects_http_video_url(self):
        with self.assertRaises(ValueError):
            download_file(
                "http://videos.pexels.com/video-files/dummy.mp4",
                "unused.mp4",
            )

    @patch("utility.render.render_engine.platform.system", return_value="Windows")
    @patch("utility.render.render_engine.subprocess.run")
    @patch(
        "utility.render.render_engine.get_program_path",
        side_effect=["C:\\ImageMagick\\magick.exe", None],
    )
    def test_finds_magick_on_windows(self, get_program_path, run, system):
        run.return_value.stdout = "Version: ImageMagick 7.1"
        run.return_value.stderr = ""

        result = _find_imagemagick()

        self.assertEqual(result, "C:\\ImageMagick\\magick.exe")
        get_program_path.assert_called_once_with("magick")
        run.assert_called_once()

    @patch("utility.render.render_engine.platform.system", return_value="Windows")
    @patch("utility.render.render_engine.subprocess.run")
    @patch(
        "utility.render.render_engine.get_program_path",
        return_value="C:\\Windows\\System32\\convert.exe",
    )
    def test_does_not_use_non_imagemagick_windows_convert(
        self,
        get_program_path,
        run,
        system,
    ):
        run.return_value.stdout = "Windows Convert Utility"
        run.return_value.stderr = ""

        self.assertIsNone(_find_imagemagick())


if __name__ == "__main__":
    unittest.main()
