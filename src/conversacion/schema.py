from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum

class PerfilAprendizajeEnum(str, Enum):
    VISUAL = "Visual"
    AUDITIVO = "Auditivo"
    LECTOR = "Lector"
    KINESTESICO = "Kinestesico"
    
class NivelEnum(str, Enum):
    PRIMARIA = "Primaria"
    SECUNDARIA = "Secundaria"
    PREGRADO = "Pregrado"
    POSGRADO = "Posgrado"
    
class TipoEntidadEnum(int, Enum):
    ESTUDIANTE = 1
    DOCENTE = 2
    CHATBOT = 3


class ConversacionCreateDTO(BaseModel):
    id_emisor: int
    id_receptor: int
    tipo_emisor: TipoEntidadEnum
    tipo_receptor: TipoEntidadEnum
    mensaje: str
    archivo: Optional[str] = None


class ConversacionResponseDTO(BaseModel):
    id: int
    id_emisor: int
    id_receptor: int
    tipo_emisor: TipoEntidadEnum
    tipo_receptor: TipoEntidadEnum
    mensaje: str
    archivo: Optional[str] = None
    created_at: datetime


class ConversacionQueryDTO(BaseModel):
    id_emisor: Optional[int] = None
    id_receptor: Optional[int] = None
    tipo_emisor: Optional[int] = None
    tipo_receptor: Optional[int] = None
    limit: Optional[int] = 50
    offset: Optional[int] = 0

class RespuestaPsicopedagogicaDTO(BaseModel):
    status: str
    estudiante_id: int
    clase_id: int
    contenido_generado: str
    perfil_cognitivo: str
    nivel_conocimientos: str
    timestamp: datetime
    tipo_respuesta: str 
    metadata: Optional[Dict] = None
    
class ChatGeneralRequestDTO(BaseModel):
    perfil_cognitivo: PerfilAprendizajeEnum
    perfil_personalidad: str
    nivel_conocimientos: NivelEnum
    id_clase: int
    historial_mensajes: List[dict]  # Lista de mensajes con 'tipo' ('user'/'bot') y 'contenido'
    mensaje_actual: str
    
class RespuestaPsicopedagogicaDTO(BaseModel):
    status: str
    estudiante_id: int
    clase_id: int
    contenido_generado: str
    perfil_cognitivo: str
    nivel_conocimientos: str
    timestamp: datetime
    tipo_respuesta: str 
    metadata: Optional[Dict] = None