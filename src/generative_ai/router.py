from fastapi import APIRouter, Body, UploadFile, File, HTTPException
from typing import Optional, List, Dict, Any
import os
import uuid
from ..files.service import file_service
# conversacion service (to update conversation records when audio is generated)
try:
    from ..conversacion import service as conversacion_service
except Exception:
    conversacion_service = None

# Guarded imports of service modules (they may not be available in test env)
try:
    from .service_audio import audio_processor, generate_audio_file, process_audio_upload
except Exception:
    audio_processor = None
    generate_audio_file = None
    process_audio_upload = None

try:
    from .service_chat import AgentePedagogico, crear_manager_agentes
except Exception:
    AgentePedagogico = None
    crear_manager_agentes = None

try:
    from .service_image import image_processor
except Exception:
    image_processor = None

router = APIRouter(prefix="/generative-ai", tags=["generative-ai"])


@router.post("/audio/tts")
async def tts_endpoint(id_clase: int = Body(...), text: str = Body(...), conversacion_id: Optional[int] = Body(None)) -> Dict[str, Any]:
    """Generate TTS audio for a class and register the file."""
    if generate_audio_file is None and audio_processor is None:
        raise HTTPException(status_code=503, detail="Audio service not available")

    # prefer async helper if present
    filename = None
    try:
        if generate_audio_file is not None:
            # compatibility wrapper may be async
            maybe = generate_audio_file(text, id_clase)
            if hasattr(maybe, "__await__"):
                filename = await maybe
            else:
                filename = maybe
        else:
            # fall back to direct processor call
            res = await audio_processor.text_to_speech(text, id_clase)
            filename = res.get("filename") if res else None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not filename:
        raise HTTPException(status_code=500, detail="TTS generation failed")

    generated_path = f"generated/audio/{id_clase}/{os.path.basename(filename)}"
    s3_path = f"/{generated_path}"

    # If a conversation id was provided, try to update its 'archivo' column with the generated file path
    if conversacion_id is not None and conversacion_service is not None:
        try:
            updated = await conversacion_service.actualizar_conversacion_archivo(conversacion_id, s3_path)
            if not updated:
                # log but don't fail the request
                print(f"Warning: failed to update conversation {conversacion_id} with archivo {s3_path}")
        except Exception as e:
            print(f"Error updating conversation archivo for id {conversacion_id}: {e}")

    # Try to generate a presigned download URL for the generated file so the frontend can play it directly
    download_url = None
    try:
        if file_service is not None:
            # file_service expects a relative path without leading slash
            presigned = file_service.get_presigned_url(generated_path)
            if presigned:
                download_url = presigned
    except Exception as e:
        print(f"Warning: failed to obtain presigned url for {generated_path}: {e}")

    resp = {"ok": True, "path": s3_path, "filename": os.path.basename(filename)}
    if download_url:
        resp["download_url"] = download_url

    return resp


@router.post("/audio/transcribe")
async def transcribe_endpoint(id_clase: int = Body(...), file: UploadFile = File(...)) -> Dict[str, Any]:
    """Transcribe an uploaded audio file and optionally register it."""
    if process_audio_upload is None and audio_processor is None:
        raise HTTPException(status_code=503, detail="Audio service not available")

    try:
        data = await file.read()
        # attempt to use process_audio_upload wrapper if available
        if process_audio_upload is not None:
            res = await process_audio_upload(data, file.filename, id_clase)
        else:
            res = await audio_processor.speech_to_text_from_bytes(data, id_clase, file.filename)

        return {"ok": True, "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/generate")
async def chat_generate_endpoint(clase_info: Dict[str, Any] = Body(...), tipo_recurso: str = Body(...)) -> Dict[str, Any]:
    """Generate pedagogical content via AgentePedagogico if available."""
    if crear_manager_agentes is None:
        raise HTTPException(status_code=503, detail="Chat/generation service not available")
    try:
        manager = crear_manager_agentes()
        # Decide which method to call based on tipo_recurso
        # Provide a small mapping
        if tipo_recurso == "estructura":
            out = await manager.generar_estructura_clase_completa(clase_info, clase_info.get("context", ""))
        else:
            out = await manager.generar_contenido_por_tipo(clase_info, clase_info.get("context", ""), tipo_recurso)
        return {"ok": True, "result": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/generar-indice")
async def chat_generar_indice(contenido: str = Body(...), nivel_clase: str = Body(...)) -> Dict[str, Any]:
    """Generate a structured class index using ManagerAgentes.agente_indice_clase"""
    if crear_manager_agentes is None:
        raise HTTPException(status_code=503, detail="Chat/index service not available")
    try:
        manager = crear_manager_agentes()
        out = await manager.generar_indice_clase(contenido, nivel_clase)
        return {"ok": True, "index": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/generar-contenido-indice")
async def chat_generar_contenido_indice(contenido_indice: str = Body(...), nivel_clase: str = Body(...), perfil_cognitivo: str = Body(...), tiempo_estimado: int = Body(...)) -> Dict[str, Any]:
    """Generate content for a specific index item using ManagerAgentes.agente_contenido_indice"""
    if crear_manager_agentes is None:
        raise HTTPException(status_code=503, detail="Chat/index service not available")
    try:
        manager = crear_manager_agentes()
        out = await manager.generar_contenido_indice(contenido_indice, nivel_clase, perfil_cognitivo, tiempo_estimado)
        return {"ok": True, "content": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/image/generate")
async def image_generate_endpoint(id_clase: int = Body(...), description: Optional[str] = Body(None)) -> Dict[str, Any]:
    """Generate an image and store it under generated/images/{id_clase}/"""
    if image_processor is None:
        raise HTTPException(status_code=503, detail="Image service not available")
    try:
        # image_processor expects a description (may be None)
        path = image_processor.generate_image_from_description(description, id_clase)
        if not path:
            raise HTTPException(status_code=500, detail="Image generation failed")

        # image service now returns an S3-relative path like /generated/images/class/{id}/{file}
        return {"ok": True, "path": path, "filename": os.path.basename(path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/image/convert-to-cartoon")
async def image_convert_to_cartoon(teacher_id: int = Body(...), filename: str = Body(...)) -> Dict[str, Any]:
    """Convert a teacher photo stored at uploaded/teacher/{teacher_id}/images/{filename} to a cartoon and store it in S3.

    The endpoint expects the original photo to already exist in S3 under uploaded/teacher/{teacher_id}/images/{filename}.
    It will obtain a presigned URL and call the image service to perform conversion. The image service uploads
    the resulting cartoon to generated/teacher/{teacher_id}/ and returns the S3 path.
    """
    if image_processor is None:
        raise HTTPException(status_code=503, detail="Image service not available")

    if file_service is None:
        raise HTTPException(status_code=503, detail="File service (S3) not available")

    try:
        s3_rel = f"uploaded/teacher/{teacher_id}/images/{filename}"
        presigned = file_service.get_presigned_url(s3_rel)
        if not presigned:
            raise HTTPException(status_code=404, detail="Teacher photo not found or presigned URL generation failed")

        result_path = image_processor.convert_to_cartoon(presigned, teacher_id)
        if not result_path:
            raise HTTPException(status_code=500, detail="Cartoon conversion failed")

        return {"ok": True, "path": result_path, "filename": os.path.basename(result_path)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
