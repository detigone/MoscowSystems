import warnings

# Harmless PyMongo/PyOpenSSL warning on some Atlas certs (Python 3.14 + cryptography 50+).
warnings.filterwarnings(
    "ignore",
    message="Parsed a serial number which wasn't positive",
)

from erm import run

run()
