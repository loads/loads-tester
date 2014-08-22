import os
from setuptools import setup, find_packages
from loadstester import __version__

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()


requires = ['gevent', 'ws4py', 'wsgiproxy2', 'requests', 'webtest']


setup(name='loads-tester',
      version=__version__,
      packages=find_packages(),
      include_package_data=True,
      description='The Loads agent',
      long_description=README,
      zip_safe=False,
      license='APLv2.0',
      classifiers=[
        "Programming Language :: Python",
      ],
      install_requires=requires,
      author='Mozilla Services',
      author_email='services-dev@mozilla.org',
      url='https://github.com/mozilla-services/loads-agent',
      tests_require=['nose', 'mock', 'unittest2'],
      test_suite='nose.collector',
      entry_points="""
      [console_scripts]
      loads-runner  = loadstester.main:main
      """)
