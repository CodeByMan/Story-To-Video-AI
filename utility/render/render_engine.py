import os
import platform
import subprocess
import tempfile
from urllib.parse import urlparse

import requests
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
)
from utility.config import get_config


DOWNLOAD_TIMEOUT_SECONDS = 30
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_VIDEO_HOSTS = {"videos.pexels.com"}


def download_file(url, filename):
    parsed_url = urlparse(url)

    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError("Background video URL must use HTTPS")

    if parsed_url.hostname not in ALLOWED_VIDEO_HOSTS:
        raise ValueError("Background video URL must come from Pexels")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        stream=True,
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
        allow_redirects=False,
    )

    if response.is_redirect or response.is_permanent_redirect:
        raise ValueError("Background video redirects are not supported")

    response.raise_for_status()

    content_length = response.headers.get("Content-Length")

    if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Background video exceeds the 100 MB download limit")

    downloaded_bytes = 0

    with open(filename, "wb") as output_file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue

            downloaded_bytes += len(chunk)

            if downloaded_bytes > MAX_DOWNLOAD_BYTES:
                raise ValueError(
                    "Background video exceeds the 100 MB download limit"
                )

            output_file.write(chunk)


def search_program(program_name):
    try:
        search_cmd = "where" if platform.system() == "Windows" else "which"
        return subprocess.check_output(
            [search_cmd, program_name]
        ).decode().strip()
    except subprocess.CalledProcessError:
        return None


def get_program_path(program_name):
    return search_program(program_name)


def _find_imagemagick():
    program_names = ["magick"]
    if platform.system() != "Windows":
        program_names.append("convert")

    for program_name in program_names:
        program_path = get_program_path(program_name)
        if not program_path:
            continue

        try:
            version = subprocess.run(
                [program_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue

        output = f"{version.stdout}\n{version.stderr}"
        if "ImageMagick" in output:
            return program_path

    return None


def _get_caption_position(
    caption_position,
    video_size,
    font_size,
    stroke_width,
):
    _, height = video_size
    margin = max(20, int(font_size * 0.35))
    top_y = margin
    center_y = max(0, int((height - font_size) / 2))
    bottom_y = max(
        margin,
        height - font_size - (stroke_width * 2) - margin,
    )

    positions = {
        "center": ["center", center_y],
        "top": ["center", top_y],
        "bottom": ["center", bottom_y],
        "bottom_center": ["center", bottom_y],
        "bottom_left": ["left", bottom_y],
        "bottom_right": ["right", bottom_y],
    }

    return positions.get(
        caption_position,
        positions["bottom_center"],
    )


def get_output_media(
    audio_file_path,
    timed_captions,
    background_video_data,
    video_server,
    output_file_name="rendered_video.mp4",
):
    config = get_config()

    background_video_data = [
        (interval, video_url)
        for interval, video_url in (background_video_data or [])
        if isinstance(video_url, str) and video_url.strip()
    ]

    if not background_video_data:
        raise ValueError(
            "No downloadable background videos were found for the requested topic"
        )

    magick_path = _find_imagemagick()
    if not magick_path:
        raise RuntimeError(
            "ImageMagick was not found. Install ImageMagick and ensure "
            "the 'magick' command is available on PATH."
        )

    os.environ["IMAGEMAGICK_BINARY"] = magick_path

    visual_clips = []
    downloaded_files = []
    audio_file_clip = None
    audio = None
    video = None

    try:
        video_size = None

        for (t1, t2), video_url in background_video_data:
            video_filename = tempfile.NamedTemporaryFile(
                delete=False
            ).name
            downloaded_files.append(video_filename)

            download_file(video_url, video_filename)

            video_clip = VideoFileClip(video_filename)
            video_size = video_size or video_clip.size
            visual_clips.append(
                video_clip.set_start(t1).set_end(t2)
            )

        audio_file_clip = AudioFileClip(audio_file_path)

        if config.get_captions_enabled():
            for (t1, t2), text in timed_captions:
                font_size = config.get_caption_font_size()
                stroke_width = config.get_caption_stroke_width()

                text_clip = TextClip(
                    txt=text,
                    font=config.get_caption_font_face(),
                    fontsize=font_size,
                    color=config.get_caption_font_color(),
                    stroke_width=stroke_width,
                    stroke_color=config.get_caption_stroke_color(),
                    method="label",
                )

                text_clip = text_clip.set_start(t1).set_end(t2)
                text_clip = text_clip.set_position(
                    _get_caption_position(
                        config.get_caption_position(),
                        video_size,
                        font_size,
                        stroke_width,
                    )
                )
                visual_clips.append(text_clip)

        video = CompositeVideoClip(visual_clips)
        audio = CompositeAudioClip([audio_file_clip])
        video.duration = audio.duration
        video.audio = audio

        video.write_videofile(
            output_file_name,
            codec="libx264",
            audio_codec="aac",
            fps=25,
            preset="veryfast",
        )

        return output_file_name

    finally:
        if video is not None:
            video.close()

        if audio is not None:
            audio.close()

        if audio_file_clip is not None:
            audio_file_clip.close()

        for clip in visual_clips:
            close = getattr(clip, "close", None)
            if close is not None:
                close()

        for filename in downloaded_files:
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass
