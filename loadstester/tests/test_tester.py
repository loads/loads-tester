import sys
import unittest
from StringIO import StringIO
import json

from loadstester.case import TestCase
from loadstester.results import Results
from loadstester.streamer import StdoutStreamer


# makes sure the TestCase works with Nose
class MyCase(TestCase):
    def test_dummy(self):
        pass


class TestTestCase(unittest.TestCase):
    def test_case(self):
        config = {}
        results = Results(streamer=StdoutStreamer())
        test = MyCase(test_name='test_dummy',
                      test_result=results,
                      config=config)

        status = {'run_id': '3456789'}

        old_stream = sys.stdout
        sys.stdout = StringIO()

        try:
            test(loads_status=status)
        finally:
            sys.stdout.seek(0)
            res = sys.stdout.read()
            sys.stdout = old_stream

        res = [json.loads(r.strip()) for r in res.split('\n')
               if r.strip()]
        for line in res:
            self.assertEqual(line['run_id'], status['run_id'])
