from typing import Optional, List, Dict, Any
from database import supabase


def inscribir_estudiante(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    d = data.copy()
    d['estado'] = True
    resp = supabase.table('estudiante_clase').insert(d).execute()
    return resp.data[0] if getattr(resp, 'data', None) else None


def get_inscripcion(id_inscripcion: int) -> Optional[Dict[str, Any]]:
    resp = supabase.table('estudiante_clase').select('*').eq('id', id_inscripcion).execute()
    return resp.data[0] if getattr(resp, 'data', None) else None


def list_inscripciones_by_student(id_estudiante: int, incluir_inactivas: bool = False) -> List[Dict[str, Any]]:
    q = supabase.table('estudiante_clase').select('*').eq('id_estudiante', id_estudiante)
    if not incluir_inactivas:
        q = q.eq('estado', True)
    resp = q.execute()
    return resp.data or []


def list_inscripciones_by_class(id_clase: int) -> List[Dict[str, Any]]:
    resp = supabase.table('estudiante_clase').select('*').eq('id_clase', id_clase).execute()
    return resp.data or []


def update_inscripcion(id_inscripcion: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    d = {k: v for k, v in update_data.items() if v is not None}
    resp = supabase.table('estudiante_clase').update(d).eq('id', id_inscripcion).execute()
    return resp.data[0] if getattr(resp, 'data', None) else None


def delete_inscripcion(id_inscripcion: int) -> bool:
    resp = supabase.table('estudiante_clase').delete().eq('id', id_inscripcion).execute()
    return bool(getattr(resp, 'data', None))


def list_all_inscripciones() -> List[Dict[str, Any]]:
    resp = supabase.table('estudiante_clase').select('*').execute()
    return resp.data or []
