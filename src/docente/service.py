from typing import Optional, Dict, Any
from database import supabase
from ..files.service import file_service
from ..generative_ai.service_image import image_processor
import os
from datetime import datetime
import hashlib


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def create_docente(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = data.copy()
    data["password"] = hash_password(data["password"])
    resp = supabase.table("docente").insert(data).execute()
    return resp.data[0] if getattr(resp, 'data', None) else None


def find_docente_by_email(correo: str) -> Optional[Dict[str, Any]]:
    resp = supabase.table("docente").select("*").eq("correo", correo).execute()
    return resp.data[0] if getattr(resp, 'data', None) else None


def update_docente(id_docente: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if 'password' in update_data:
        update_data['password'] = hash_password(update_data['password'])
    # Perform update. The Supabase Python client may not support chaining select() after update
    # (causes SyncFilterRequestBuilder error). So execute the update, then fetch the public
    # fields with get_docente to guarantee a consistent response shape.
    resp = supabase.table("docente").update(update_data).eq("id", id_docente).execute()
    if not getattr(resp, 'data', None):
        return None
    # Return the public view of the docente (selects specific columns)
    return get_docente(id_docente)


def get_docente(id_docente: int) -> Optional[Dict[str, Any]]:
    resp = supabase.table("docente").select("id, nombre, correo, foto, foto_caricatura").eq("id", id_docente).execute()
    return resp.data[0] if getattr(resp, 'data', None) else None


def list_docentes() -> list:
    resp = supabase.table("docente").select("id, nombre, correo, foto, foto_caricatura").execute()
    return resp.data or []


async def save_teacher_photo(upload_file, teacher_id: int) -> Optional[str]:
    """Upload photo using file_service and return relative S3 path like /uploaded/teacher/{id}/images/{filename}"""
    try:
        return await file_service.save_teacher_photo(upload_file, teacher_id)
    except Exception as e:
        print(f"save_teacher_photo error: {e}")
        return None


def generate_cartoon_from_s3_path(s3_relative_path: str, teacher_id: int) -> Optional[str]:
    """Given a presigned or public URL (s3_relative_path may be a full URL), call image_processor.convert_to_cartoon
    which will upload the cartoon to S3 and return the S3 path.
    """
    try:
        return image_processor.convert_to_cartoon(s3_relative_path, teacher_id)
    except Exception as e:
        print(f"generate_cartoon error: {e}")
        return None


def delete_teacher_photos(docente_record: Dict[str, Any]) -> None:
    try:
        if docente_record.get('foto'):
            file_service.delete_file(docente_record['foto'])
        if docente_record.get('foto_caricatura') and docente_record['foto_caricatura'] != docente_record.get('foto'):
            file_service.delete_file(docente_record['foto_caricatura'])
    except Exception as e:
        print(f"delete_teacher_photos error: {e}")
