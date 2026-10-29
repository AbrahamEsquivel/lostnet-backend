"""Fixtures de integración: usan MySQL y MongoDB reales.

En GitHub Actions ambas bases se levantan como servicios del pipeline.
Antes de cada prueba se vacían las tablas y colecciones para que las
pruebas no dependan unas de otras.
"""
import mysql.connector
import pytest
from pymongo import MongoClient

import api

TABLAS = [
    "t1_users", "report_index", "report_rate_events", "report_purge_queue",
    "t7_buzon", "t8_comentarios", "puntos_seguros",
    "frag_usuarios_sabuesos", "frag_usuarios_perdedores",
]


@pytest.fixture
def db():
    conn = mysql.connector.connect(**api.MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    for tabla in TABLAS:
        cursor.execute(f"DELETE FROM {tabla}")  # nosec B608 - nombres fijos de la lista TABLAS
    conn.commit()
    yield conn, cursor
    cursor.close()
    conn.close()


@pytest.fixture
def mongo():
    cliente = MongoClient(api.MONGO_URI)
    base = cliente["lostnet_gamificacion"]
    for nombre in ("perfiles_usuarios", "fotos_validadas", "verificaciones_telefono"):
        base[nombre].delete_many({})
    return base


@pytest.fixture
def cliente(db, mongo):
    api.app.config["TESTING"] = True
    with api.app.test_client() as c:
        yield c


def nuevo_reporte(email="ana@correo.com", **extra):
    datos = {
        "email": email,
        "user_id": "google-123",
        "latitude": 21.8818,
        "longitude": -102.2916,
        "description": "Cartera café",
        "category": "Documentos",
        "phone": "4491234567",
        "security_question": "¿Qué color tiene?",
        "security_answer": "café",
    }
    datos.update(extra)
    return datos
