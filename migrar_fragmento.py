import os

import mysql.connector
from pymongo import MongoClient

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "lostnet_api"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "lostnet_db"),
}
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")


def migrar_fragmento_gamificacion():
    """Copia los fragmentos de usuarios de MySQL hacia MongoDB.

    Regresa el número de documentos insertados.
    """
    print("🔄 Iniciando extracción desde MySQL (Servidor Principal)...")
    mysql_conn = None
    cursor = None
    try:
        # 1. EXTRACCIÓN desde MySQL
        mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = mysql_conn.cursor(dictionary=True)

        # 2. CARGA en MongoDB
        print("🔄 Conectando a MongoDB (Servidor Secundario)...")
        mongo_client = MongoClient(MONGO_URI)
        coleccion_perfiles = mongo_client["lostnet_gamificacion"]["perfiles_usuarios"]

        # Limpiamos por si hay pruebas previas
        coleccion_perfiles.delete_many({})

        # --- Extrayendo Sabuesos ---
        cursor.execute("SELECT email, user_type, badge, joined_date FROM frag_usuarios_sabuesos")
        documentos_nosql = []
        for s in cursor.fetchall():
            documentos_nosql.append({
                "email_usuario": s["email"],
                "rol": s["user_type"],
                "emblema": s["badge"],
                "fecha_registro": s["joined_date"],
                "metricas_exclusivas": {
                    "objetos_devueltos": 0,
                    "nivel_confiabilidad": "Alto"
                }
            })

        # --- Extrayendo Perdedores ---
        cursor.execute("SELECT email, user_type, badge, joined_date FROM frag_usuarios_perdedores")
        for p in cursor.fetchall():
            documentos_nosql.append({
                "email_usuario": p["email"],
                "rol": p["user_type"],
                "emblema": p["badge"],
                "fecha_registro": p["joined_date"],
                "historial_extravios": [],
                "tasa_descuido": "Alta"
            })

        # 3. INYECCIÓN en MongoDB
        if documentos_nosql:
            coleccion_perfiles.insert_many(documentos_nosql)
            print(f"✅ ¡Éxito! Se migraron {len(documentos_nosql)} usuarios al fragmento NoSQL.")
        else:
            print("⚠️ No se encontraron registros en las vistas de MySQL.")
        return len(documentos_nosql)

    except Exception as e:
        print(f"❌ Error en la migración: {e}")
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if mysql_conn is not None and mysql_conn.is_connected():
            mysql_conn.close()


if __name__ == "__main__":
    migrar_fragmento_gamificacion()
