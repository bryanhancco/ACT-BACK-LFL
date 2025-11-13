from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Query
from fastapi.responses import JSONResponse
import asyncio
from pydantic import BaseModel
from typing import List, Optional
from .schema import ClaseCreateDTO, ClaseResponseDTO
from . import service
from database import supabase
from ..estudiante_clase.schema import EstudianteClaseDetalleDTO
from ..estudiante_clase.service import list_inscripciones_by_class as lic

router = APIRouter(prefix="/clases", tags=["clases"])


@router.post("/", response_model=ClaseResponseDTO)
async def crear_clase(clase: ClaseCreateDTO):
    try:
        # verify docente exists
        docente_resp = supabase.table('docente').select('id').eq('id', clase.id_docente).execute()
        if not docente_resp.data:
            raise HTTPException(status_code=404, detail="Docente no encontrado")

        data = clase.model_dump()
        created = service.create_clase(data)
        if created:
            return ClaseResponseDTO(**created)
        else:
            raise HTTPException(status_code=400, detail="Error al crear la clase")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id_clase}", response_model=ClaseResponseDTO)
async def obtener_clase(id_clase: int):
    try:
        c = service.get_clase(id_clase)
        if not c:
            raise HTTPException(status_code=404, detail="Clase no encontrada")
        return ClaseResponseDTO(**c)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def listar_clases(id_docente: Optional[int] = Query(None)):
    try:
        rows = service.list_clases(id_docente)
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class EstadoDTO(BaseModel):
    estado: bool


@router.patch("/{id_clase}/estado")
async def cambiar_estado_clase(id_clase: int, payload: EstadoDTO):
    """Recibe JSON { "estado": boolean } y actualiza el estado de la clase."""
    try:
        estado = payload.estado
        ok = service.cambiar_estado_clase(id_clase, estado)
        if ok:
            return {"message": "Estado actualizado", "id_clase": id_clase, "nuevo_estado": estado}
        else:
            raise HTTPException(status_code=400, detail="Error al actualizar el estado de la clase")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{id_clase}/estudiantes/estadisticas")
async def obtener_estadisticas_estudiantes_clase(id_clase: int):
    try:
        # validate class exists
        clase_check = supabase.table('clase').select('*').eq('id', id_clase).execute()
        if not clase_check.data:
            raise HTTPException(status_code=404, detail="Clase no encontrada")

        stats = service.get_estadisticas_por_clase(id_clase)
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{id_clase}/estudiantes", response_model=List[EstudianteClaseDetalleDTO])
async def obtener_estudiantes_clase(id_clase: int):
    try:
        clase_check = supabase.table('clase').select('*').eq('id', id_clase).execute()
        if not clase_check.data:
            raise HTTPException(status_code=404, detail="Clase no encontrada")

        inscs = lic(id_clase)
        detalles = []
        clase = clase_check.data[0]

        for insc in inscs:
            estudiante_resp = supabase.table('estudiante').select('nombre, correo, perfil_cognitivo, perfil_personalidad').eq('id', insc['id_estudiante']).execute()
            estudiante = estudiante_resp.data[0] if estudiante_resp.data else {}

            detalle = {
                **insc,
                'estudiante_nombre': estudiante.get('nombre', ''),
                'estudiante_correo': estudiante.get('correo', ''),
                'estudiante_perfil_cognitivo': estudiante.get('perfil_cognitivo'),
                'estudiante_perfil_personalidad': estudiante.get('perfil_personalidad'),
                'clase_nombre': clase.get('nombre'),
                'clase_tema': clase.get('tema')
            }

            detalles.append(EstudianteClaseDetalleDTO(**detalle))

        return detalles
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{id_clase}/process")
async def procesar_clase_route(id_clase: int):
    """Endpoint que inicia el procesamiento RAG + generación de la clase.

    Este endpoint delega en `service.procesar_clase` y devuelve un resumen de lo generado.
    """
    try:
        # Schedule the potentially long-running processing as a background
        # asyncio task so the HTTP request can return quickly and avoid
        # triggering gunicorn worker timeouts. The task will still run in
        # the same worker process — use a proper background job queue for
        # production if the job is heavy or memory intensive.
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(service.procesar_clase(id_clase))
        except RuntimeError:
            # If there's no running loop (unlikely under uvicorn worker),
            # spawn a new one in a background thread as a last resort.
            import threading

            def _run():
                import asyncio as _asyncio
                _loop = _asyncio.new_event_loop()
                _asyncio.set_event_loop(_loop)
                _loop.run_until_complete(service.procesar_clase(id_clase))

            t = threading.Thread(target=_run, daemon=True)
            t.start()

        return JSONResponse(status_code=202, content={"message": "Processing started", "clase_id": id_clase})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
