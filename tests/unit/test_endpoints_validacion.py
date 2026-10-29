"""Pruebas unitarias de validación de entradas en los endpoints.

Estas rutas responden antes de consultar la base de datos, por lo que
no requieren MySQL ni MongoDB.
"""
import pytest

import api


@pytest.fixture
def cliente():
    api.app.config["TESTING"] = True
    with api.app.test_client() as c:
        yield c


def test_config_regresa_los_colores_del_mapa(cliente):
    respuesta = cliente.get("/api/config")
    assert respuesta.status_code == 200
    assert set(respuesta.get_json()["colores_mapa"]) == {"pin_propio", "pin_ajeno", "pin_seguro"}


def test_reportar_sin_correo_responde_400(cliente):
    respuesta = cliente.post("/api/reportar", json={"latitude": 21.88, "longitude": -102.29})
    assert respuesta.status_code == 400


def test_reportar_con_coordenadas_no_numericas_responde_400(cliente):
    respuesta = cliente.post("/api/reportar", json={"email": "a@b.com", "latitude": "norte", "longitude": "x"})
    assert respuesta.status_code == 400


def test_comentar_sin_datos_responde_400(cliente):
    assert cliente.post("/api/comentar", json={}).status_code == 400


def test_perfil_sin_correo_responde_400(cliente):
    assert cliente.get("/api/perfil").status_code == 400


def test_alertas_sin_correo_regresa_lista_vacia(cliente):
    respuesta = cliente.get("/api/mis-alertas")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == []


def test_comentarios_sin_reporte_regresa_lista_vacia(cliente):
    assert cliente.get("/api/comentarios").get_json() == []
