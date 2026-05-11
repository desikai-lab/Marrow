# Compatibility shim — do not delete until all import sites are confirmed migrated.
# Real app assembly lives in transport/app_factory.py
from transport.app_factory import app  # noqa: F401
