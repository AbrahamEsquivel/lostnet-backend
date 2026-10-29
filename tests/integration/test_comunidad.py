"""Pruebas de integración de comentarios, puntos seguros y alertas."""
import pytest

import api
from tests.integration.conftest import nuevo_reporte

pytestmark = pytest.mark.integration


def test_comentar_y_consultar_comentarios(cliente):
    report_id = cliente.post("/api/reportar", json=nuevo_reporte()).get_json()["id"]

    respuesta = cliente.post("/api/comentar", json={"report_id": report_id, "user_name": "Luis", "text": "Lo vi en la plaza"})
    assert respuesta.status_code == 201

    comentarios = cliente.get(f"/api/comentarios?report_id={report_id}").get_json()
    assert [c["text"] for c in comentarios] == ["Lo vi en la plaza"]


def test_puntos_seguros(cliente, db):
    conn, cursor = db
    cursor.execute(
        "INSERT INTO puntos_seguros (nombre, lat, lon, tipo) VALUES (%s, %s, %s, %s)",
        ("Módulo Policía Centro", 21.8818, -102.2916, "Oficial"),
    )
    conn.commit()

    puntos = cliente.get("/api/puntos-seguros").get_json()
    assert [p["nombre"] for p in puntos] == ["Módulo Policía Centro"]


def test_geofencing_alerta_solo_a_usuarios_cercanos(cliente, db):
    conn, cursor = db
    cursor.executemany(
        "INSERT INTO t1_users (email, user_id, last_lat, last_lon) VALUES (%s, %s, %s, %s)",
        [
            ("cerca@correo.com", "u1", 21.8900, -102.2916),   # ~1 km
            ("lejos@correo.com", "u2", 21.9900, -102.2916),   # ~12 km
            ("dueno@correo.com", "u3", 21.8818, -102.2916),   # quien reporta
        ],
    )
    conn.commit()

    api.procesar_geofencing(21.8818, -102.2916, "Llaves", "dueno@correo.com")

    assert len(cliente.get("/api/mis-alertas?email=cerca@correo.com").get_json()) == 1
    assert cliente.get("/api/mis-alertas?email=lejos@correo.com").get_json() == []
    assert cliente.get("/api/mis-alertas?email=dueno@correo.com").get_json() == []
