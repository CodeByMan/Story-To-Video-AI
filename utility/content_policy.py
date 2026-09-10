MAX_TOPIC_LENGTH = 500
MAX_SCRIPT_LENGTH = 20_000
MAX_QUERY_LENGTH = 500


def validate_english_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")

    if not value.isascii():
        raise ValueError(f"{label} must use English text")

    if any(character in value for character in "\r\n\x00"):
        raise ValueError(f"{label} contains unsupported control characters")


def validate_topic(topic):
    validate_english_text(topic, "The topic")
    if len(topic.strip()) > MAX_TOPIC_LENGTH:
        raise ValueError(f"The topic must be {MAX_TOPIC_LENGTH} characters or fewer")


def validate_script(script):
    validate_english_text(script, "The generated script")
    if len(script.strip()) > MAX_SCRIPT_LENGTH:
        raise ValueError(f"The generated script must be {MAX_SCRIPT_LENGTH} characters or fewer")


def validate_english_visual_query(query):
    validate_english_text(query, "Visual search queries")
    if len(query.strip()) > MAX_QUERY_LENGTH:
        raise ValueError(f"Visual search queries must be {MAX_QUERY_LENGTH} characters or fewer")
