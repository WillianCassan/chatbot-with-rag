import os
from minio import Minio
from fastapi.responses import StreamingResponse
import io


class MinioRepository:
    def __init__(self):
        self.client = None
        self.bucket = None
        self._initialized = False

    def _ensure_initialized(self):
        """Inicializa o cliente MinIO apenas quando necessário"""
        if not self._initialized:
            minio_endpoint = os.getenv("MINIO_ENDPOINT")
            minio_access_key = os.getenv("MINIO_ACCESS_KEY")
            minio_secret_key = os.getenv("MINIO_SECRET_KEY")
            minio_secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
            minio_bucket = os.getenv("MINIO_BUCKET")
            
            if not all([minio_endpoint, minio_access_key, minio_secret_key, minio_bucket]):
                raise ValueError("Variáveis de ambiente MinIO não configuradas corretamente")
            
            self.client = Minio(
                minio_endpoint,
                access_key=minio_access_key,
                secret_key=minio_secret_key,
                secure=minio_secure,
            )
            self.bucket = minio_bucket
            self._ensure_bucket_exists()
            self._initialized = True

    def _ensure_bucket_exists(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    async def upload_file(self, filename: str, file_stream: io.BytesIO):
        self._ensure_initialized()
        file_stream.seek(0)

        self.client.put_object(
            bucket_name=self.bucket,
            object_name=filename,
            data=file_stream,
            length=file_stream.getbuffer().nbytes,
            content_type="application/octet-stream",
        )

    def delete_file(self, filename: str):
        self._ensure_initialized()
        self.client.remove_object(self.bucket, filename)

    def download_file(self, filename: str):
        self._ensure_initialized()
        response = self.client.get_object(self.bucket, filename)

        return StreamingResponse(
            response,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def list_files(self):
        self._ensure_initialized()
        files = []
        objetos = self.client.list_objects(self.bucket)

        for obj in objetos:
            files.append(obj.object_name)

        return {"files": files}
