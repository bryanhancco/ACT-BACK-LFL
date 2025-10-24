from fastapi import APIRouter, HTTPException
from typing import List

from . import service
from .schema import (
    ContenidoEstudianteCreateDTO,
    ContenidoEstudianteResponseDTO,
    ContenidoEstudianteUpdateDTO,
    ContenidoEstudianteDataCreateDTO,
    ContenidoEstudianteDataResponseDTO,
    ContenidoEstudianteDataUpdateDTO,
)

from database import supabase

router = APIRouter()


@router.post("/clases/{id_clase}/generar-indices-contenido", response_model=List[ContenidoEstudianteResponseDTO])
async def generar_indices_contenido(id_clase: int):
    try:
        # try to create a manager if available (legacy code provides crear_manager_agentes in api)
        try:
            from api.api import crear_manager_agentes
            manager = crear_manager_agentes()
        except Exception:
            manager = None

        contenidos = await service.generar_indices_contenido_estudiante(id_clase, manager)
        return contenidos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clases/{id_clase}/contenido-estudiante", response_model=List[ContenidoEstudianteResponseDTO])
async def obtener_contenido_estudiante_por_clase(id_clase: int):
    try:
        return await service.listar_contenidos_por_clase(id_clase)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clases/{id_clase}/contenido-estudiante/{perfil_cognitivo}")
async def obtener_contenido_por_perfil(id_clase: int, perfil_cognitivo: str):
    try:
        contenido = await service.obtener_contenido_por_perfil(id_clase, perfil_cognitivo)
        if contenido:
            return contenido
        raise HTTPException(status_code=404, detail="No se encontró contenido para el perfil")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clases/{id_clase}/contenido-estudiante", response_model=ContenidoEstudianteResponseDTO)
async def crear_contenido(id_clase: int, contenido: ContenidoEstudianteCreateDTO):
    try:
        # basic validation: ensure id_clase matches
        if contenido.id_clase != id_clase:
            raise HTTPException(status_code=400, detail="id_clase mismatch")
        return await service.crear_contenido(contenido)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/contenido-estudiante/{contenido_id}", response_model=ContenidoEstudianteResponseDTO)
async def actualizar_contenido(contenido_id: int, datos: ContenidoEstudianteUpdateDTO):
    try:
        return await service.actualizar_contenido(contenido_id, datos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/contenido-estudiante/{contenido_id}")
async def eliminar_contenido(contenido_id: int):
    try:
        ok = await service.eliminar_contenido(contenido_id)
        if ok:
            return {"message": "Contenido eliminado exitosamente", "id": contenido_id}
        raise HTTPException(status_code=404, detail="Contenido no encontrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/estudiantes/{estudiante_id}/clases/{id_clase}/inicializar-progreso")
async def inicializar_progreso_estudiante(estudiante_id: int, id_clase: int):
    try:
        return await service.inicializar_progreso_estudiante(estudiante_id, id_clase)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/estudiantes/{estudiante_id}/clases/{id_clase}/progreso")
async def obtener_progreso_clase_estudiante(estudiante_id: int, id_clase: int):
    try:
        return await service.obtener_progreso(estudiante_id, id_clase)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/contenido-estudiante-data/{progreso_id}/actualizar-estado", response_model=ContenidoEstudianteDataResponseDTO)
async def actualizar_estado_progreso(progreso_id: int, datos_actualizacion: ContenidoEstudianteDataUpdateDTO):
    try:
        return await service.actualizar_estado_progreso(progreso_id, datos_actualizacion)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
