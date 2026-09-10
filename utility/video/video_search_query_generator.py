import json
import math
import re
import time
from numbers import Real

from utility.config import get_config
from utility.content_policy import validate_english_visual_query
from utility.utils import log_response, LOG_TYPE_GPT


MAX_RETRIES = 3
MAX_VISUAL_SEGMENTS = 30
TIMELINE_TOLERANCE_SECONDS = 0.05

prompt = """# Instructions

Given the following video script and timed captions, extract three visually concrete and specific keywords for each time segment that can be used to search for background videos. The keywords should be short and capture the main essence of the sentence. They can be synonyms or related terms. If a caption is vague or general, consider the next timed caption for more context. If a keyword is a single word, try to return a two-word keyword that is visually concrete. If a time frame contains two or more important pieces of information, divide it into shorter time frames with one keyword each. Ensure that the time periods are strictly consecutive and cover the entire length of the video. Each keyword should cover between 2-4 seconds. The output should be in JSON format, like this: [[[t1, t2], ["keyword1", "keyword2", "keyword3"]], [[t2, t3], ["keyword4", "keyword5", "keyword6"]], ...]. Please handle all edge cases, such as overlapping time segments, vague or general captions, and single-word keywords.

For example, if the caption is 'The Eiffel Tower is a famous landmark in France', the keywords could include 'Eiffel Tower France', 'Paris skyline', and 'French landmark'. Similarly, for 'Dubai has a modern skyline', the keywords could be 'Dubai skyline', 'UAE skyscrapers', and 'city architecture'.

Important Guidelines:

Use only English in your text queries.
Each search string must depict something visual.
The depictions have to be extremely visually concrete, like rainy street, or cat sleeping.
'emotional moment' <= BAD, because it doesn't depict something visually.
'crying child' <= GOOD, because it depicts something visual.
The list must always contain the most relevant and appropriate query searches.
['Car', 'Car driving', 'Car racing', 'Car parked'] <= BAD, because it's 4 strings.
['Fast car'] <= GOOD, because it's 1 string.
['dog', 'fast car', 'red house'] <= BAD, because the list contains three separate queries instead of one focused query.

Note: Your response should be the response only and no extra text or data.
"""


def _strip_model_response(text):
    if not isinstance(text, str):
        raise ValueError("LLM response was not text")

    text = re.sub(r'\s+', ' ', text).strip()

    for prefix in ('```json', '```'):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    if text.endswith('```'):
        text = text[:-3].strip()

    for prefix in ('content:', 'content =', 'content='):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break

    return text


def _validate_segments(segments, expected_end):
    if not isinstance(segments, list) or not segments:
        raise ValueError(
            "LLM response must contain at least one visual segment"
        )

    if len(segments) > MAX_VISUAL_SEGMENTS:
        raise ValueError(
            f"LLM response contains more than {MAX_VISUAL_SEGMENTS} visual segments"
        )

    validated = []
    previous_end = 0.0

    for index, segment in enumerate(segments):
        if not isinstance(segment, list) or len(segment) != 2:
            raise ValueError(f"Invalid visual segment at index {index}")

        interval, queries = segment

        if (
            not isinstance(interval, list)
            or len(interval) != 2
            or not all(
                isinstance(value, Real) and not isinstance(value, bool)
                for value in interval
            )
        ):
            raise ValueError(f"Invalid time interval at index {index}")

        start, end = float(interval[0]), float(interval[1])

        if (
            not math.isfinite(start)
            or not math.isfinite(end)
            or start < 0
            or end <= start
        ):
            raise ValueError(f"Invalid time range at index {index}")

        if abs(start - previous_end) > TIMELINE_TOLERANCE_SECONDS:
            raise ValueError("Visual segments must be consecutive")

        if not isinstance(queries, list) or not 1 <= len(queries) <= 3:
            raise ValueError(f"Invalid query list at index {index}")

        for query in queries:
            try:
                validate_english_visual_query(query)
            except ValueError as error:
                raise ValueError(
                    f"Invalid English visual query at index {index}: {error}"
                ) from error

        validated.append(
            [[start, end], [query.strip() for query in queries]]
        )
        previous_end = end

    if abs(previous_end - float(expected_end)) > TIMELINE_TOLERANCE_SECONDS:
        raise ValueError(
            "Visual segments do not cover the complete caption timeline"
        )

    return validated


def getVideoSearchQueriesTimed(script, captions_timed):
    if not captions_timed:
        print("No timed captions available for visual search")
        return None

    expected_end = captions_timed[-1][0][1]

    for attempt in range(MAX_RETRIES):
        try:
            content = call_OpenAI(script, captions_timed)
            parsed = json.loads(_strip_model_response(content))
            return _validate_segments(parsed, expected_end)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            print(
                f"Invalid visual-query response on attempt {attempt + 1}: "
                f"{error}"
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        except Exception as error:
            print(
                f"Visual-query generation failed on attempt {attempt + 1}: "
                f"{error}"
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

    print(
        f"Unable to generate valid visual queries after {MAX_RETRIES} attempts"
    )
    return None


def call_OpenAI(script, captions_timed):
    config = get_config()
    client = config.get_llm_client()
    model = config.get_llm_model()
    provider = config.get_llm_provider()

    user_content = """Script: {}
Timed Captions:{}
""".format(script, "".join(map(str, captions_timed)))

    if provider == 'gemini':
        response = client.generate_content(
            contents=[
                {
                    "role": "user",
                    "parts": [{"text": f"{prompt}\n\n{user_content}"}],
                }
            ],
            generation_config={
                "temperature": 1.0,
                "top_p": 0.9,
                "max_output_tokens": 1200,
            },
            request_options={"timeout": 30},
        )
        text = response.text
    else:
        response = client.chat.completions.create(
            model=model,
            temperature=1,
            max_tokens=1200,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
        )
        text = response.choices[0].message.content

    text = _strip_model_response(text)
    json.loads(text)
    log_response(LOG_TYPE_GPT, script, text)
    return text


def merge_empty_intervals(segments):
    if segments is None:
        print("No background videos available to merge")
        return None

    merged = []
    i = 0

    while i < len(segments):
        interval, url = segments[i]

        if not url:
            j = i + 1

            while j < len(segments) and not segments[j][1]:
                j += 1

            if i > 0:
                prev_interval, prev_url = merged[-1]

                if prev_url and prev_interval[1] == interval[0]:
                    merged[-1] = [
                        [prev_interval[0], segments[j - 1][0][1]],
                        prev_url,
                    ]
                else:
                    merged.append([interval, prev_url])
            else:
                merged.append([interval, None])

            i = j
        else:
            merged.append([interval, url])
            i += 1

    return [segment for segment in merged if segment[1]]
