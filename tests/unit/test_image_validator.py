"""Pruebas unitarias del validador antifraude de imágenes."""
from io import BytesIO

from PIL import Image
from werkzeug.datastructures import FileStorage

from image_validator import crear_log_validacion, validar_imagen


def _imagen(formato="PNG", tamano=(64, 64), color=(200, 30, 30), software=None):
    img = Image.new("RGB", tamano, color)
    buffer = BytesIO()
    if software:
        exif = Image.Exif()
        exif[0x0131] = software  # etiqueta EXIF "Software"
        img.save(buffer, format=formato, exif=exif)
    else:
        img.save(buffer, format=formato)
    buffer.seek(0)
    return FileStorage(stream=buffer, filename=f"foto.{formato.lower()}")


class ColeccionFalsa:
    """Simula la colección de MongoDB con fotos ya registradas."""

    def __init__(self, documentos=None):
        self.documentos = documentos or []

    def find_one(self, filtro, proyeccion=None):
        for doc in self.documentos:
            if all(doc.get(k) == v for k, v in filtro.items()):
                return doc
        return None

    def find(self, filtro, proyeccion=None):
        class _Cursor(list):
            def limit(self, _n):
                return self
        return _Cursor(d for d in self.documentos if "hash_perceptual" in d)


def test_imagen_png_valida():
    resultado = validar_imagen(_imagen())
    assert resultado["valida"] is True
    assert resultado["formato"] == "PNG"
    assert len(resultado["hash_sha256"]) == 64


def test_imagen_sin_exif_genera_advertencia():
    resultado = validar_imagen(_imagen())
    assert any("EXIF" in a for a in resultado["advertencias"])


def test_sin_archivo_se_rechaza():
    assert validar_imagen(None)["valida"] is False


def test_archivo_vacio_se_rechaza():
    vacio = FileStorage(stream=BytesIO(b""), filename="vacia.png")
    assert validar_imagen(vacio)["valida"] is False


def test_archivo_corrupto_se_rechaza():
    corrupto = FileStorage(stream=BytesIO(b"esto no es una imagen"), filename="x.png")
    resultado = validar_imagen(corrupto)
    assert resultado["valida"] is False
    assert "dañado" in resultado["motivo"]


def test_formato_no_permitido_se_rechaza():
    resultado = validar_imagen(_imagen(formato="GIF"))
    assert resultado["valida"] is False
    assert "no permitido" in resultado["motivo"]


def test_resolucion_insuficiente_se_rechaza():
    resultado = validar_imagen(_imagen(tamano=(16, 16)))
    assert resultado["valida"] is False
    assert "Resolución" in resultado["motivo"]


def test_software_de_edicion_marca_la_imagen_como_sospechosa():
    resultado = validar_imagen(_imagen(formato="JPEG", software="Adobe Photoshop 25.0"))
    assert resultado["valida"] is True
    assert resultado["es_sospechosa"] is True


def test_imagen_duplicada_exacta_se_rechaza():
    original = validar_imagen(_imagen())
    coleccion = ColeccionFalsa([{"hash_sha256": original["hash_sha256"], "valida": True, "reporte_id": "REP-1"}])
    resultado = validar_imagen(_imagen(), coleccion)
    assert resultado["valida"] is False
    assert resultado["reporte_duplicado"] == "REP-1"


def test_imagen_visualmente_similar_se_rechaza():
    original = validar_imagen(_imagen())
    coleccion = ColeccionFalsa([{"hash_perceptual": original["hash_perceptual"], "valida": True, "reporte_id": "REP-2"}])
    # Misma imagen guardada como JPEG: distinto SHA-256, mismo contenido visual
    resultado = validar_imagen(_imagen(formato="JPEG"), coleccion)
    assert resultado["valida"] is False
    assert resultado["reporte_duplicado"] == "REP-2"


def test_log_de_validacion_incluye_reporte_y_fecha():
    archivo = _imagen()
    log = crear_log_validacion({"valida": True}, archivo, reporte_id="REP-9")
    assert log["reporte_id"] == "REP-9"
    assert log["nombre_original"] == "foto.png"
    assert "fecha_validacion" in log
