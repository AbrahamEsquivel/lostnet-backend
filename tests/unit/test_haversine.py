"""Pruebas unitarias de la fórmula de Haversine usada por el geovallado."""
import pytest

from api import haversine


def test_misma_coordenada_da_distancia_cero():
    assert haversine(21.8818, -102.2916, 21.8818, -102.2916) == pytest.approx(0.0)


def test_un_grado_de_latitud_mide_aproximadamente_111_km():
    assert haversine(0, 0, 1, 0) == pytest.approx(111.19, abs=0.1)


def test_distancia_conocida_aguascalientes_a_ciudad_de_mexico():
    # Centro de Aguascalientes -> Zócalo de la CDMX: ~420 km en línea recta
    distancia = haversine(21.8818, -102.2916, 19.4326, -99.1332)
    assert 400 < distancia < 440


def test_la_distancia_es_simetrica():
    ida = haversine(21.88, -102.29, 21.91, -102.31)
    vuelta = haversine(21.91, -102.31, 21.88, -102.29)
    assert ida == pytest.approx(vuelta)


@pytest.mark.parametrize(
    "lat2, lon2, dentro",
    [
        (21.8818 + 0.018, -102.2916, True),   # ~2 km al norte
        (21.8818 + 0.054, -102.2916, False),  # ~6 km al norte
    ],
)
def test_radio_de_alerta_de_5_km(lat2, lon2, dentro):
    assert (haversine(21.8818, -102.2916, lat2, lon2) < 5.0) is dentro
