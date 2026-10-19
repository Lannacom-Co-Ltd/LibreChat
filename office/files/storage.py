"""File store for the chat's generated files: one S3 bucket, short public links, cleanup.

A file's key is <random token>/<ascii name>.<ext>. The bucket lets anyone read an object by
its exact key but not list, write or delete, so the 16-character random token is what keeps a
file private, in place of a presigned signature (letters and digits only, so nothing in it
reads as Markdown). That makes a link about 70 characters long
instead of ~320, short enough for a model to copy without corrupting it.
"""

import json
import os
import re
import secrets
import string
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, unquote, urlsplit

import boto3
from botocore.config import Config

BUCKET = os.environ.get("S3_BUCKET", "office-docs")
FILE_TTL_HOURS = float(os.environ.get("FILE_TTL_HOURS", "24"))
S3_ENDPOINT = os.environ["S3_ENDPOINT"].rstrip("/")
PUBLIC_URL = os.environ.get("S3_PUBLIC_URL", S3_ENDPOINT).rstrip("/")

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=os.environ["S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    region_name="us-east-1",
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)

TOKEN_ALPHABET = string.ascii_letters + string.digits
TOKEN_LENGTH = 16  # ~95 bits
OWN_PREFIXES = tuple({f"{PUBLIC_URL}/{BUCKET}/", f"{S3_ENDPOINT}/{BUCKET}/"})
READ_ONLY_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{BUCKET}/*"],
        }
    ],
}
OWN_LINK = re.compile(
    "(?:" + "|".join(re.escape(p) for p in OWN_PREFIXES) + r")[^\s)\]\"'<>]+"
)


def display_name(name: str, extension: str) -> str:
    """The name the browser saves the file as; Thai is kept."""
    stem = re.sub(rf"\.{extension}$", "", (name or "").strip(), flags=re.IGNORECASE)
    stem = re.sub(r"[^\w฀-๿\-]+", "_", stem).strip("_")
    return stem[:100] or "document"


def key_name(name: str) -> str:
    """ASCII part of the key, so the link carries no percent-encoded Thai."""
    stem = re.sub(r"[^A-Za-z0-9\-]+", "_", name).strip("_")
    return stem[:60] or "document"


def link(key: str) -> str:
    return f"{PUBLIC_URL}/{BUCKET}/{key}"


def own_key(url: str) -> str | None:
    """The key when url points into this bucket (signed or not), else None."""
    if not url.startswith(OWN_PREFIXES):
        return None
    return unquote(urlsplit(url).path.split(f"/{BUCKET}/", 1)[1])


def store(data: bytes, file_name: str, extension: str, content_type: str, inline=False) -> str:
    """Saves a file under a new random key and returns its public link. Documents download as
    attachments (an html file must not render on the site's own domain); images are inline."""
    name = display_name(file_name, extension)
    token = "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))
    key = f"{token}/{key_name(name)}.{extension}"
    disposition = "inline" if inline else "attachment"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
        ContentDisposition=f"{disposition}; filename*=UTF-8''{quote(f'{name}.{extension}')}",
    )
    return link(key)


def read(key: str) -> tuple[bytes, str]:
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")


def remove(key: str) -> None:
    s3.delete_object(Bucket=BUCKET, Key=key)


def ensure_bucket() -> None:
    for _ in range(60):
        try:
            if BUCKET not in [b["Name"] for b in s3.list_buckets()["Buckets"]]:
                s3.create_bucket(Bucket=BUCKET)
            s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps(READ_ONLY_POLICY))
            return
        except Exception as err:  # the store may still be starting
            print(f"waiting for store: {err}", flush=True)
            time.sleep(2)
    raise SystemExit("store did not come up")


def sweep() -> None:
    """Deletes files older than FILE_TTL_HOURS."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=FILE_TTL_HOURS)
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET)
    old = [
        {"Key": obj["Key"]}
        for page in pages
        for obj in page.get("Contents", [])
        if obj["LastModified"] < cutoff
    ]
    for i in range(0, len(old), 1000):
        s3.delete_objects(Bucket=BUCKET, Delete={"Objects": old[i : i + 1000], "Quiet": True})
    if old:
        print(f"deleted {len(old)} files older than {FILE_TTL_HOURS:g} hours", flush=True)


def sweep_forever() -> None:
    while True:
        try:
            sweep()
        except Exception as err:
            print(f"cleanup failed: {err}", flush=True)
        time.sleep(3600)
