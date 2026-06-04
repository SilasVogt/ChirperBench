import json
import tempfile
import unittest
from pathlib import Path

from chirperbench.report import write_run_artifacts
from chirperbench.site import generate_site, make_public_run_data


class SiteTest(unittest.TestCase):
    def test_static_site_contains_required_sections_filters_and_downloads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runs_dir = root / "runs"
            run_dir = runs_dir / "20260101-000000"
            site_dir = root / "site"
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
                "judge_enabled": True,
                "results": [
                    {
                        "model": "model-a",
                        "case_id": "literal_question_no_answer",
                        "category": "instruction_as_content",
                        "output": "Paris",
                        "score": 0,
                        "passed": False,
                        "latency_seconds": 1.25,
                        "ollama_status": "ok",
                        "judge_status": "ok",
                        "stderr": "",
                        "telemetry": {
                            "status": "ok",
                            "provider": "amd-sysfs",
                            "sample_count": 3,
                            "metrics": {
                                "power_w_avg": 55.0,
                                "power_w_peak": 60.0,
                                "vram_mb_peak": 2048.0,
                                "gpu_busy_percent_avg": 70.0,
                            },
                        },
                        "judge": {
                            "stdout": "large stdout log",
                            "stderr": "large stderr log",
                            "command": ["codex", "exec"],
                            "summary": "Answered the question instead of transcribing it.",
                            "errors": [
                                {
                                    "type": "answered_content",
                                    "severity": "critical",
                                    "detail": "Output was an answer.",
                                }
                            ],
                        },
                    }
                ],
            }
            write_run_artifacts(run_dir, run_data)
            index_path = generate_site(runs_dir, site_dir)
            html = index_path.read_text(encoding="utf-8")
            self.assertIn("Overall Leaderboard", html)
            self.assertIn("Model Metrics", html)
            self.assertIn("Telemetry Graphs", html)
            self.assertIn("Outcome Graphs", html)
            self.assertIn("Pass / Fail by Transcript Category", html)
            self.assertIn("Judge Issues by Type", html)
            self.assertIn("Issue Type by Severity", html)
            self.assertIn("Compare Outputs", html)
            self.assertIn("highest score", html)
            self.assertIn("lowest latency", html)
            self.assertIn("best score/sec", html)
            self.assertIn("Score/Sec", html)
            self.assertIn("Judge Issues", html)
            self.assertIn("compareCaseSelect", html)
            self.assertIn("compareGrid", html)
            self.assertIn("Top 6", html)
            self.assertIn("Detailed Results", html)
            self.assertIn("Case Matrix", html)
            self.assertIn("average power", html)
            self.assertIn("peak VRAM", html)
            self.assertIn("average GPU busy", html)
            self.assertIn("refusal_or_meta", html)
            self.assertIn("answered_content", html)
            self.assertIn("partial_mixed_task", html)
            self.assertIn("run.json", html)
            self.assertIn("summary.md", html)

            latest = json.loads((site_dir / "data" / "latest-run.json").read_text(encoding="utf-8"))
            self.assertEqual(latest["run_id"], "20260101-000000")
            self.assertTrue(latest["summary"]["telemetry"]["available"])
            self.assertNotIn("stderr", latest["results"][0])
            self.assertNotIn("stdout", latest["results"][0]["judge"])
            self.assertNotIn("command", latest["results"][0]["judge"])
            self.assertTrue((site_dir / "data" / "20260101-000000.json").exists())

    def test_public_run_data_strips_large_process_logs(self):
        public = make_public_run_data(
            {
                "run_id": "run",
                "models": ["model-a"],
                "cases": [],
                "summary": {},
                "results": [
                    {
                        "model": "model-a",
                        "case_id": "case-a",
                        "output": "clean text",
                        "stderr": "ansi spinner log",
                        "ollama_command": ["ollama", "run"],
                        "judge": {
                            "summary": "ok",
                            "stdout": "huge stdout",
                            "stderr": "huge stderr",
                            "command": ["codex", "exec"],
                            "errors": [],
                        },
                    }
                ],
            }
        )
        result = public["results"][0]
        self.assertEqual(result["output"], "clean text")
        self.assertNotIn("stderr", result)
        self.assertNotIn("ollama_command", result)
        self.assertNotIn("stdout", result["judge"])
        self.assertNotIn("command", result["judge"])


if __name__ == "__main__":
    unittest.main()
