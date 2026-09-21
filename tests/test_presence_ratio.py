import unittest

from services import presence_tracker


class PresenceRatioTests(unittest.TestCase):
    def tearDown(self):
        presence_tracker.reset(9001)

    def test_present_absent_present_timeline(self):
        presence_tracker.observe(9001, True, 0)
        presence_tracker.observe(9001, False, 10)
        presence_tracker.observe(9001, True, 12)
        result = presence_tracker.finalize(9001, 30)
        self.assertEqual(result["active_seconds"], 30.0)
        self.assertEqual(result["present_seconds"], 28.0)
        self.assertEqual(result["absent_seconds"], 2.0)
        self.assertAlmostEqual(result["presence_ratio"], 28 / 30, places=6)

    def test_continuous_presence_is_one(self):
        presence_tracker.observe(9001, True, 10)
        result = presence_tracker.finalize(9001, 20)
        self.assertEqual(result["presence_ratio"], 1.0)

    def test_all_absent_is_zero(self):
        presence_tracker.observe(9001, False, 10)
        result = presence_tracker.finalize(9001, 20)
        self.assertEqual(result["presence_ratio"], 0.0)

    def test_multiple_absence_intervals_and_return(self):
        presence_tracker.observe(9001, True, 0)
        presence_tracker.observe(9001, False, 5)
        presence_tracker.observe(9001, True, 7)
        presence_tracker.observe(9001, False, 10)
        presence_tracker.observe(9001, True, 13)
        result = presence_tracker.finalize(9001, 20)
        self.assertEqual(result["present_seconds"], 15.0)
        self.assertEqual(result["absent_seconds"], 5.0)
        self.assertAlmostEqual(result["presence_ratio"], 0.75, places=6)

    def test_termination_closes_monitoring_at_termination(self):
        presence_tracker.observe(9001, True, 100)
        presence_tracker.observe(9001, False, 108)
        result = presence_tracker.finalize(9001, 110)
        self.assertEqual(result["active_seconds"], 10.0)
        self.assertEqual(result["presence_ratio"], 0.8)


if __name__ == "__main__":
    unittest.main()
