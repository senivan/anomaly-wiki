from __future__ import annotations

from datetime import timedelta
from typing import Protocol

import anyio

from config import Settings


class ObjectStorage(Protocol):
    async def put_object(
        self,
        *,
        storage_path: str,
        data: bytes,
        content_type: str,
    ) -> None:
        ...

    async def presigned_get_url(
        self,
        *,
        storage_path: str,
        expires_in_seconds: int,
    ) -> str:
        ...

    async def check_connection(self) -> None:
        ...


class MinioObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._bucket = settings.object_storage_bucket
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from minio import Minio

            self._client = Minio(
                self._settings.object_storage_endpoint,
                access_key=self._settings.object_storage_access_key,
                secret_key=self._settings.object_storage_secret_key,
                secure=self._settings.object_storage_secure,
            )
        return self._client

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self._bucket):
            self.client.make_bucket(self._bucket)

    async def put_object(
        self,
        *,
        storage_path: str,
        data: bytes,
        content_type: str,
    ) -> None:
        from io import BytesIO

        def _put() -> None:
            self._ensure_bucket()
            self.client.put_object(
                self._bucket,
                storage_path,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )

        await anyio.to_thread.run_sync(_put)

    async def presigned_get_url(
        self,
        *,
        storage_path: str,
        expires_in_seconds: int,
    ) -> str:
        def _url() -> str:
            self._ensure_bucket()
            return self.client.presigned_get_object(
                self._bucket,
                storage_path,
                expires=timedelta(seconds=expires_in_seconds),
            )

        return await anyio.to_thread.run_sync(_url)

    async def check_connection(self) -> None:
        await anyio.to_thread.run_sync(self._ensure_bucket)


def build_object_storage(settings: Settings) -> ObjectStorage:
    return MinioObjectStorage(settings)
