import argparse
import asyncio
import os
import tempfile
import uuid
from pathlib import Path

from utility.content_policy import validate_topic as validate_topic_text


# Runtime dependencies are loaded only when video generation starts. This keeps
# CLI help and offline policy checks usable before provider packages are set up.
generate_audio = None
generate_timed_captions = None
get_config = None
get_output_media = None
generate_script = None
generate_video_url = None
getVideoSearchQueriesTimed = None
merge_empty_intervals = None


def _load_pipeline_dependencies():
    global generate_audio
    global generate_timed_captions
    global get_config
    global get_output_media
    global generate_script
    global generate_video_url
    global getVideoSearchQueriesTimed
    global merge_empty_intervals

    dependencies = (
        generate_audio,
        generate_timed_captions,
        get_config,
        get_output_media,
        generate_script,
        generate_video_url,
        getVideoSearchQueriesTimed,
        merge_empty_intervals,
    )
    if all(dependency is not None for dependency in dependencies):
        return

    try:
        from utility.audio.audio_generator import generate_audio as audio_generator
        from utility.captions.timed_captions_generator import (
            generate_timed_captions as captions_generator,
        )
        from utility.config import get_config as config_loader
        from utility.render.render_engine import get_output_media as media_renderer
        from utility.script.script_generator import generate_script as script_generator
        from utility.video.background_video_generator import (
            generate_video_url as video_url_generator,
        )
        from utility.video.video_search_query_generator import (
            getVideoSearchQueriesTimed as query_generator,
            merge_empty_intervals as interval_merger,
        )
    except ImportError as error:
        raise RuntimeError(
            "Runtime dependencies are not installed. "
            "Use the documented Python 3.13 setup command and install "
            "requirements.txt before generating a video."
        ) from error

    generate_audio = audio_generator
    generate_timed_captions = captions_generator
    get_config = config_loader
    get_output_media = media_renderer
    generate_script = script_generator
    generate_video_url = video_url_generator
    getVideoSearchQueriesTimed = query_generator
    merge_empty_intervals = interval_merger


def validate_topic(topic):
    validate_topic_text(topic)


def _prepare_output_path(output_file_name):
    output_file_name = output_file_name or (
        f"rendered_video_{uuid.uuid4().hex[:8]}.mp4"
    )
    output_path = Path(output_file_name)

    if output_path.suffix.casefold() != ".mp4":
        raise ValueError("The output path must use the .mp4 extension")

    if output_path.exists() and not output_path.is_file():
        raise ValueError("The output path must point to a file")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return str(output_path)


def generate_video(topic, output_file_name=None):
    validate_topic(topic)
    output_file_name = _prepare_output_path(output_file_name)
    _load_pipeline_dependencies()

    video_server = "pexel"
    config = get_config()
    orientation_landscape = config.get_video_orientation()

    with tempfile.TemporaryDirectory(prefix="text_to_video_") as work_dir:
        audio_file_path = os.path.join(work_dir, "audio_tts.mp3")
        response = generate_script(topic)
        print("script: {}".format(response))

        asyncio.run(generate_audio(response, audio_file_path))

        timed_captions = generate_timed_captions(audio_file_path)
        print(timed_captions)

        if not timed_captions:
            raise RuntimeError(
                "Speech-to-text returned no timed captions; video generation cannot continue"
            )

        search_terms = getVideoSearchQueriesTimed(response, timed_captions)
        print(search_terms)

        background_video_urls = None
        if search_terms is not None:
            background_video_urls = generate_video_url(
                search_terms,
                video_server,
                orientation_landscape=orientation_landscape,
            )
            print(background_video_urls)
        else:
            print("No background video")

        background_video_urls = merge_empty_intervals(background_video_urls)

        if not background_video_urls:
            print("No video")
            return None

        return get_output_media(
            audio_file_path,
            timed_captions,
            background_video_urls,
            video_server,
            output_file_name=output_file_name,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a video from a topic.")
    parser.add_argument("topic", type=str, help="The English video topic")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path; otherwise a unique rendered filename is used",
    )
    args = parser.parse_args()
    print(generate_video(args.topic, args.output))
