import requests

from utility.config import get_config
from utility.utils import LOG_TYPE_PEXEL, log_response


TARGET_ASPECT_RATIO = 16 / 9


def _get_dimensions(item):
    try:
        width = float(item.get("width"))
        height = float(item.get("height"))
    except (AttributeError, TypeError, ValueError):
        return None

    if width <= 0 or height <= 0:
        return None

    return width, height


def _matches_orientation(item, orientation_landscape):
    dimensions = _get_dimensions(item)
    if dimensions is None:
        return False

    width, height = dimensions
    minimum_width, minimum_height = (
        (1280, 720) if orientation_landscape else (720, 1280)
    )

    if orientation_landscape:
        return (
            width >= minimum_width
            and height >= minimum_height
            and abs((width / height) - TARGET_ASPECT_RATIO) < 0.05
        )

    return (
        width >= minimum_width
        and height >= minimum_height
        and abs((height / width) - TARGET_ASPECT_RATIO) < 0.05
    )


def _get_duration(item):
    try:
        duration = float(item.get("duration", 15))
    except (AttributeError, TypeError, ValueError):
        return 15

    return duration if duration >= 0 else 15


def search_videos(query_string, orientation_landscape=True):
    config = get_config()
    pexels_api_key = config.get_pexels_api_key()

    url = "https://api.pexels.com/videos/search"
    headers = {
        "Authorization": pexels_api_key,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
    }
    params = {
        "query": query_string,
        "orientation": "landscape" if orientation_landscape else "portrait",
        "per_page": 15,
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    json_data = response.json()

    if not isinstance(json_data, dict) or not isinstance(
        json_data.get('videos'), list
    ):
        raise ValueError(
            "Pexels API returned an unexpected videos response"
        )

    log_response(LOG_TYPE_PEXEL, query_string, json_data)
    return json_data


def getBestVideo(query_string, orientation_landscape=True, used_vids=None):
    if used_vids is None:
        used_vids = []

    vids = search_videos(query_string, orientation_landscape)
    videos = vids['videos']

    filtered_videos = [
        video
        for video in videos
        if isinstance(video, dict)
        and _matches_orientation(video, orientation_landscape)
    ]

    sorted_videos = sorted(
        filtered_videos,
        key=lambda video: abs(15 - _get_duration(video)),
    )

    for video in sorted_videos:
        for video_file in video.get('video_files', []):
            matches_orientation = (
                isinstance(video_file, dict)
                and _matches_orientation(video_file, orientation_landscape)
            )

            if matches_orientation:
                link = video_file.get('link')
                if not isinstance(link, str) or not link.strip():
                    continue

                normalized_link = link.split('.hd')[0]
                if normalized_link not in used_vids:
                    return link

    print("NO LINKS found for this round of search with query:", query_string)
    return None


def generate_video_url(
    timed_video_searches,
    video_server,
    orientation_landscape=True,
):
    timed_video_urls = []

    if video_server == "pexel":
        used_links = []

        for (t1, t2), search_terms in timed_video_searches:
            url = None

            for query in search_terms:
                url = getBestVideo(
                    query,
                    orientation_landscape=orientation_landscape,
                    used_vids=used_links,
                )

                if url:
                    used_links.append(url.split('.hd')[0])
                    break

            timed_video_urls.append([[t1, t2], url])

    elif video_server == "stable_diffusion":
        raise ValueError("stable_diffusion is not supported by this project")

    return timed_video_urls
