"""Files service implementing S3-backed storage with filesystem fallback.

This service exposes a small API for uploading, listing, downloading (presigned URL),
deleting, renaming and copying files. It mirrors the public/ layout recommended in the project.
"""
from typing import Optional, List
import os
import shutil
from datetime import datetime
import uuid

from fastapi import UploadFile

from ..aws.client import get_aws_client
from .models import TipoArchivoEnum
from database import supabase

aws = get_aws_client()


class FileService:
    def __init__(self, base_public: str = "public"):
        self.base_public = base_public
        self.base_public = base_public
        # ensure S3 is enabled at service startup
        if not aws.is_enabled():
            raise RuntimeError("S3 is not enabled. Set USE_S3 and S3_BUCKET environment variables to enable S3 storage.")

    def _local_path(self, relative_path: str) -> str:
        if relative_path.startswith('/'):
            relative_path = relative_path[1:]
        return os.path.join(os.getcwd(), relative_path)

    def _s3_key(self, relative_path: str) -> str:
        if relative_path.startswith('/'):
            relative_path = relative_path[1:]
        return relative_path

    def _infer_id_clase_from_key(self, key: str) -> Optional[int]:
        # attempt to infer class id from common prefixes
        try:
            parts = key.split('/')
            # uploaded/class/{id}/...
            if len(parts) >= 3 and parts[0] == 'uploaded' and parts[1] == 'class':
                return int(parts[2])
            # generated/images/class/{id}/...
            if len(parts) >= 4 and parts[0] == 'generated' and parts[1] == 'images' and parts[2] == 'class':
                return int(parts[3])
            # generated/audio/{id}/...
            if len(parts) >= 3 and parts[0] == 'generated' and parts[1] == 'audio':
                return int(parts[2])
        except Exception:
            return None
        return None

    def _insert_archivo_record(self, id_clase: Optional[int], filename: str, tipo: str, filepath: str, original_filename: Optional[str] = None, id_silabo: Optional[int] = None, descripcion: Optional[str] = None) -> Optional[dict]:
        try:
            record = {
                "id_clase": id_clase,
                "id_silabo": id_silabo,
                "filename": filename,
                "tipo": tipo,
                "original_filename": original_filename or filename,
                "filepath": filepath,
                "created_at": datetime.utcnow().isoformat(),
                "descripcion": descripcion
            }
            resp = supabase.table("archivos").insert(record).execute()
            return resp.data[0] if resp and getattr(resp, 'data', None) else None
        except Exception as e:
            print(f"_insert_archivo_record error: {e}")
            return None

    async def save_teacher_photo(self, file: UploadFile, teacher_id: int) -> Optional[str]:
        """Save teacher photo to S3 or local FS and return relative path like /public/generated/{teacher_id}/images/filename"""
        ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique = str(uuid.uuid4())[:8]
        filename = f"docente_{teacher_id}_{timestamp}_{unique}{ext}"
        # new teacher photo path under uploaded/teacher/{teacher_id}
        relative = f"uploaded/teacher/{teacher_id}/images/{filename}"

        try:
            client = aws.get_client()
            bucket = aws.get_bucket()
            if client is None or bucket is None:
                raise RuntimeError("S3 client or bucket not configured")
            file.file.seek(0)
            client.upload_fileobj(file.file, bucket, self._s3_key(relative), ExtraArgs={"ContentType": file.content_type or "application/octet-stream"})
            # record in DB
            try:
                # teacher photos are considered 'Subido'
                self._insert_archivo_record(None, filename, TipoArchivoEnum.SUBIDO.value, f"/{relative}", original_filename=file.filename)
            except Exception:
                pass
            return f"/{relative}"
        except Exception as e:
            print(f"save_teacher_photo error: {e}")
            return None
        finally:
            try:
                file.file.close()
            except Exception:
                pass

    def upload_bytes(self, data: bytes, relative_path: str, content_type: Optional[str] = None, descripcion: Optional[str] = None) -> bool:
        client = aws.get_client()
        bucket = aws.get_bucket()
        if client is None or bucket is None:
            raise RuntimeError("S3 client or bucket not configured")
        try:
            client.put_object(Bucket=bucket, Key=self._s3_key(relative_path), Body=data, ContentType=content_type or "application/octet-stream")
            # If this looks like a generated file, insert record into archivos
            try:
                key = self._s3_key(relative_path)
                filename = key.split('/')[-1]
                id_clase = self._infer_id_clase_from_key(key)
                # mark as 'Generado'
                self._insert_archivo_record(id_clase, filename, TipoArchivoEnum.GENERADO.value, f"/{key}", descripcion=descripcion)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"upload_bytes error: {e}")
            return False

    async def upload_multiple_files(self, files: List[UploadFile], class_id: int, id_silabo: Optional[int] = None) -> List[dict]:
        """Upload multiple UploadFile objects to S3 under uploaded/class/{class_id}/ and insert metadata into the 'archivos' table.

        Returns a list of dicts with upload results: {'filename', 'path', 'db_result'}
        """
        results = []
        client = aws.get_client()
        bucket = aws.get_bucket()
        if client is None or bucket is None:
            raise RuntimeError("S3 client or bucket not configured")

        for file in files:
            try:
                filename = file.filename or f"uploaded_{str(uuid.uuid4())[:8]}"
                relative = f"uploaded/class/{class_id}/{filename}"
                # upload
                file.file.seek(0)
                client.upload_fileobj(file.file, bucket, self._s3_key(relative), ExtraArgs={"ContentType": file.content_type or "application/octet-stream"})

                # insert into supabase 'archivos' table using helper
                db_result = None
                try:
                    db_result = self._insert_archivo_record(class_id, filename, TipoArchivoEnum.SUBIDO.value, f"/{relative}", original_filename=file.filename, id_silabo=id_silabo)
                except Exception as db_e:
                    print(f"supabase insert error: {db_e}")

                results.append({"filename": filename, "path": f"/{relative}", "db_result": db_result})
            except Exception as e:
                print(f"upload_multiple_files error for file {getattr(file, 'filename', None)}: {e}")
                results.append({"filename": getattr(file, 'filename', None), "path": None, "db_result": None, "error": str(e)})
            finally:
                try:
                    file.file.close()
                except Exception:
                    pass

        return results

    def get_presigned_url(self, relative_path: str, expires_in: int = 3600) -> Optional[str]:
        client = aws.get_client()
        bucket = aws.get_bucket()
        if client is None or bucket is None:
            raise RuntimeError("S3 client or bucket not configured")
        try:
            url = client.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': self._s3_key(relative_path)}, ExpiresIn=expires_in)
            return url
        except Exception as e:
            print(f"get_presigned_url error: {e}")
            return None

    def list_files(self, prefix: str = None) -> List[str]:
        out: List[str] = []
        client = aws.get_client()
        bucket = aws.get_bucket()
        if client is None or bucket is None:
            raise RuntimeError("S3 client or bucket not configured")
        try:
            paginator = client.get_paginator('list_objects_v2')
            if prefix and prefix.startswith('/'):
                prefix = prefix[1:]
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix or f"{self.base_public}/"):
                for obj in page.get('Contents', []):
                    out.append(obj['Key'])
            return out
        except Exception as e:
            print(f"list_files error: {e}")
            return []

    def download_to_local(self, relative_path: str, dest_path: str) -> bool:
        client = aws.get_client()
        bucket = aws.get_bucket()
        if client is None or bucket is None:
            raise RuntimeError("S3 client or bucket not configured")
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            client.download_file(bucket, self._s3_key(relative_path), dest_path)
            return True
        except Exception as e:
            print(f"download_to_local error: {e}")
            return False

    def delete_file(self, relative_path: str) -> bool:
        client = aws.get_client()
        bucket = aws.get_bucket()
        if client is None or bucket is None:
            raise RuntimeError("S3 client or bucket not configured")
        try:
            client.delete_object(Bucket=bucket, Key=self._s3_key(relative_path))
            # delete DB record if present
            try:
                key = self._s3_key(relative_path)
                filename = key.split('/')[-1]
                # delete any matching record
                supabase.table('archivos').delete().eq('filename', filename).eq('filepath', f"/{key}").execute()
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"delete_file error: {e}")
            return False

    def rename_file(self, old_relative: str, new_relative: str) -> bool:
        client = aws.get_client()
        bucket = aws.get_bucket()
        if client is None or bucket is None:
            raise RuntimeError("S3 client or bucket not configured")
        try:
            copy_source = {'Bucket': bucket, 'Key': self._s3_key(old_relative)}
            client.copy(copy_source, bucket, self._s3_key(new_relative))
            client.delete_object(Bucket=bucket, Key=self._s3_key(old_relative))
            # update DB record filepath/filename if exists
            try:
                old_key = self._s3_key(old_relative)
                new_key = self._s3_key(new_relative)
                old_filename = os.path.basename(old_key)
                new_filename = os.path.basename(new_key)
                supabase.table('archivos').update({"filename": new_filename, "filepath": f"/{new_key}"}).eq('filename', old_filename).eq('filepath', f"/{old_key}").execute()
            except Exception as e:
                print(f"rename DB update error: {e}")
            return True
        except Exception as e:
            print(f"rename_file error: {e}")
            return False

    def copy_file(self, src_relative: str, dest_relative: str) -> bool:
        client = aws.get_client()
        bucket = aws.get_bucket()
        if client is None or bucket is None:
            raise RuntimeError("S3 client or bucket not configured")
        try:
            copy_source = {'Bucket': bucket, 'Key': self._s3_key(src_relative)}
            client.copy(copy_source, bucket, self._s3_key(dest_relative))
            # insert DB record for the copied file
            try:
                new_key = self._s3_key(dest_relative)
                filename = os.path.basename(new_key)
                id_clase = self._infer_id_clase_from_key(new_key)
                self._insert_archivo_record(id_clase, filename, TipoArchivoEnum.GENERADO.value, f"/{new_key}")
            except Exception as e:
                print(f"copy_file DB insert error: {e}")
            return True
        except Exception as e:
            print(f"copy_file error: {e}")
            return False

    def create_folder(self, relative_path: str) -> bool:
        try:
            if relative_path.startswith('/'):
                relative_path = relative_path[1:]
            client = aws.get_client()
            bucket = aws.get_bucket()
            if client is None or bucket is None:
                raise RuntimeError("S3 client or bucket not configured")
            key = self._s3_key(os.path.join(relative_path, ''))
            client.put_object(Bucket=bucket, Key=key)
            return True
        except Exception as e:
            print(f"create_folder error: {e}")
            return False


# singleton instance
file_service = FileService()
