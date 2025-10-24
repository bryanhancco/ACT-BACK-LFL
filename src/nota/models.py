from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime

class NotaDB(BaseModel):
    id_estudiante: int
    notas: str
    estado: bool = True