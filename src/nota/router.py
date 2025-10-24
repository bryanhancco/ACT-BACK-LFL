from fastapi import APIRouter, HTTPException
from typing import List

from .schema import NotaCreateDTO, NotaResponseDTO, NotaUpdateDTO
from . import service

router = APIRouter(prefix="/notas", tags=["notas"])

@router.post("/estudiantes/{estudiante_id}", response_model=NotaResponseDTO)
async def crear_nota_estudiante(estudiante_id: int, nota_data: NotaCreateDTO):
    try:
        return await service.crear_nota_estudiante(estudiante_id, nota_data)
    except Exception as e:
        if str(e) == "Estudiante no encontrado":
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/estudiantes/{estudiante_id}", response_model=List[NotaResponseDTO])
async def obtener_notas_estudiante(estudiante_id: int):
    try:
        return await service.obtener_notas_estudiante(estudiante_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{nota_id}", response_model=NotaResponseDTO)
async def actualizar_nota(nota_id: int, nota_data: NotaUpdateDTO):
    try:
        return await service.actualizar_nota(nota_id, nota_data)
    except Exception as e:
        if str(e) == "Nota no encontrada":
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{nota_id}")
async def eliminar_nota(nota_id: int):
    try:
        ok = await service.eliminar_nota(nota_id)
        if ok:
            return {"message": "Nota eliminada exitosamente", "id": nota_id}
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
