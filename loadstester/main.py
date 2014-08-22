import argparse
import sys
import json

from loadstester.runner import Runner


def main(sysargs=sys.argv):
    # parsing the command line
    parser = argparse.ArgumentParser(description='Runs a load test.')
    parser.add_argument('options', help='Running options', type=str,
                        default='', nargs='?')

    args = parser.parse_args(sysargs[1:])

    if not args.options:
        options = {}
    else:
        try:
            options = json.loads(args.options)
        except ValueError:
            print('Could not load options')
            raise

    # XXX todo - control the options
    return Runner(options).execute()
