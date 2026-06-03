import unittest

from chirperbench.cases import find_case, get_builtin_cases


class CasesTest(unittest.TestCase):
    def test_required_instruction_and_mixed_cases_exist(self):
        cases = get_builtin_cases()
        ids = {case.id for case in cases}
        self.assertIn("literal_pr_review_instruction", ids)
        self.assertIn("literal_agent_instruction", ids)
        self.assertIn("literal_question_no_answer", ids)
        self.assertIn("literal_email_request", ids)
        self.assertIn("onboarding_mixed_format", ids)
        self.assertIn("markdown_checklist_instruction_content", ids)
        self.assertIn("shell_command_as_content", ids)
        self.assertIn("spoken_correction_chain", ids)

        categories = {case.category for case in cases}
        self.assertIn("instruction_as_content", categories)
        self.assertIn("mixed_formatting", categories)

    def test_baseline_categories_exist(self):
        categories = {case.category for case in get_builtin_cases()}
        self.assertIn("urls", categories)
        self.assertIn("emails", categories)
        self.assertIn("casing_identifiers", categories)
        self.assertIn("code_identifiers", categories)
        self.assertIn("numbers_versions", categories)
        self.assertIn("lists", categories)
        self.assertIn("no_change_needed", categories)

    def test_onboarding_expected_contains_all_mixed_parts(self):
        case = find_case("onboarding_mixed_format")
        self.assertIn("Accent Friendly Words:", case.expected)
        self.assertIn("- aluminium", case.expected)
        self.assertIn("chirper.local/launch", case.expected)
        self.assertIn("PostgreSQL, FFmpeg, GNOME, Nextcloud, and Tailscale", case.expected)
        self.assertTrue(case.expected.endswith("Thanks!"))


if __name__ == "__main__":
    unittest.main()

