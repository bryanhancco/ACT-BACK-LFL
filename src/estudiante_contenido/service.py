from typing import List, Optional
from database import supabase
from .schema import (
    ContenidoEstudianteCreateDTO,
    ContenidoEstudianteResponseDTO,
    ContenidoEstudianteUpdateDTO,
    ContenidoEstudianteDataCreateDTO,
    ContenidoEstudianteDataResponseDTO,
    ContenidoEstudianteDataUpdateDTO,
)
from src.estudiante_contenido.models import EstadoContenidoEnum
from src.estudiante_clase.service import get_inscripcion


async def generar_indices_contenido_estudiante(id_clase: int, manager) -> List[ContenidoEstudianteResponseDTO]:
    """
    Generate indices for a class using an injected manager (agent factory).
    This mirrors the logic from api/api.py but keeps side-effects in the service layer.
    """
    # verify class exists
    clase_result = supabase.table("clase").select("*").eq("id", id_clase).execute()
    if not clase_result.data:
        raise Exception("Clase no encontrada")

    # Try to prepare a richer 'contenido' for the indexer by running a RAG retrieval
    # so the index generation is grounded in the class materials (if available).
    indice_resultado = []
    try:
        tema = clase_result.data[0].get("tema", "Contenido educativo")
        # attempt to import RAG retrieval util
        try:
            from src.rag.service import retrieve_top_k_documents
        except Exception:
            retrieve_top_k_documents = None

        retrieved_texts = []
        if retrieve_top_k_documents is not None:
            try:
                # use the class namespace to retrieve relevant chunks
                namespace = f"clase_{id_clase}"
                docs = retrieve_top_k_documents(tema, namespace=namespace, top_k=10)
                for d in (docs or []):
                    txt = None
                    if isinstance(d, dict):
                        txt = d.get('text') or (d.get('metadata') or {}).get('text') or d.get('content')
                    else:
                        try:
                            txt = getattr(d, 'text', None) or getattr(d, 'content', None)
                        except Exception:
                            txt = None
                    if txt:
                        retrieved_texts.append(txt[:2000])
            except Exception as e:
                print(f"Error retrieving docs for indices generation: {e}")

        # Build the contenido passed to the index generator: include tema and retrieved texts
        contenido_para_indice = tema + "\n\n" + "\n\n".join(retrieved_texts) if retrieved_texts else tema

        # manager should expose generar_indice_clase and expects the full content
        try:
            indice_resultado = await manager.generar_indice_clase(contenido=contenido_para_indice, nivel_clase=clase_result.data[0].get("nivel_educativo", "Secundaria"))
        except Exception as e:
            print(f"Error calling manager.generar_indice_clase: {e}")
            indice_resultado = []
    except Exception as e:
        print(f"Error preparing contenido for indice generation: {e}")
        indice_resultado = []

    perfiles_cognitivos = ['Visual', 'Auditivo', 'Lector', 'Kinestesico']
    contenidos_creados: List[ContenidoEstudianteResponseDTO] = []

    for elemento_indice in indice_resultado:
        for perfil in perfiles_cognitivos:
            if not isinstance(elemento_indice, dict):
                continue
            orden = elemento_indice.get('orden', 1)
            titulo_indice = elemento_indice.get('indice', 'Contenido de la clase')
            tiempo_estimado = elemento_indice.get('tiempo_estimado', 15)

            contenido_data = ContenidoEstudianteCreateDTO(
                id_clase=id_clase,
                indice=titulo_indice,
                orden=orden,
                contenido="",
                perfil_cognitivo=perfil,
                tiempo_estimado=tiempo_estimado,
                estado=True,
            )

            result = supabase.table("contenido_estudiante").insert(contenido_data.dict()).execute()
            if result.data:
                contenidos_creados.append(ContenidoEstudianteResponseDTO(**result.data[0]))

    return contenidos_creados


async def crear_contenido(contenido: ContenidoEstudianteCreateDTO) -> ContenidoEstudianteResponseDTO:
    result = supabase.table("contenido_estudiante").insert(contenido.dict()).execute()
    if not result.data:
        raise Exception("No se pudo crear el contenido")
    return ContenidoEstudianteResponseDTO(**result.data[0])


async def listar_contenidos_por_clase(id_clase: int) -> List[ContenidoEstudianteResponseDTO]:
    result = supabase.table("contenido_estudiante").select("*").eq("id_clase", id_clase).order("orden").execute()
    return [ContenidoEstudianteResponseDTO(**item) for item in (result.data or [])]


async def obtener_contenido_por_perfil(id_clase: int, perfil_cognitivo: str) -> Optional[ContenidoEstudianteResponseDTO]:
    result = supabase.table("contenido_estudiante").select("*").eq("id_clase", id_clase).eq("perfil_cognitivo", perfil_cognitivo).order("orden").execute()
    if result.data:
        return ContenidoEstudianteResponseDTO(**result.data[0])
    return None


async def actualizar_contenido(contenido_id: int, datos: ContenidoEstudianteUpdateDTO) -> ContenidoEstudianteResponseDTO:
    update_dict = datos.dict(exclude_unset=True)
    result = supabase.table("contenido_estudiante").update(update_dict).eq("id", contenido_id).execute()
    if not result.data:
        raise Exception("No se pudo actualizar el contenido")
    return ContenidoEstudianteResponseDTO(**result.data[0])


async def eliminar_contenido(contenido_id: int) -> bool:
    result = supabase.table("contenido_estudiante").delete().eq("id", contenido_id).execute()
    return bool(result.data)


async def inicializar_progreso_estudiante(estudiante_id: int, id_clase: int):
    # Verify enrollment
    matricula_result = supabase.table("estudiante_clase").select("*").eq("id_estudiante", estudiante_id).eq("id_clase", id_clase).execute()
    if not matricula_result.data:
        raise Exception("El estudiante no está matriculado en esta clase")

    estudiante_result = supabase.table("estudiante").select("perfil_cognitivo").eq("id", estudiante_id).execute()
    if not estudiante_result.data:
        raise Exception("Estudiante no encontrado")

    perfil_cognitivo = estudiante_result.data[0]["perfil_cognitivo"]

    contenidos_result = supabase.table("contenido_estudiante").select("*").eq("id_clase", id_clase).eq("perfil_cognitivo", perfil_cognitivo).execute()
    if not contenidos_result.data:
        # try to generate automatically (caller might call generar_indices_contenido_estudiante)
        return {"message": "No hay contenidos disponibles", "registros_creados": 0}

    registros_creados = []
    for contenido in contenidos_result.data:
        existing_result = supabase.table("contenido_estudiante_data_estudiante").select("*").eq("id_contenido", contenido['id']).eq("id_estudiante", estudiante_id).execute()
        if not existing_result.data:
            progreso_data = ContenidoEstudianteDataCreateDTO(id_contenido=contenido['id'], id_estudiante=estudiante_id, estado=EstadoContenidoEnum.NO_INICIADO)
            result = supabase.table("contenido_estudiante_data_estudiante").insert(progreso_data.dict()).execute()
            if result.data:
                registros_creados.append(ContenidoEstudianteDataResponseDTO(**result.data[0]))

    return {"message": "Progreso inicializado exitosamente", "registros_creados": len(registros_creados), "progreso": registros_creados, "perfil_cognitivo": perfil_cognitivo}


async def obtener_progreso(estudiante_id: int, id_clase: int):
    # Get contents for profile
    estudiante_result = supabase.table("estudiante").select("perfil_cognitivo").eq("id", estudiante_id).execute()
    if not estudiante_result.data:
        raise Exception("Estudiante no encontrado")

    perfil_cognitivo = estudiante_result.data[0]["perfil_cognitivo"]
    contenidos_result = supabase.table("contenido_estudiante").select("*").eq("id_clase", id_clase).eq("perfil_cognitivo", perfil_cognitivo).order("orden").execute()
    contenidos_disponibles = [c for c in (contenidos_result.data or [])]

    progreso_result = supabase.table("contenido_estudiante_data_estudiante").select("*").eq("id_estudiante", estudiante_id).execute()
    progreso_estudiante = []
    for progreso in (progreso_result.data or []):
        for contenido in contenidos_disponibles:
            if contenido['id'] == progreso['id_contenido']:
                progreso_estudiante.append(ContenidoEstudianteDataResponseDTO(**progreso))
                break

    return {
        "contenidos_disponibles": contenidos_disponibles,
        "progreso_estudiante": progreso_estudiante,
        "perfil_cognitivo": perfil_cognitivo,
    }


async def actualizar_estado_progreso(progreso_id: int, datos: ContenidoEstudianteDataUpdateDTO) -> ContenidoEstudianteDataResponseDTO:
    datos_dict = datos.dict(exclude_unset=True)
    result = supabase.table("contenido_estudiante_data_estudiante").update(datos_dict).eq("id", progreso_id).execute()
    if not result.data:
        raise Exception("No se pudo actualizar el progreso")
    return ContenidoEstudianteDataResponseDTO(**result.data[0])
