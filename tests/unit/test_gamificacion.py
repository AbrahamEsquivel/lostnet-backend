"""Pruebas unitarias de la asignación de rangos, con bases de datos simuladas."""
from unittest.mock import MagicMock

import pytest

import api


def _conexion_falsa(filas):
    cursor = MagicMock()
    cursor.fetchall.return_value = filas
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


@pytest.mark.parametrize(
    "filas, rango",
    [
        ([], "BUSCADOR"),
        ([{"status": "FOUND", "total": 5}], "SABUESO"),
        ([{"status": "LOST", "total": 5}], "PERDEDOR"),
        ([{"status": "LOST", "total": 7}, {"status": "FOUND", "total": 6}], "SABUESO"),
        ([{"status": "LOST", "total": 4}], "BUSCADOR"),
    ],
)
def test_rango_segun_reportes(monkeypatch, filas, rango):
    perfiles = MagicMock()
    monkeypatch.setattr(api, "get_mysql_db", lambda: _conexion_falsa(filas))
    monkeypatch.setattr(api, "coleccion_perfiles", perfiles)

    api.evaluar_rango_usuario("ana@correo.com")

    perfiles.update_one.assert_called_once_with(
        {"email_usuario": "ana@correo.com"}, {"$set": {"rol": rango}}
    )
