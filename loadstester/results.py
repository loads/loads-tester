import unittest


class Results(unittest.TestResult):
    """The Results class does two things:

    - emit the event in a json stream
    - call the usual unittest API so the tests work with Nose or Unittest(2).

    """
    def __init__(self, streamer=None):
        self.streamer = streamer
        unittest.TestResult.__init__(self)

    def _stream(self, action, test, kw):
        if not self.streamer:
            return
        data = kw
        data.update(test.loads_status)
        self.streamer.push(action, **data)

    def startTest(self, test, *args, **kw):
        unittest.TestResult.startTest(self, test)
        self._stream('startTest', test, kw)

    def stopTest(self, test, *args, **kw):
        unittest.TestResult.stopTest(self, test)
        self._stream('stopTest', test, kw)

    def addError(self, test, exc_info, *args, **kw):
        unittest.TestResult.addError(self, test, exc_info)
        self._stream('addError', test, kw)

    def addFailure(self, test, exc_info, *args, **kw):
        unittest.TestResult.addFailure(self, test, exc_info)
        self._stream('addFailure', test, kw)

    def addSuccess(self, test, *args, **kw):
        unittest.TestResult.addSuccess(self, test)
        self._stream('addSuccess', test, kw)

    def incr_counter(self, test, *args, **kw):
        self._stream('incr_counter', test, kw)
