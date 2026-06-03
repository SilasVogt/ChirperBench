import json
import tempfile
import unittest
from pathlib import Path

from chirperbench.judge_codex import parse_judge_json
from chirperbench.ollama import parse_ollama_list
from chirperbench.report import rank_models, write_run_artifacts
from chirperbench.telemetry import AmdSysfsReader


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

    def test_ranking_includes_telemetry_metrics(self):
        results = [
            {
                "model": "model-a",
                "score": 80,
                "passed": True,
                "latency_seconds": 3,
                "ollama_status": "ok",
                "judge": {"errors": []},
                "telemetry": {
                    "sample_count": 2,
                    "metrics": {
                        "power_w_avg": 60.0,
                        "power_w_peak": 70.0,
                        "vram_mb_peak": 2048.0,
                        "gpu_busy_percent_avg": 75.0,
                    },
                },
            },
            {
                "model": "model-a",
                "score": 90,
                "passed": True,
                "latency_seconds": 2,
                "ollama_status": "ok",
                "judge": {"errors": []},
                "telemetry": {
                    "sample_count": 2,
                    "metrics": {
                        "power_w_avg": 80.0,
                        "power_w_peak": 90.0,
                        "vram_mb_peak": 4096.0,
                        "gpu_busy_percent_avg": 95.0,
                    },
                },
            },
        ]
        ranked = rank_models(results)
        self.assertEqual(ranked[0]["telemetry_sample_count"], 4)
        self.assertEqual(ranked[0]["median_power_w_avg"], 70.0)
        self.assertEqual(ranked[0]["peak_power_w"], 90.0)
        self.assertEqual(ranked[0]["median_vram_mb_peak"], 3072.0)
        self.assertEqual(ranked[0]["median_gpu_busy_percent_avg"], 85.0)

    def test_amd_sysfs_reader_parses_common_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            device = Path(temp) / "card0" / "device"
            hwmon = device / "hwmon" / "hwmon0"
            hwmon.mkdir(parents=True)
            (device / "vendor").write_text("0x1002\n", encoding="utf-8")
            (device / "mem_info_vram_used").write_text(str(2 * 1024 * 1024), encoding="utf-8")
            (device / "mem_info_vram_total").write_text(str(8 * 1024 * 1024), encoding="utf-8")
            (device / "gpu_busy_percent").write_text("42\n", encoding="utf-8")
            (hwmon / "name").write_text("amdgpu\n", encoding="utf-8")
            (hwmon / "power1_average").write_text("30000000\n", encoding="utf-8")

            reader = AmdSysfsReader.from_device(device, "card0")
            sample = reader.sample()
            self.assertEqual(reader.status, "ok")
            self.assertEqual(sample["power_w"], 30.0)
            self.assertEqual(sample["vram_mb"], 2.0)
            self.assertEqual(sample["vram_total_mb"], 8.0)
            self.assertEqual(sample["gpu_busy_percent"], 42.0)

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
                "telemetry": {
                    "mode": "auto",
                    "status": "ok",
                    "provider": "amd-sysfs",
                },
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
                        "telemetry": {
                            "status": "ok",
                            "provider": "amd-sysfs",
                            "sample_count": 1,
                            "metrics": {
                                "power_w_avg": 40.0,
                                "vram_mb_peak": 1024.0,
                            },
                        },
                    }
                ],
            }
            write_run_artifacts(run_dir, run_data)
            loaded = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["run_id"], "20260101-000000")
            self.assertIn("summary", loaded)
            self.assertEqual(loaded["summary"]["result_count"], 1)
            self.assertTrue(loaded["summary"]["telemetry"]["available"])
            self.assertTrue((run_dir / "summary.md").exists())


if __name__ == "__main__":
    unittest.main()
