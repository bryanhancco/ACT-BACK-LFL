from pydantic import BaseModel
from typing import Optional
from enum import Enum 
from src.estudiante.models import PerfilAprendizajeEnum

class EstadoContenidoEnum(str, Enum):
    NO_INICIADO = "No iniciado"
    EN_PROCESO = "En proceso"
    FINALIZADO = "Finalizado"

class ContenidoEstudianteDB(BaseModel):
    id_clase: int
    orden: int
    indice: str
    perfil_cognitivo: PerfilAprendizajeEnum
    tiempo_estimado: int
    contenido: Optional[str] = None
    estado: Optional[bool] = True
    
class ContenidoEstudianteDataDB(BaseModel):
    id_contenido: int
    id_estudiante: int
    estado: EstadoContenidoEnum = EstadoContenidoEnum.NO_INICIADO