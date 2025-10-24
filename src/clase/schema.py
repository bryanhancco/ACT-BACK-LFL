from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .models import PerfilAprendizajeEnum, NivelEnum, TipoSesionEnum, ModalidadEnum, ResultadoTaxonomiaEnum, EstiloContenidoEnum


class ClaseCreateDTO(BaseModel):
    id_docente: int
    nombre: Optional[str] = None
    perfil: PerfilAprendizajeEnum
    area: Optional[str] = None
    tema: Optional[str] = None
    nivel_educativo: Optional[NivelEnum] = None
    duracion_estimada: Optional[int] = None
    solo_informacion_proporcionada: Optional[bool] = None
    conocimientos_previos_estudiantes: Optional[str] = None
    tipo_sesion: Optional[TipoSesionEnum] = None
    modalidad: Optional[ModalidadEnum] = None
    objetivos_aprendizaje: Optional[str] = None
    resultado_taxonomia: Optional[ResultadoTaxonomiaEnum] = None
    aspectos_motivacionales: Optional[str] = None
    estilo_material: Optional[EstiloContenidoEnum] = None
    tipo_recursos_generar: Optional[str] = None


class ClaseResponseDTO(ClaseCreateDTO):
    id: int
    estado: bool
    created_at: Optional[datetime] = None
