import unittest

from chirperbench.progress import estimate_progress, format_duration, format_progress


class ProgressTest(unittest.TestCase):
    def test_format_duration(self):
        self.assertEqual(format_duration(None), "pending")
        self.assertEqual(format_duration(0), "0s")
        self.assertEqual(format_duration(59.4), "59s")
        self.assertEqual(format_duration(61), "1m 01s")
        self.assertEqual(format_duration(3661), "1h 01m 01s")

    def test_estimate_progress_calculates_eta(self):
        estimate = estimate_progress(
            completed=2,
            total=10,
            elapsed_seconds=100,
            last_seconds=40,
        )
        self.assertEqual(estimate.percent, 20.0)
        self.assertEqual(estimate.average_seconds, 50.0)
        self.assertEqual(estimate.eta_seconds, 400.0)
        self.assertEqual(estimate.last_seconds, 40)

    def test_format_progress_includes_elapsed_average_eta_and_last(self):
        text = format_progress(
            completed=2,
            total=10,
            elapsed_seconds=100,
            last_seconds=40,
        )
        self.assertIn("2/10", text)
        self.assertIn("20.0%", text)
        self.assertIn("elapsed 1m 40s", text)
        self.assertIn("avg 50s/result", text)
        self.assertIn("eta 6m 40s", text)
        self.assertIn("last 40s", text)


if __name__ == "__main__":
    unittest.main()

