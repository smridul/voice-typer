import unittest
from types import SimpleNamespace

from language_processing import TEXT_MODEL, convert_transcript


class FakeCompletions:
    def __init__(self, response_text):
        self.response_text = response_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.response_text)
                )
            ]
        )


class FakeClient:
    def __init__(self, response_text):
        self.chat = SimpleNamespace(completions=FakeCompletions(response_text))


class LanguageProcessingTests(unittest.TestCase):
    def test_same_language_output_skips_model_call(self):
        client = FakeClient("unused")

        result = convert_transcript(
            client=client,
            transcript="I need to go tomorrow",
            context_language="en",
            output_language="en",
        )

        self.assertEqual(result, "I need to go tomorrow")
        self.assertEqual(client.chat.completions.calls, [])

    def test_empty_transcript_returns_empty_string(self):
        client = FakeClient("unused")

        result = convert_transcript(
            client=client,
            transcript="   ",
            context_language="en",
            output_language="hi",
        )

        self.assertEqual(result, "")
        self.assertEqual(client.chat.completions.calls, [])

    def test_english_to_hindi_uses_translation_prompt(self):
        client = FakeClient("मुझे कल जाना है")

        result = convert_transcript(
            client=client,
            transcript="I need to go tomorrow",
            context_language="en",
            output_language="hi",
        )

        self.assertEqual(result, "मुझे कल जाना है")
        self.assertEqual(len(client.chat.completions.calls), 1)
        call = client.chat.completions.calls[0]
        self.assertEqual(call["model"], TEXT_MODEL)
        self.assertEqual(call["temperature"], 0)
        messages = call["messages"]
        self.assertIn("Translate the text into natural Hindi written in Devanagari script.", messages[0]["content"])
        self.assertIn("I need to go tomorrow", messages[1]["content"])

    def test_hindi_to_english_uses_local_transliteration(self):
        client = FakeClient("I need to go tomorrow")

        result = convert_transcript(
            client=client,
            transcript="मुझे कल जाना है",
            context_language="hi",
            output_language="en",
        )

        self.assertEqual(result, "mujhe kal jana hai")
        self.assertEqual(client.chat.completions.calls, [])

    def test_empty_model_response_raises_value_error(self):
        client = FakeClient("   ")

        with self.assertRaises(ValueError):
            convert_transcript(
                client=client,
                transcript="I need to go tomorrow",
                context_language="en",
                output_language="hi",
            )

    def test_english_to_hindi_rejects_non_devanagari_response(self):
        client = FakeClient("mujhe kal jana hai")

        with self.assertRaises(ValueError):
            convert_transcript(
                client=client,
                transcript="I need to go tomorrow",
                context_language="en",
                output_language="hi",
            )

    def test_hindi_to_english_transliterates_with_punctuation(self):
        client = FakeClient("unused")

        result = convert_transcript(
            client=client,
            transcript="कल?",
            context_language="hi",
            output_language="en",
        )

        self.assertEqual(result, "kal?")
        self.assertEqual(client.chat.completions.calls, [])

    def test_english_to_hindi_rejects_mixed_script_response(self):
        client = FakeClient("मुझे kal jana hai")

        with self.assertRaises(ValueError):
            convert_transcript(
                client=client,
                transcript="I need to go tomorrow",
                context_language="en",
                output_language="hi",
            )


if __name__ == "__main__":
    unittest.main()
