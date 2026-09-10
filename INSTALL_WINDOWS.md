# Windows Installation Guide

## Prerequisites

Install the following before setting up the project:

1. CPython 3.13.x from https://www.python.org/downloads/
2. FFmpeg and add its `bin` directory to PATH.
3. ImageMagick and add the directory containing `magick.exe` to PATH.
4. An API key for the selected LLM provider.
5. A Pexels API key.

During Python installation, enable **Add Python to PATH**.

Verify the installations in Command Prompt:

```cmd
py -3.13 --version
ffmpeg -version
```

If ImageMagick was installed or its PATH was changed during this setup,
close this Command Prompt and open a new one before checking `magick`. An
existing Command Prompt does not automatically receive PATH changes. In the
new Command Prompt, run:

```cmd
where magick
magick -version
```

## Project Setup

From the directory containing the project:

```cmd
cd Text-To-Video-AI
py -3.13 -m venv venv
venv\Scripts\activate
python --version
python -m pip install --upgrade pip
python -m pip install --upgrade -r requirements.txt
copy .env.example .env
```

The active environment must report CPython 3.13.x. The dependency pins are
selected for Python 3.13 and should not be mixed with an older environment.

Open `.env` and set the API key required by `LLM_PROVIDER` and
`PEXELS_API_KEY`. Do not commit `.env` or share its contents.

## Run the Browser Studio

Start the thin local HTTP adapter around the existing Python pipeline:

```cmd
python web_server.py
```

Open `http://127.0.0.1:8000` in a browser. Enter an English topic and select
**Generate video**. The browser submits a bounded local job, polls its status,
and displays the completed MP4. This requires the configured provider keys,
Pexels access, FFmpeg, and ImageMagick when a real video is generated.

## Generate a Video from the CLI

Run the CLI with any English topic about a country, region, subject, or global story:

```cmd
python app.py "History of India"
```

Choose an output path when needed:

```cmd
python app.py "The Eiffel Tower in France" --output outputs\eiffel-tower.mp4
```

## Run Tests

Run each command separately. Do not concatenate the commands on one line.

API-free checks that do not contact providers:

```cmd
python -m unittest tests.test_content_policy tests.test_pipeline_smoke -v
python app.py --help
python web_server.py --help
```

After the dependency installation succeeds, run the complete regression suite:

```cmd
python -m pip check
python -m unittest discover -s tests -v
```

Run the project-only syntax check separately:

```cmd
python -m compileall -q app.py web_server.py utility tests
```

Do not run the syntax checker against the repository root, because that also
scans the virtual environment's third-party files. If `magick -version` still
fails in a new Command Prompt, repair the ImageMagick installation or add the
directory containing `magick.exe` to PATH before rendering.
