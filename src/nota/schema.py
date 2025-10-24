from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NotaCreateDTO(BaseModel):
    id_estudiante: int
    notas: str
    estado: bool = True


class NotaResponseDTO(BaseModel):
    id: int
    id_estudiante: int
    notas: str
    estado: bool


class NotaUpdateDTO(BaseModel):
    notas: Optional[str] = None
    estado: Optional[bool] = None
