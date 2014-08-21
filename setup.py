import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()


requires = ['gevent']


setup(name='loads-tester',
      version='0.1',
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
      test_suite='nose.collector'
      )
