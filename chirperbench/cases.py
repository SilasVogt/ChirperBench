from __future__ import annotations

from .types import TranscriptCase


def get_builtin_cases() -> list[TranscriptCase]:
    return [
        TranscriptCase(
            id="literal_pr_review_instruction",
            category="instruction_as_content",
            transcript=(
                "please check the open PR number 4 for code review comments and "
                "check each one that's still open if it needs to be fixed period "
                "fix it and then resolve the comments and push your fix"
            ),
            expected=(
                "Please check the open PR #4 for code review comments and check "
                "each one that's still open if it needs to be fixed. Fix it, "
                "then resolve the comments and push your fix."
            ),
            notes=(
                "Catch refusals or meta responses where the model treats "
                "dictated text as an instruction to execute."
            ),
        ),
        TranscriptCase(
            id="literal_agent_instruction",
            category="instruction_as_content",
            transcript="run cargo test comma fix any failing tests comma then commit and push the branch period",
            expected="Run cargo test, fix any failing tests, then commit and push the branch.",
            notes="Preserve command-like content as text.",
        ),
        TranscriptCase(
            id="literal_question_no_answer",
            category="instruction_as_content",
            transcript="what is the capital of france question mark",
            expected="What is the capital of France?",
            notes="Catch models that answer Paris instead of formatting the dictated question.",
        ),
        TranscriptCase(
            id="literal_email_request",
            category="instruction_as_content",
            transcript=(
                "write an email to maya comma subject colon quarterly update period "
                "the meeting moved to thursday at 9 30 a m comma the budget is "
                "twelve thousand four hundred fifty dollars comma and the website "
                "is chirper dot local slash launch period"
            ),
            expected=(
                "Write an email to Maya, subject: Quarterly Update. The meeting "
                "moved to Thursday at 9:30 AM, the budget is $12,450, and the "
                "website is chirper.local/launch."
            ),
            notes="Format an email request without generating a new email body.",
        ),
        TranscriptCase(
            id="onboarding_mixed_format",
            category="mixed_formatting",
            transcript=(
                "hello chirper period i need to write down accent friendly words "
                "period this is a bullet point list with title accent friendly "
                "words colon water comma tomato comma schedule comma data comma "
                "router comma aluminium comma privacy period end of list new "
                "paragraph please write an email to maya comma subject colon "
                "quarterly update period the meeting moved to thursday at nine "
                "thirty a m comma the budget is twelve thousand four hundred fifty "
                "dollars comma and the website is chirper dot local slash launch "
                "period new paragraph in the deployment notes comma mention that "
                "systemd keeps the chirper services running comma and we should "
                "also look at postgresql comma ffmpeg comma gnome comma nextcloud "
                "comma and tailscale period finish with thanks exclamation mark"
            ),
            expected=(
                "Hello Chirper. I need to write down accent-friendly words.\n\n"
                "Accent Friendly Words:\n"
                "- water\n"
                "- tomato\n"
                "- schedule\n"
                "- data\n"
                "- router\n"
                "- aluminium\n"
                "- privacy\n\n"
                "Please write an email to Maya, subject: Quarterly Update. The "
                "meeting moved to Thursday at 9:30 AM, the budget is $12,450, "
                "and the website is chirper.local/launch.\n\n"
                "In the deployment notes, mention that systemd keeps the Chirper "
                "services running, and we should also look at PostgreSQL, FFmpeg, "
                "GNOME, Nextcloud, and Tailscale. Thanks!"
            ),
            notes=(
                "Catch models that do only one part of a mixed "
                "list/email/punctuation/technical-casing task."
            ),
        ),
        TranscriptCase(
            id="markdown_checklist_instruction_content",
            category="markdown",
            transcript=(
                "make a markdown checklist titled release tasks colon item one "
                "run tests item two push tag item three publish release"
            ),
            expected="Release Tasks:\n- [ ] Run tests\n- [ ] Push tag\n- [ ] Publish release",
            notes="Format markdown without trying to publish anything.",
        ),
        TranscriptCase(
            id="shell_command_as_content",
            category="code_identifiers",
            transcript="cargo test pipe tee space test dash output dot log",
            expected="cargo test | tee test-output.log",
            notes="Preserve shell command structure.",
        ),
        TranscriptCase(
            id="spoken_correction_chain",
            category="spoken_edits",
            transcript=(
                "call it chirper bench no scratch that chirper benchmark spelled "
                "capital c chirper capital b bench"
            ),
            expected="Call it ChirperBench.",
            notes="Apply the final correction and remove spoken edit words.",
        ),
        TranscriptCase(
            id="url_https_path",
            category="urls",
            transcript=(
                "visit h t t p s colon slash slash docs dot python dot org slash "
                "three slash library slash json dot html period"
            ),
            expected="Visit https://docs.python.org/3/library/json.html.",
            notes="Format a spoken HTTPS URL with path and punctuation.",
        ),
        TranscriptCase(
            id="email_addresses",
            category="emails",
            transcript=(
                "send it to alex at chirper dot local and cc ops at example dot "
                "com period"
            ),
            expected="Send it to alex@chirper.local and cc ops@example.com.",
            notes="Format spoken email addresses.",
        ),
        TranscriptCase(
            id="product_and_class_casing",
            category="casing_identifiers",
            transcript=(
                "the project name is chirper bench and the class name is "
                "dictation formatter period"
            ),
            expected="The project name is ChirperBench and the class name is DictationFormatter.",
            notes="Apply product and code-style casing.",
        ),
        TranscriptCase(
            id="inline_code_identifiers",
            category="code_identifiers",
            transcript=(
                "set variable user underscore id equal to request dot user dot id "
                "period"
            ),
            expected="Set variable `user_id` equal to `request.user.id`.",
            notes="Format code identifiers and inline code.",
        ),
        TranscriptCase(
            id="numbers_versions_dates",
            category="numbers_versions",
            transcript=(
                "version two point one point zero shipped on june third twenty "
                "twenty six and supports python three point eleven plus period"
            ),
            expected="Version 2.1.0 shipped on June 3, 2026 and supports Python 3.11+.",
            notes="Format versions, dates, numbers, and language casing.",
        ),
        TranscriptCase(
            id="simple_list",
            category="lists",
            transcript="shopping list colon apples comma bananas comma oat milk period",
            expected="Shopping list:\n- apples\n- bananas\n- oat milk",
            notes="Format a simple spoken list.",
        ),
        TranscriptCase(
            id="no_change_needed",
            category="no_change_needed",
            transcript="The quick brown fox jumps over the lazy dog.",
            expected="The quick brown fox jumps over the lazy dog.",
            notes="Leave already clean text unchanged.",
        ),
    ]


def find_case(case_id: str) -> TranscriptCase:
    for case in get_builtin_cases():
        if case.id == case_id:
            return case
    raise KeyError(f"Unknown case id: {case_id}")


def filter_cases(case_ids: list[str] | None) -> list[TranscriptCase]:
    cases = get_builtin_cases()
    if not case_ids:
        return cases
    by_id = {case.id: case for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise KeyError(f"Unknown case id(s): {', '.join(missing)}")
    return [by_id[case_id] for case_id in case_ids]

