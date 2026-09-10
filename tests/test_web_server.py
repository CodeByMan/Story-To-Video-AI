import json
import tempfile
import unittest
from pathlib import Path

from web_server import (
    JOB_RETENTION_SECONDS,
    MAX_BODY_BYTES,
    _cleanup_expired_jobs,
    _job_response,
    _jobs,
    parse_job_payload,
)


class WebServerTests(unittest.TestCase):
    def test_accepts_valid_global_topic(self):
        raw_body = json.dumps({"topic": "The Eiffel Tower and modern Paris"}).encode()

        self.assertEqual(parse_job_payload(raw_body), "The Eiffel Tower and modern Paris")

    def test_rejects_malformed_json(self):
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            parse_job_payload(b"not-json")

    def test_rejects_non_english_topic(self):
        raw_body = json.dumps({"topic": "La historia de París"}).encode()

        with self.assertRaises(ValueError):
            parse_job_payload(raw_body)

    def test_rejects_overlong_topic(self):
        raw_body = json.dumps({"topic": "A" * 501}).encode()

        with self.assertRaisesRegex(ValueError, "500 characters"):
            parse_job_payload(raw_body)

    def test_rejects_oversized_request(self):
        with self.assertRaisesRegex(ValueError, "too large"):
            parse_job_payload(b"x" * (MAX_BODY_BYTES + 1))

    def test_job_response_does_not_expose_output_path(self):
        job = {
            "id": "job-123",
            "topic": "A story about Germany",
            "status": "completed",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:01:00+00:00",
            "output_path": "C:/private/outputs/job-123.mp4",
            "error": None,
        }

        response = _job_response(job)

        self.assertEqual(response["download_url"], "/api/media/job-123")
        self.assertNotIn("output_path", response)

    def test_cleanup_removes_expired_terminal_jobs_and_media(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "expired.mp4"
            output_path.write_bytes(b"video")
            job_id = "expired-job"
            _jobs[job_id] = {
                "status": "completed",
                "created_epoch": 100.0,
                "output_path": output_path,
            }
            try:
                _cleanup_expired_jobs(now=100.0 + JOB_RETENTION_SECONDS)
                self.assertNotIn(job_id, _jobs)
                self.assertFalse(output_path.exists())
            finally:
                _jobs.pop(job_id, None)


if __name__ == "__main__":
    unittest.main()
