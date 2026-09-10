import json
from utility.config import get_config
from utility.content_policy import validate_script


def clean_markdown(text):
    """Remove markdown formatting from text to prevent TTS issues."""
    import re

    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def generate_script(topic):
    config = get_config()
    client = config.get_llm_client()
    model = config.get_llm_model()
    provider = config.get_llm_provider()

    prompt = (
        """You are a seasoned content writer for a global YouTube Shorts channel, specializing in English facts videos.
        Your facts shorts are concise, each lasting less than 50 seconds (approximately 140 words).
        They are engaging and original. When a user requests a specific type of facts short, create it around the requested country, region, people, places, history, culture, science, or everyday life anywhere in the world.
        Use only broadly established facts. If a precise detail is uncertain, omit it rather than inventing it.

        For instance, if the user asks for:
        Weird facts
        You would produce content like this:

        World facts you may not know:
        - The Eiffel Tower is one of the most recognizable landmarks in France.
        - The Sahara is the largest hot desert in the world.
        - The Amazon rainforest spans several countries in South America.
        - The Great Wall is a landmark associated with China's history.
        - The Alps extend across multiple European countries.
        - Cities, cultures, and natural landscapes around the world offer diverse stories.

        You are now tasked with creating the best short script based on the user's requested type of global facts.

        Keep it brief, highly interesting, and unique.

        Strictly output the script in a JSON format like below, and only provide a parsable JSON object with the key 'script'.

        # Output
        {"script": "Here is the script ..."}
        """
    )

    if provider == 'gemini':
        content = _call_gemini(client, topic, prompt)
    else:
        content = _call_openai_groq(client, model, topic, prompt)

    try:
        text = content

        for prefix in [
            'content:',
            'content =',
            'content: ',
            'content=',
        ]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        json_start = text.find('{')
        json_end = text.rfind('}')

        if json_start == -1 or json_end == -1:
            raise ValueError("No valid JSON found in response")

        script_text = text[json_start:json_end + 1]
        payload = json.loads(script_text)

        if not isinstance(payload, dict):
            raise ValueError(
                "LLM response must be a JSON object with a string 'script' value"
            )

        script = payload.get("script")

        if not isinstance(script, str):
            raise ValueError(
                "LLM response must be a JSON object with a string 'script' value"
            )

        script = script.strip()

        if not script:
            raise ValueError("LLM returned an empty script")

        if len(script.split()) > 180:
            raise ValueError(
                "LLM returned a script longer than the supported short-video limit"
            )

        cleaned_script = clean_markdown(script)
        validate_script(cleaned_script)
        return cleaned_script

    except Exception as error:
        print(f"Error: {error}")
        raise


def _call_openai_groq(client, model, topic, prompt):
    response = client.chat.completions.create(
        model=model,
        max_tokens=300,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": topic},
        ],
    )

    return response.choices[0].message.content


def _call_gemini(client, topic, prompt):
    response = client.generate_content(
        contents=[
            {"role": "user", "parts": [{"text": f"{prompt}\n\nTopic: {topic}"}]}
        ],
        generation_config={
            "temperature": 0.7,
            "top_p": 0.8,
            "max_output_tokens": 300,
        },
        request_options={"timeout": 30},
    )

    text = response.text

    if text.startswith('```json'):
        text = text[7:]

    if text.startswith('```'):
        text = text[3:]

    if text.endswith('```'):
        text = text[:-3]

    return text.strip()
