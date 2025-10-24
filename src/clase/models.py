from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime

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
    
class TipoSesionEnum(str, Enum):
    CLASE_TEORICA = "Clase teorica"
    TALLER_PRACTICO = "Taller practico"
    SESION_REPASO = "Sesion de repaso"
    EVALUACION_FORMATIVA = "Evaluacion formativa"
    SESION_INTEGRACION = "Sesion de integracion"

class ModalidadEnum(str, Enum):
    PRESENCIAL = "Presencial"
    HIBRIDA = "Hibrida"
    VIRTUAL_SINCRONICA = "Virtual sincronica"
    VIRTUAL_ASINCRONICA = "Virtual asincronica"

class ResultadoTaxonomiaEnum(str, Enum):
    RECORDAR = "Recordar"
    COMPRENDER = "Comprender"
    APLICAR = "Aplicar"
    ANALIZAR = "Analizar"
    EVALUAR = "Evaluar"
    CREAR = "Crear"

class EstiloContenidoEnum(str, Enum):
    FORMAL_ACADEMICO = "Formal academico"
    CERCANO_MOTIVADOR = "Cercano y motivador"
    PRACTICO_DIRECTO = "Practico y directo"
    NARRATIVO_STORYTELLING = "Narrativo/Storytelling"

class ClaseDB(BaseModel):
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
    estado: bool = True
    created_at: datetime