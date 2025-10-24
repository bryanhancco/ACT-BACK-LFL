from pydantic import BaseModel, EmailStr
from typing import Optional


class DocenteCreateDTO(BaseModel):
    nombre: str
    correo: str
    password: str
    foto: Optional[str] = None


class DocenteLoginDTO(BaseModel):
    correo: str
    password: str


class DocenteUpdateDTO(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[str] = None
    password: Optional[str] = None
    foto: Optional[str] = None


class DocenteResponseDTO(BaseModel):
    id: int
    nombre: str
    correo: str
    foto: Optional[str] = None
    foto_caricatura: Optional[str] = None
