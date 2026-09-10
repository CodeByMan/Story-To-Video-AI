import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class DummyConfig:
    def get_video_orientation(self):
        return False


async def dummy_generate_audio(text, output_path):
    return None


class PipelineSmokeTests(unittest.TestCase):
    def test_pipeline_orchestration_without_external_apis(self):
        output_path = Path(tempfile.gettempdir()) / "global-smoke.mp4"
        captions = [((0, 1), "France history")]
        queries = [[[0, 1], ["Paris heritage"]]]
        video_urls = [[[0, 1], "https://videos.pexels.com/video-files/dummy.mp4"]]

        with patch.object(app, "get_config", return_value=DummyConfig()), \
             patch.object(app, "generate_script", return_value="France history"), \
             patch.object(app, "generate_audio", new=dummy_generate_audio), \
             patch.object(app, "generate_timed_captions", return_value=captions), \
             patch.object(app, "getVideoSearchQueriesTimed", return_value=queries), \
             patch.object(app, "generate_video_url", return_value=video_urls), \
             patch.object(app, "merge_empty_intervals", side_effect=lambda urls: urls), \
             patch.object(app, "get_output_media", return_value=str(output_path)) as render:
            result = app.generate_video(
                "History of France",
                str(output_path),
            )

        self.assertEqual(result, str(output_path))
        render.assert_called_once()


if __name__ == "__main__":
    unittest.main()
