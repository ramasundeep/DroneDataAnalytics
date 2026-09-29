"""One-shot infrastructure bootstrap: create MinIO buckets.

Run by the ``minio-init`` compose service (``python -m cdsim_common.bootstrap``)
after MinIO is healthy. Idempotent. Database schema is applied by the
TimescaleDB container itself from services/recorder/db/*.sql.
"""

from __future__ import annotations

import sys
import time

from cdsim_common.config import get_settings


def main(retries: int = 30, delay_s: float = 2.0) -> int:
    from minio import Minio

    s = get_settings()
    client = Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key.get_secret_value(),
        secure=s.minio_secure,
    )
    for attempt in range(1, retries + 1):
        try:
            for bucket in (s.recordings_bucket, s.areas_bucket):
                if not client.bucket_exists(bucket):
                    client.make_bucket(bucket)
                    print(f"created bucket {bucket}")
                else:
                    print(f"bucket {bucket} exists")
            return 0
        except Exception as exc:  # MinIO not ready yet
            print(f"attempt {attempt}/{retries}: {exc}", file=sys.stderr)
            time.sleep(delay_s)
    return 1


if __name__ == "__main__":
    sys.exit(main())
