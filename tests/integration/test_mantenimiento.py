"""Pruebas de integración de la purga de reportes y la migración a MongoDB."""
import pytest

import api
import migrar_fragmento

pytestmark = pytest.mark.integration


def test_purga_elimina_reportes_vencidos(db, mongo):
    conn, cursor = db
    cursor.execute(
        """
        INSERT INTO report_index (id, email, desc_short, status_logico, photo_url, created_at)
        VALUES ('REP-viejo', 'a@b.com', 'Reporte viejo', 'ACTIVO', '/photos/default.png', NOW() - INTERVAL 6 DAY),
               ('REP-nuevo', 'a@b.com', 'Reporte nuevo', 'ACTIVO', '/photos/default.png', NOW())
        """
    )
    cursor.execute(
        "INSERT INTO t8_comentarios (id, report_id, user_name, text, timestamp) VALUES ('COM-1', 'REP-viejo', 'x', 'y', 0)"
    )
    conn.commit()

    en_cola, eliminados = api.purgar_reportes_expirados()

    assert (en_cola, eliminados) == (1, 1)
    cursor.execute("SELECT id FROM report_index")
    assert [f["id"] for f in cursor.fetchall()] == ["REP-nuevo"]
    cursor.execute("SELECT COUNT(*) AS n FROM t8_comentarios")
    assert cursor.fetchone()["n"] == 0
    cursor.execute("SELECT COUNT(*) AS n FROM report_purge_queue")
    assert cursor.fetchone()["n"] == 0


def test_migracion_de_fragmentos_a_mongodb(db, mongo):
    conn, cursor = db
    cursor.executemany(
        "INSERT INTO frag_usuarios_sabuesos (email, user_type, badge, joined_date) VALUES (%s, %s, %s, %s)",
        [("s1@correo.com", "SABUESO", "Oro", "2026-01-10"), ("s2@correo.com", "SABUESO", "Plata", "2026-02-11")],
    )
    cursor.execute(
        "INSERT INTO frag_usuarios_perdedores (email, user_type, badge, joined_date) VALUES (%s, %s, %s, %s)",
        ("p1@correo.com", "PERDEDOR", "Novato", "2026-03-12"),
    )
    conn.commit()

    assert migrar_fragmento.migrar_fragmento_gamificacion() == 3

    perfiles = mongo["perfiles_usuarios"]
    assert perfiles.count_documents({}) == 3
    assert perfiles.find_one({"email_usuario": "p1@correo.com"})["tasa_descuido"] == "Alta"
