"""
Módulo de Validación y Detección Antifraude de Imágenes para LostNet.
Soporta detección de duplicados exactos (SHA-256) y perceptuales (pHash),
análisis de metadatos EXIF, y marcas de software de edición / IA generativa.
"""

import hashlib
from datetime import datetime, timezone
from io import BytesIO

import imagehash
from PIL import Image, UnidentifiedImageError, ExifTags

# Configuración de límites y formatos
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}
PHASH_DISTANCE_LIMIT = 6

SOFTWARE_SOSPECHOSO = [
    "photoshop", "gimp", "canva", "picsart", "lightroom", "pixlr",
    "midjourney", "dall-e", "stable diffusion", "generative ai"
]


def _read_file_bytes(file_storage):
    """Lee el contenido en memoria de manera segura y restaura el puntero."""
    if hasattr(file_storage, "stream"):
        file_storage.stream.seek(0)
        content = file_storage.stream.read(MAX_IMAGE_BYTES + 1)
        file_storage.stream.seek(0)
        return content
    elif hasattr(file_storage, "read"):
        file_storage.seek(0)
        content = file_storage.read(MAX_IMAGE_BYTES + 1)
        file_storage.seek(0)
        return content
    return b""


def _buscar_duplicado_sha256(hash_sha256, coleccion):
    """Búsqueda directa indexada por huella binaria exacta."""
    if coleccion is None:
        return None
    try:
        doc = coleccion.find_one({"hash_sha256": hash_sha256, "valida": True}, {"reporte_id": 1})
        if doc:
            return doc.get("reporte_id") or "Existente (Exacta)"
    except Exception as e:
        print(f"⚠️ Error buscando duplicado SHA256: {e}")
    return None


def _buscar_duplicado_phash(perceptual_hash, coleccion):
    """Búsqueda por similitud perceptual (pHash) en MongoDB."""
    if coleccion is None:
        return None

    try:
        # Consultamos únicamente documentos con hash perceptual guardado
        cursor = coleccion.find(
            {"hash_perceptual": {"$exists": True}, "valida": True},
            {"hash_perceptual": 1, "reporte_id": 1}
        ).limit(5000)

        for doc in cursor:
            try:
                stored_hash_str = doc.get("hash_perceptual")
                if not stored_hash_str:
                    continue
                stored_hash = imagehash.hex_to_hash(stored_hash_str)
                distancia = perceptual_hash - stored_hash
                if distancia <= PHASH_DISTANCE_LIMIT:
                    return doc.get("reporte_id") or "Existente (Perceptual)"
            except (KeyError, TypeError, ValueError):
                continue
    except Exception as e:
        print(f"⚠️ Error escaneando pHash en MongoDB: {e}")

    return None


def validar_imagen(file_storage, coleccion=None):
    """
    Valida una imagen subida y genera un dict serializable a JSON.
    - Rechaza: archivos vacíos, corruptos, no soportados, o duplicados.
    - Alerta (warnings): ausencia de EXIF o indicios de software de edición.
    """
    if file_storage is None or not getattr(file_storage, "filename", ""):
        return {"valida": False, "motivo": "No se recibió ninguna imagen o el nombre de archivo está vacío"}

    try:
        content = _read_file_bytes(file_storage)
        if not content:
            return {"valida": False, "motivo": "La imagen recibida está vacía"}

        if len(content) > MAX_IMAGE_BYTES:
            return {"valida": False, "motivo": "La imagen supera el límite permitido de 10 MB"}

        # 1. Huella SHA-256
        hash_sha256 = hashlib.sha256(content).hexdigest()

        # Chequeo rápido de duplicado exacto
        dup_sha = _buscar_duplicado_sha256(hash_sha256, coleccion)
        if dup_sha:
            return {
                "valida": False,
                "motivo": "Imagen duplicada: ya existe un reporte registrado con esta misma foto exacta",
                "reporte_duplicado": dup_sha,
                "hash_sha256": hash_sha256
            }

        # 2. Verificación de integridad con Pillow
        with Image.open(BytesIO(content)) as img_verify:
            img_verify.verify()

        # 3. Inspección y extracción de propiedades
        with Image.open(BytesIO(content)) as img:
            formato = (img.format or "").upper()
            if formato not in ALLOWED_FORMATS:
                return {"valida": False, "motivo": f"Formato '{formato}' no permitido. Use JPEG, PNG o WEBP"}

            width, height = img.size
            if width < 32 or height < 32:
                return {"valida": False, "motivo": "Resolución insuficiente (mínimo 32x32 píxeles)"}

            # Hash perceptual (robusto ante recortes o compresión)
            perceptual_hash = imagehash.phash(img)

            # Extracción de metadatos EXIF
            metadatos = {}
            software_detectado = None
            raw_exif = img.getexif()

            if raw_exif:
                for tag_id, val in raw_exif.items():
                    nombre_tag = ExifTags.TAGS.get(tag_id, tag_id)
                    metadatos[str(nombre_tag)] = str(val)

                software_detectado = metadatos.get("Software", "").strip().lower()

        # 4. Chequeo de duplicado perceptual (pHash)
        dup_phash = _buscar_duplicado_phash(perceptual_hash, coleccion)
        if dup_phash:
            return {
                "valida": False,
                "motivo": "Imagen duplicada: es visualmente muy similar a una foto ya registrada",
                "reporte_duplicado": dup_phash,
                "hash_sha256": hash_sha256,
                "hash_perceptual": str(perceptual_hash)
            }

        # 5. Análisis de advertencias (antifraude / edición)
        warnings = []
        if not raw_exif:
            warnings.append("Sin metadatos EXIF (común al compartir por mensajería)")

        es_sospechosa = False
        if software_detectado:
            for prog in SOFTWARE_SOSPECHOSO:
                if prog in software_detectado:
                    es_sospechosa = True
                    warnings.append(f"Indicios de edición o generación sintética ({software_detectado})")
                    break

        return {
            "valida": True,
            "motivo": "Imagen válida" if not warnings else "; ".join(warnings),
            "advertencias": warnings,
            "es_sospechosa": es_sospechosa,
            "hash_sha256": hash_sha256,
            "hash_perceptual": str(perceptual_hash),
            "formato": formato,
            "ancho": width,
            "alto": height,
            "tamano_bytes": len(content),
            "software_exif": software_detectado or None
        }

    except (UnidentifiedImageError, OSError, ValueError) as e:
        return {"valida": False, "motivo": f"El archivo está dañado o no es una imagen válida: {str(e)}"}


def crear_log_validacion(resultado, file_storage, reporte_id=None):
    """Prepara el documento BSON estructurado para persistir en MongoDB."""
    return {
        **resultado,
        "reporte_id": reporte_id,
        "persistida": True,
        "nombre_original": getattr(file_storage, "filename", "desconocido"),
        "fecha_validacion": datetime.now(timezone.utc)
    }
