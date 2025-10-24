from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Optional, List
from datetime import datetime

from .service import file_service
from database import supabase

router = APIRouter(prefix="/files", tags=["files"])

@router.post("/upload-teacher-photo/{teacher_id}")
async def upload_teacher_photo(teacher_id: int, file: UploadFile = File(...)):
    path = await file_service.save_teacher_photo(file, teacher_id)
    if not path:
        raise HTTPException(status_code=500, detail="Error saving teacher photo")
    return {"path": path}


@router.post("/upload")
async def upload_file(class_id: int = Query(..., alias="class_id"), file: UploadFile = File(...)):
    """Upload a single file for a given class_id. Files are stored under uploaded/class/{class_id}/"""
    filename = file.filename or "uploaded"
    dest = f"uploaded/class/{class_id}/{filename}"

    data = await file.read()
    ok = file_service.upload_bytes(data, dest, content_type=file.content_type)
    if not ok:
        raise HTTPException(status_code=500, detail="Upload failed")

    # insert record in DB
    try:
        record = {
            "id_clase": class_id,
            "filename": filename,
            "tipo": "Subido",
            "original_filename": file.filename or filename,
            "filepath": f"/{dest}",
            "created_at": datetime.utcnow().isoformat()
        }
        db_resp = supabase.table("archivos").insert(record).execute()
    except Exception as e:
        print(f"DB insert error: {e}")

    return {"path": f"/{dest}"}


@router.post("/upload-multiple")
async def upload_multiple(class_id: int = Query(..., alias="class_id"), files: List[UploadFile] = File(...), id_silabo: Optional[int] = Query(None)):
    """Upload multiple files for a class and record them in DB."""
    results = await file_service.upload_multiple_files(files, class_id, id_silabo)
    return {"results": results}


@router.get("/list")
def list_files(prefix: Optional[str] = Query(None)):
    items = file_service.list_files(prefix)
    return {"files": items}


@router.get("/url")
def get_url(path: str, expires_in: int = 3600):
    url = file_service.get_presigned_url(path, expires_in=expires_in)
    if not url:
        raise HTTPException(status_code=404, detail="File not found or cannot generate URL")
    return {"url": url}


@router.get("/download")
def download(path: str, expires_in: int = 3600):
    url = file_service.get_presigned_url(path, expires_in=expires_in)
    if not url:
        raise HTTPException(status_code=404, detail="File not available")
    # redirect to presigned or local path
    return RedirectResponse(url)


@router.delete("/delete")
def delete(path: str):
    ok = file_service.delete_file(path)
    if not ok:
        raise HTTPException(status_code=404, detail="File not found or could not be deleted")
    return JSONResponse({"deleted": path})


@router.post("/rename")
def rename(old: str, new: str):
    ok = file_service.rename_file(old, new)
    if not ok:
        raise HTTPException(status_code=400, detail="Rename failed")
    return {"from": old, "to": new}


@router.post("/copy")
def copy(src: str, dest: str):
    ok = file_service.copy_file(src, dest)
    if not ok:
        raise HTTPException(status_code=400, detail="Copy failed")
    return {"from": src, "to": dest}


@router.post("/create-folder")
def create_folder(path: str):
    ok = file_service.create_folder(path)
    if not ok:
        raise HTTPException(status_code=400, detail="Create folder failed")
    return {"created": path}
