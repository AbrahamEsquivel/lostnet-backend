"""Configuración común de las pruebas.

Se definen variables de entorno ANTES de importar la API para que use
una clave Fernet temporal y una carpeta de fotos temporal, sin tocar
los archivos reales del servidor.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="lostnet-tests-")
os.environ.setdefault("FERNET_KEY_FILE", os.path.join(_TMP, "secret.key"))
os.environ.setdefault("PHOTOS_PATH", os.path.join(_TMP, "photos"))
os.environ.setdefault("MONGO_TIMEOUT_MS", "1000")

# Solo para correr las pruebas en una máquina sin MongoDB:
# LOSTNET_TEST_MONGOMOCK=1 usa una base de datos en memoria.
if os.getenv("LOSTNET_TEST_MONGOMOCK") == "1":
    import mongomock
    import pymongo

    _shared = mongomock.MongoClient()
    pymongo.MongoClient = lambda *a, **k: _shared
