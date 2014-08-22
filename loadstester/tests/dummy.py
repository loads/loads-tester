from loadstester.case import TestCase


class TestDummy(TestCase):
    def test_dummy(self):
        self.incr_counter('dummy')
