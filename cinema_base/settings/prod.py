from .base import *

DEBUG = False
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost").split(",")
    if host.strip()
]

CORS_ALLOWED_ORIGINS = [
    origin
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin
]

AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")

if AWS_STORAGE_BUCKET_NAME:
    # No access keys here: boto3 takes the IAM role of the container
    s3_options = {
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "region_name": os.getenv("AWS_S3_REGION_NAME"),
        # A file with the same name replaces the old one
        "file_overwrite": True,
    }
    # Domain of CloudFront, e.g. cinebase.fun: file links in the API look
    # like https://cinebase.fun/avatars/1.webp instead of direct S3 links
    AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN")
    if AWS_S3_CUSTOM_DOMAIN:
        s3_options["custom_domain"] = AWS_S3_CUSTOM_DOMAIN
        # Public links without ?X-Amz-Signature=... in them
        s3_options["querystring_auth"] = False

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": s3_options,
        },
        "staticfiles": {
            "BACKEND": (
                "django.contrib.staticfiles.storage.StaticFilesStorage"
            ),
        },
    }

# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST"),
        "PORT": os.getenv("POSTGRES_DB_PORT", 5432),
        "OPTIONS": {"sslmode": os.getenv("POSTGRES_SSLMODE", "prefer")},
    }
}
