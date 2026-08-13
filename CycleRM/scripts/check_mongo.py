"""Quick MongoDB Atlas connectivity check for CycleRM."""

from __future__ import annotations

import sys

import certifi
import requests
from decouple import config
from pymongo import MongoClient
from pymongo.errors import PyMongoError


def mongo_client_kwargs() -> dict:
    return {
        "tlsCAFile": certifi.where(),
        "serverSelectionTimeoutMS": 15_000,
        "connectTimeoutMS": 15_000,
    }


def _mask_uri(uri: str) -> str:
    if "@" not in uri or "://" not in uri:
        return uri
    prefix, rest = uri.split("://", 1)
    if "@" not in rest:
        return uri
    creds, host = rest.split("@", 1)
    user = creds.split(":", 1)[0] if ":" in creds else creds
    return f"{prefix}://{user}:****@{host}"


def _public_ip() -> str | None:
    try:
        resp = requests.get("https://api.ipify.org", timeout=5)
        resp.raise_for_status()
        return resp.text.strip()
    except requests.RequestException:
        return None


def main() -> int:
    uri = config("MONGO_URL", default="").strip()
    if not uri:
        print("MONGO_URL is empty in .env")
        return 1

    print(f"Testing: {_mask_uri(uri)}")
    print(f"Python TLS CA bundle: {certifi.where()}")

    ip = _public_ip()
    if ip:
        print(f"Your public IP (whitelist this in Atlas): {ip}")
    else:
        print("Could not detect public IP — open https://ifconfig.me in a browser")

    print()

    try:
        client = MongoClient(uri, **mongo_client_kwargs())
        client.admin.command("ping")
        db_name = config("MONGO_DB_NAME", default="erm")
        collections = client[db_name].list_collection_names()
        print("MongoDB OK")
        print(f"Database '{db_name}': {len(collections)} collection(s)")
        return 0
    except PyMongoError as exc:
        print(f"MongoDB FAIL: {exc.__class__.__name__}")
        print(str(exc)[:700])
        print()
        if "access denied" in str(exc).lower():
            print(">>> tlsv1 alert access denied = Atlas blocked your IP.")
            print(">>> Fix: MongoDB Atlas -> Network Access -> Add IP Address")
            if ip:
                print(f">>> Add exactly: {ip}")
            print(">>> Or temporarily: Allow Access from Anywhere (0.0.0.0/0)")
            print(">>> Wait 1-2 minutes after saving, then run this script again.")
        else:
            print("Checklist:")
            print("1. Atlas -> Network Access -> Add Current IP (or 0.0.0.0/0 for test)")
            print("2. Atlas -> Database Access -> user has readWrite on the database")
            print("3. Atlas -> Connect -> Drivers -> copy fresh connection string to MONGO_URL")
            print("4. URL-encode special characters in the password (@ -> %40, etc.)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
