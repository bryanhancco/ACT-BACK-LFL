from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Query
from typing import List

from .schema import ConversacionCreateDTO, ConversacionResponseDTO, ChatGeneralRequestDTO, TipoEntidadEnum, RespuestaPsicopedagogicaDTO
from . import service

router = APIRouter()


@router.post("/api/chat-general/{estudiante_id}", response_model=RespuestaPsicopedagogicaDTO)
async def chat_general_personalizado(estudiante_id: int, request_data: ChatGeneralRequestDTO):
    """Thin wrapper: delegate chat logic to service.chat_general_personalizado

    Returns the DTO created in the service or raises HTTPException on error.
    """
    try:
        res = await service.chat_general_personalizado(estudiante_id, request_data)
        if not res:
            raise HTTPException(status_code=500, detail="Error generando respuesta del chat")
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversaciones", response_model=ConversacionResponseDTO)
async def crear_conversacion(conversacion: ConversacionCreateDTO):
    try:
        res = await service.registrar_conversacion(conversacion)
        if res:
            return res
        raise HTTPException(status_code=500, detail="Error al registrar la conversación")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversaciones/chat/{estudiante_id}/{id_clase}", response_model=List[ConversacionResponseDTO])
async def obtener_historial_chat(estudiante_id: int, id_clase: int, limit: int = Query(50)):
    try:
        return await service.obtener_historial_chat(estudiante_id, id_clase, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversaciones/{conversacion_id}")
async def eliminar_conversacion(conversacion_id: int):
    try:
        ok = await service.eliminar_conversacion(conversacion_id)
        if ok:
            return {"message": "Conversación eliminada exitosamente", "id": conversacion_id}
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversaciones/audio-upload")
async def audio_upload_and_transcribe(id_clase: int = Body(...), id_emisor: int = Body(...), id_receptor: int = Body(...), tipo_emisor: int = Body(...), tipo_receptor: int = Body(...), file: UploadFile = File(...)):
    try:
        data = await file.read()
        tipo_emisor_enum = TipoEntidadEnum(tipo_emisor)
        tipo_receptor_enum = TipoEntidadEnum(tipo_receptor)
        res = await service.process_audio_and_register(data, file.filename, id_clase, id_emisor, id_receptor, tipo_emisor_enum, tipo_receptor_enum)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
