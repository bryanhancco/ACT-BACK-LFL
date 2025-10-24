"""
Audio Processor Service - TTS y STT
Maneja Text-to-Speech (TTS) y Speech-to-Text (STT) usando Deepgram API
"""

import os
import time
import requests
import tempfile
import hashlib
from typing import Optional, Dict, Any, Union
from pathlib import Path
import asyncio
import aiofiles
from database import supabase

# optional file service (S3) to register generated files
try:
    from ..files.service import file_service
except Exception:
    file_service = None

class AudioProcessor:
    """
    Procesador de audio que maneja TTS (Text-to-Speech) y STT (Speech-to-Text)
    utilizando la API de Deepgram
    """
    
    def __init__(self):
        self.deepgram_api_key = os.environ.get('DEEPGRAM_API_KEY')
        self.tts_url = "https://api.deepgram.com/v1/speak"
        self.stt_url = "https://api.deepgram.com/v1/listen"
        
        if not self.deepgram_api_key:
            print("[WARNING] DEEPGRAM_API_KEY no encontrada en variables de entorno")
        
        # Configuración por defecto para TTS
        self.default_tts_config = {
            "model": "aura-2-celeste-es",  # Modelo en español con voz femenina
            "encoding": "mp3"
        }
        
        # Configuración por defecto para STT
        self.default_stt_config = {
            "model": "nova-2",
            "language": "es",
            "smart_format": True,
            "punctuate": True,
            "diarize": False
        }
        
        # Directorio base para archivos
        self.base_directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "files")
        self._ensure_base_directory()
    
    def _ensure_base_directory(self):
        """Asegura que el directorio base existe"""
        os.makedirs(self.base_directory, exist_ok=True)
    
    def _get_class_folder_path(self, id_clase: int) -> str:
        """Obtiene la ruta de la carpeta de una clase"""
        return os.path.join(self.base_directory, str(id_clase))
    
    def _ensure_class_folder_exists(self, id_clase: int) -> str:
        """Asegura que la carpeta de la clase existe"""
        folder_path = self._get_class_folder_path(id_clase)
        os.makedirs(folder_path, exist_ok=True)
        return folder_path
    
    def _get_timestamp(self) -> int:
        """Obtiene timestamp actual"""
        return int(time.time())
    
    def _generate_audio_filename(self, id_clase: int, prefix: str = "audio") -> str:
        """Genera un nombre único para archivo de audio"""
        timestamp = self._get_timestamp()
        return f"{id_clase}_{timestamp}_{prefix}.mp3"
    
    def _generate_text_filename(self, id_clase: int, prefix: str = "transcript") -> str:
        """Genera un nombre único para archivo de transcripción"""
        timestamp = self._get_timestamp()
        return f"{id_clase}_{timestamp}_{prefix}.txt"
    
    async def _save_file_to_database(self, id_clase: int, filename: str, tipo: str = "Generado", filepath: str | None = None) -> bool:
        """Guarda información del archivo en la base de datos"""
        try:
            archivo_data = {
                "id_clase": id_clase,
                "filename": filename,
                "tipo": tipo
            }
            if filepath:
                archivo_data["filepath"] = filepath
            
            result = supabase.table("archivos").insert(archivo_data).execute()
            return bool(result.data)
        except Exception as e:
            print(f"Error guardando archivo en BD: {str(e)}")
            return False
    
    # ===============================
    # TEXT-TO-SPEECH (TTS) FUNCTIONS
    # ===============================
    
    async def text_to_speech(
        self, 
        text: str, 
        id_clase: int,
        voice_model: str = "aura-2-celeste-es",
        save_to_db: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Convierte texto a audio usando Deepgram TTS
        
        Args:
            text: Texto a convertir
            id_clase: ID de la clase
            voice_model: Modelo de voz a usar
            save_to_db: Si guardar en base de datos
            
        Returns:
            Dict con información del archivo generado o None si hay error
        """
        try:
            if not self.deepgram_api_key:
                raise Exception("API key de Deepgram no configurada")
            
            # Validar texto
            if not text or len(text.strip()) == 0:
                raise Exception("Texto vacío proporcionado")
                        
            # Generar nombre único para el archivo
            audio_filename = self._generate_audio_filename(id_clase, "tts")

            # Preparar datos para Deepgram TTS
            data = {"text": text}
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Token {self.deepgram_api_key}"
            }
            
            # Configurar URL con parámetros
            params = {
                "model": voice_model,
                "encoding": "mp3"
            }
            
            url_with_params = f"{self.tts_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
            
            # Hacer solicitud a Deepgram
            response = requests.post(url_with_params, json=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # We handle everything in-memory and upload directly to S3 (no local copies)
                audio_bytes = response.content
                file_size = len(audio_bytes)

                # Ensure S3 is available — we require file_service for no-local mode
                if file_service is None:
                    raise RuntimeError("S3 file_service not available. Local copies are disabled; configure S3 to enable generated file storage.")

                # Upload to S3 under generated/audio/{id_clase}/
                generated_key = f"generated/audio/{id_clase}/{audio_filename}"
                try:
                    ok = file_service.upload_bytes(audio_bytes, generated_key, content_type="audio/mpeg")
                    if not ok:
                        raise RuntimeError("S3 upload failed")
                    s3_path = f"/{generated_key}"
                except Exception as e:
                    print(f"Warning: failed to upload generated audio to S3: {e}")
                    raise

                # Save DB record if requested (include s3 path)
                if save_to_db:
                    await self._save_file_to_database(id_clase, audio_filename, "Generado", filepath=generated_key)

                print(f"[SUCCESS] Archivo de audio TTS generado and uploaded: {audio_filename} ({file_size} bytes) -> {s3_path}")

                return {
                    "filename": audio_filename,
                    "s3_path": s3_path,
                    "size": file_size,
                    "duration_estimate": len(text.split()) * 0.5,
                    "text_length": len(text),
                    "voice_model": voice_model,
                    "success": True
                }
            else:
                error_msg = f"Error TTS Deepgram: {response.status_code} - {response.text}"
                print(f"[ERROR] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            error_msg = f"Error generando TTS: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def batch_text_to_speech(
        self, 
        texts: list[str], 
        id_clase: int,
        voice_model: str = "aura-2-celeste-es"
    ) -> Dict[str, Any]:
        """
        Convierte múltiples textos a audio de forma asíncrona
        
        Args:
            texts: Lista de textos a convertir
            id_clase: ID de la clase
            voice_model: Modelo de voz a usar
            
        Returns:
            Dict con resultados de todas las conversiones
        """
        results = []
        successful = 0
        failed = 0
        
        try:
            # Crear tareas asíncronas para todos los textos
            tasks = []
            for i, text in enumerate(texts):
                task = self.text_to_speech(
                    text=text, 
                    id_clase=id_clase, 
                    voice_model=voice_model, 
                    save_to_db=True
                )
                tasks.append(task)
            
            # Ejecutar todas las tareas
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Procesar resultados
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed += 1
                    results[i] = {"success": False, "error": str(result), "text_index": i}
                elif result and result.get("success"):
                    successful += 1
                else:
                    failed += 1
            
            return {
                "total_texts": len(texts),
                "successful": successful,
                "failed": failed,
                "results": results,
                "success": successful > 0
            }
            
        except Exception as e:
            return {
                "total_texts": len(texts),
                "successful": 0,
                "failed": len(texts),
                "error": str(e),
                "success": False
            }
    
    # ===============================
    # SPEECH-TO-TEXT (STT) FUNCTIONS
    # ===============================
    
    async def speech_to_text(
        self, 
        audio_file_path: str, 
        id_clase: int,
        language: str = "es",
        save_transcript: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Convierte audio a texto usando Deepgram STT
        
        Args:
            audio_file_path: Ruta al archivo de audio
            id_clase: ID de la clase
            language: Idioma del audio
            save_transcript: Si guardar transcripción en archivo
            
        Returns:
            Dict con transcripción y metadata o None si hay error
        """
        try:
            if not self.deepgram_api_key:
                raise Exception("API key de Deepgram no configurada")
            
            # Verificar que el archivo existe
            if not os.path.exists(audio_file_path):
                raise Exception(f"Archivo de audio no encontrado: {audio_file_path}")
            
            # Configurar headers
            headers = {
                "Authorization": f"Token {self.deepgram_api_key}"
            }
            
            # Configurar parámetros para STT
            params = {
                "model": "nova-2",
                "language": language,
                "smart_format": "true",
                "punctuate": "true",
                "diarize": "false",
                "utterances": "true",
                "paragraphs": "true"
            }
            
            url_with_params = f"{self.stt_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
            
            # Leer archivo de audio
            with open(audio_file_path, "rb") as audio_file:
                audio_data = audio_file.read()
            
            # Hacer solicitud a Deepgram
            response = requests.post(
                url_with_params, 
                data=audio_data, 
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Extraer transcripción principal
                transcript = ""
                confidence = 0.0
                words_count = 0
                
                if "results" in result and "channels" in result["results"]:
                    channel = result["results"]["channels"][0]
                    if "alternatives" in channel and len(channel["alternatives"]) > 0:
                        alternative = channel["alternatives"][0]
                        transcript = alternative.get("transcript", "")
                        confidence = alternative.get("confidence", 0.0)
                        
                        # Contar palabras
                        if "words" in alternative:
                            words_count = len(alternative["words"])
                
                print(f"[SUCCESS] STT completado: {len(transcript)} caracteres, confianza: {confidence:.2f}")
                
                return {
                    "transcript": transcript,
                    "confidence": confidence,
                    "words_count": words_count,
                    "character_count": len(transcript),
                    "language": language,
                    "full_response": result,
                    "success": True
                }
            else:
                error_msg = f"Error STT Deepgram: {response.status_code} - {response.text}"
                print(f"[ERROR] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            error_msg = f"Error procesando STT: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def speech_to_text_from_bytes(
        self, 
        audio_bytes: bytes, 
        id_clase: int,
        filename: str,
        language: str = "es",
        save_audio: bool = True,
        save_transcript: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Convierte audio desde bytes a texto
        
        Args:
            audio_bytes: Datos de audio en bytes
            id_clase: ID de la clase
            filename: Nombre original del archivo
            language: Idioma del audio
            save_audio: Si guardar el archivo de audio
            save_transcript: Si guardar la transcripción
            
        Returns:
            Dict con transcripción y metadata
        """
        try:
            # Upload original audio to S3 when requested (no local copies)
            s3_path = None
            audio_filename = f"{id_clase}_{self._get_timestamp()}_{filename}"
            if save_audio:
                if file_service is None:
                    raise RuntimeError("S3 file_service not available. Local copies are disabled; configure S3 to enable uploaded file storage.")
                generated_key = f"uploaded/class/{id_clase}/{audio_filename}"
                ok = file_service.upload_bytes(audio_bytes, generated_key, content_type="audio/mpeg")
                if not ok:
                    raise RuntimeError("Failed to upload original audio to S3")
                s3_path = f"/{generated_key}"
                # Save DB record (include filepath)
                await self._save_file_to_database(id_clase, audio_filename, "Subido", filepath=s3_path)

            # Call STT using direct bytes (Deepgram accepts raw bytes). Avoid local files.
            # We'll write to a temporary NamedTemporaryFile only if provider requires a path (here Deepgram accepts bytes)
            # Create a simple in-memory request
            try:
                # Reuse speech_to_text by providing a temporary file path if it expects a path.
                # But Deepgram speech_to_text implementation in this module requires a file path; to avoid changing it,
                # we'll create a NamedTemporaryFile in-memory and ensure it's cleaned up immediately.
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                    temp_file.write(audio_bytes)
                    temp_audio_path = temp_file.name
                result = await self.speech_to_text(
                    audio_file_path=temp_audio_path,
                    id_clase=id_clase,
                    language=language,
                    save_transcript=save_transcript
                )
            finally:
                try:
                    if 'temp_audio_path' in locals() and os.path.exists(temp_audio_path):
                        os.unlink(temp_audio_path)
                except Exception:
                    pass

            return result
            
        except Exception as e:
            error_msg = f"Error procesando audio desde bytes: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    # ===============================
    # UTILITY FUNCTIONS
    # ===============================
    
    def get_supported_audio_formats(self) -> list[str]:
        """Retorna formatos de audio soportados"""
        return [
            "mp3", "wav", "flac", "ogg", "aac", "m4a", 
            "webm", "mp4", "3gp", "amr", "wma"
        ]
    
    def get_supported_tts_voices(self) -> Dict[str, str]:
        """Retorna voces TTS disponibles"""
        return {
            "aura-2-celeste-es": "Celeste (Español, Femenina)",
            "aura-2-diego-es": "Diego (Español, Masculina)",
            "aura-2-elena-es": "Elena (Español, Femenina)",
            "aura-2-mario-es": "Mario (Español, Masculina)",
            "aura-asteria-en": "Asteria (Inglés, Femenina)",
            "aura-luna-en": "Luna (Inglés, Femenina)",
            "aura-stella-en": "Stella (Inglés, Femenina)",
            "aura-athena-en": "Athena (Inglés, Femenina)",
            "aura-hera-en": "Hera (Inglés, Femenina)",
            "aura-orion-en": "Orion (Inglés, Masculina)",
            "aura-arcas-en": "Arcas (Inglés, Masculina)",
            "aura-perseus-en": "Perseus (Inglés, Masculina)",
            "aura-angus-en": "Angus (Inglés, Masculina)",
            "aura-orpheus-en": "Orpheus (Inglés, Masculina)"
        }
    
    def validate_audio_file(self, file_path: str) -> Dict[str, Any]:
        """Valida un archivo de audio"""
        try:
            if not os.path.exists(file_path):
                return {"valid": False, "error": "Archivo no encontrado"}
            
            file_size = os.path.getsize(file_path)
            file_extension = Path(file_path).suffix.lower().replace(".", "")
            
            # Validar tamaño (máximo 25MB para Deepgram)
            max_size = 25 * 1024 * 1024  # 25MB
            if file_size > max_size:
                return {
                    "valid": False, 
                    "error": f"Archivo muy grande: {file_size} bytes (máximo: {max_size})"
                }
            
            # Validar formato
            supported_formats = self.get_supported_audio_formats()
            if file_extension not in supported_formats:
                return {
                    "valid": False, 
                    "error": f"Formato no soportado: {file_extension}"
                }
            
            return {
                "valid": True,
                "size": file_size,
                "format": file_extension,
                "size_mb": round(file_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    async def get_audio_info(self, file_path: str) -> Dict[str, Any]:
        """Obtiene información detallada de un archivo de audio"""
        validation = self.validate_audio_file(file_path)
        
        if not validation["valid"]:
            return validation
        
        try:
            # Información básica del archivo
            file_stats = os.stat(file_path)
            
            return {
                "valid": True,
                "path": file_path,
                "filename": os.path.basename(file_path),
                "size": validation["size"],
                "size_mb": validation["size_mb"],
                "format": validation["format"],
                "created": file_stats.st_ctime,
                "modified": file_stats.st_mtime,
                "supported_for_stt": True,
                "supported_for_storage": True
            }
            
        except Exception as e:
            return {"valid": False, "error": str(e)}


# Instancia global del procesador de audio
audio_processor = AudioProcessor()


# ===============================
# FUNCIONES DE COMPATIBILIDAD
# ===============================

async def generate_audio_file(text: str, id_clase: int) -> Optional[str]:
    """
    Función de compatibilidad con la API existente
    Mantiene la misma interfaz que la función original
    """
    result = await audio_processor.text_to_speech(text, id_clase)
    
    if result and result.get("success"):
        return result.get("filename")
    return None


async def transcribe_audio_file(audio_path: str, id_clase: int) -> Optional[str]:
    """
    Función helper para transcribir audio y retornar solo el texto
    """
    result = await audio_processor.speech_to_text(audio_path, id_clase)
    
    if result and result.get("success"):
        return result.get("transcript")
    return None


async def process_audio_upload(audio_bytes: bytes, filename: str, id_clase: int) -> Dict[str, Any]:
    """
    Función helper para procesar uploads de audio
    """
    return await audio_processor.speech_to_text_from_bytes(
        audio_bytes=audio_bytes,
        id_clase=id_clase,
        filename=filename,
        save_audio=True,
        save_transcript=True
    )
