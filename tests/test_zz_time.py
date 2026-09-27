import time
import unittest

from tests import START


class TimeGuard(unittest.TestCase):
    def test_suite_stays_fast(self):
        self.assertLess(time.perf_counter() - START, 15, "the suite targets 3 s; 15 s fails it")
