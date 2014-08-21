import urlparse
import socket
import random


_DNS_CACHE = {}


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
