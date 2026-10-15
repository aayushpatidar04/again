from datetime import timedelta
from unittest import TestCase

from field_service_management.field_service_management.page.schedule_board_lunch import (
    spans_lunch,
    work_intervals,
)


class TestScheduleBoardLunch(TestCase):
    def test_visit_spanning_lunch_has_two_work_blocks(self):
        start = timedelta(hours=11)
        end = timedelta(hours=15)

        self.assertTrue(spans_lunch(start, end))
        intervals = work_intervals(start, end)
        self.assertEqual(intervals, [
            (start, timedelta(hours=12)),
            (timedelta(hours=13), end),
        ])
        self.assertEqual(
            sum((block_end - block_start for block_start, block_end in intervals), timedelta()),
            timedelta(hours=3),
        )

    def test_partial_lunch_overlap_is_not_split(self):
        start = timedelta(hours=11)
        end = timedelta(hours=12, minutes=30)

        self.assertFalse(spans_lunch(start, end))
        self.assertEqual(work_intervals(start, end), [(start, end)])

    def test_visit_after_lunch_is_unchanged(self):
        start = timedelta(hours=13)
        end = timedelta(hours=15)

        self.assertFalse(spans_lunch(start, end))
        self.assertEqual(work_intervals(start, end), [(start, end)])
