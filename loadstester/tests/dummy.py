from loadstester.case import TestCase


class TestDummy(TestCase):
    def test_dummy(self):
        res = self.session.get('http://google.com')
        self.incr_counter('dummy')
