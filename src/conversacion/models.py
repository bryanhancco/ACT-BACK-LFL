from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime
class TipoEntidadEnum(int, Enum):
    ESTUDIANTE = 1
    DOCENTE = 2
    CHATBOT = 3 

class ConversacionDB(BaseModel):
    id_emisor: int
    id_receptor: int
    tipo_emisor: TipoEntidadEnum
    tipo_receptor: TipoEntidadEnum
    mensaje: str
    archivo: Optional[str] = None  # Ruta del archivo de audio opcional
    created_at: datetime
