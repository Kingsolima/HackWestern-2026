"""Vultr Object Storage (S3-compatible) client for GLB/STEP files, datasheets and html evidence."""

import boto3

from app.config import settings


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
    )
