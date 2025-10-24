import replicate
import os
import requests
from typing import Optional
import tempfile
from datetime import datetime
# optional file service for S3 operations (no-local requirement)
try:
    from ..files.service import file_service
except Exception:
    file_service = None

class ImageProcessor:
    def __init__(self):
        # Configurar token de Replicate desde variables de entorno
        self.replicate_token = os.getenv("REPLICATE_API_TOKEN")
        if self.replicate_token:
            replicate.api_token = self.replicate_token
    
    def convert_to_cartoon(self, image_url: str, teacher_id: int = None) -> Optional[str]:
        """
        Convierte una imagen a estilo caricaturesco usando Replicate y la guarda localmente
        
        Args:
            image_url (str): URL de la imagen original
            teacher_id (int): ID del docente para crear nombre único
            
        Returns:
            Optional[str]: Path relativo de la imagen caricaturesca guardada localmente o None si falla
        """
        try:
            if not self.replicate_token:
                print("Warning: REPLICATE_API_TOKEN no configurado. Usando imagen original.")
                return image_url
            
            output = replicate.run(
                "google/nano-banana",
                input={
                    "prompt": "Estilo caricaturesco a la foto",
                    "image_input": [f"{image_url}"],
                    "output_format": "jpg"
                }
            )
            # Extract a usable URL from the replicate output. Replicate's
            # return type can vary: it may be a string, an object with a
            # `url` attribute that is either a string or a callable, or
            # a list whose first element is one of the above. Handle
            # those cases safely to avoid calling a string.
            def _extract_url(obj):
                if obj is None:
                    return None
                if isinstance(obj, str):
                    return obj
                # object has .url attribute
                if hasattr(obj, "url"):
                    attr = getattr(obj, "url")
                    try:
                        return attr() if callable(attr) else attr
                    except Exception:
                        return None
                # if it's an iterable, try first element
                if isinstance(obj, (list, tuple)) and len(obj) > 0:
                    return _extract_url(obj[0])
                return None

            cartoon_url = _extract_url(output)
            print("Replicate cartoon url:", cartoon_url)
            
            if cartoon_url:
                print(f"Imagen caricaturesca generada: {cartoon_url}")

                # If teacher_id provided and file_service available, upload the generated
                # cartoon bytes to S3 under generated/teacher/{teacher_id}/ and return that S3 path.
                if teacher_id and file_service is not None:
                    try:
                        r = requests.get(cartoon_url, timeout=30)
                        r.raise_for_status()
                        content = r.content
                        content_type = r.headers.get("content-type", "image/jpeg")
                        # determine extension
                        if "png" in content_type:
                            ext = ".png"
                        elif "gif" in content_type:
                            ext = ".gif"
                        else:
                            ext = ".jpg"

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"docente_{teacher_id}_caricatura_{timestamp}{ext}"
                        s3_key = f"generated/images/teacher/{teacher_id}/{filename}"
                        ok = file_service.upload_bytes(content, s3_key, content_type=content_type)
                        if ok:
                            return f"/{s3_key}"
                        else:
                            print("Warning: failed to upload cartoon image to S3")
                            return cartoon_url
                    except Exception as e:
                        print(f"Error downloading/uploading cartoon image: {e}")
                        return cartoon_url

                return cartoon_url
            else:
                print("Error: No se pudo obtener la URL de la imagen caricaturesca")
                return image_url
                
        except Exception as e:
            print(f"Error al convertir imagen a caricatura: {str(e)}")
            # En caso de error, devolver la imagen original
            return image_url
    
    def generate_image_from_description(self, description: str, class_id: Optional[int] = None, filename: str = None) -> Optional[str]:
        """
        Genera una imagen basada en una descripción usando Replicate y la guarda localmente
        
        Args:
            description (str): Descripción de la imagen a generar
            class_id (int): ID de la clase para crear directorio específico
            filename (str): Nombre personalizado del archivo (opcional)
            
        Returns:
            Optional[str]: Path relativo de la imagen generada guardada localmente o None si falla
        """
        try:
            if not self.replicate_token:
                print("Warning: REPLICATE_API_TOKEN no configurado. No se puede generar imagen.")
                return None
            
            # Usar un modelo de generación de imágenes
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": description
                }
            )
            
            # Obtener la URL de la imagen generada
            if isinstance(output, list) and len(output) > 0:
                image_url = output[0]
            elif isinstance(output, str):
                image_url = output
            else:
                image_url = None
            
            if image_url:
                print(f"Imagen generada exitosamente: {image_url}")
                
                # Enforce S3-only: prepare filename and upload generated content to
                # generated/images/class/{class_id}/<filename>
                if file_service is None:
                    raise RuntimeError("S3 file_service is required to store generated images. Set up S3 and ensure file_service is available.")

                try:
                    r = requests.get(image_url, timeout=30)
                    r.raise_for_status()
                    content = r.content
                    content_type = r.headers.get("content-type", "image/jpeg")
                    # determine extension
                    if "png" in content_type:
                        ext = ".png"
                    elif "gif" in content_type:
                        ext = ".gif"
                    else:
                        ext = ".jpg"


                    if not filename:
                        cid = class_id if class_id is not None else 'misc'
                        filename = f"class_{cid}_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

                    # exact key as requested by user; if class_id is None, store under 'misc'
                    if class_id is None:
                        s3_key = f"generated/images/misc/{filename}"
                    else:
                        s3_key = f"generated/images/class/{class_id}/{filename}"
                    ok = file_service.upload_bytes(content, s3_key, content_type=content_type, descripcion=description)
                    if ok:
                        return f"/{s3_key}"
                    else:
                        raise RuntimeError("Failed to upload generated image to S3")
                except Exception as e:
                    print(f"Error fetching/generated image URL or uploading to S3: {e}")
                    return None
            else:
                print("Error: No se pudo obtener la URL de la imagen generada")
                return None
                
        except Exception as e:
            print(f"Error al generar imagen desde descripción: {str(e)}")
            return None
    
    def save_image_from_url(self, image_url: str, filename: str, directory: str = "public/images") -> Optional[str]:
        """
        Descarga y guarda una imagen desde una URL
        
        Args:
            image_url (str): URL de la imagen a descargar
            filename (str): Nombre del archivo sin extensión
            directory (str): Directorio donde guardar la imagen
            
        Returns:
            Optional[str]: Path relativo del archivo guardado o None si falla
        """
        try:
            # Crear directorio si no existe
            os.makedirs(directory, exist_ok=True)
            
            # Descargar la imagen
            response = requests.get(image_url)
            response.raise_for_status()
            
            # Determinar extensión del archivo
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                extension = '.jpg'
            elif 'png' in content_type:
                extension = '.png'
            else:
                extension = '.jpg'  # Por defecto
            
            # Crear nombre de archivo único
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(directory, f"{filename}_{timestamp}{extension}")
            
            # Guardar el archivo
            with open(file_path, 'wb') as file:
                file.write(response.content)
            
            print(f"Imagen guardada en: {file_path}")
            return file_path
            
        except Exception as e:
            print(f"Error al guardar imagen: {str(e)}")
            return None
    
    def get_default_avatar_url(self) -> str:
        """
        Retorna la URL de la imagen de avatar predeterminada
        
        Returns:
            str: URL del avatar predeterminado
        """
        return "/images/default-teacher-avatar.png"
    
    def get_default_cartoon_avatar_url(self) -> str:
        """
        Retorna la URL de la imagen de avatar caricaturesco predeterminada
        
        Returns:
            str: URL del avatar caricaturesco predeterminado
        """
        return "/images/default-teacher-cartoon-avatar.png"

# Instancia global del procesador de imágenes
image_processor = ImageProcessor()
