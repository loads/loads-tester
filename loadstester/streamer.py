from loadstester.util import DateTimeJSONEncoder
import json


class StdoutStreamer(object):
    def push(self, action, **data):
        res = {'action': action}
        res.update(data)
        # use sys.stdout
        print(json.dumps(res, cls=DateTimeJSONEncoder))
