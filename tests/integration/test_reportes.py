"""Pruebas de integración del ciclo de vida de un reporte."""
import pytest

import api
from tests.integration.conftest import nuevo_reporte

pytestmark = pytest.mark.integration


def test_reportar_y_listar(cliente):
    respuesta = cliente.post("/api/reportar", json=nuevo_reporte())
    assert respuesta.status_code == 201
    report_id = respuesta.get_json()["id"]

    listado = cliente.get("/api/reportes").get_json()
    reporte = next(r for r in listado if r["id"] == report_id)
    assert reporte["desc_short"] == "Cartera café"
    assert reporte["phone"] == "4491234567"  # la API lo regresa descifrado


def test_el_telefono_se_guarda_cifrado_en_mysql(cliente, db):
    report_id = cliente.post("/api/reportar", json=nuevo_reporte()).get_json()["id"]
    _, cursor = db
    cursor.execute("SELECT phone, security_answer FROM report_index WHERE id = %s", (report_id,))
    fila = cursor.fetchone()
    assert fila["phone"] != "4491234567"
    assert api.desencriptar(fila["phone"]) == "4491234567"
    assert fila["security_answer"] != "café"


def test_reportar_registra_al_usuario_y_su_perfil(cliente, db, mongo):
    cliente.post("/api/reportar", json=nuevo_reporte(email="nuevo@correo.com"))
    _, cursor = db
    cursor.execute("SELECT email FROM t1_users WHERE email = %s", ("nuevo@correo.com",))
    assert cursor.fetchone() is not None
    perfil = mongo["perfiles_usuarios"].find_one({"email_usuario": "nuevo@correo.com"})
    assert perfil["rol"] == "BUSCADOR"


def test_limite_diario_de_reportes(cliente):
    for _ in range(api.REPORT_DAILY_LIMIT):
        assert cliente.post("/api/reportar", json=nuevo_reporte()).status_code == 201

    respuesta = cliente.post("/api/reportar", json=nuevo_reporte())
    assert respuesta.status_code == 429
    assert int(respuesta.headers["Retry-After"]) > 0


def test_borrado_logico(cliente):
    report_id = cliente.post("/api/reportar", json=nuevo_reporte()).get_json()["id"]

    assert cliente.delete(f"/api/reportes/{report_id}").status_code == 200
    ids = [r["id"] for r in cliente.get("/api/reportes").get_json()]
    assert report_id not in ids


def test_borrar_reporte_inexistente_responde_404(cliente):
    assert cliente.delete("/api/reportes/REP-noexiste").status_code == 404
