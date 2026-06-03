import json
import tempfile
import unittest
from pathlib import Path

from chirperbench.judge_codex import parse_judge_json
from chirperbench.ollama import parse_ollama_list
from chirperbench.report import rank_models, write_run_artifacts


class ReportTest(unittest.TestCase):
    def test_ollama_list_parser(self):
        output = """NAME                  ID              SIZE      MODIFIED
granite4.1:3b         abc123          2.0 GB    2 days ago
llama3.2:latest       def456          4.1 GB    1 week ago
"""
        self.assertEqual(parse_ollama_list(output), ["granite4.1:3b", "llama3.2:latest"])

    def test_judge_parser_accepts_valid_json(self):
        raw = json.dumps(
            {
                "score": 100,
                "passed": True,
                "summary": "Exact match.",
                "errors": [],
                "ideal_output": "What is the capital of France?",
            }
        )
        parsed = parse_judge_json(raw)
        self.assertEqual(parsed.judge_status, "ok")
        self.assertEqual(parsed.score, 100)
        self.assertTrue(parsed.passed)
        self.assertEqual(parsed.errors, [])

    def test_judge_parser_marks_invalid_json(self):
        parsed = parse_judge_json("not json", expected="Expected")
        self.assertEqual(parsed.judge_status, "invalid_json")
        self.assertEqual(parsed.score, 0)
        self.assertFalse(parsed.passed)
        self.assertEqual(parsed.ideal_output, "Expected")
        self.assertEqual(parsed.raw_response, "not json")

    def test_ranking_sorts_by_score_pass_latency_errors(self):
        results = [
            {
                "model": "slow",
                "score": 90,
                "passed": True,
                "latency_seconds": 10,
                "ollama_status": "ok",
                "judge": {"errors": []},
            },
            {
                "model": "fast",
                "score": 90,
                "passed": True,
                "latency_seconds": 5,
                "ollama_status": "ok",
                "judge": {"errors": []},
            },
            {
                "model": "top",
                "score": 95,
                "passed": False,
                "latency_seconds": 20,
                "ollama_status": "ok",
                "judge": {"errors": [{"type": "wrong_casing", "severity": "minor"}]},
            },
            {
                "model": "fast_with_error",
                "score": 90,
                "passed": True,
                "latency_seconds": 5,
                "ollama_status": "ok",
                "judge": {"errors": [{"type": "other", "severity": "minor"}]},
            },
        ]
        ranked = rank_models(results)
        self.assertEqual([row["model"] for row in ranked], ["top", "fast", "fast_with_error", "slow"])

    def test_report_writer_emits_valid_run_json(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "20260101-000000"
            run_data = {
                "run_id": "20260101-000000",
                "created_at": "2026-01-01T00:00:00",
                "models": ["model-a"],
                "cases": [
                    {
                        "id": "literal_question_no_answer",
                        "category": "instruction_as_content",
                        "transcript": "what is the capital of france question mark",
                        "expected": "What is the capital of France?",
                        "notes": "",
                    }
                ],
                "judge_enabled": False,
                "results": [
                    {
                        "model": "model-a",
                        "case_id": "literal_question_no_answer",
                        "category": "instruction_as_content",
                        "score": 0,
                        "passed": False,
                        "latency_seconds": 0.25,
                        "ollama_status": "ok",
                        "judge": None,
                    }
                ],
            }
            write_run_artifacts(run_dir, run_data)
            loaded = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["run_id"], "20260101-000000")
            self.assertIn("summary", loaded)
            self.assertEqual(loaded["summary"]["result_count"], 1)
            self.assertTrue((run_dir / "summary.md").exists())


if __name__ == "__main__":
    unittest.main()

