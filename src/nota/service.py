from typing import List
from database import supabase
from .schema import NotaCreateDTO, NotaResponseDTO, NotaUpdateDTO


async def crear_nota_estudiante(estudiante_id: int, nota_data: NotaCreateDTO) -> NotaResponseDTO:
    # Validate student exists
    estudiante_result = supabase.table("estudiante").select("*").eq("id", estudiante_id).execute()
    if not estudiante_result.data:
        raise Exception("Estudiante no encontrado")

    result = supabase.table("notas").insert(nota_data.dict()).execute()
    if not result.data:
        raise Exception("Error al crear la nota")
    return NotaResponseDTO(**result.data[0])


async def obtener_notas_estudiante(estudiante_id: int) -> List[NotaResponseDTO]:
    result = supabase.table("notas").select("*").eq("id_estudiante", estudiante_id).eq("estado", True).execute()
    return [NotaResponseDTO(**n) for n in (result.data or [])]


async def actualizar_nota(nota_id: int, nota_data: NotaUpdateDTO) -> NotaResponseDTO:
    datos_actualizacion = nota_data.dict(exclude_unset=True)
    result = supabase.table("notas").update(datos_actualizacion).eq("id", nota_id).execute()
    if not result.data:
        raise Exception("Nota no encontrada")
    return NotaResponseDTO(**result.data[0])


async def eliminar_nota(nota_id: int) -> bool:
    result = supabase.table("notas").update({"estado": False}).eq("id", nota_id).execute()
    return bool(result.data)
