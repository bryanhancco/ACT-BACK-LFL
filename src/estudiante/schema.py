from pydantic import BaseModel
from typing import Optional


class EstudianteCreateDTO(BaseModel):
    nombre: str
    correo: str
    password: str
    perfil_cognitivo: Optional[str] = None
    perfil_personalidad: Optional[str] = None


class EstudianteResponseDTO(BaseModel):
    id: int
    nombre: str
    correo: str
    perfil_cognitivo: Optional[str] = None
    perfil_personalidad: Optional[str] = None


class EstudianteLoginDTO(BaseModel):
    correo: str
    password: str


class EstudianteUpdateDTO(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[str] = None
    password: Optional[str] = None
    perfil_cognitivo: Optional[str] = None
    perfil_personalidad: Optional[str] = None
