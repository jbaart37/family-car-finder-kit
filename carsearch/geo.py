"""ZIP-to-ZIP distance. pgeocode downloads the GeoNames US ZIP table once and caches it."""
import math
import os
import sys
import time
from functools import lru_cache

_geo = None
_failed_at = 0.0   # when the ZIP table last failed to load; we retry after a while instead of on every listing
RETRY_AFTER = 600
_certifi_added = False


def use_certifi():
    """python.org's Mac installer ships without CA certificates until its "Install Certificates" step is run, so
    Python's HTTPS downloads fail with CERTIFICATE_VERIFY_FAILED. Add certifi's bundle (the one `requests` uses) to the
    default HTTPS settings that urllib uses, and point SSL_CERT_FILE at it for anything else."""
    global _certifi_added
    try:
        import certifi
    except ImportError:
        return
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    if _certifi_added:
        return
    import ssl
    base = ssl.create_default_context

    def with_certifi(purpose=ssl.Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None):
        ctx = base(purpose, cafile=cafile, capath=capath, cadata=cadata)
        if purpose == ssl.Purpose.SERVER_AUTH and not (cafile or capath or cadata):
            ctx.load_verify_locations(certifi.where())   # in addition to the system's certificates
        return ctx

    ssl._create_default_https_context = with_certifi   # what urllib.request / http.client call for https URLs
    import urllib.request
    urllib.request.install_opener(None)   # urlopen builds its HTTPS settings once; rebuild them with certifi included
    _certifi_added = True


use_certifi()   # at startup, before anything downloads


def _load():
    global _geo, _failed_at
    if _geo is None and time.time() - _failed_at > RETRY_AFTER:
        try:
            use_certifi()
            import pgeocode
            _geo = pgeocode.GeoDistance("us")
        except Exception as e:  # no network, certificate trouble, ...: carry on without distances
            _failed_at = time.time()
            print(f"warning: couldn't load the ZIP-code table ({type(e).__name__}: {str(e)[:150]}). "
                  "Cars will show without distances this time.", file=sys.stderr)
    return _geo


@lru_cache(maxsize=4096)
def miles_between(zip_a, zip_b):
    """Miles between two ZIP codes, or None if unknown. Never raises: one missing distance shouldn't sink a search."""
    if not zip_a or not zip_b or _load() is None:
        return None
    try:
        km = _geo.query_postal_code(zip_a[:5], zip_b[:5])
    except Exception:
        return None
    if km is None or (isinstance(km, float) and math.isnan(km)):
        return None
    return round(float(km) * 0.621371, 1)
