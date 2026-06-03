CANONICAL_PROMPT_TEMPLATE = (
    "Your job is to fix transcription errors and human made mistakes. "
    "The user may misspeak and try to correct themselves or specify specific "
    "spellings of words and names. Apply spoken edit commands, punctuation, "
    "casing, spelling, URLs, emails, basic markdown and identifiers. Remove "
    "any spoken edits you have applied from the transcript. Do not explain "
    "your actions. Return only the cleaned-up final text. This is the original "
    "transcript: {transcript}"
)


def render_prompt(transcript: str) -> str:
    return CANONICAL_PROMPT_TEMPLATE.format(transcript=transcript)

