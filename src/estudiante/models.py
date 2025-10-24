from pydantic import BaseModel
from typing import Optional
from enum import Enum

class PerfilAprendizajeEnum(str, Enum):
    VISUAL = "Visual"
    AUDITIVO = "Auditivo"
    LECTOR = "Lector"
    KINESTESICO = "Kinestesico"
    
class EstudianteDB(BaseModel):
    nombre: str
    correo: str
    password: str
    perfil_cognitivo: Optional[PerfilAprendizajeEnum] = None
    perfil_personalidad: Optional[str] = None