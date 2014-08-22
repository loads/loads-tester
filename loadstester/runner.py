import os
import subprocess
import sys

import gevent

from loadstester.util import (resolve_name, logger, pack_include_files,
                              unpack_include_files)
from loadstester.results import Results
from loadstester.case import TestCase
from loadstester.streamer import StdoutStreamer


DEFAULT_LOGFILE = os.path.join('/tmp', 'loads-worker.log')


def _compute_arguments(args):
    """
    Read the given :param args: and builds up the total number of runs, the
    number of hits, duration, users and agents to use.

    Returns a tuple of (total, hits, duration, users, agents).
    """
    users = args.get('users', '1')
    if isinstance(users, str):
        users = users.split(':')
    users = [int(user) for user in users]
    hits = args.get('hits')
    duration = args.get('duration')
    if duration is None and hits is None:
        hits = '1'

    if hits is not None:
        if isinstance(hits, int):
            hits = [hits]
        elif not isinstance(hits, list):
            hits = [int(hit) for hit in hits.split(':')]

    agents = args.get('agents', 1)

    # XXX duration based == no total
    total = 0
    if duration is None:
        for user in users:
            total += sum([hit * user for hit in hits])
        if agents is not None:
            total *= agents

    return total, hits, duration, users, agents


class Runner(object):
    """Local tests runner.

    Runs the tests for the given number of users.
    """

    name = 'local'
    options = {}

    def __init__(self, args):
        self.args = args
        self.fqn = args.get('fqn',
                            'loadstester.tests.dummy.TestDummy.test_dummy')
        self.test = None
        self.run_id = None
        self.project_name = args.get('project_name', 'N/A')
        self._test_result = None
        self.outputs = []
        self.stop = False

        (self.total, self.hits,
         self.duration, self.users, self.agents) = _compute_arguments(args)

        self.args['hits'] = self.hits
        self.args['users'] = self.users
        self.args['agents'] = self.agents
        self.args['total'] = self.total

    def _resolve_name(self):
        if self.fqn is not None:
            try:
                self.test = resolve_name(self.fqn)
                if not hasattr(self.test, 'im_class'):
                    raise ValueError("The FQN of the test doesn't point "
                                     " to a test class (%s)." % self.test)
            except Exception:
                self.test = TestCase()
                raise

    @property
    def test_result(self):
        if self._test_result is None:
            self._test_result = Results(streamer=StdoutStreamer(),
                                        args=self.args)
        return self._test_result

    def _deploy_python_deps(self, deps=None):
        # XXX pip hack to avoid uninstall
        # deploy python deps if asked
        deps = deps or self.args.get('python_dep', [])
        if deps == []:
            return

        # accepting lists and list of comma-separated values
        pydeps = []
        for dep in deps:
            dep = [d.strip() for d in dep.split(',')]
            for d in dep:
                if d == '':
                    continue
                pydeps.append(d)

        build_dir = os.path.join(self.args['test_dir'],
                                 'build-', str(os.getpid()))
        nil = "lambda *args, **kw: None"
        code = ["from pip.req import InstallRequirement",
                "InstallRequirement.uninstall = %s" % nil,
                "InstallRequirement.commit_uninstall = %s" % nil,
                "import pip", "pip.main()"]

        cmd = [sys.executable, '-c', '"%s"' % ';'.join(code),
               'install', '-t', 'deps', '-I', '-b', build_dir]

        for dep in pydeps:
            logger.debug('Deploying %r in %r' % (dep, os.getcwd()))
            process = subprocess.Popen(' '.join(cmd + [dep]), shell=True,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            # XXX see https://github.com/mozilla-services/loads/issues/253
            if 'Successfully installed' not in stdout:
                logger.debug('Failed to deploy %r' % dep)
                logger.debug('Error: %s' % str(stderr))
                logger.debug('Stdout: %s' % str(stdout))
                logger.debug("Command used: %s" % str(' '.join(cmd + [dep])))
                raise Exception(stderr)
            else:
                logger.debug('Successfully deployed %r' % dep)

        sys.path.insert(0, 'deps')

    def _func2test(self, test):
        # creating the test case instance
        if not hasattr(test, 'im_class'):
            return test
        return test.im_class(test_name=test.__name__,
                             test_result=self.test_result,
                             config=self.args)

    def execute(self):
        """The method to start the load runner."""
        old_location = os.getcwd()
        self.running = True
        try:
            self._execute()
            if self.test_result.nb_errors + self.test_result.nb_failures:
                return 1
        except Exception:
            test = self._func2test(self.test)
            self.test_result.addError(test, sys.exc_info(), **self._status())
            raise
        finally:
            self.running = False
            os.chdir(old_location)

    def _status(self, current_hit=0, nb_hits=0, current_user=0, nb_users=0):
        return {'current_hit': current_hit,
                'current_user': current_user,
                'nb_users': nb_users,
                'nb_hits': nb_hits}

    def _run(self, current_user, nb_users):
        """This method is actually spawned by gevent so there is more than
        one actual test suite running in parallel.
        """
        # creating the test case instance
        test = self._func2test(self.test)

        if self.stop:
            return

        # starting to count at 1 for stats purposes.
        current_user += 1

        loads_status = self.args.get('loads_status',
                                     self._status(current_user=current_user,
                                                  nb_users=nb_users))

        if self.duration is None:
            for nb_hits in self.hits:
                gevent.sleep(0)
                loads_status['nb_hits'] = nb_hits

                for current_hit in range(nb_hits):
                    loads_status['current_hit'] += 1
                    test(loads_status=loads_status)
                    gevent.sleep(0)
        else:
            def spawn_test():
                while True:
                    loads_status['current_hit'] += 1
                    loads_status['nb_hits '] = loads_status['current_hit']
                    test(loads_status=loads_status)
                    gevent.sleep(0)

            spawned_test = gevent.spawn(spawn_test)
            timer = gevent.Timeout(self.duration).start()
            try:
                spawned_test.join(timeout=timer)
            except (gevent.Timeout, KeyboardInterrupt):
                pass

    def _prepare_filesystem(self):
        test_dir = self.args.get('test_dir')

        # in standalone mode we take care of creating
        # the files
        if test_dir is not None:
            test_dir = test_dir + '-%d' % os.getpid()

            if not os.path.exists(test_dir):
                os.makedirs(test_dir)

            # Copy over the include files, if any.
            # It's inefficient to package them up and then immediately
            # unpackage them, but this has the advantage of ensuring
            # consistency with how it's done in the distributed case.
            includes = self.args.get('include_file', [])
            logger.debug("unpacking %s" % str(includes))
            filedata = pack_include_files(includes)
            unpack_include_files(filedata, test_dir)

            # change to execution directory if asked
            logger.debug('chdir %r' % test_dir)
            os.chdir(test_dir)

    def _execute(self):
        """Spawn all the tests needed and wait for them to finish.
        """
        self._prepare_filesystem()
        self._deploy_python_deps()
        self._run_python_tests()

    def _run_python_tests(self):
        # resolve the name now
        logger.debug('Resolving the test fqn')
        self._resolve_name()
        logger.debug('Ready to spawn greenlets for testing.')
        agent_id = self.args.get('agent_id')
        exception = None
        try:
            if not self.args.get('no_patching', False):
                logger.debug('Gevent monkey patches the stdlib')
                from gevent import monkey
                monkey.patch_all()

            gevent.spawn(self._grefresh)

            if not self.args.get('externally_managed'):
                self.test_result.startTestRun(agent_id)

            for user in self.users:
                if self.stop:
                    break

                group = []
                for i in range(user):
                    group.append(gevent.spawn(self._run, i, user))
                    gevent.sleep(0)

                gevent.joinall(group)

            gevent.sleep(0)

            if not self.args.get('externally_managed'):
                self.test_result.stopTestRun(agent_id)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            exception = e
        finally:
            logger.debug('Test over - cleaning up')
            if exception:
                logger.debug('We had an exception, re-raising it')
                raise exception

    def refresh(self):
        if not self.stop:
            for output in self.outputs:
                if hasattr(output, 'refresh'):
                    output.refresh(self.run_id)

    def _grefresh(self):
        self.refresh()
        if not self.stop:
            gevent.spawn_later(.1, self._grefresh)
