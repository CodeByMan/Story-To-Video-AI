import whisper_timestamped as whisper
from whisper_timestamped import load_model, transcribe_timestamped
import re


def generate_timed_captions(audio_filename, model_size="base"):
    whisper_model = load_model(model_size)
    transcription = transcribe_timestamped(
        whisper_model,
        audio_filename,
        verbose=False,
        fp16=False,
    )
    return getCaptionsWithTime(transcription)


def splitWordsBySize(words, maxCaptionSize):
    halfCaptionSize = maxCaptionSize / 2
    captions = []

    while words:
        caption = words[0]
        words = words[1:]

        while words and len(caption + ' ' + words[0]) <= maxCaptionSize:
            caption += ' ' + words[0]
            words = words[1:]

            if len(caption) >= halfCaptionSize and words:
                break

        captions.append(caption)

    return captions


def getTimestampMapping(whisper_analysis):
    index = 0
    locationToTimestamp = {}
    text = whisper_analysis['text']

    for segment in whisper_analysis['segments']:
        for word in segment['words']:
            clean_text = cleanWord(word['text'])
            newIndex = index + len(clean_text) + 1
            locationToTimestamp[(index, newIndex)] = (
                word['start'],
                word['end'],
            )
            index = newIndex

    return locationToTimestamp


def cleanWord(word):
    return re.sub(r'[^\w\s\-_%\']', '', word)


def interpolateTimeFromDict(word_position, dictionary):
    for key, value in dictionary.items():
        if key[0] <= word_position <= key[1]:
            return value

    return None


def getCaptionsWithTime(
    whisper_analysis,
    maxCaptionSize=15,
    considerPunctuation=False,
):
    if maxCaptionSize <= 0:
        raise ValueError("maxCaptionSize must be greater than zero")

    captions = []
    current_words = []
    current_start = None
    current_end = None

    def flush_caption():
        nonlocal current_words, current_start, current_end

        if current_words:
            captions.append(
                (
                    (current_start, current_end),
                    " ".join(current_words),
                )
            )

        current_words = []
        current_start = None
        current_end = None

    last_end = 0

    for segment in whisper_analysis['segments']:
        for word_info in segment['words']:
            clean_word = cleanWord(word_info['text'])

            if not clean_word:
                continue

            start = word_info['start']
            end = word_info['end']

            if start >= end or start < last_end or end <= last_end:
                start = last_end
                end = last_end + 0.3

            last_end = end

            proposed_text = " ".join(current_words + [clean_word])
            has_punctuation = (
                considerPunctuation
                and word_info['text'].rstrip().endswith(('.', '!', '?'))
            )

            if current_words and (
                len(proposed_text) > maxCaptionSize
                or has_punctuation
            ):
                flush_caption()

            if not current_words:
                current_start = start

            current_words.append(clean_word)
            current_end = end

    flush_caption()
    return captions