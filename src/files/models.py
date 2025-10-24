from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime

class TipoArchivoEnum(str, Enum):
    SUBIDO = "Subido"
    GENERADO = "Generado"
    
class ArchivoDB(BaseModel):
    id_clase: Optional[int] = None
    id_silabo: Optional[int] = None
    filename: str
    tipo: TipoArchivoEnum
    original_filename: str
    filepath: str
    created_at: datetime
    descripcion: Optional[str] = None
    