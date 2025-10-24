from typing import List, Optional, Dict, Any
from database import supabase
from .schema import ConversacionCreateDTO, ConversacionResponseDTO, TipoEntidadEnum, RespuestaPsicopedagogicaDTO
from datetime import datetime

# guarded imports for file and generative services
try:
    from src.files.service import file_service
except Exception:
    file_service = None

try:
    from src.generative_ai.service_audio import process_audio_upload, generate_audio_file
except Exception:
    process_audio_upload = None
    generate_audio_file = None


# RAG / Pinecone retrieval helper (guarded)
try:
    from src.rag.service import retrieve_top_k_documents
except Exception:
    retrieve_top_k_documents = None


async def chat_general_personalizado(estudiante_id: int, request_data) -> Optional[dict]:
    """Función migrada desde el router: chat general personalizado.

    Args:
        estudiante_id: id del estudiante que pregunta
        request_data: instancia de ChatGeneralRequestDTO (pydantic) con los campos esperados

    Returns:
        RespuestaPsicopedagogicaDTO-like dict (compatible con el response_model usado en router)
    """
    try:
        # Validar estudiante
        estudiante_response = supabase.table('estudiante').select("*").eq('id', estudiante_id).execute()
        if not estudiante_response.data:
            raise Exception("Estudiante no encontrado")
        estudiante = estudiante_response.data[0]

        # Validar clase
        clase_response = supabase.table('clase').select("*").eq('id', request_data.id_clase).execute()
        if not clase_response.data:
            raise Exception("Clase no encontrada")
        clase = clase_response.data[0]

        # Mensaje actual
        mensaje_actual = (request_data.mensaje_actual or "").strip()
        if not mensaje_actual or len(mensaje_actual) < 3:
            respuesta_incomprensible = f"""No comprendo tu mensaje. Como tu profesor virtual de **{clase.get('nombre','la clase')}**, necesito que seas más específico.

Puedes preguntarme sobre:
• Conceptos específicos del tema
• Dudas sobre materiales de estudio
• Ejercicios o ejemplos prácticos
• Aplicaciones del contenido

¿Podrías reformular tu pregunta más claramente?"""

            # Registrar la conversación (usuario)
            try:
                conv_in = ConversacionCreateDTO(
                    id_emisor=estudiante_id,
                    id_receptor=request_data.id_clase,
                    tipo_emisor=TipoEntidadEnum.ESTUDIANTE,
                    tipo_receptor=TipoEntidadEnum.CHATBOT,
                    mensaje=mensaje_actual,
                )
                await registrar_conversacion(conv_in)
            except Exception:
                pass

            # Registrar respuesta del bot
            bot_conv = None
            try:
                conv_bot = ConversacionCreateDTO(
                    id_emisor=request_data.id_clase,
                    id_receptor=estudiante_id,
                    tipo_emisor=TipoEntidadEnum.CHATBOT,
                    tipo_receptor=TipoEntidadEnum.ESTUDIANTE,
                    mensaje=respuesta_incomprensible,
                )
                bot_conv = await registrar_conversacion(conv_bot)
            except Exception:
                bot_conv = None

            metadata = {
                "mensaje_usuario": mensaje_actual,
                "perfil_personalidad": request_data.perfil_personalidad,
                "comprensible": False,
            }
            try:
                if bot_conv is not None:
                    metadata["conversacion_id"] = bot_conv.id
            except Exception:
                pass

            return RespuestaPsicopedagogicaDTO(
                status="success",
                estudiante_id=estudiante_id,
                clase_id=request_data.id_clase,
                contenido_generado=respuesta_incomprensible,
                perfil_cognitivo=getattr(request_data.perfil_cognitivo, 'value', str(request_data.perfil_cognitivo)),
                nivel_conocimientos=getattr(request_data.nivel_conocimientos, 'value', str(request_data.nivel_conocimientos)),
                timestamp=datetime.now(),
                tipo_respuesta="chat_general",
                metadata=metadata,
            )

        # Recuperar contexto usando Pinecone (retrieve_top_k_documents) si está disponible
        contenido_contexto = ""
        try:
            if retrieve_top_k_documents is not None:
                namespace = f"clase_{request_data.id_clase}"
                docs = retrieve_top_k_documents(mensaje_actual, namespace=namespace, top_k=5)
                parts = []
                for d in docs:
                    t = d.get('text') or (d.get('metadata') or {}).get('text') or ''
                    if t:
                        parts.append(t)
                contenido_contexto = "\n\n".join(parts)
        except Exception:
            contenido_contexto = ""

        # Construir historial breve
        historial_contexto = ""
        try:
            if getattr(request_data, 'historial_mensajes', None):
                historial_contexto = "\n\n**HISTORIAL DE CONVERSACIÓN ANTERIOR:**\n"
                for msg in request_data.historial_mensajes[-5:]:
                    tipo = msg.get('tipo', 'user')
                    contenido = msg.get('contenido', '')
                    if tipo == 'user':
                        historial_contexto += f"🧑‍🎓 **Estudiante:** {contenido}\n"
                    else:
                        historial_contexto += f"👨‍🏫 **Profesor:** {contenido}\n"
        except Exception:
            historial_contexto = ""

        # Intentar usar LLM si está disponible para generar respuesta
        contenido_respuesta = None
        try:
            # Intento de cargar manager/agentes o llm desde generative_ai
            try:
                from src.generative_ai.service_chat import crear_manager_agentes
                manager = None
                try:
                    manager = crear_manager_agentes()
                except Exception:
                    manager = None
            except Exception:
                manager = None

            # Si tenemos manager.llm o manager disponible, pedir la respuesta
            if manager is not None and getattr(manager, 'llm', None) is not None:
                # construir prompt simple
                prompt_profesor = f"Eres un profesor virtual personalizado especializado en {clase.get('area','')} - {clase.get('nombre','')}.\n\n" \
                    f"INFORMACIÓN DEL ESTUDIANTE:\n- Nombre: {estudiante.get('nombre','')}\n- Perfil: {getattr(request_data.perfil_cognitivo,'value',request_data.perfil_cognitivo)}\n- Personalidad: {request_data.perfil_personalidad}\n\n" \
                    f"CONTENIDO DEL CURSO:\n{(contenido_contexto or 'No hay contenido específico disponible.')[:1500]}\n\n{historial_contexto}\n\nPREGUNTA: {mensaje_actual}\n\nResponde en máximo 200 palabras."

                resp = manager.llm.invoke(prompt_profesor)
                contenido_respuesta = resp.content if hasattr(resp, 'content') else str(resp)
            else:
                # fallback simple
                contenido_respuesta = f"Hola {estudiante.get('nombre','')}, soy tu profesor virtual de **{clase.get('nombre','la clase')}**.\n\nHe recibido tu mensaje: \"{mensaje_actual}\"\n\nTe recomiendo revisar los materiales de la clase y preguntar con más detalle sobre el concepto que te interesa."
        except Exception as e:
            print(f"Error generando respuesta del profesor: {e}")
            contenido_respuesta = f"Hola {estudiante.get('nombre','')}, tengo dificultades técnicas temporales. Por favor reformula tu pregunta." 

        # Registrar conversaciones
        try:
            conv_user = ConversacionCreateDTO(
                id_emisor=estudiante_id,
                id_receptor=request_data.id_clase,
                tipo_emisor=TipoEntidadEnum.ESTUDIANTE,
                tipo_receptor=TipoEntidadEnum.CHATBOT,
                mensaje=mensaje_actual,
            )
            await registrar_conversacion(conv_user)
        except Exception:
            pass

        bot_conv = None
        try:
            conv_bot = ConversacionCreateDTO(
                id_emisor=request_data.id_clase,
                id_receptor=estudiante_id,
                tipo_emisor=TipoEntidadEnum.CHATBOT,
                tipo_receptor=TipoEntidadEnum.ESTUDIANTE,
                mensaje=contenido_respuesta,
            )
            bot_conv = await registrar_conversacion(conv_bot)
        except Exception:
            bot_conv = None

        metadata = {
            "mensaje_usuario": mensaje_actual,
            "perfil_personalidad": request_data.perfil_personalidad,
            "clase_nombre": clase.get('nombre'),
            "clase_tema": clase.get('tema'),
            "comprensible": True,
            "historial_length": len(getattr(request_data, 'historial_mensajes', []) or []),
        }
        try:
            if bot_conv is not None:
                metadata['conversacion_id'] = bot_conv.id
        except Exception:
            pass

        return RespuestaPsicopedagogicaDTO(
            status="success",
            estudiante_id=estudiante_id,
            clase_id=request_data.id_clase,
            contenido_generado=contenido_respuesta,
            perfil_cognitivo=getattr(request_data.perfil_cognitivo, 'value', str(request_data.perfil_cognitivo)),
            nivel_conocimientos=getattr(request_data.nivel_conocimientos, 'value', str(request_data.nivel_conocimientos)),
            timestamp=datetime.now(),
            tipo_respuesta="chat_general",
            metadata=metadata,
        )

    except Exception as e:
        print(f"chat_general_personalizado error: {e}")
        return None


async def registrar_conversacion(conversacion: ConversacionCreateDTO) -> Optional[ConversacionResponseDTO]:
    try:
        data = {
            "id_emisor": conversacion.id_emisor,
            "id_receptor": conversacion.id_receptor,
            "tipo_emisor": conversacion.tipo_emisor.value,
            "tipo_receptor": conversacion.tipo_receptor.value,
            "mensaje": conversacion.mensaje,
        }
        if conversacion.archivo:
            data["archivo"] = conversacion.archivo

        result = supabase.table("conversacion").insert(data).execute()
        if result.data:
            conv = result.data[0]
            return ConversacionResponseDTO(
                id=conv["id"],
                id_emisor=conv["id_emisor"],
                id_receptor=conv["id_receptor"],
                tipo_emisor=TipoEntidadEnum(conv["tipo_emisor"]),
                tipo_receptor=TipoEntidadEnum(conv["tipo_receptor"]),
                mensaje=conv["mensaje"],
                archivo=conv.get("archivo"),
                created_at=conv.get("created_at", datetime.utcnow())
            )
        return None
    except Exception as e:
        print(f"registrar_conversacion error: {e}")
        return None


async def obtener_conversaciones(filters: Dict[str, Any]) -> List[ConversacionResponseDTO]:
    try:
        query = supabase.table("conversacion").select("*")
        if filters.get("id_emisor") is not None:
            query = query.eq("id_emisor", filters.get("id_emisor"))
        if filters.get("id_receptor") is not None:
            query = query.eq("id_receptor", filters.get("id_receptor"))
        if filters.get("tipo_emisor") is not None:
            query = query.eq("tipo_emisor", filters.get("tipo_emisor"))
        if filters.get("tipo_receptor") is not None:
            query = query.eq("tipo_receptor", filters.get("tipo_receptor"))

        limit = filters.get("limit", 50)
        offset = filters.get("offset", 0)
        query = query.order("created_at", desc=True).range(offset, offset + limit - 1)

        result = query.execute()
        out = []
        for conv in (result.data or []):
            out.append(ConversacionResponseDTO(
                id=conv["id"],
                id_emisor=conv["id_emisor"],
                id_receptor=conv["id_receptor"],
                tipo_emisor=TipoEntidadEnum(conv["tipo_emisor"]),
                tipo_receptor=TipoEntidadEnum(conv["tipo_receptor"]),
                mensaje=conv["mensaje"],
                archivo=conv.get("archivo"),
                created_at=conv.get("created_at")
            ))
        return out
    except Exception as e:
        print(f"obtener_conversaciones error: {e}")
        return []


async def obtener_historial_chat(estudiante_id: int, id_clase: int, limit: int = 50):
    try:
        query = supabase.table("conversacion").select("*").or_(
            f"and(id_emisor.eq.{estudiante_id},id_receptor.eq.{id_clase},tipo_emisor.eq.1,tipo_receptor.eq.3),"
            f"and(id_emisor.eq.{id_clase},id_receptor.eq.{estudiante_id},tipo_emisor.eq.3,tipo_receptor.eq.1)"
        ).order("created_at", desc=False).limit(limit)

        result = query.execute()
        out = []
        for conv in (result.data or []):
            out.append(ConversacionResponseDTO(
                id=conv["id"],
                id_emisor=conv["id_emisor"],
                id_receptor=conv["id_receptor"],
                tipo_emisor=TipoEntidadEnum(conv["tipo_emisor"]),
                tipo_receptor=TipoEntidadEnum(conv["tipo_receptor"]),
                mensaje=conv["mensaje"],
                archivo=conv.get("archivo"),
                created_at=conv.get("created_at")
            ))
        return out
    except Exception as e:
        print(f"obtener_historial_chat error: {e}")
        return []


async def eliminar_conversacion(conversacion_id: int) -> bool:
    try:
        result = supabase.table("conversacion").delete().eq("id", conversacion_id).execute()
        return bool(result.data)
    except Exception as e:
        print(f"eliminar_conversacion error: {e}")
        return False


async def actualizar_conversacion_archivo(conversacion_id: int, archivo_path: str) -> bool:
    """Update the 'archivo' field of an existing conversacion record."""
    try:
        if conversacion_id is None:
            return False
        result = supabase.table("conversacion").update({"archivo": archivo_path}).eq("id", conversacion_id).execute()
        return bool(result.data)
    except Exception as e:
        print(f"actualizar_conversacion_archivo error: {e}")
        return False


async def process_audio_and_register(file_bytes: bytes, filename: str, id_clase: int, id_emisor: int, id_receptor: int, tipo_emisor: TipoEntidadEnum, tipo_receptor: TipoEntidadEnum) -> dict:
    # Attempts to store the audio via file_service and transcribe using generative_ai audio service if available.
    s3_path = None
    transcript = None
    try:
        if file_service is not None:
            rel = f"uploaded/class/{id_clase}/{filename}"
            ok = file_service.upload_bytes(file_bytes, rel)
            if ok:
                s3_path = f"/{rel}"

        # Use process_audio_upload wrapper if available
        if process_audio_upload is not None:
            res = await process_audio_upload(file_bytes, filename, id_clase)
            transcript = res.get("transcript") if isinstance(res, dict) else None
        else:
            # fallback: no STT available
            transcript = None

        # register conversation with transcript or file path
        mensaje = transcript or "[audio]"
        conversacion = ConversacionCreateDTO(
            id_emisor=id_emisor,
            id_receptor=id_receptor,
            tipo_emisor=tipo_emisor,
            tipo_receptor=tipo_receptor,
            mensaje=mensaje,
            archivo=s3_path
        )
        await registrar_conversacion(conversacion)

        return {"transcript": transcript, "s3_path": s3_path}
    except Exception as e:
        print(f"process_audio_and_register error: {e}")
        return {"error": str(e)}
