from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Dict
from . import service
from .schemas import DocenteCreateDTO, DocenteLoginDTO, DocenteUpdateDTO, DocenteResponseDTO
import os
from database import supabase

router = APIRouter(prefix="/docentes", tags=["docentes"])


@router.post("/", response_model=DocenteResponseDTO)
async def crear_docente(docente: DocenteCreateDTO):
    existing = service.find_docente_by_email(docente.correo)
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un docente con este correo")
    data = docente.model_dump()
    created = service.create_docente(data)
    if not created:
        raise HTTPException(status_code=400, detail="Error al crear el docente")
    if 'password' in created:
        del created['password']
    return created


@router.post("/login")
async def login_docente(login_data: DocenteLoginDTO):
    docente = service.find_docente_by_email(login_data.correo)
    if not docente:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not service.verify_password(login_data.password, docente.get('password', '')):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if 'password' in docente:
        del docente['password']
    return {"message": "Login exitoso", "docente": docente}


@router.put("/{id_docente}", response_model=DocenteResponseDTO)
async def actualizar_docente(id_docente: int, docente_update: DocenteUpdateDTO):
    existing = service.get_docente(id_docente)
    if not existing:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

    update_data = {k: v for k, v in docente_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    # check email uniqueness
    if 'correo' in update_data:
        other = service.find_docente_by_email(update_data['correo'])
        if other and other.get('id') != id_docente:
            raise HTTPException(status_code=400, detail="El correo ya está siendo usado por otro docente")

    updated = service.update_docente(id_docente, update_data)
    if not updated:
        raise HTTPException(status_code=400, detail="Error al actualizar el docente")
    # updated already only contains public fields due to service.select
    return updated


@router.get("/{id_docente}", response_model=DocenteResponseDTO)
async def obtener_docente(id_docente: int):
    d = service.get_docente(id_docente)
    if not d:
        raise HTTPException(status_code=404, detail="Docente no encontrado")
    return d


@router.get("/")
async def listar_docentes():
    return service.list_docentes()


@router.post("/{id_docente}/foto")
async def subir_foto_docente(id_docente: int, file: UploadFile = File(...)):
    docente = service.get_docente(id_docente)
    if not docente:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

    # delete existing photos if any
    service.delete_teacher_photos(docente)

    # save new photo
    foto_url = await service.save_teacher_photo(file, id_docente)
    if not foto_url:
        raise HTTPException(status_code=400, detail="Error al guardar la foto")

    # build full URL (assume API_BASE_URL env var if needed by image processor)
    base_url = os.getenv("S3_BUCKET_BASE_URL")
    foto_url_completa = f"{base_url}{foto_url}"

    try:
        foto_caricatura_url = service.generate_cartoon_from_s3_path(foto_url_completa, id_docente)
        if not foto_caricatura_url or foto_caricatura_url == foto_url_completa:
            foto_caricatura_url = foto_url
    except Exception:
        foto_caricatura_url = foto_url

    update = {"foto": foto_url, "foto_caricatura": foto_caricatura_url}
    resp = supabase.table("docente").update(update).eq("id", id_docente).execute()
    if resp.data:
        docente_actualizado = resp.data[0]
        if 'password' in docente_actualizado:
            del docente_actualizado['password']
        return {"message": "Foto subida y caricatura generada exitosamente", "docente": docente_actualizado, "foto_url": foto_url, "foto_caricatura_url": foto_caricatura_url}
    else:
        raise HTTPException(status_code=400, detail="Error al actualizar el docente en la base de datos")
