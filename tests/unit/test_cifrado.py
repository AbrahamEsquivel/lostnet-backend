"""Pruebas unitarias del cifrado Fernet de datos personales."""
from api import desencriptar, encriptar


def test_cifrar_y_descifrar_regresa_el_texto_original():
    telefono = "4491234567"
    cifrado = encriptar(telefono)
    assert cifrado != telefono
    assert desencriptar(cifrado) == telefono


def test_el_texto_cifrado_no_contiene_el_dato_en_claro():
    assert "4491234567" not in encriptar("4491234567")


def test_cifrar_dos_veces_produce_textos_distintos():
    # Fernet usa un vector de inicialización aleatorio
    assert encriptar("dato") != encriptar("dato")


def test_texto_vacio_o_nulo():
    assert encriptar("") == ""
    assert encriptar(None) == ""
    assert desencriptar("") == ""
    assert desencriptar(None) == ""


def test_texto_no_cifrado_se_regresa_sin_cambios():
    # Compatibilidad con registros antiguos guardados sin cifrar
    assert desencriptar("texto-plano") == "texto-plano"
