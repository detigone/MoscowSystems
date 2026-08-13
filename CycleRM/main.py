import sys
import warnings
from pathlib import Path

_SHARED = Path(__file__).resolve().parent.parent / "shared"
if _SHARED.is_dir() and str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

# Harmless PyMongo/PyOpenSSL warning on some Atlas certs (Python 3.14 + cryptography 50+).
warnings.filterwarnings(
    "ignore",
    message="Parsed a serial number which wasn't positive",
)

from erm import run

run()
