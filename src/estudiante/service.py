from typing import Optional, Dict, Any, List
from database import supabase
from ..docente.service import hash_password, verify_password


def create_estudiante(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    d = data.copy()
    d['password'] = hash_password(d['password'])
    resp = supabase.table('estudiante').insert(d).execute()
    return resp.data[0] if getattr(resp, 'data', None) else None


def find_by_email(correo: str) -> Optional[Dict[str, Any]]:
    resp = supabase.table('estudiante').select('*').eq('correo', correo).execute()
    return resp.data[0] if getattr(resp, 'data', None) else None


def get_estudiante(id_estudiante: int) -> Optional[Dict[str, Any]]:
    resp = supabase.table('estudiante').select('id, nombre, correo, perfil_cognitivo, perfil_personalidad').eq('id', id_estudiante).execute()
    return resp.data[0] if getattr(resp, 'data', None) else None


def list_estudiantes() -> List[Dict[str, Any]]:
    resp = supabase.table('estudiante').select('id, nombre, correo, perfil_cognitivo, perfil_personalidad').execute()
    return resp.data or []


def update_estudiante(id_estudiante: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    d = update_data.copy()
    if 'password' in d and d['password']:
        d['password'] = hash_password(d['password'])
    resp = supabase.table('estudiante').update(d).eq('id', id_estudiante).execute()
    return resp.data[0] if getattr(resp, 'data', None) else None


def check_perfil_completo(id_estudiante: int) -> Dict[str, bool]:
    """Return whether perfil_cognitivo and perfil_personalidad are present (not null/empty)."""
    resp = supabase.table('estudiante').select('perfil_cognitivo, perfil_personalidad').eq('id', id_estudiante).execute()
    row = resp.data[0] if getattr(resp, 'data', None) else None
    if not row:
        return {"perfil_cognitivo": False, "perfil_personalidad": False, "completo": False}

    pc = row.get('perfil_cognitivo') is not None and str(row.get('perfil_cognitivo')).strip() != ''
    pp = row.get('perfil_personalidad') is not None and str(row.get('perfil_personalidad')).strip() != ''
    return {"perfil_cognitivo": bool(pc), "perfil_personalidad": bool(pp), "completo": bool(pc and pp)}


def delete_estudiante(id_estudiante: int) -> bool:
    # ensure not enrolled
    inscritos = supabase.table('estudiante_clase').select('*').eq('id_estudiante', id_estudiante).execute()
    if inscritos.data:
        return False
    resp = supabase.table('estudiante').delete().eq('id', id_estudiante).execute()
    return bool(getattr(resp, 'data', None))
