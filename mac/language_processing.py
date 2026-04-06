TEXT_MODEL = "llama-3.1-8b-instant"

_DEVANAGARI_VOWELS = {
    "अ": "a",
    "आ": "a",
    "इ": "i",
    "ई": "i",
    "उ": "u",
    "ऊ": "u",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
    "ऋ": "ri",
}

_DEVANAGARI_MATRAS = {
    "ा": "a",
    "ि": "i",
    "ी": "i",
    "ु": "u",
    "ू": "u",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
    "ृ": "ri",
}

_DEVANAGARI_CONSONANTS = {
    "क": "k",
    "ख": "kh",
    "ग": "g",
    "घ": "gh",
    "ङ": "ng",
    "च": "ch",
    "छ": "chh",
    "ज": "j",
    "झ": "jh",
    "ञ": "ny",
    "ट": "t",
    "ठ": "th",
    "ड": "d",
    "ढ": "dh",
    "ण": "n",
    "त": "t",
    "थ": "th",
    "द": "d",
    "ध": "dh",
    "न": "n",
    "प": "p",
    "फ": "ph",
    "ब": "b",
    "भ": "bh",
    "म": "m",
    "य": "y",
    "र": "r",
    "ल": "l",
    "व": "v",
    "श": "sh",
    "ष": "sh",
    "स": "s",
    "ह": "h",
    "ड़": "r",
    "ढ़": "rh",
    "क़": "q",
    "ख़": "kh",
    "ग़": "gh",
    "ज़": "z",
    "फ़": "f",
}

_DEVANAGARI_MARKS = {
    "ं": "n",
    "ँ": "n",
    "ः": "h",
}

_DEVANAGARI_DIGITS = {
    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9",
}

_DEVANAGARI_VIRAMA = "्"


def _contains_devanagari(text):
    return any("\u0900" <= character <= "\u097f" for character in text)


def _contains_latin(text):
    return any(
        ("a" <= character <= "z") or ("A" <= character <= "Z")
        for character in text
    )


def _transliterate_hindi_to_latin(text):
    pieces = []
    pending_consonant = None

    def flush_pending(add_schwa):
        nonlocal pending_consonant
        if pending_consonant is None:
            return

        pieces.append(pending_consonant + ("a" if add_schwa else ""))
        pending_consonant = None

    for character in text:
        if character in _DEVANAGARI_CONSONANTS:
            flush_pending(add_schwa=True)
            pending_consonant = _DEVANAGARI_CONSONANTS[character]
            continue

        if character in _DEVANAGARI_MATRAS:
            if pending_consonant is not None:
                pieces.append(pending_consonant + _DEVANAGARI_MATRAS[character])
                pending_consonant = None
            else:
                pieces.append(_DEVANAGARI_MATRAS[character])
            continue

        if character == _DEVANAGARI_VIRAMA:
            flush_pending(add_schwa=False)
            continue

        if character in _DEVANAGARI_VOWELS:
            flush_pending(add_schwa=True)
            pieces.append(_DEVANAGARI_VOWELS[character])
            continue

        if character in _DEVANAGARI_MARKS:
            flush_pending(add_schwa=True)
            pieces.append(_DEVANAGARI_MARKS[character])
            continue

        if character in _DEVANAGARI_DIGITS:
            flush_pending(add_schwa=False)
            pieces.append(_DEVANAGARI_DIGITS[character])
            continue

        flush_pending(add_schwa=False)
        pieces.append(character)

    flush_pending(add_schwa=False)
    return "".join(pieces)


def _conversion_messages(transcript, context_language, output_language):
    if context_language == "en" and output_language == "hi":
        return [
            {
                "role": "system",
                "content": (
                    "Translate the text into natural Hindi written in Devanagari script. "
                    "Preserve the meaning, make the result sound natural, and respond "
                    "only in Devanagari script."
                ),
            },
            {
                "role": "user",
                "content": transcript,
            },
        ]

    return []


def convert_transcript(client, transcript, context_language, output_language):
    if not transcript or not transcript.strip():
        return ""

    if context_language == output_language:
        return transcript

    if context_language == "hi" and output_language == "en":
        return _transliterate_hindi_to_latin(transcript).strip()

    messages = _conversion_messages(transcript, context_language, output_language)
    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=0,
        messages=messages,
    )
    raw_content = response.choices[0].message.content
    if not isinstance(raw_content, str):
        raw_content = ""

    content = raw_content.strip()
    if not content:
        raise ValueError("Converted transcript was empty")

    if context_language == "en" and output_language == "hi":
        if not _contains_devanagari(content) or _contains_latin(content):
            raise ValueError("Converted transcript must be Hindi in Devanagari script")

    return content
