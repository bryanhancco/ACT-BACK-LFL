from pydantic import BaseModel
from typing import Optional
from enum import Enum

class NivelGeneralEnum(str, Enum):
    SIN_CONOCIMIENTO = "Sin conocimiento"
    BASICO = "Básico"
    INTERMEDIO = "Intermedio"
    EXPERTO = "Experto"
    
class MotivacionEnum(str, Enum):
    BAJA = "Baja"
    MEDIA = "Media"
    ALTA = "Alta"
    
class EstudianteClaseDB(BaseModel):
    id_estudiante: int
    id_clase: int
    nivel_conocimientos: Optional[NivelGeneralEnum] = None
    nivel_motivacion: Optional[MotivacionEnum] = None
    estado: bool