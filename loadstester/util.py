from logging import handlers
import urlparse
import socket
import random
import logging
import sys
import os
import zipfile
import fnmatch
from StringIO import StringIO
import json
import datetime


_DNS_CACHE = {}
logger = logging.getLogger('loads')


def total_seconds(td):
    # works for 2.7 and 2.6
    diff = (td.seconds + td.days * 24 * 3600) * 10 ** 6
    return (td.microseconds + diff) / float(10 ** 6)



class DateTimeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.timedelta):
            return total_seconds(obj)
        else:
            return super(DateTimeJSONEncoder, self).default(obj)


def set_logger(debug=False, name='loads', logfile='stdout'):
    # setting up the logger
    logger_ = logging.getLogger(name)
    logger_.setLevel(logging.DEBUG)

    if logfile == 'stdout':
        ch = logging.StreamHandler()
    else:
        ch = handlers.RotatingFileHandler(logfile, mode='a+')

    if debug:
        ch.setLevel(logging.DEBUG)
    else:
        ch.setLevel(logging.INFO)

    formatter = logging.Formatter('[%(asctime)s][%(process)d] %(message)s')
    ch.setFormatter(formatter)
    logger_.addHandler(ch)

    # for the tests
    if 'TESTING' in os.environ:
        fh = logging.FileHandler('/tmp/loads.log')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)


def dns_resolve(url):
    """Resolve hostname in the given url, using cached results where possible.

    Given a url, this function does DNS resolution on the contained hostname
    and returns a 3-tuple giving:  the URL with hostname replace by IP addr,
    the original hostname string, and the resolved IP addr string.

    The results of DNS resolution are cached to make sure this doesn't become
    a bottleneck for the loadtest.  If the hostname resolves to multiple
    addresses then a random address is chosen.
    """
    parts = urlparse.urlparse(url)
    netloc = parts.netloc.rsplit(':')
    if len(netloc) == 1:
        netloc.append('80')

    original = netloc[0]
    addrs = _DNS_CACHE.get(original)
    if addrs is None:
        addrs = socket.gethostbyname_ex(original)[2]
        _DNS_CACHE[original] = addrs

    resolved = random.choice(addrs)
    netloc = resolved + ':' + netloc[1]
    parts = (parts.scheme, netloc) + parts[2:]
    return urlparse.urlunparse(parts), original, resolved


# taken from distutils2
def resolve_name(name):
    """Resolve a name like ``module.object`` to an object and return it.

    This functions supports packages and attributes without depth limitation:
    ``package.package.module.class.class.function.attr`` is valid input.
    However, looking up builtins is not directly supported: use
    ``__builtin__.name``.

    Raises ImportError if importing the module fails or if one requested
    attribute is not found.
    """

    # Depending how loads is ran, "" can or cannot be present in the path. This
    # adds it if it's missing.
    if len(sys.path) < 1 or sys.path[0] not in ('', os.getcwd()):
        sys.path.insert(0, '')

    if '.' not in name:
        # shortcut
        __import__(name)
        return sys.modules[name]

    # FIXME clean up this code!
    parts = name.split('.')
    cursor = len(parts)
    module_name = parts[:cursor]
    ret = ''

    while cursor > 0:
        try:
            ret = __import__('.'.join(module_name))
            break
        except ImportError:
            cursor -= 1
            module_name = parts[:cursor]

    if ret == '':
        raise ImportError(parts[0])

    for part in parts[1:]:
        try:
            ret = getattr(ret, part)
        except AttributeError, exc:
            raise ImportError(exc)

    return ret


def glob(patterns, location='.'):
    for pattern in patterns:
        basedir, pattern = os.path.split(pattern)
        basedir = os.path.abspath(os.path.join(location, basedir))
        for file_ in os.listdir(basedir):
            if fnmatch.fnmatch(file_, pattern):
                yield os.path.join(basedir, file_)


def pack_include_files(include_files, location='.'):
    """Package up the specified include_files into a zipfile data bundle.

    This is a convenience function for packaging up data files into a binary
    blob, that can then be shipped to the different agents.  Unpack the files
    using unpack_include_files().
    """
    file_data = StringIO()
    zf = zipfile.ZipFile(file_data, "w", compression=zipfile.ZIP_DEFLATED)

    def store_file(name, filepath):
        info = zipfile.ZipInfo(name)
        info.external_attr = os.stat(filepath).st_mode << 16L
        with open(filepath) as f:
            zf.writestr(info, f.read())

    for basepath in glob(include_files, location):
        basedir, basename = os.path.split(basepath)
        if not os.path.isdir(basepath):
            store_file(basename, basepath)
        else:
            for root, dirnames, filenames in os.walk(basepath):
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    store_file(filepath[len(basedir):], filepath)

    zf.close()
    return file_data.getvalue().encode('base64')


def maybe_makedirs(dirpath):
    """Like os.makedirs, but no error if the final directory exists."""
    if not os.path.isdir(dirpath):
        os.makedirs(dirpath)


def unpack_include_files(file_data, location='.'):
    """Unpack a blob of include_files data into the specified directory.

    This is a convenience function for unpackaging data files from a binary
    blob, that can be used on the different agents.  It accepts data in the
    format produced by pack_include_files().
    """
    file_data = str(file_data).decode('base64')
    zf = zipfile.ZipFile(StringIO(file_data))

    for itemname in zf.namelist():
        itempath = os.path.join(location, itemname.lstrip("/"))
        if itemname.endswith("/"):
            maybe_makedirs(itempath)
        else:
            maybe_makedirs(os.path.dirname(itempath))
            with open(itempath, "w") as f:
                f.write(zf.read(itemname))
            mode = zf.getinfo(itemname).external_attr >> 16L
            if mode:
                os.chmod(itempath, mode)
    zf.close()
