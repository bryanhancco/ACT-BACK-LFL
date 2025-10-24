from fastapi import APIRouter, HTTPException
from typing import List, Optional
from .schema import (
    EstudianteClaseCreateDTO,
    EstudianteClaseResponseDTO,
    EstudianteClaseDetalleDTO,
    EstudianteClaseUpdateDTO,
)
from . import service
from database import supabase

router = APIRouter(prefix="/estudiante-clase", tags=["estudiante-clase"])


@router.post("/", response_model=EstudianteClaseResponseDTO)
async def inscribir_estudiante_clase(inscripcion: EstudianteClaseCreateDTO):
    try:
        estudiante_check = supabase.table('estudiante').select('*').eq('id', inscripcion.id_estudiante).execute()
        if not estudiante_check.data:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")

        clase_check = supabase.table('clase').select('*').eq('id', inscripcion.id_clase).execute()
        if not clase_check.data:
            raise HTTPException(status_code=404, detail="Clase no encontrada")

        existing = supabase.table('estudiante_clase').select('*').eq('id_estudiante', inscripcion.id_estudiante).eq('id_clase', inscripcion.id_clase).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="El estudiante ya está inscrito en esta clase")

        data = inscripcion.model_dump()
        data['estado'] = True
        resp = service.inscribir_estudiante(data)
        if resp:
            # attempt to initialize progreso asynchronously if function exists in api.py
            try:
                # call to module-level _inicializar_progreso_estudiante if available
                from api.api import _inicializar_progreso_estudiante  # type: ignore
                try:
                    await _inicializar_progreso_estudiante(inscripcion.id_estudiante, inscripcion.id_clase)
                except Exception:
                    pass
            except Exception:
                pass

            return EstudianteClaseResponseDTO(**resp)

        raise HTTPException(status_code=500, detail="Error al inscribir al estudiante")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id_inscripcion}", response_model=EstudianteClaseDetalleDTO)
async def obtener_inscripcion(id_inscripcion: int):
    try:
        insc = service.get_inscripcion(id_inscripcion)
        if not insc:
            raise HTTPException(status_code=404, detail="Inscripción no encontrada")

        estudiante_resp = supabase.table('estudiante').select('nombre, correo, perfil_cognitivo, perfil_personalidad').eq('id', insc['id_estudiante']).execute()
        estudiante = estudiante_resp.data[0] if estudiante_resp.data else {}

        clase_resp = supabase.table('clase').select('nombre, tema').eq('id', insc['id_clase']).execute()
        clase = clase_resp.data[0] if clase_resp.data else {}

        detalle = {
            **insc,
            'estudiante_nombre': estudiante.get('nombre', ''),
            'estudiante_correo': estudiante.get('correo', ''),
            'estudiante_perfil_cognitivo': estudiante.get('perfil_cognitivo'),
            'estudiante_perfil_personalidad': estudiante.get('perfil_personalidad'),
            'clase_nombre': clase.get('nombre'),
            'clase_tema': clase.get('tema')
        }

        return EstudianteClaseDetalleDTO(**detalle)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[EstudianteClaseDetalleDTO])
async def listar_todas_inscripciones():
    try:
        rows = service.list_all_inscripciones()
        detalles = []
        for insc in rows:
            estudiante_resp = supabase.table('estudiante').select('nombre, correo, perfil_cognitivo').eq('id', insc['id_estudiante']).execute()
            estudiante = estudiante_resp.data[0] if estudiante_resp.data else {}
            clase_resp = supabase.table('clase').select('nombre, tema').eq('id', insc['id_clase']).execute()
            clase = clase_resp.data[0] if clase_resp.data else {}

            detalle = {
                **insc,
                'estudiante_nombre': estudiante.get('nombre', ''),
                'estudiante_correo': estudiante.get('correo', ''),
                'estudiante_perfil_cognitivo': estudiante.get('perfil_cognitivo'),
                'clase_nombre': clase.get('nombre'),
                'clase_tema': clase.get('tema')
            }
            detalles.append(EstudianteClaseDetalleDTO(**detalle))

        return detalles
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id_estudiante}/clases", response_model=List[EstudianteClaseDetalleDTO])
async def obtener_clases_estudiante(id_estudiante: int, incluir_inactivas: bool = False):
    try:
        estudiante_check = supabase.table('estudiante').select('*').eq('id', id_estudiante).execute()
        if not estudiante_check.data:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")

        inscs = service.list_inscripciones_by_student(id_estudiante, incluir_inactivas)
        detalles = []
        estudiante = estudiante_check.data[0]

        for insc in inscs:
            clase_resp = supabase.table('clase').select('nombre, tema').eq('id', insc['id_clase']).execute()
            clase = clase_resp.data[0] if clase_resp.data else {}

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


@router.put("/{id_inscripcion}", response_model=EstudianteClaseResponseDTO)
async def actualizar_inscripcion(id_inscripcion: int, inscripcion_update: EstudianteClaseUpdateDTO):
    try:
        existing = service.get_inscripcion(id_inscripcion)
        if not existing:
            raise HTTPException(status_code=404, detail="Inscripción no encontrada")

        update_data = {k: v for k, v in inscripcion_update.model_dump().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar")

        resp = service.update_inscripcion(id_inscripcion, update_data)
        if resp:
            return EstudianteClaseResponseDTO(**resp)
        raise HTTPException(status_code=400, detail="Error al actualizar la inscripción")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{id_inscripcion}/salir")
async def salir_de_clase(id_inscripcion: int):
    try:
        existing = service.get_inscripcion(id_inscripcion)
        if not existing:
            raise HTTPException(status_code=404, detail="Inscripción no encontrada")

        resp = service.update_inscripcion(id_inscripcion, {'estado': False})
        if not resp:
            raise HTTPException(status_code=500, detail="Error al salir de la clase")

        return {"message": "Has salido de la clase exitosamente", "id_inscripcion": id_inscripcion, "nuevo_estado": False}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{id_inscripcion}/reincorporar")
async def reincorporar_a_clase(id_inscripcion: int):
    try:
        existing = service.get_inscripcion(id_inscripcion)
        if not existing:
            raise HTTPException(status_code=404, detail="Inscripción no encontrada")

        resp = service.update_inscripcion(id_inscripcion, {'estado': True})
        if not resp:
            raise HTTPException(status_code=500, detail="Error al reincorporar a la clase")

        return {"message": "Te has reincorporado a la clase exitosamente", "id_inscripcion": id_inscripcion, "nuevo_estado": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{id_inscripcion}")
async def desinscribir_estudiante(id_inscripcion: int):
    try:
        existing = service.get_inscripcion(id_inscripcion)
        if not existing:
            raise HTTPException(status_code=404, detail="Inscripción no encontrada")

        ok = service.delete_inscripcion(id_inscripcion)
        if not ok:
            raise HTTPException(status_code=500, detail="Error al desinscribir")

        return {"message": "Estudiante desinscrito correctamente", "id_inscripcion": id_inscripcion, "id_estudiante": existing['id_estudiante'], "id_clase": existing['id_clase']}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

