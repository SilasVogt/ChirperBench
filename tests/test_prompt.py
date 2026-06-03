import unittest

from chirperbench.prompt import CANONICAL_PROMPT_TEMPLATE, render_prompt


class PromptTest(unittest.TestCase):
    def test_prompt_is_canonical(self):
        transcript = "what is the capital of france question mark"
        expected = (
            "Your job is to fix transcription errors and human made mistakes. "
            "The user may misspeak and try to correct themselves or specify specific "
            "spellings of words and names. Apply spoken edit commands, punctuation, "
            "casing, spelling, URLs, emails, basic markdown and identifiers. Remove "
            "any spoken edits you have applied from the transcript. Do not explain "
            "your actions. Return only the cleaned-up final text. This is the original "
            "transcript: what is the capital of france question mark"
        )
        self.assertEqual(render_prompt(transcript), expected)

    def test_template_has_single_transcript_slot(self):
        self.assertEqual(CANONICAL_PROMPT_TEMPLATE.count("{transcript}"), 1)
        self.assertNotIn("\n", CANONICAL_PROMPT_TEMPLATE)


if __name__ == "__main__":
    unittest.main()

