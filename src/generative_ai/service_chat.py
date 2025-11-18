import os
import replicate
import requests
import json
from typing import Optional, Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import GoogleGenerativeAI
from dotenv import load_dotenv
import re
# Import RAG retrieval from the new rag service (src/rag/service.py)
try:
    from src.rag.service import retrieve_top_k_documents
except Exception:
    # Fallback: not available in this environment
    retrieve_top_k_documents = None

# image processing helper (may be unavailable in some test envs)
try:
    from .service_image import image_processor
except Exception:
    image_processor = None

# Cargar variables de entorno
load_dotenv()

class AgentePedagogico:
    """Clase base para agentes pedagógicos"""
    
    def __init__(self, llm=None):
        self.llm = llm
        # Configurar Replicate
        self.replicate_api_key = os.environ.get("REPLICATE_API_TOKEN")
        if self.replicate_api_key:
            self.replicate_client = replicate.Client(self.replicate_api_key)
        else:
            self.replicate_client = None
    
    def _clean_json_response(self, json_text: str) -> str:
        """Limpia la respuesta JSON eliminando markdown y formato extra"""
        if not json_text:
            return json_text
        
        # Eliminar bloques de código markdown
        json_text = json_text.strip()
        
        # Eliminar ```json al inicio
        if json_text.startswith('```json'):
            json_text = json_text[7:]  # Remover ```json
        
        # Eliminar ``` al final
        if json_text.endswith('```'):
            json_text = json_text[:-3]  # Remover ```
        
        # Eliminar solo ``` al inicio si existe
        if json_text.startswith('```'):
            json_text = json_text[3:]
        
        # Limpiar espacios en blanco extra
        json_text = json_text.strip()
        
        return json_text
    
    def _build_class_info(self, clase_data: Dict[str, Any]) -> str:
        """Construye la información de la clase para los prompts"""
        return f"""
        Información de la clase:
        - Área: {clase_data.get('area', 'No especificada')}
        - Tema: {clase_data.get('tema', 'No especificado')}
        - Nivel educativo: {clase_data.get('nivel_educativo', 'No especificado')}
        - Perfil de aprendizaje: {clase_data.get('perfil', 'No especificado')}
        - Duración estimada: {clase_data.get('duracion_estimada', 'No especificada')} minutos
        - Tipo de sesión: {clase_data.get('tipo_sesion', 'No especificado')}
        - Modalidad: {clase_data.get('modalidad', 'No especificada')}
        - Objetivos de aprendizaje: {clase_data.get('objetivos_aprendizaje', 'No especificados')}
        - Resultado taxonomía: {clase_data.get('resultado_taxonomia', 'No especificado')}
        - Conocimientos previos: {clase_data.get('conocimientos_previos_estudiantes', 'No especificados')}
        - Aspectos motivacionales: {clase_data.get('aspectos_motivacionales', 'No especificados')}
        - Estilo de material: {clase_data.get('estilo_material', 'No especificado')}
        """

    def retrieve_context(self, query: str, index_name: Optional[str] = None, top_k: int = 5) -> Optional[Dict[str, Any]]:
        """Helper to run RAG retrieval (uses src.rag.service.retrieve_top_k_documents).

        Returns the retrieval result dict with keys: query, index, namespace, matches, prompt
        or None if RAG retrieval function is not available.
        """
        if retrieve_top_k_documents is None:
            # RAG not available in this environment
            return None
        try:
            idx = index_name if index_name else None
            docs = retrieve_top_k_documents(query, index_name=idx, top_k=top_k)
            # Build a simple structure compatible with older callers
            prompt_contexts = [d.get("text") or (d.get("metadata") or {}).get("text") for d in docs]
            context = "\n\n".join([c for c in prompt_contexts if c])
            prompt = f"Usa la siguiente información para responder la pregunta:\n\nCONTEXT:\n{context}\n\nQUESTION: {query}\n\nRESPUESTA:"
            return {"query": query, "index": index_name, "namespace": None, "matches": docs, "prompt": prompt}
        except Exception as e:
            print(f"RAG retrieval error: {e}")
            return None


class AgenteContenidoGeneral(AgentePedagogico):
    """Agente para generar contenido educativo general en formato HTML"""
    
    async def generar_contenido(self, clase_data: Dict[str, Any], context: str, tipo_recurso: str) -> Optional[str]:
        """
        Genera contenido educativo general en formato HTML
        """
        if not self.llm:
            return None
            
        try:
            class_info = self._build_class_info(clase_data)
            
            system_prompt = f'''
            Eres un experto asistente pedagógico especializado en crear contenido educativo de alta calidad.
            Debes crear un {tipo_recurso.lower()} basado en la información de la clase y el contexto proporcionado.

            {class_info}

            El contenido debe:
            1. Estar completamente en formato HTML (solo con el contenido que iría en el body, el header o doctype e incluso los estilos son innecesarios)
            2. Ser apropiado para el nivel educativo indicado
            3. Seguir el estilo de material especificado
            4. Incorporar los aspectos motivacionales
            5. Alinearse con los objetivos de aprendizaje
            6. Considerar el perfil de aprendizaje de los estudiantes
            7. Ser específico para el tipo de recurso: {tipo_recurso}

            IMPORTANTE: Responde ÚNICAMENTE con el contenido en formato MARKDOWN
            '''
            
            user_prompt = f"""
            Contexto educativo extraído de los materiales:
            {context}
            
            Crear un {tipo_recurso} siguiendo las especificaciones de la clase.
            """
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            return response
            
        except Exception as e:
            print(f"Error generando contenido general: {str(e)}")
            return None


class AgenteAudio(AgentePedagogico):
    """Agente especializado en generar scripts para audio"""
    
    async def generar_script_audio(self, clase_data: Dict[str, Any], context: str) -> Optional[str]:
        """
        Genera un script optimizado para audio
        """
        if not self.llm:
            return None
            
        try:
            class_info = self._build_class_info(clase_data)
            
            system_prompt = f"""
            Eres un experto asistente pedagógico especializado en crear contenido educativo de alta calidad.
            Debes crear un script para un archivo de audio basado en la información de la clase y el contexto proporcionado.
            
            {class_info}
            
            El contenido debe:
            1. El script no debe superar las 100 palabras.
            2. Ser apropiado para el nivel educativo indicado
            3. Seguir el estilo de material especificado
            4. Incorporar los aspectos motivacionales
            5. Alinearse con los objetivos de aprendizaje
            6. Considerar el perfil de aprendizaje de los estudiantes
            7. Ser claro y natural para audio
            
            IMPORTANTE: Responde ÚNICAMENTE con el texto del script, sin explicaciones adicionales.
            """
            
            user_prompt = f"""
            Contexto educativo extraído de los materiales:
            {context}
            
            Crear el script para el audio siguiendo las especificaciones de la clase.
            """
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # Generar el texto del script
            script_response = self.llm.invoke(messages)
            return script_response
            
        except Exception as e:
            print(f"Error generando script de audio: {str(e)}")
            return None


class AgenteEstructuraClase(AgentePedagogico):
    """Agente para generar estructura de clases (Inicio, Desarrollo, Cierre)"""
    
    async def generar_estructura_clase(self, clase_data: Dict[str, Any], context: str) -> Optional[str]:
        """
        Genera estructura de clase con actividades definidas en Inicio, Desarrollo y Cierre
        """
        if not self.llm:
            return None
            
        try:
            nivel_educativo = clase_data.get('nivel_educativo', 'No especificado')
            duracion_estimada = clase_data.get('duracion_estimada', 'No especificada')
            modalidad = clase_data.get('modalidad', 'No especificada')
            perfil = clase_data.get('perfil', 'No especificado')
            tema = clase_data.get('tema', 'No especificado')
            
            system_prompt = f"""
            Eres un experto asistente pedagógico especializado en crear contenido educativo de alta calidad.
            Genera una estructura de clase y sus actividades definidas en Inicio, Desarrollo y Cierre, bajo los siguientes parámetros:
            - Nivel educativo: {nivel_educativo}
            - Duración estimada: {duracion_estimada} minutos
            - Modalidad: {modalidad}
            - Perfil cognitivo: {perfil}. Este punto es relevante, pues dependiendo de si son visuales, auditivos, lectores o kinestésicos, las actividades preparadas deben ser apropiadas y no entrar en conflicto.
            
            Sobre el tema: {tema}
            
            Respuesta esperada (EJEMPLO):
            1. Introducción ([duración estimada en minutos])
            1.1. [actividad 1] ([duración estimada en minutos])
            1.2. [actividad 2] ([duración estimada en minutos])
            1.3. [actividad 3] ([duración estimada en minutos])
            2. Desarrollo ([duración estimada en minutos])
            2.1. [actividad 1] ([duración estimada en minutos])
            2.2. [actividad 2] ([duración estimada en minutos])
            2.3. [actividad 3] ([duración estimada en minutos])
            3. Cierre ([duración estimada en minutos])
            3.1. [actividad 1] ([duración estimada en minutos])
            3.2. [actividad 2] ([duración estimada en minutos])
            
            Pueden haber más actividades de las señaladas, no es estricto.
            No debes agregar nada más, solo lo que se tiene como respuesta esperada.
            """
            
            user_prompt = f"""
            Contexto educativo extraído de los materiales:
            {context}
            
            Generar la estructura de clase siguiendo las especificaciones indicadas.
            """
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            return response
            
        except Exception as e:
            print(f"Error generando estructura de clase: {str(e)}")
            return None


class AgentePreguntas(AgentePedagogico):
    """Agente especializado en generar preguntas de opción múltiple"""
    
    async def generar_preguntas(self, clase_data: Dict[str, Any], context: str, num_preguntas: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        Genera preguntas de opción múltiple basadas en la información de la clase y el contexto
        
        Args:
            clase_data: Información de la clase
            context: Contexto educativo extraído de los materiales
            num_preguntas: Número de preguntas a generar (por defecto 5)
            
        Returns:
            List[Dict]: Lista de preguntas con sus alternativas y retroalimentaciones
        """
        if not self.llm:
            return None
            
        try:
            class_info = self._build_class_info(clase_data)
            nivel_educativo = clase_data.get('nivel_educativo', 'No especificado')
            tema = clase_data.get('tema', 'No especificado')
            objetivos = clase_data.get('objetivos_aprendizaje', 'No especificados')
            
            system_prompt = f"""
            Eres un experto asistente pedagógico especializado en crear preguntas de opción múltiple de alta calidad educativa.
            
            {class_info}
            
            Debes generar exactamente {num_preguntas} preguntas de opción múltiple basadas en la información de la clase y el contexto proporcionado.
            
            Cada pregunta debe:
            1. Ser apropiada para el nivel educativo: {nivel_educativo}
            2. Estar relacionada con el tema: {tema}
            3. Evaluar los objetivos de aprendizaje: {objetivos}
            4. Tener exactamente cuatro alternativas (A, B, C, D)
            5. Tener solo una respuesta correcta
            6. Incluir retroalimentación específica para cada alternativa
            7. Ser clara y sin ambigüedades
            8. Evaluar comprensión real, no memorización
            
            IMPORTANTE: Debes responder ÚNICAMENTE con un JSON válido en el siguiente formato:
            [
              {{
                "pregunta": "Pregunta específica sobre el tema",
                "alternativa_a": "Primera opción de respuesta",
                "alternativa_b": "Segunda opción de respuesta", 
                "alternativa_c": "Tercera opción de respuesta",
                "alternativa_d": "Cuarta opción de respuesta",
                "alternativa_correcta": 1,
                "retroalimentacion_a": "Explicación de por qué esta opción es correcta/incorrecta",
                "retroalimentacion_b": "Explicación de por qué esta opción es correcta/incorrecta",
                "retroalimentacion_c": "Explicación de por qué esta opción es correcta/incorrecta", 
                "retroalimentacion_d": "Explicación de por qué esta opción es correcta/incorrecta"
              }}
            ]
            
            Donde alternativa_correcta es un entero del 1 al 4 (1=A, 2=B, 3=C, 4=D).
            """
            
            user_prompt = f"""
            Contexto educativo extraído de los materiales:
            {context}
            
            Tema específico: {tema}
            Nivel educativo: {nivel_educativo}
            
            Genera {num_preguntas} preguntas de opción múltiple que evalúen la comprensión del tema.
            """
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # Intentar parsear la respuesta como JSON
            try:
                # Limpiar la respuesta si contiene texto adicional
                response_text = str(response).strip()
                
                # Buscar el JSON en la respuesta
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                
                if start_idx != -1 and end_idx != 0:
                    json_text = response_text[start_idx:end_idx]
                    json_text = self._clean_json_response(json_text)  # Limpiar formato
                    preguntas = json.loads(json_text)
                    
                    # Validar estructura de cada pregunta
                    preguntas_validadas = []
                    for pregunta in preguntas:
                        if self._validar_pregunta(pregunta):
                            preguntas_validadas.append(pregunta)
                    
                    return preguntas_validadas if preguntas_validadas else None
                else:
                    print("No se encontró JSON válido en la respuesta")
                    return None
                    
            except json.JSONDecodeError as e:
                print(f"Error al parsear JSON: {e}")
                print(f"Respuesta recibida: {response}")
                return None
            
        except Exception as e:
            print(f"Error generando preguntas: {str(e)}")
            return None
    
    def _validar_pregunta(self, pregunta: Dict[str, Any]) -> bool:
        """Valida que una pregunta tenga la estructura correcta"""
        campos_requeridos = [
            'pregunta', 'alternativa_a', 'alternativa_b', 'alternativa_c', 'alternativa_d',
            'alternativa_correcta', 'retroalimentacion_a', 'retroalimentacion_b', 
            'retroalimentacion_c', 'retroalimentacion_d'
        ]
        
        # Verificar que todos los campos estén presentes
        for campo in campos_requeridos:
            if campo not in pregunta:
                return False
        
        # Verificar que alternativa_correcta sea un entero entre 1 y 4
        try:
            alt_correcta = int(pregunta['alternativa_correcta'])
            if alt_correcta < 1 or alt_correcta > 4:
                return False
        except (ValueError, TypeError):
            return False
        
        return True


class AgentePresentacion(AgentePedagogico):
    """Agente especializado en generar presentaciones usando SlidesGPT"""
    
    def __init__(self, llm=None):
        super().__init__(llm)
        self.slidesgpt_api_key = os.environ.get("SLIDESGPT_API_KEY")
    
    def generar_presentacion(self, clase_data: Dict[str, Any], context: str) -> Optional[Dict[str, Any]]:
        """
        Genera una presentación usando la API de SlidesGPT
        
        Args:
            clase_data: Información de la clase
            context: Contexto educativo extraído de los materiales
            
        Returns:
            dict: Respuesta de la API con id, embed y download URLs
        """
        if not self.slidesgpt_api_key:
            raise ValueError("SLIDESGPT_API_KEY no encontrada en las variables de entorno")
        
        try:
            class_info = self._build_class_info(clase_data)
            
            # Construir el prompt para la presentación
            prompt = f"""
            Eres un experto asistente pedagógico especializado en crear presentaciones educativas de alta calidad.
            
            {class_info}
            
            Contexto educativo:
            {context}
            
            Crea una presentación profesional que:
            1. Sea apropiada para el nivel educativo: {clase_data.get('nivel_educativo', 'No especificado')}
            2. Cubra el tema: {clase_data.get('tema', 'No especificado')}
            3. Incluya los objetivos de aprendizaje: {clase_data.get('objetivos_aprendizaje', 'No especificados')}
            4. Considere el perfil de aprendizaje: {clase_data.get('perfil', 'No especificado')}
            5. Incorpore aspectos motivacionales: {clase_data.get('aspectos_motivacionales', 'No especificados')}
            6. Tenga una duración estimada de: {clase_data.get('duracion_estimada', 'No especificada')} minutos
            
            La presentación debe ser clara, visual y educativa, con contenido estructurado y ejemplos prácticos.
            """
            
            # Realizar petición a SlidesGPT
            url = "https://api.slidesgpt.com/v1/presentations/generate"
            
            headers = {
                "Authorization": f"Bearer {self.slidesgpt_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "prompt": prompt
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error al generar presentación: {e}")
            return None
        except Exception as e:
            print(f"Error inesperado: {e}")
            return None
    
    def descargar_presentacion(self, download_url: str, filename: str = "presentation.pptx") -> bool:
        """
        Descarga la presentación desde la URL proporcionada
        
        Args:
            download_url: URL de descarga de la presentación
            filename: Nombre del archivo a guardar
            
        Returns:
            bool: True si la descarga fue exitosa, False en caso contrario
        """
        try:
            response = requests.get(download_url)
            response.raise_for_status()
            
            with open(filename, 'wb') as file:
                file.write(response.content)
            
            print(f"Presentación descargada como: {filename}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error al descargar la presentación: {e}")
            return False


class AgenteBusquedaRecursos(AgentePedagogico):
    """Agente para buscar recursos educativos en la web usando Replicate"""
    
    def generar_busqueda_recursos(self, clase_data: Dict[str, Any], context: str) -> Optional[str]:
        """
        Busca recursos educativos en la web (videos, imágenes, textos)
        """
        if not self.replicate_client:
            print("Error: Replicate no está configurado")
            return None
            
        try:
            nivel_educativo = clase_data.get('nivel_educativo', 'No especificado')
            
            prompt = f"""
            Eres un experto asistente pedagógico especializado en encontrar contenido educativo de alta calidad.
            Investiga y encuentra recursos que existan en la web: videos, imágenes, textos y otros recursos que consideres relevantes. 
            Todas las fuentes deben ser verificadas y de alta calidad.
            Considera que los recursos deben ser adecuados para el siguiente nivel educativo: {nivel_educativo}
            
            Contenido:
            {context}

            Respuesta esperada (EJEMPLO):
            Videos
            1. [Título del video]
            1.1. [Descripción del recurso]
            1.2. [Enlace al recurso]
            1.3. [Propietario del video, la organización o el canal que elaboró el contenido]
            2. [Título del video]...
            ...
            Imágenes
            1. [Título de la imagen]
            1.1. [Descripción del recurso]
            1.2. [Enlace al recurso]
            1.3. [Propietario de la imagen, la organización o el canal que elaboró el contenido]
            2. [Título de la imagen]...
            Textos
            (misma estructura que en los videos o imágenes)
            
            No debes agregar nada más, solo lo que se tiene como respuesta esperada.
            """
            
            input_data = {"prompt": prompt}
            
            # Usar Replicate para generar la búsqueda
            result = ""
            for event in self.replicate_client.stream("openai/gpt-5-nano", input=input_data):
                result += str(event)
            
            return result
            
        except Exception as e:
            print(f"Error en búsqueda de recursos: {str(e)}")
            return None


class AgentePsicopedagogico(AgentePedagogico):
    """Agente psicopedagógico especializado en apoyo personalizado a estudiantes usando gpt-5-nano"""
    def generar_apoyo_estudiante(self, 
                                estudiante_id: int,
                                perfil_cognitivo: str, 
                                perfil_personalidad: str, 
                                nivel_conocimientos: str, 
                                id_clase: int, 
                                contenido_contexto: str,
                                mensaje_usuario: str,
                                problema_especifico: str = None) -> Optional[str]:
        """
        Genera apoyo psicopedagógico personalizado para un estudiante específico
        
        Args:
            estudiante_id: ID único del estudiante
            perfil_cognitivo: visual/lector/kinestesico/auditivo
            perfil_personalidad: Descripción textual basada en BigFive Test
            nivel_conocimientos: sin conocimiento/basico/intermedio
            id_clase: ID de la clase para obtener contexto
            contenido_contexto: Contexto del contenido de la clase
            mensaje_usuario: Mensaje/consulta específica del estudiante
            problema_especifico: Problema específico adicional (opcional)
            
        Returns:
            str: Respuesta personalizada del agente psicopedagógico
        """
        if not self.replicate_client:
            print("Error: Replicate no está configurado")
            return None
            
        try:
            # Construir prompt especializado para el agente psicopedagógico
            prompt = f"""
            Eres un experto agente psicopedagógico especializado en apoyo personalizado a estudiantes. Tu función es proporcionar orientación educativa adaptada a las características individuales del estudiante.

            **PERFIL DEL ESTUDIANTE (ID: {estudiante_id}):**
            
            📊 **Perfil Cognitivo:** {perfil_cognitivo}
            - Visual: Aprende mejor con imágenes, diagramas, mapas conceptuales, colores y organizadores gráficos
            - Auditivo: Aprende mejor escuchando explicaciones, discusiones, música y sonidos
            - Lector: Aprende mejor leyendo textos, tomando notas escritas y organizando información textual
            - Kinestésico: Aprende mejor con movimiento, actividades prácticas, experimentación y manipulación de objetos

            🧠 **Perfil de Personalidad (BigFive):**
            {perfil_personalidad}

            📚 **Nivel de Conocimientos:** {nivel_conocimientos}
            - Sin conocimiento: Requiere introducción básica y conceptos fundamentales
            - Básico: Maneja conceptos elementales, necesita refuerzo y práctica
            - Intermedio: Comprende conceptos principales, puede aplicar conocimientos
            - Experto: Domina el tema, puede analizar y crear contenido avanzado

            **CONTEXTO DE LA CLASE (ID: {id_clase}):**
            {contenido_contexto if contenido_contexto else "No se ha proporcionado contexto específico de la clase."}

            **MENSAJE DEL ESTUDIANTE:**
            {mensaje_usuario}
            
            **PROBLEMA ESPECÍFICO ADICIONAL:**
            {problema_especifico if problema_especifico else "No se ha especificado un problema adicional."}

            **INSTRUCCIONES ESPECÍFICAS:**

            1. **Adaptación Cognitiva:** Ajusta tu respuesta al perfil cognitivo del estudiante:
               - Visual: Incluye descripciones visuales, sugiere diagramas, usa metáforas visuales
               - Auditivo: Usa lenguaje musical, sugiere explicaciones verbales, incluye ritmo en la información
               - Lector: Organiza información en listas, usa estructura textual clara, sugiere lecturas
               - Kinestésico: Sugiere actividades prácticas, experimentos, movimiento físico

            2. **Consideración Psicológica:** Adapta tu tono y enfoque según el perfil de personalidad:
               - Identifica fortalezas y áreas de atención mencionadas en el perfil
               - Usa un lenguaje que resuene con la personalidad del estudiante
               - Proporciona estrategias que aprovechen sus fortalezas naturales
               - Ofrece apoyo específico para sus áreas de desarrollo

            3. **Nivel de Conocimientos:** Ajusta la complejidad y profundidad:
               - Sin conocimiento: Conceptos muy básicos, analogías simples, mucha motivación
               - Básico: Refuerzo de fundamentos, ejemplos prácticos, conexiones claras
               - Intermedio: Aplicaciones más complejas, análisis de casos, síntesis de información

            4. **Apoyo Emocional:** Proporciona motivación y apoyo emocional apropiado para la personalidad del estudiante

            5. **Estrategias de Aprendizaje:** Sugiere técnicas específicas de estudio y comprensión adaptadas al perfil completo

            **ANÁLISIS REQUERIDO:**
            Basándote en el mensaje del estudiante y su perfil completo, proporciona:

            **RESPUESTA ESPERADA:**
            Proporciona una respuesta personalizada, empática y pedagógicamente efectiva que:
            - Se adapte específicamente al perfil cognitivo del estudiante
            - Considere su personalidad y características psicológicas
            - Ajuste el nivel de complejidad a sus conocimientos actuales
            - Incluya estrategias de aprendizaje específicas
            - Ofrezca apoyo motivacional apropiado
            - Proporcione pasos concretos y accionables
            - Use un tono cálido y profesional

            Estructura tu respuesta de manera clara y organizada, usando el formato que mejor se adapte al perfil cognitivo del estudiante.
            """
            
            input_data = {"prompt": prompt}
            
            # Usar Replicate con gpt-5-nano para generar la respuesta personalizada
            result = ""
            for event in self.replicate_client.stream("openai/gpt-5-nano", input=input_data):
                result += str(event)
            
            return result
            
        except Exception as e:
            print(f"Error en agente psicopedagógico: {str(e)}")
            return None

    def generar_plan_estudio_personalizado(self, 
                                         estudiante_id: int,
                                         perfil_cognitivo: str, 
                                         perfil_personalidad: str, 
                                         nivel_conocimientos: str,
                                         id_clase: int,
                                         contenido_contexto: str,
                                         mensaje_usuario: str,
                                         objetivos_especificos: str = None) -> Optional[str]:
        """
        Genera un plan de estudio personalizado para el estudiante
        
        Args:
            estudiante_id: ID único del estudiante
            perfil_cognitivo: Perfil cognitivo del estudiante
            perfil_personalidad: Descripción de personalidad
            nivel_conocimientos: Nivel actual del estudiante
            id_clase: ID de la clase
            contenido_contexto: Contexto del contenido de la clase
            mensaje_usuario: Solicitud específica del estudiante para el plan
            objetivos_especificos: Objetivos específicos adicionales (opcional)
            
        Returns:
            str: Plan de estudio personalizado
        """
        if not self.replicate_client:
            print("Error: Replicate no está configurado")
            return None
            
        try:
            prompt = f"""
            Eres un experto agente psicopedagógico. Crea un plan de estudio personalizado y detallado basado en la solicitud específica del estudiante.

            **PERFIL DEL ESTUDIANTE (ID: {estudiante_id}):**
            - Perfil Cognitivo: {perfil_cognitivo}
            - Personalidad: {perfil_personalidad}
            - Nivel de Conocimientos: {nivel_conocimientos}

            **CONTEXTO DE LA CLASE (ID: {id_clase}):**
            {contenido_contexto}

            **SOLICITUD DEL ESTUDIANTE:**
            {mensaje_usuario}

            **OBJETIVOS ESPECÍFICOS ADICIONALES:**
            {objetivos_especificos if objetivos_especificos else "No se han especificado objetivos adicionales."}

            **INSTRUCCIONES:**
            Crea un plan de estudio estructurado que incluya:

            1. **Objetivos de la sesión** (adaptados al nivel de conocimientos)
            2. **Calentamiento** (5-10% del tiempo) - Actividad motivacional adaptada al perfil cognitivo
            3. **Desarrollo principal** (70-80% del tiempo) - Estrategias específicas para el perfil cognitivo
            4. **Consolidación** (10-15% del tiempo) - Técnicas de refuerzo personalizadas
            5. **Recursos recomendados** - Adaptados al perfil cognitivo y personalidad
            6. **Estrategias de motivación** - Basadas en el perfil de personalidad
            7. **Indicadores de progreso** - Cómo evaluar el avance

            **ADAPTACIONES ESPECÍFICAS:**
            - Para Visual: mapas mentales, diagramas, colores, esquemas
            - Para Auditivo: lectura en voz alta, música, explicaciones verbales, discusiones
            - Para Lector: lecturas estructuradas, resúmenes escritos, notas organizadas
            - Para Kinestésico: actividades físicas, experimentos, manipulación de objetos

            Considera la personalidad para ajustar el tono, nivel de estructura, y tipo de motivación necesaria.

            Proporciona un plan detallado, cronometrado y práctico que el estudiante pueda seguir inmediatamente.
            """
            
            input_data = {"prompt": prompt}
            
            result = ""
            for event in self.replicate_client.stream("openai/gpt-5-nano", input=input_data):
                result += str(event)
            
            return result
            
        except Exception as e:
            print(f"Error generando plan de estudio: {str(e)}")
            return None

    def evaluar_comprension_estudiante(self, 
                                     estudiante_id: int,
                                     perfil_cognitivo: str, 
                                     perfil_personalidad: str, 
                                     nivel_conocimientos: str,
                                     id_clase: int,
                                     contenido_contexto: str,
                                     mensaje_usuario: str,
                                     respuestas_estudiante: Optional[str] = None) -> Optional[str]:
        """
        Evalúa la comprensión del estudiante y proporciona retroalimentación personalizada
        
        Args:
            estudiante_id: ID único del estudiante
            perfil_cognitivo: Perfil cognitivo del estudiante
            perfil_personalidad: Descripción de personalidad
            nivel_conocimientos: Nivel actual del estudiante
            id_clase: ID de la clase
            contenido_contexto: Contexto del contenido de la clase
            respuestas_estudiante: Respuestas del estudiante para evaluar
            
        Returns:
            str: Evaluación y retroalimentación personalizada
        """
        if not self.replicate_client:
            print("Error: Replicate no está configurado")
            return None
            
        try:
            respuestas_texto = respuestas_estudiante if respuestas_estudiante else "No se proporcionaron respuestas específicas para evaluar"
            
            prompt = f"""
            Eres un experto agente psicopedagógico especializado en evaluación formativa personalizada.

            **PERFIL DEL ESTUDIANTE (ID: {estudiante_id}):**
            - Perfil Cognitivo: {perfil_cognitivo}
            - Personalidad: {perfil_personalidad}
            - Nivel de Conocimientos: {nivel_conocimientos}

            **CONTEXTO DE LA CLASE (ID: {id_clase}):**
            {contenido_contexto}

            **MENSAJE/CONSULTA DEL ESTUDIANTE:**
            {mensaje_usuario}

            **RESPUESTAS DEL ESTUDIANTE:**
            {respuestas_texto}

            **INSTRUCCIONES PARA LA EVALUACIÓN:**

            Proporciona una evaluación comprensiva que incluya:

            1. **Análisis de Comprensión:**
               - Nivel de comprensión demostrado
               - Fortalezas identificadas en las respuestas
               - Áreas que necesitan refuerzo

            2. **Retroalimentación Personalizada:**
               - Adaptada al perfil cognitivo del estudiante
               - Considerando su personalidad y forma de recibir feedback
               - Ajustada a su nivel de conocimientos actual

            3. **Estrategias de Mejora:**
               - Técnicas específicas para el perfil cognitivo
               - Recursos recomendados personalizados
               - Actividades de refuerzo adaptadas

            4. **Motivación y Apoyo:**
               - Reconocimiento de esfuerzos y logros
               - Motivación apropiada para la personalidad del estudiante
               - Enfoque en el crecimiento y progreso

            5. **Próximos Pasos:**
               - Recomendaciones específicas para continuar el aprendizaje
               - Objetivos alcanzables a corto plazo
               - Recursos adicionales personalizados

            **TONO Y ENFOQUE:**
            - Mantén un tono constructivo y alentador
            - Adapta el lenguaje al nivel de conocimientos del estudiante
            - Considera la personalidad para el tipo de feedback más efectivo
            - Enfócate en el crecimiento y el potencial de mejora

            Proporciona una evaluación detallada, constructiva y personalizada que ayude al estudiante a crecer y mejorar.
            """
            
            input_data = {"prompt": prompt}
            
            result = ""
            for event in self.replicate_client.stream("openai/gpt-5-nano", input=input_data):
                result += str(event)
            
            return result
            
        except Exception as e:
            print(f"Error evaluando comprensión: {str(e)}")
            return None


class AgenteIndiceClase(AgentePedagogico):
    """Agente especializado en generar índices para el contenido de clase"""
    
    async def generar_indice_clase(self, contenido: str, nivel_clase: str) -> Optional[List[Dict[str, Any]]]:
        """
        Genera un índice estructurado para el contenido de la clase
        
        Args:
            contenido: Contenido completo de la clase
            nivel_clase: Nivel educativo de la clase
            
        Returns:
            List[Dict]: Lista de índices con orden, título y tiempo estimado
        """
        print("LLLLLLLLLLLLLLLLEGO AQUIIIIIIIIIIIIIIIII")
        if not self.llm:
            print("LLLLLLLLLLLLLLLLEGO AQUIIIIIIIIIIIIIIIII222222")
            return None
            
        try:
            system_prompt = f"""
            Eres un experto asistente pedagógico especializado en crear índices estructurados para contenido educativo.
            
            Tu tarea es crear un índice organizado para el contenido de una clase de nivel: {nivel_clase}
            
            **INSTRUCCIONES ESPECÍFICAS:**
            
            1. **Análisis del contenido:** Analiza el contenido completo y divide en secciones lógicas
            2. **Estructura del índice:** Cada elemento debe tener orden, título descriptivo y tiempo estimado
            3. **Cálculo de tiempo:** Usa como base 120 palabras por minuto para estimar tiempos
            4. **Organización lógica:** Ordena las secciones de forma pedagógica y progresiva
            
            **RESTRICCIONES OBLIGATORIAS:**
            - El orden debe partir de 1 y ser secuencial
            - El título para el índice debe ser menor a 20 palabras
            - El tiempo estimado no debe superar los 30 minutos por sección
            - El tiempo se calcula contando como base las 120 palabras por minuto
            
            **FORMATO DE RESPUESTA REQUERIDO:**
            Debes responder ÚNICAMENTE con un JSON válido en el siguiente formato:
            [
                {{
                    "orden": 1,
                    "indice": "Título descriptivo del primer tema",
                    "tiempo_estimado": 15
                }},
                {{
                    "orden": 2,
                    "indice": "Título descriptivo del segundo tema", 
                    "tiempo_estimado": 20
                }}
            ]
            
            **CONSIDERACIONES PEDAGÓGICAS:**
            - Para {nivel_clase}: Adapta la complejidad y profundidad según el nivel
            - Organiza el contenido de lo más básico a lo más complejo
            - Asegúrate de que cada sección tenga un propósito educativo claro
            - Los títulos deben ser descriptivos y motivadores para estudiantes de {nivel_clase}
            
            IMPORTANTE: Responde ÚNICAMENTE con el array JSON, sin explicaciones adicionales.
            """
            
            user_prompt = f"""
            Contenido de la clase a indexar:
            {contenido}
            
            Nivel educativo: {nivel_clase}
            
            Genera el índice estructurado siguiendo las especificaciones indicadas.
            """
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            print("RESPUESTA DEL LLM:")
            print(response)
            
            # Intentar parsear la respuesta como JSON
            try:
                # Obtener el contenido de la respuesta correctamente
                if hasattr(response, 'content'):
                    response_text = response.content.strip()
                else:
                    response_text = str(response).strip()
                
                print(f"Texto de respuesta procesado: {response_text}")
                
                # Intentar parsear directamente como JSON
                try:
                    response_text = self._clean_json_response(response_text)  # Limpiar formato
                    indice = json.loads(response_text)
                except json.JSONDecodeError:
                    # Si falla, buscar el JSON en la respuesta
                    start_idx = response_text.find('[')
                    end_idx = response_text.rfind(']') + 1
                    
                    if start_idx != -1 and end_idx != 0:
                        json_text = response_text[start_idx:end_idx]
                        json_text = self._clean_json_response(json_text)  # Limpiar formato
                        print(f"JSON extraído: {json_text}")
                        indice = json.loads(json_text)
                    else:
                        print("No se encontró JSON válido en la respuesta")
                        # Crear un índice básico como fallback
                        indice = [
                            {
                                "orden": 1,
                                "indice": "Introducción al tema",
                                "tiempo_estimado": 15
                            },
                            {
                                "orden": 2,
                                "indice": "Desarrollo del contenido",
                                "tiempo_estimado": 20
                            },
                            {
                                "orden": 3,
                                "indice": "Conclusiones y resumen",
                                "tiempo_estimado": 10
                            }
                        ]
                
                # Validar estructura de cada elemento del índice
                indice_validado = []
                for item in indice:
                    if isinstance(item, dict) and self._validar_item_indice(item):
                        indice_validado.append(item)
                    else:
                        print(f"Item inválido encontrado: {item}")
                
                print(f"Índice validado: {indice_validado}")
                return indice_validado if indice_validado else None
                    
            except json.JSONDecodeError as e:
                print(f"Error al parsear JSON del índice: {e}")
                print(f"Respuesta recibida: {response_text}")
                # Crear un índice básico como fallback
                return [
                    {
                        "orden": 1,
                        "indice": "Contenido de la clase",
                        "tiempo_estimado": 25
                    }
                ]
            
        except Exception as e:
            print(f"Error generando índice de clase: {str(e)}")
            # Crear un índice básico como fallback en caso de error
            return [
                {
                    "orden": 1,
                    "indice": "Introducción",
                    "tiempo_estimado": 10
                },
                {
                    "orden": 2,
                    "indice": "Desarrollo del tema",
                    "tiempo_estimado": 20
                },
                {
                    "orden": 3,
                    "indice": "Conclusión",
                    "tiempo_estimado": 10
                }
            ]
    
    def _validar_item_indice(self, item: Dict[str, Any]) -> bool:
        """Valida que un item del índice tenga la estructura correcta"""
        if not isinstance(item, dict):
            print(f"Item no es un diccionario: {type(item)}")
            return False
            
        campos_requeridos = ['orden', 'indice', 'tiempo_estimado']
        
        # Verificar que todos los campos estén presentes
        for campo in campos_requeridos:
            if campo not in item:
                print(f"Campo '{campo}' faltante en item: {item}")
                return False
        
        # Verificar que orden sea un entero positivo
        try:
            orden = int(item['orden'])
            if orden < 1:
                print(f"Orden debe ser positivo: {orden}")
                return False
        except (ValueError, TypeError) as e:
            print(f"Error al convertir orden a entero: {item['orden']}, error: {e}")
            return False
        
        # Verificar que tiempo_estimado sea un entero y no supere 30 minutos
        try:
            tiempo = int(item['tiempo_estimado'])
            if tiempo < 1 or tiempo > 30:
                print(f"Tiempo estimado fuera de rango (1-30): {tiempo}")
                return False
        except (ValueError, TypeError) as e:
            print(f"Error al convertir tiempo_estimado a entero: {item['tiempo_estimado']}, error: {e}")
            return False
        
        # Verificar que el título no esté vacío y no supere 20 palabras
        titulo = str(item['indice']).strip()
        if not titulo:
            print("Título del índice está vacío")
            return False
            
        if len(titulo.split()) > 20:
            print(f"Título supera 20 palabras: {len(titulo.split())} palabras")
            return False
        
        return True


class AgenteContenidoIndice(AgentePedagogico):
    """Agente especializado en generar contenido específico para cada índice de clase"""
    
    async def generar_contenido_indice(self, contenido_indice: str, nivel_clase: str, perfil_cognitivo: str, tiempo_estimado: int) -> Optional[Dict[str, Any]]:
        """
        Genera contenido específico para un índice de clase
        
        Args:
            contenido_indice: Descripción o título del índice para el cual generar contenido
            nivel_clase: Nivel educativo de la clase
            perfil_cognitivo: Perfil cognitivo del estudiante (Visual, Auditivo, Lector, Kinestésico)
            tiempo_estimado: Tiempo estimado en minutos para este contenido
            
        Returns:
            Dict: Contenido generado con estructura:
                {
                    'contenido': str,  # Contenido en formato Markdown
                    'perfil_cognitivo': str  # Perfil cognitivo utilizado
                }
        """
        if not self.llm:
            return None
            
        try:
            # Calcular palabras aproximadas basado en el tiempo (120 palabras por minuto)
            palabras_aproximadas = tiempo_estimado * 120
            
            # Ajustar contenido según perfil cognitivo
            instrucciones_perfil = self._get_instrucciones_perfil(perfil_cognitivo, palabras_aproximadas)
            
            system_prompt = f"""
            Eres un experto asistente pedagógico especializado en crear contenido educativo personalizado.
            
            Tu tarea es generar contenido específico para un índice de clase adaptado al perfil cognitivo del estudiante.
            
            **PARÁMETROS DE LA TAREA:**
            - Titulo del índice: {contenido_indice}
            - Nivel educativo: {nivel_clase}
            - Perfil cognitivo: {perfil_cognitivo}
            - Tiempo estimado: {tiempo_estimado} minutos
            - Palabras aproximadas: {palabras_aproximadas} palabras (120 palabras/minuto)
            
            **INSTRUCCIONES ESPECÍFICAS PARA {perfil_cognitivo.upper()}:**
            {instrucciones_perfil}
            
            **RESTRICCIONES OBLIGATORIAS:**
            - El contenido debe cumplir el tiempo estimado de {tiempo_estimado} minutos
            - Considera como base las 120 palabras por minuto para el cálculo
            - El contenido debe estar en formato Markdown
            - Debe ser apropiado para el nivel: {nivel_clase}
            
            **FORMATO DE RESPUESTA REQUERIDO:**
            Debes responder ÚNICAMENTE con el contenido educativo en formato MARKDOWN.
            NO incluyas JSON, NO incluyas explicaciones adicionales.
            Responde directamente con el contenido en formato Markdown listo para usar.
            """
            
            user_prompt = f"""
            Genera contenido educativo para el siguiente índice:
            "{contenido_indice}"
            
            Especificaciones:
            - Nivel: {nivel_clase}
            - Perfil cognitivo: {perfil_cognitivo}
            - Duración: {tiempo_estimado} minutos
            - Aproximadamente {palabras_aproximadas} palabras
            
            El contenido debe ser educativo, atractivo y apropiado para el perfil cognitivo especificado.
            """
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # Procesar respuesta directa en Markdown
            try:
                # Obtener el contenido directamente como string
                contenido_texto = str(response).strip()
                
                # Validar que el contenido no esté vacío
                if not contenido_texto:
                    print("ERROR: El contenido generado está vacío")
                    return None
                
                # Crear el diccionario de respuesta con el perfil cognitivo de los parámetros
                contenido_generado = {
                    'contenido': contenido_texto,
                    'perfil_cognitivo': perfil_cognitivo
                }
                
                print("=" * 50)
                print("CONTENIDO GENERADO EXITOSAMENTE:")
                print(f"Perfil cognitivo: {perfil_cognitivo}")
                print(f"Longitud del contenido: {len(contenido_texto)} caracteres")
                print(f"Primeras 100 caracteres: {contenido_texto[:100]}...")
                print("=" * 50)
                
                # Validar estructura del contenido
                if self._validar_contenido_indice(contenido_generado):
                    return contenido_generado
                else:
                    print("ERROR: Estructura del contenido inválida")
                    return None
                    
            except Exception as e:
                print(f"Error procesando respuesta del contenido: {e}")
                print(f"Respuesta recibida: {response}")
                return None
            
        except Exception as e:
            print(f"Error generando contenido de índice: {str(e)}")
            return None
    
    def _get_instrucciones_perfil(self, perfil_cognitivo: str, palabras_aproximadas: int) -> str:
        """Genera instrucciones específicas según el perfil cognitivo"""
        perfil = perfil_cognitivo.lower()
        
        if perfil == 'visual':
            return f"""
            Para perfil VISUAL:
            - Genera MENOS texto (aproximadamente {int(palabras_aproximadas * 0.7)} palabras)
            - Incluye descripciones de imágenes que serán generadas posteriormente
            - Las descripciones de imágenes deben ir entre llaves dobles: {{{{descripción de la imagen}}}}
            - Usa formato Markdown con encabezados, listas y énfasis visual
            - Incluye diagramas conceptuales descritos como imágenes: {{{{Diagrama: mostrando...}}}}
            - Organiza la información de manera visual y estructurada
            - Ejemplo: {{{{Imagen: de un gráfico circular mostrando las proporciones de...}}}}
            - Estos descripciones siempre iniciaran así: Imagen|Diagrama|Tabla|Matriz: ... es importante que se siga esta estructura.
            """
        elif perfil == 'auditivo':
            return f"""
            Para perfil AUDITIVO:
            - Genera contenido conversacional y narrativo ({palabras_aproximadas} palabras aprox.)
            - Incluye elementos que sugieran sonidos, ritmos o explicaciones verbales
            - Usa un tono como si fuera una explicación hablada
            - Incluye repeticiones y refuerzos auditivos
            - Sugiere actividades de discusión o explicación oral
            """
        elif perfil == 'lector':
            return f"""
            Para perfil LECTOR:
            - Genera contenido textual rico y detallado ({palabras_aproximadas} palabras aprox.)
            - Organiza la información en párrafos bien estructurados
            - Incluye definiciones claras y explicaciones textuales
            - Usa listas, numeraciones y organización textual clara
            - Proporciona lecturas complementarias o referencias textuales
            """
        elif perfil == 'kinestesico':
            return f"""
            Para perfil KINESTÉSICO:
            - Genera contenido que incluya actividades prácticas ({palabras_aproximadas} palabras aprox.)
            - Sugiere experimentos, ejercicios físicos o manipulación de objetos
            - Incluye pasos para actividades hands-on
            - Describe movimientos y acciones concretas
            - Proporciona ejemplos prácticos y aplicables
            """
        else:
            return f"Genera contenido equilibrado de aproximadamente {palabras_aproximadas} palabras."
    
    def _validar_contenido_indice(self, contenido: Dict[str, Any]) -> bool:
        """Valida que el contenido del índice tenga la estructura correcta"""
        print("INICIANDO VALIDACIÓN DEL CONTENIDO: ==========================")
        
        # Verificar que sea un diccionario
        if not isinstance(contenido, dict):
            print(f"ERROR: El contenido no es un diccionario, es: {type(contenido)}")
            return False
        
        campos_requeridos = ['contenido', 'perfil_cognitivo']
        print(f"Campos disponibles: {list(contenido.keys())}")
        
        # Verificar que todos los campos estén presentes
        for campo in campos_requeridos:
            if campo not in contenido:
                print(f"ERROR: Campo '{campo}' no encontrado en el contenido")
                return False

        # Verificar que el contenido no esté vacío
        contenido_texto = contenido.get('contenido', '')
        if not contenido_texto or not str(contenido_texto).strip():
            print(f"ERROR: El campo 'contenido' está vacío o es None: '{contenido_texto}'")
            return False
        
        # Verificar que perfil_cognitivo sea válido
        perfil = contenido.get('perfil_cognitivo', '')
        perfiles_validos = ['Visual', 'Auditivo', 'Lector', 'Kinestesico']
        print(f"Validando perfil cognitivo: '{perfil}'")
        print(f"Perfiles válidos: {perfiles_validos}")
        
        if perfil not in perfiles_validos:
            print(f"ERROR: Perfil cognitivo '{perfil}' no es válido")
            return False
        
        print("✅ VALIDACIÓN EXITOSA: Contenido tiene estructura correcta")
        return True


class ManagerAgentes:
    """Manager principal para coordinar todos los agentes"""
    
    def __init__(self, llm=None):
        self.llm = llm
        self.agente_contenido = AgenteContenidoGeneral(llm)
        self.agente_audio = AgenteAudio(llm)
        self.agente_estructura = AgenteEstructuraClase(llm)
        self.agente_preguntas = AgentePreguntas(llm)
        self.agente_busqueda = AgenteBusquedaRecursos(llm)
        self.agente_presentacion = AgentePresentacion(llm)
        self.agente_psicopedagogico = AgentePsicopedagogico(llm)
        self.agente_indice_clase = AgenteIndiceClase(llm)
        self.agente_contenido_indice = AgenteContenidoIndice(llm)
    
    async def generar_contenido_por_tipo(self, clase_data: Dict[str, Any], context: str, tipo_recurso: str) -> Optional[str]:
        """
        Genera contenido según el tipo de recurso solicitado
        """
        try:
            if tipo_recurso.lower() == 'audio':
                script_text = await self.agente_audio.generar_script_audio(clase_data, context)
                return script_text
            
            elif tipo_recurso.lower() in ['estructura de clase', 'planificacion', 'sesion']:
                estructura = await self.agente_estructura.generar_estructura_clase(clase_data, context)
                return estructura
            
            elif tipo_recurso.lower() in ['preguntas', 'quiz', 'evaluacion', 'opcion multiple']:
                preguntas = await self.agente_preguntas.generar_preguntas(clase_data, context)
                return preguntas
            
            elif tipo_recurso.lower() in ['recursos web', 'busqueda recursos', 'recursos educativos']:
                recursos = self.agente_busqueda.generar_busqueda_recursos(clase_data, context)
                return recursos
            
            elif tipo_recurso.lower() in ['presentacion', 'slides', 'ppt', 'powerpoint']:
                presentacion = self.agente_presentacion.generar_presentacion(clase_data, context)
                return presentacion
            
            else:
                # Para cualquier otro tipo de contenido, usar el agente general
                contenido = await self.agente_contenido.generar_contenido(clase_data, context, tipo_recurso)
                return contenido
                
        except Exception as e:
            print(f"Error en manager de agentes: {str(e)}")
            return None
    
    async def generar_estructura_clase_completa(self, clase_data: Dict[str, Any], context: str) -> Optional[str]:
        """Método específico para generar estructura de clase"""
        return await self.agente_estructura.generar_estructura_clase(clase_data, context)
    
    def buscar_recursos_educativos(self, clase_data: Dict[str, Any], context: str) -> Optional[str]:
        """Método específico para buscar recursos educativos"""
        return self.agente_busqueda.generar_busqueda_recursos(clase_data, context)
    
    async def generar_script_audio(self, clase_data: Dict[str, Any], context: str) -> Optional[str]:
        """Método específico para generar scripts de audio"""
        return await self.agente_audio.generar_script_audio(clase_data, context)
    
    def generar_presentacion(self, clase_data: Dict[str, Any], context: str) -> Optional[Dict[str, Any]]:
        """Método específico para generar presentaciones"""
        return self.agente_presentacion.generar_presentacion(clase_data, context)
    
    def apoyo_psicopedagogico(self, estudiante_id, perfil_cognitivo, perfil_personalidad, nivel_conocimientos, id_clase, contenido_contexto, mensaje_usuario, problema_especifico=None):
        """Genera apoyo psicopedagógico personalizado para un estudiante"""
        return self.agente_psicopedagogico.generar_apoyo_estudiante(
            estudiante_id, perfil_cognitivo, perfil_personalidad, 
            nivel_conocimientos, id_clase, contenido_contexto, mensaje_usuario, problema_especifico
        )
    
    def plan_estudio_personalizado(self, estudiante_id, perfil_cognitivo, perfil_personalidad, nivel_conocimientos, id_clase, contenido_contexto, mensaje_usuario, objetivos_especificos=None):
        """Genera un plan de estudio personalizado para un estudiante"""
        return self.agente_psicopedagogico.generar_plan_estudio_personalizado(
            estudiante_id, perfil_cognitivo, perfil_personalidad,
            nivel_conocimientos, id_clase, contenido_contexto, mensaje_usuario, objetivos_especificos
        )
    
    def evaluacion_comprension(self, estudiante_id, perfil_cognitivo, perfil_personalidad, nivel_conocimientos, id_clase, contenido_contexto, mensaje_usuario, respuestas_estudiante=None):
        """Evalúa la comprensión del estudiante y proporciona retroalimentación personalizada"""
        return self.agente_psicopedagogico.evaluar_comprension_estudiante(
            estudiante_id, perfil_cognitivo, perfil_personalidad,
            nivel_conocimientos, id_clase, contenido_contexto, mensaje_usuario, respuestas_estudiante
        )
    
    def descargar_presentacion(self, download_url: str, filename: str = "presentation.pptx") -> bool:
        """Método específico para descargar presentaciones"""
        return self.agente_presentacion.descargar_presentacion(download_url, filename)
    
    async def generar_preguntas(self, clase_data: Dict[str, Any], context: str, num_preguntas: int = 5) -> Optional[List[Dict[str, Any]]]:
        """Método específico para generar preguntas de opción múltiple"""
        return await self.agente_preguntas.generar_preguntas(clase_data, context, num_preguntas)
    
    async def generar_indice_clase(self, contenido: str, nivel_clase: str) -> Optional[List[Dict[str, Any]]]:
        """Método específico para generar índice de clase"""
        return await self.agente_indice_clase.generar_indice_clase(contenido, nivel_clase)
    
    async def generar_contenido_indice(self, contenido_indice: str, nivel_clase: str, perfil_cognitivo: str, tiempo_estimado: int) -> Optional[Dict[str, Any]]:
        """Método específico para generar contenido de un índice específico"""
        # Generar contenido con el agente
        contenido = await self.agente_contenido_indice.generar_contenido_indice(contenido_indice, nivel_clase, perfil_cognitivo, tiempo_estimado)

        if not contenido or not isinstance(contenido, dict):
            return contenido

        contenido_texto = contenido.get('contenido')
        if not contenido_texto or not isinstance(contenido_texto, str):
            return contenido

        # Buscar patrones de imágenes:
        # - braced: {{Imagen: ...}}, {{Diagrama: ...}}, {{Tabla: ...}} o {{Matriz: ...}}
        # - line-prefixed: una línea que empieza con "Imagen: ...", "Diagrama: ...", "Tabla: ..." o "Matriz: ..."
        pattern_braced = re.compile(r"\{\{\s*(Imagen|Diagrama|Tabla|Matriz)\s*:\s*(.*?)\s*\}\}", re.IGNORECASE | re.DOTALL)
        pattern_line = re.compile(r"^(?:\s*)(Imagen|Diagrama|Tabla|Matriz)\s*:\s*(.+?)(?=(\n\s*\n)|$)", re.IGNORECASE | re.MULTILINE | re.DOTALL)

        imagenes = []

        # Helper to generate image, build full URL, and replace the matched text
        def _handle_match(tipo: str, descripcion: str, original_text: str):
            path = None
            try:
                if image_processor is not None:
                    path = image_processor.generate_image_from_description(descripcion, None)
            except Exception as e:
                print(f"Error generando imagen para descripcion: {e}")

            archivo = {
                'tipo': tipo,
                'descripcion': descripcion,
                'path': path,
                'filename': os.path.basename(path) if path else None
            }

            # Determine full URL using S3_BUCKET_BASE_URL if path is a relative S3 key
            s3_base = os.environ.get('S3_BUCKET_BASE_URL', '').strip()
            full_url = path
            if path and path.startswith('/') and s3_base:
                full_url = s3_base.rstrip('/') + path

            archivo['path'] = full_url
            imagenes.append(archivo)

            # Reemplazar la etiqueta en el contenido Markdown por una imagen si se obtuvo full_url
            if full_url:
                md_img = f"![{tipo}]({full_url})"
                return contenido_texto.replace(original_text, md_img)
            return contenido_texto

        # First process braced patterns
        for m in list(pattern_braced.finditer(contenido_texto)):
            tipo = m.group(1).strip()
            descripcion = m.group(2).strip()
            contenido_texto = _handle_match(tipo, descripcion, m.group(0))

        # Then process any remaining line-prefixed patterns (covers cases where LLM didn't use braces)
        for m in list(pattern_line.finditer(contenido_texto)):
            tipo = m.group(1).strip()
            descripcion = m.group(2).strip()
            # original matched block
            original = m.group(0)
            # Avoid re-processing if we've already replaced it
            if original.strip().startswith('!['):
                continue
            contenido_texto = _handle_match(tipo, descripcion, original)

        # Actualizar el contenido con las sustituciones realizadas
        contenido['contenido'] = contenido_texto
        if imagenes:
            contenido['imagenes'] = imagenes

        return contenido

# Función de conveniencia para usar en la API
def crear_manager_agentes(llm=None):
    """
    Crea y retorna una instancia del manager de agentes
    """
    google_api_key = os.environ['GOOGLE_API_KEY']
    llm = GoogleGenerativeAI(model="gemini-2.5-flash-lite", google_api_key=google_api_key)
    return ManagerAgentes(llm)