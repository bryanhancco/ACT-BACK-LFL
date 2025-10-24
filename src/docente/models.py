from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime

class DocenteBD(BaseModel):
    nombre: str
    correo: str
    password: str
    foto: Optional[str] = None
    foto_caricatura: Optional[str] = None