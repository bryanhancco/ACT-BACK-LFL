"""Reusable AWS client helper for S3.

This module centralizes boto3 client creation so other modules can import
and reuse the same logic and configuration.
"""
from typing import Optional
import os
from dotenv import load_dotenv, find_dotenv

try:
    import boto3
    from botocore.exceptions import ClientError
except Exception:  # optional dependency
    boto3 = None
    ClientError = Exception

load_dotenv(find_dotenv())

class AWSClient:
    def __init__(self):
        self._enabled = os.getenv("USE_S3", "false").lower() in ("1", "true", "yes") and boto3 is not None
        self._bucket = os.getenv("S3_BUCKET")
        self._region = os.getenv("AWS_REGION") or None
        self._client = None
        if self._enabled:
            if not self._bucket:
                self._enabled = False
            else:
                try:
                    # create an S3 client
                    self._client = boto3.client(
                        "s3",
                        region_name=self._region,
                        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                    )
                except Exception as e:
                    print(f"Failed to initialize S3 client: {e}")
                    self._enabled = False
                    self._client = None

    def is_enabled(self) -> bool:
        return bool(self._enabled and self._client)

    def get_client(self):
        return self._client

    def get_bucket(self) -> Optional[str]:
        return self._bucket


# module-level singleton
_aws_client = AWSClient()


def get_aws_client() -> AWSClient:
    return _aws_client
