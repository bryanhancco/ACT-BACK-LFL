from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime

from .models import EstadoContenidoEnum
from src.estudiante.models import PerfilAprendizajeEnum


class ContenidoEstudianteCreateDTO(BaseModel):
    id_clase: int
    orden: int
    indice: str
    perfil_cognitivo: PerfilAprendizajeEnum
    tiempo_estimado: int
    contenido: Optional[str] = None
    estado: Optional[bool] = True


class ContenidoEstudianteResponseDTO(BaseModel):
    id: int
    id_clase: int
    orden: int
    indice: str
    contenido: Optional[str]
    perfil_cognitivo: PerfilAprendizajeEnum
    tiempo_estimado: int
    estado: bool


class ContenidoEstudianteUpdateDTO(BaseModel):
    contenido: Optional[str] = None
    tiempo_estimado: Optional[int] = None
    estado: Optional[bool] = None


class ContenidoEstudianteDataCreateDTO(BaseModel):
    id_contenido: int
    id_estudiante: int
    estado: EstadoContenidoEnum = EstadoContenidoEnum.NO_INICIADO


class ContenidoEstudianteDataResponseDTO(BaseModel):
    id: int
    id_contenido: int
    id_estudiante: int
    estado: EstadoContenidoEnum


class ContenidoEstudianteDataUpdateDTO(BaseModel):
    estado: Optional[EstadoContenidoEnum] = None


class IndiceClaseResponseDTO(BaseModel):
    orden: int
    indice: str
    tiempo_estimado: int
