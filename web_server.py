import argparse
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import app as pipeline_app


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
OUTPUT_ROOT = PROJECT_ROOT / "outputs"
MAX_BODY_BYTES = 64 * 1024
MAX_PENDING_JOBS = 3
JOB_RETENTION_SECONDS = 60 * 60

_jobs = {}
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="story-to-video",
)


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def parse_job_payload(raw_body):
    if len(raw_body) > MAX_BODY_BYTES:
        raise ValueError("The request body is too large")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("The request must contain valid JSON") from error

    if not isinstance(payload, dict):
        raise ValueError("The request must contain a JSON object")

    topic = payload.get("topic")
    try:
        pipeline_app.validate_topic(topic)
    except (TypeError, ValueError) as error:
        raise ValueError(str(error)) from error

    return topic.strip()


def _active_job_count():
    return sum(
        job["status"] in {"queued", "running"}
        for job in _jobs.values()
    )


def _cleanup_expired_jobs(now=None):
    """Bound the in-memory job registry and remove completed output files."""
    now = time.time() if now is None else now
    expired_paths = []
    with _jobs_lock:
        expired_ids = [
            job_id
            for job_id, job in _jobs.items()
            if job.get("status") not in {"queued", "running"}
            and now - job.get("created_epoch", now) >= JOB_RETENTION_SECONDS
        ]
        for job_id in expired_ids:
            job = _jobs.pop(job_id)
            expired_paths.append(job.get("output_path"))

    for output_path in expired_paths:
        if isinstance(output_path, Path):
            output_path.unlink(missing_ok=True)


def _create_job(topic):
    _cleanup_expired_jobs()
    with _jobs_lock:
        if _active_job_count() >= MAX_PENDING_JOBS:
            raise RuntimeError("The local generation queue is full")

        job_id = uuid.uuid4().hex
        output_path = OUTPUT_ROOT / f"{job_id}.mp4"
        now = _timestamp()
        _jobs[job_id] = {
            "id": job_id,
            "topic": topic,
            "status": "queued",
            "created_at": now,
            "created_epoch": time.time(),
            "updated_at": now,
            "output_path": output_path,
            "error": None,
        }

    _executor.submit(_run_job, job_id, topic, output_path)
    return job_id


def _update_job(job_id, **updates):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job.update(updates)
        job["updated_at"] = _timestamp()


def _run_job(job_id, topic, output_path):
    _update_job(job_id, status="running")

    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        result = pipeline_app.generate_video(topic, str(output_path))

        if not result or not output_path.is_file():
            raise RuntimeError("The pipeline did not produce a video file")

        _update_job(job_id, status="completed", error=None)
    except Exception as error:
        print(f"Job {job_id} failed: {type(error).__name__}: {error}")
        output_path.unlink(missing_ok=True)
        _update_job(
            job_id,
            status="failed",
            error="Video generation failed. Check the server terminal for details.",
        )


def _job_response(job):
    response = {
        "id": job["id"],
        "topic": job["topic"],
        "status": job["status"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }

    if job["status"] == "completed":
        response["download_url"] = f"/api/media/{job['id']}"
    elif job["status"] == "failed":
        response["error"] = job["error"]

    return response


class StoryToVideoHandler(BaseHTTPRequestHandler):
    server_version = "StoryToVideo/1.0"

    def _security_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; media-src 'self'; "
            "script-src 'self'; style-src 'self'; img-src 'self' data:;",
        )

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message, status):
        self._send_json({"error": message}, status)

    def _serve_static(self, filename, content_type):
        path = FRONTEND_ROOT / filename
        if not path.is_file():
            self._send_error_json("Frontend asset not found", HTTPStatus.NOT_FOUND)
            return

        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_media(self, job_id):
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is None or job["status"] != "completed":
                self._send_error_json("Video is not available", HTTPStatus.NOT_FOUND)
                return
            output_path = job["output_path"]

        try:
            output_path = output_path.resolve(strict=True)
            output_path.relative_to(OUTPUT_ROOT.resolve())
        except (FileNotFoundError, OSError, ValueError):
            self._send_error_json("Video is not available", HTTPStatus.NOT_FOUND)
            return

        body_size = output_path.stat().st_size
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(body_size))
        self.end_headers()

        with output_path.open("rb") as media_file:
            while chunk := media_file.read(1024 * 1024):
                self.wfile.write(chunk)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self._security_headers()
        self.end_headers()

    def do_GET(self):
        _cleanup_expired_jobs()
        path = urlsplit(self.path).path

        if path in {"/", "/index.html"}:
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if path == "/styles.css":
            self._serve_static("styles.css", "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._serve_static("app.js", "text/javascript; charset=utf-8")
            return
        if path == "/api/health":
            self._send_json(
                {
                    "status": "ok",
                    "service": "Story to Video AI",
                    "mode": "local",
                    "max_workers": 1,
                    "max_pending_jobs": MAX_PENDING_JOBS,
                }
            )
            return

        if path.startswith("/api/jobs/"):
            job_id = unquote(path.removeprefix("/api/jobs/"))
            with _jobs_lock:
                job = _jobs.get(job_id)
                response = _job_response(job) if job else None
            if response is None:
                self._send_error_json("Job not found", HTTPStatus.NOT_FOUND)
            else:
                self._send_json(response)
            return

        if path.startswith("/api/media/"):
            job_id = unquote(path.removeprefix("/api/media/"))
            self._serve_media(job_id)
            return

        self._send_error_json("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path != "/api/jobs":
            self._send_error_json("Not found", HTTPStatus.NOT_FOUND)
            return

        content_length = self.headers.get("Content-Length")
        try:
            body_length = int(content_length)
        except (TypeError, ValueError):
            self._send_error_json("Content-Length is required", HTTPStatus.LENGTH_REQUIRED)
            return

        if body_length < 0 or body_length > MAX_BODY_BYTES:
            self._send_error_json("The request body is too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return

        try:
            raw_body = self.rfile.read(body_length)
            topic = parse_job_payload(raw_body)
            job_id = _create_job(topic)
        except ValueError as error:
            self._send_error_json(str(error), HTTPStatus.BAD_REQUEST)
            return
        except RuntimeError as error:
            self._send_error_json(str(error), HTTPStatus.TOO_MANY_REQUESTS)
            return

        self._send_json(
            {"id": job_id, "status": "queued", "topic": topic},
            HTTPStatus.ACCEPTED,
        )

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")


def main():
    parser = argparse.ArgumentParser(
        description="Run the local Story to Video AI web interface."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        choices=("127.0.0.1", "localhost"),
        help="Local interface host; remote binding is intentionally disabled",
    )
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), StoryToVideoHandler)
    print(f"Story to Video AI running at http://127.0.0.1:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Story to Video AI")
    finally:
        server.server_close()
        _executor.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
