from typing import Optional, List, Dict, Any
from database import supabase
from ..files.service import file_service
from datetime import datetime
import os
from typing import Any, Dict, List


def create_clase(clase_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        clase_data['estado'] = True
        resp = supabase.table('clase').insert(clase_data).execute()
        return resp.data[0] if resp and getattr(resp, 'data', None) else None
    except Exception as e:
        print(f"create_clase error: {e}")
        return None


def get_clase(id_clase: int) -> Optional[Dict[str, Any]]:
    try:
        resp = supabase.table('clase').select('*').eq('id', id_clase).execute()
        return resp.data[0] if resp and getattr(resp, 'data', None) else None
    except Exception as e:
        print(f"get_clase error: {e}")
        return None


def list_clases(id_docente: Optional[int] = None) -> List[Dict[str, Any]]:
    try:
        q = supabase.table('clase').select('*')
        if id_docente:
            q = q.eq('id_docente', id_docente)
        resp = q.execute()
        return resp.data if resp and getattr(resp, 'data', None) else []
    except Exception as e:
        print(f"list_clases error: {e}")
        return []


def cambiar_estado_clase(id_clase: int, estado: bool) -> bool:
    try:
        resp = supabase.table('clase').update({'estado': estado}).eq('id', id_clase).execute()
        return bool(resp and getattr(resp, 'data', None))
    except Exception as e:
        print(f"cambiar_estado_clase error: {e}")
        return False


def upload_files(id_clase: int, upload_files) -> List[Dict[str, Any]]:
    """Upload multiple FastAPI UploadFile objects to S3 via file_service and insert metadata into 'archivos' table."""
    results = []
    try:
        # delegate to file_service.upload_multiple_files which already inserts DB records
        # file_service.upload_multiple_files returns list of dicts with 'filename','path','db_result'
        res = None
        # the file_service upload_multiple_files is async in some implementations; try both
        try:
            # if it's a coroutine function
            maybe = file_service.upload_multiple_files(upload_files, id_clase)
            # if returns an awaitable
            if getattr(maybe, '__await__', None):
                import asyncio
                res = asyncio.get_event_loop().run_until_complete(maybe)
            else:
                res = maybe
        except TypeError:
            # fallback direct call
            res = file_service.upload_multiple_files(upload_files, id_clase)

        results = res or []
    except Exception as e:
        print(f"upload_files error: {e}")
    return results


def listar_archivos_clase(id_clase: int, tipo: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        q = supabase.table('archivos').select('*').eq('id_clase', id_clase)
        if tipo and tipo in ['Subido', 'Generado']:
            q = q.eq('tipo', tipo)
        resp = q.execute()
        return resp.data if resp and getattr(resp, 'data', None) else []
    except Exception as e:
        print(f"listar_archivos_clase error: {e}")
        return []


def get_presigned_download(id_clase: int, filename: str) -> Optional[str]:
    # Expect files to be stored under uploaded/class/{id_clase}/{filename} or generated/images/{id_clase}/{filename}
    candidates = [f"uploaded/class/{id_clase}/{filename}", f"generated/images/{id_clase}/{filename}"]
    for key in candidates:
        try:
            url = file_service.get_presigned_url(key)
            if url:
                return url
        except Exception:
            continue
    return None


def eliminar_archivo(id_clase: int, filename: str) -> bool:
    try:
        # find record
        archivo_resp = supabase.table('archivos').select('*').eq('id_clase', id_clase).eq('filename', filename).execute()
        if not archivo_resp.data:
            return False
        archivo_id = archivo_resp.data[0]['id']

        # attempt S3 delete (both possible keys)
        keys = [f"uploaded/class/{id_clase}/{filename}", f"generated/images/{id_clase}/{filename}"]
        for k in keys:
            try:
                file_service.delete_file(k)
            except Exception:
                pass

        supabase.table('archivos').delete().eq('id', archivo_id).execute()
        return True
    except Exception as e:
        print(f"eliminar_archivo error: {e}")
        return False


async def procesar_clase(id_clase: int) -> Dict[str, Any]:
    """Procesa los archivos de la clase y coordina generación de contenido usando RAG + agentes.

    - Usa `src.rag.service.process_class_files` para extraer y subir chunks a Pinecone (namespace por clase)
    - Recupera contexto (top_k) desde Pinecone y construye `context` para los agentes
    - Crea un `ManagerAgentes` (si está disponible) para generar estructura, recursos, preguntas, presentaciones y contenido por índice
    - Inserta resultados en la tabla `contenido` y actualiza `contenido_estudiante` cuando aplique
    """
    try:
        # Lazy imports so module still loads if optional deps are missing
        try:
            from src.rag.service import process_class_files, retrieve_top_k_documents
        except Exception:
            process_class_files = None
            retrieve_top_k_documents = None

        try:
            from src.generative_ai.service_chat import crear_manager_agentes
        except Exception:
            crear_manager_agentes = None

        try:
            from src.estudiante_contenido import service as estudiante_contenido_service
        except Exception:
            estudiante_contenido_service = None

        # Check class existence
        clase_resp = supabase.table('clase').select('*').eq('id', id_clase).execute()
        if not clase_resp.data:
            raise Exception('Clase no encontrada')
        clase_data = clase_resp.data[0]

        # Check archivos
        archivos_resp = supabase.table('archivos').select('*').eq('id_clase', id_clase).execute()
        if not archivos_resp.data:
            raise Exception('No hay archivos para procesar en esta clase')

        # 1) Procesar archivos y crear namespace/index en Pinecone
        rag_result = None
        if process_class_files is None:
            raise Exception('RAG service no disponible en este entorno')

        # process_class_files will look into uploaded/class/{id_clase} in S3
        rag_result = process_class_files(str(id_clase))
        if not rag_result or not rag_result.get('ok'):
            raise Exception(f"RAG processing failed: {rag_result}")

        namespace = rag_result.get('namespace')

        # 2) Recuperar contexto usando top-k
        context = ''
        if retrieve_top_k_documents is not None and namespace:
            try:
                docs = retrieve_top_k_documents(clase_data.get('tema', 'contenido educativo'), namespace=namespace, top_k=10)
                parts = [d.get('text') or (d.get('metadata') or {}).get('text') for d in docs]
                parts = [p for p in parts if p]
                context = '\n\n'.join(parts) if parts else 'Contenido educativo general'
            except Exception:
                context = 'Contenido educativo general'
        else:
            context = 'Contenido educativo general'

        contenidos_generados: List[Dict[str, Any]] = []

        # 3) Crear manager de agentes si está disponible
        manager = None
        if crear_manager_agentes is not None:
            try:
                manager = crear_manager_agentes()
            except Exception:
                manager = None

        # 4) Generar estructura de clase
        if manager and hasattr(manager, 'generar_estructura_clase_completa'):
            try:
                estructura = await manager.generar_estructura_clase_completa(clase_data, context)
                if estructura:
                    contenido_data = {
                        'id_clase': id_clase,
                        'tipo_recurso_generado': 'Estructura de Clase',
                        'contenido': estructura,
                        'estado': True,
                    }
                    resp = supabase.table('contenido').insert(contenido_data).execute()
                    contenidos_generados.append({'tipo': 'Estructura de Clase', 'status': 'success', 'contenido_id': resp.data[0]['id'] if resp.data else None, 'preview': estructura[:200]})
                else:
                    contenidos_generados.append({'tipo': 'Estructura de Clase', 'status': 'error', 'error': 'No se pudo generar estructura'})
            except Exception as e:
                contenidos_generados.append({'tipo': 'Estructura de Clase', 'status': 'error', 'error': str(e)})
        else:
            contenidos_generados.append({'tipo': 'Estructura de Clase', 'status': 'skipped', 'error': 'Manager de agentes no disponible'})

        # 5) Buscar recursos educativos
        if manager and hasattr(manager, 'buscar_recursos_educativos'):
            try:
                recursos = manager.buscar_recursos_educativos(clase_data, context)
                if recursos:
                    contenido_data = {'id_clase': id_clase, 'tipo_recurso_generado': 'Recursos Educativos Web', 'contenido': recursos, 'estado': True}
                    resp = supabase.table('contenido').insert(contenido_data).execute()
                    contenidos_generados.append({'tipo': 'Recursos Educativos Web', 'status': 'success', 'contenido_id': resp.data[0]['id'] if resp.data else None, 'preview': (recursos[:200] if isinstance(recursos, str) else str(recursos)[:200])})
                else:
                    contenidos_generados.append({'tipo': 'Recursos Educativos Web', 'status': 'error', 'error': 'No se encontraron recursos'})
            except Exception as e:
                contenidos_generados.append({'tipo': 'Recursos Educativos Web', 'status': 'error', 'error': str(e)})
        else:
            contenidos_generados.append({'tipo': 'Recursos Educativos Web', 'status': 'skipped', 'error': 'Manager no disponible'})

        # 6) Generar índices de contenido para estudiantes (por perfiles)
        indices_result = []
        if estudiante_contenido_service is not None and crear_manager_agentes is not None and manager is not None:
            try:
                indices_result = await estudiante_contenido_service.generar_indices_contenido_estudiante(id_clase, manager)
                contenidos_generados.append({'tipo': 'Índices de Contenido para Estudiantes', 'status': 'success', 'indices_generados': len(indices_result)})
            except Exception as e:
                contenidos_generados.append({'tipo': 'Índices de Contenido para Estudiantes', 'status': 'error', 'error': str(e)})
        else:
            contenidos_generados.append({'tipo': 'Índices de Contenido para Estudiantes', 'status': 'skipped', 'error': 'Servicio de contenidos o manager no disponible'})

        # 7) Actualizar contenido personalizado usando manager.generar_contenido_indice
        try:
            contenidos_actualizados = 0
            contenidos_result = supabase.table('contenido_estudiante').select('*').eq('id_clase', id_clase).execute()
            for contenido in (contenidos_result.data or []):
                try:
                    if manager and hasattr(manager, 'generar_contenido_indice'):
                        gen = await manager.generar_contenido_indice(contenido.get('indice', ''), clase_data.get('nivel_educativo', ''), contenido.get('perfil_cognitivo', ''), int(contenido.get('tiempo_estimado', 15) or 15))
                        if gen and isinstance(gen, dict) and gen.get('contenido'):
                            supabase.table('contenido_estudiante').update({'contenido': gen['contenido']}).eq('id', contenido['id']).execute()
                            contenidos_actualizados += 1
                except Exception:
                    # proceed with next
                    continue
            contenidos_generados.append({'tipo': 'Actualización de Contenido Personalizado', 'status': 'success', 'contenidos_actualizados': contenidos_actualizados})
        except Exception as e:
            contenidos_generados.append({'tipo': 'Actualización de Contenido Personalizado', 'status': 'error', 'error': str(e)})

        # 8) Generar preguntas (opcional)
        if manager and hasattr(manager, 'generar_preguntas'):
            try:
                preguntas = await manager.generar_preguntas(clase_data, context, num_preguntas=5)
                if preguntas:
                    contenido_data = {'id_clase': id_clase, 'tipo_recurso_generado': 'Preguntas', 'contenido': str(preguntas), 'estado': True}
                    resp = supabase.table('contenido').insert(contenido_data).execute()
                    contenidos_generados.append({'tipo': 'Preguntas', 'status': 'success', 'contenido_id': resp.data[0]['id'] if resp.data else None})
                else:
                    contenidos_generados.append({'tipo': 'Preguntas', 'status': 'error', 'error': 'No se generaron preguntas'})
            except Exception as e:
                contenidos_generados.append({'tipo': 'Preguntas', 'status': 'error', 'error': str(e)})
        else:
            contenidos_generados.append({'tipo': 'Preguntas', 'status': 'skipped', 'error': 'Manager no disponible'})

        exitosos = sum(1 for item in contenidos_generados if item.get('status') == 'success')
        errores = sum(1 for item in contenidos_generados if item.get('status') == 'error')

        return {
            'message': 'Procesamiento de clase completado',
            'clase_id': id_clase,
            'contenidos_generados': contenidos_generados,
            'tema': clase_data.get('tema', 'No especificado'),
            'nivel_educativo': clase_data.get('nivel_educativo', 'No especificado'),
            'exitosos': exitosos,
            'errores': errores,
        }

    except Exception as e:
        print(f"procesar_clase error: {e}")
        raise

def get_estadisticas_por_clase(id_clase: int) -> Dict[str, Any]:
    insc = supabase.table('estudiante_clase').select('*').eq('id_clase', id_clase).execute()
    total = len(insc.data) if insc.data else 0
    perfiles = {"Visual": 0, "Auditivo": 0, "Lector": 0, "Kinestesico": 0}
    for item in insc.data or []:
        est = supabase.table('estudiante').select('perfil_cognitivo').eq('id', item['id_estudiante']).execute()
        if est.data:
            perfil = est.data[0].get('perfil_cognitivo')
            if perfil in perfiles:
                perfiles[perfil] += 1

    pred = 'Visual'
    max_count = perfiles.get(pred, 0)
    for p, c in perfiles.items():
        if c > max_count:
            pred = p
            max_count = c

    return {"total": total, "perfiles_cognitivos": perfiles, "perfil_predominante": pred}
