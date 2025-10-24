from fastapi import APIRouter, HTTPException
from typing import List
from .schema import EstudianteCreateDTO, EstudianteResponseDTO, EstudianteLoginDTO, EstudianteUpdateDTO
from . import service

router = APIRouter(prefix="/estudiantes", tags=["estudiantes"])


@router.post("/", response_model=EstudianteResponseDTO)
async def crear_estudiante(estudiante: EstudianteCreateDTO):
    try:
        existing = service.find_by_email(estudiante.correo)
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe un estudiante con este correo")

        data = estudiante.model_dump()
        created = service.create_estudiante(data)
        if created:
            # remove password from response
            created.pop('password', None)
            return EstudianteResponseDTO(**created)
        raise HTTPException(status_code=400, detail="Error al crear el estudiante")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def login_estudiante(login_data: EstudianteLoginDTO):
    try:
        user = service.find_by_email(login_data.correo)
        if not user:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        if not service.verify_password(login_data.password, user['password']):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        user.pop('password', None)
        return {"message": "Login exitoso", "estudiante": EstudianteResponseDTO(**user)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id_estudiante}", response_model=EstudianteResponseDTO)
async def obtener_estudiante(id_estudiante: int):
    try:
        e = service.get_estudiante(id_estudiante)
        if not e:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")
        return EstudianteResponseDTO(**e)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[EstudianteResponseDTO])
async def listar_estudiantes():
    try:
        rows = service.list_estudiantes()
        return [EstudianteResponseDTO(**r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{id_estudiante}", response_model=EstudianteResponseDTO)
async def actualizar_estudiante(id_estudiante: int, estudiante_update: EstudianteUpdateDTO):
    try:
        existing = service.get_estudiante(id_estudiante)
        if not existing:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")

        if estudiante_update.correo:
            other = service.find_by_email(estudiante_update.correo)
            if other and other.get('id') != id_estudiante:
                raise HTTPException(status_code=400, detail="Ya existe otro estudiante con este correo")

        update_data = {k: v for k, v in estudiante_update.model_dump().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar")

        updated = service.update_estudiante(id_estudiante, update_data)
        if updated:
            updated.pop('password', None)
            return EstudianteResponseDTO(**updated)
        raise HTTPException(status_code=400, detail="Error al actualizar el estudiante")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{id_estudiante}")
async def eliminar_estudiante(id_estudiante: int):
    try:
        existing = service.get_estudiante(id_estudiante)
        if not existing:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")

        ok = service.delete_estudiante(id_estudiante)
        if not ok:
            raise HTTPException(status_code=400, detail="No se puede eliminar el estudiante porque está inscrito en clases")

        return {"message": "Estudiante eliminado correctamente", "id_estudiante": id_estudiante}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id_estudiante}/perfil-completo")
async def verificar_perfil_completo(id_estudiante: int):
    try:
        existing = service.get_estudiante(id_estudiante)
        if not existing:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")

        status = service.check_perfil_completo(id_estudiante)
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
