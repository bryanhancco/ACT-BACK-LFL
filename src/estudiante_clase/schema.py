from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .models import NivelGeneralEnum, MotivacionEnum


class EstudianteClaseCreateDTO(BaseModel):
    id_estudiante: int
    id_clase: int
    nivel_conocimientos: Optional[NivelGeneralEnum] = None
    nivel_motivacion: Optional[MotivacionEnum] = None


class EstudianteClaseResponseDTO(EstudianteClaseCreateDTO):
    id: int
    estado: bool
    created_at: Optional[datetime] = None


class EstudianteClaseUpdateDTO(BaseModel):
    nivel_conocimientos: Optional[NivelGeneralEnum] = None
    nivel_motivacion: Optional[MotivacionEnum] = None
    estado: Optional[bool] = None


class EstudianteClaseDetalleDTO(EstudianteClaseResponseDTO):
    estudiante_nombre: Optional[str] = None
    estudiante_correo: Optional[str] = None
    estudiante_perfil_cognitivo: Optional[str] = None
    estudiante_perfil_personalidad: Optional[str] = None
    clase_nombre: Optional[str] = None
    clase_tema: Optional[str] = None
