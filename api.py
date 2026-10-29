from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import threading
import os
import time
import math
import uuid
from datetime import datetime
from cryptography.fernet import Fernet
from pymongo import MongoClient
import mysql.connector
from image_validator import crear_log_validacion, validar_imagen

REPORT_DAILY_LIMIT = 5
REPORT_WEEKLY_LIMIT = 20

app = Flask(__name__)
# Habilitamos CORS para que la web en Astro pueda consumir la API
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

# ==========================================
#     CONEXIONES DE BASES DE DATOS
# ==========================================

# La configuración se lee de variables de entorno para no guardar
# credenciales en el código y poder ejecutar la API en el servidor y en CI.
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "lostnet_api"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "lostnet_db"),
}
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
MONGO_TIMEOUT_MS = int(os.getenv("MONGO_TIMEOUT_MS", "5000"))


# 1. MySQL (Transaccional)
def get_mysql_db():
    return mysql.connector.connect(**MYSQL_CONFIG)

# 2. MongoDB (Gamificación y Estadísticas - Servidor Secundario REMOTO)
mongo_db_gamificacion = None
coleccion_perfiles = None
coleccion_fotos_validadas = None
try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=MONGO_TIMEOUT_MS)
    mongo_db_gamificacion = mongo_client["lostnet_gamificacion"]
    coleccion_perfiles = mongo_db_gamificacion["perfiles_usuarios"]
    coleccion_fotos_validadas = mongo_db_gamificacion["fotos_validadas"]

    # Validamos conexión
    mongo_client.admin.command('ping')
    print("✅ Conectado a MongoDB")
except Exception as e:
    print(f"⚠️ Error conectando a MongoDB remoto: {e}")

# ==========================================
#     CONFIGURACIONES Y CRIPTOGRAFÍA
# ==========================================

PHOTOS_PATH = os.getenv("PHOTOS_PATH", "photos")
KEY_FILE = os.getenv("FERNET_KEY_FILE", "secret.key")

if not os.path.exists(PHOTOS_PATH):
    os.makedirs(PHOTOS_PATH, exist_ok=True)

# Genera o carga la llave de encriptación
def cargar_clave():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    else:
        with open(KEY_FILE, "rb") as f:
            key = f.read()
    return key

cipher = Fernet(cargar_clave())

def encriptar(texto):
    if not texto:
        return ""
    try:
        return cipher.encrypt(str(texto).encode()).decode()
    except Exception:
        return ""

def desencriptar(texto_encriptado):
    if not texto_encriptado:
        return ""
    try:
        return cipher.decrypt(str(texto_encriptado).encode()).decode()
    except Exception:
        return texto_encriptado

# ==========================================
#     CÁLCULO DE DISTANCIAS Y GAMIFICACIÓN
# ==========================================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radio de la Tierra en km
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def procesar_geofencing(lat_reporte, lon_reporte, desc_reporte, email_actual):
    """Busca usuarios cercanos y genera una alerta en la tabla t7_buzon"""
    print(f"📡 Iniciando Harvester: Buscando usuarios cerca de ({lat_reporte}, {lon_reporte})")
    try:
        conn = get_mysql_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT email, last_lat, last_lon FROM t1_users WHERE email != %s AND last_lat IS NOT NULL", (email_actual,))
        usuarios = cursor.fetchall()

        for u in usuarios:
            distancia = haversine(lat_reporte, lon_reporte, float(u['last_lat']), float(u['last_lon']))
            if distancia < 5.0:
                print(f"🚨 ALERTA GEOFENCING: {u['email']} está a {distancia:.1f}km del objeto.")
                cursor_ins = conn.cursor()
                alerta_id = f"ALT-{uuid.uuid4().hex[:8]}"
                mensaje = f"Objeto reportado cerca de tu ubicación: {desc_reporte}"
                cursor_ins.execute(
                    "INSERT INTO t7_buzon (id, to_email, title, message) VALUES (%s, %s, %s, %s)",
                    (alerta_id, u['email'], "Alerta de proximidad LostNet", mensaje)
                )
                conn.commit()
                cursor_ins.close()
    except Exception as e:
        print(f"❌ Error en Harvester: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# --- NUEVO CEREBRO GAMIFICADOR ---
def evaluar_rango_usuario(email_usuario):
    """Cuenta los reportes en MySQL y actualiza la medalla en MongoDB"""
    try:
        conn = get_mysql_db()
        cursor = conn.cursor(dictionary=True)
        # Contamos cuántos objetos ha perdido y cuántos ha encontrado
        cursor.execute("SELECT status, COUNT(*) as total FROM report_index WHERE email = %s AND status_logico = 'ACTIVO' GROUP BY status", (email_usuario,))
        resultados = cursor.fetchall()

        perdidos = 0
        encontrados = 0

        for fila in resultados:
            if fila['status'] == 'LOST':
                perdidos = fila['total']
            if fila['status'] == 'FOUND':
                encontrados = fila['total']

        # Lógica de medallas (Priorizamos al héroe)
        nuevo_rol = "BUSCADOR"
        if encontrados >= 5:
            nuevo_rol = "SABUESO"
        elif perdidos >= 5:
            nuevo_rol = "PERDEDOR"

        # Actualizamos en la base de datos secundaria (MongoDB)
        coleccion_perfiles.update_one(
            {"email_usuario": email_usuario},
            {"$set": {"rol": nuevo_rol}}
        )
        print(f"🏅 Gamificación: Evaluado {email_usuario} -> Rango: {nuevo_rol}")

    except Exception as e:
        print(f"❌ Error evaluando gamificación: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def purgar_reportes_expirados(batch_size=500):
    """Elimina reportes vencidos y reintenta borrar sus archivos y metadatos."""
    conn = get_mysql_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, photo_url
            FROM report_index
            WHERE created_at <= NOW() - INTERVAL 5 DAY
            ORDER BY created_at
            LIMIT %s
            """,
            (batch_size,)
        )
        vencidos = cursor.fetchall()

        if vencidos:
            for reporte in vencidos:
                cursor.execute(
                    """
                    INSERT IGNORE INTO report_purge_queue (report_id, photo_url)
                    VALUES (%s, %s)
                    """,
                    (reporte["id"], reporte.get("photo_url"))
                )
                cursor.execute(
                    "DELETE FROM t8_comentarios WHERE report_id = %s",
                    (reporte["id"],)
                )
                cursor.execute(
                    "DELETE FROM report_index WHERE id = %s",
                    (reporte["id"],)
                )
        cursor.execute(
            "DELETE FROM report_rate_events WHERE created_at < NOW() - INTERVAL 7 DAY"
        )
        conn.commit()

        cursor.execute(
            "SELECT report_id, photo_url FROM report_purge_queue ORDER BY queued_at LIMIT %s",
            (batch_size,)
        )
        pendientes = cursor.fetchall()
        eliminados = 0
        fallidos = []

        for reporte in pendientes:
            try:
                photo_url = reporte.get("photo_url") or ""
                if photo_url.startswith("/photos/"):
                    filename = os.path.basename(photo_url)
                    if filename and filename != "default.png":
                        photo_path = os.path.join(PHOTOS_PATH, filename)
                        if os.path.isfile(photo_path):
                            os.remove(photo_path)

                if coleccion_fotos_validadas is None:
                    raise RuntimeError("MongoDB de validaciones no está disponible; se reintentará.")
                coleccion_fotos_validadas.delete_many(
                    {"reporte_id": reporte["report_id"]}
                )

                cursor.execute(
                    "DELETE FROM report_purge_queue WHERE report_id = %s",
                    (reporte["report_id"],)
                )
                conn.commit()
                eliminados += 1
            except Exception as e:
                conn.rollback()
                fallidos.append(reporte["report_id"])
                print(f"❌ No se pudo completar la purga de {reporte['report_id']}: {e}")

        if fallidos:
            raise RuntimeError(
                f"No se completó la purga de {len(fallidos)} reportes; se reintentará."
            )
        return len(vencidos), eliminados
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

# ==========================================
#     ENDPOINTS PRINCIPALES (REPORTES)
# ==========================================

@app.route('/api/reportes', methods=['GET'])
def listar_reportes():
    """Jala todos los reportes ACTIVOS de MySQL"""
    try:
        conn = get_mysql_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT *,
                   UNIX_TIMESTAMP(DATE_ADD(created_at, INTERVAL 5 DAY)) AS expires_at_epoch,
                   GREATEST(
                       0,
                       TIMESTAMPDIFF(SECOND, NOW(), DATE_ADD(created_at, INTERVAL 5 DAY))
                   ) AS seconds_until_expiry
            FROM report_index
            WHERE status_logico = 'ACTIVO'
              AND created_at > NOW() - INTERVAL 5 DAY
            """
        )
        resultados = cursor.fetchall()

        # Desencriptamos datos sensibles antes de enviarlos a la web/app
        for fila in resultados:
            fila['phone'] = desencriptar(fila.get('phone'))
            if 'security_answer' in fila:
                fila['security_answer'] = desencriptar(fila.get('security_answer'))

        return jsonify(resultados), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/reportar', methods=['POST'])
def reportar_objeto():
    """Guarda reporte en MySQL, valida imagen/OTP y crea/actualiza perfil en Mongo"""
    data = request.get_json(silent=True) if request.is_json else request.form
    if data is None:
        return jsonify({"error": "El cuerpo de la solicitud no es válido"}), 400
    email_actual = data.get('email')
    if not email_actual:
        return jsonify({"error": "Se requiere una cuenta para enviar reportes"}), 400

    conn = None
    cursor = None
    foto_guardada = None
    mongo_log_guardada = False
    advertencias = []
    try:
        try:
            lat = float(data.get('latitude', 0))
            lon = float(data.get('longitude', 0))
        except (TypeError, ValueError):
            return jsonify({"error": "La latitud y longitud deben ser numéricas"}), 400
        user_id = data.get('user_id', 'usuario_anonimo')
        conn = get_mysql_db()
        cursor = conn.cursor(dictionary=True)

        # Serializar envíos concurrentes de la misma cuenta.
        cursor.execute(
            """
            INSERT IGNORE INTO t1_users (email, user_id, last_lat, last_lon)
            VALUES (%s, %s, %s, %s)
            """,
            (email_actual, user_id, lat, lon)
        )
        usuario_nuevo = cursor.rowcount > 0
        cursor.execute(
            "SELECT email FROM t1_users WHERE email = %s FOR UPDATE",
            (email_actual,)
        )
        if not cursor.fetchone():
            return jsonify({"error": "No se pudo validar la cuenta"}), 500

        cursor.execute(
            """
            SELECT COUNT(*) AS total,
                   GREATEST(0, TIMESTAMPDIFF(
                       SECOND, NOW(), DATE_ADD(MIN(created_at), INTERVAL 1 DAY)
                   )) AS retry_after
            FROM report_rate_events
            WHERE email = %s AND created_at >= NOW() - INTERVAL 1 DAY
            """,
            (email_actual,)
        )
        diario = cursor.fetchone()
        cursor.execute(
            """
            SELECT COUNT(*) AS total,
                   GREATEST(0, TIMESTAMPDIFF(
                       SECOND, NOW(), DATE_ADD(MIN(created_at), INTERVAL 7 DAY)
                   )) AS retry_after
            FROM report_rate_events
            WHERE email = %s AND created_at >= NOW() - INTERVAL 7 DAY
            """,
            (email_actual,)
        )
        semanal = cursor.fetchone()

        if diario["total"] >= REPORT_DAILY_LIMIT or semanal["total"] >= REPORT_WEEKLY_LIMIT:

            conn.rollback()
            reintentos = []
            if diario["total"] >= REPORT_DAILY_LIMIT:
                reintentos.append(diario["retry_after"] or 0)
            if semanal["total"] >= REPORT_WEEKLY_LIMIT:
                reintentos.append(semanal["retry_after"] or 0)
            retry_after = max(1, *reintentos)
            response = jsonify({
                "error": "Límite de reportes alcanzado",
                "limite_diario": REPORT_DAILY_LIMIT,
                "limite_semanal": REPORT_WEEKLY_LIMIT,
                "reintentar_en_segundos": retry_after
            })
            response.headers["Retry-After"] = str(retry_after)
            return response, 429

    # 1. Validación de Teléfono con OTP (si viene en el formulario)
        telefono_raw = data.get('phone', '')
        codigo_otp = data.get('codigo_otp')
        if telefono_raw and codigo_otp and mongo_db_gamificacion is not None:
            reg_otp = mongo_db_gamificacion["verificaciones_telefono"].find_one({"telefono": telefono_raw})
            if not reg_otp or str(reg_otp.get("codigo")) != str(codigo_otp):
                conn.rollback()
                return jsonify({
                    "valida": False,
                    "error": "Código de verificación telefónica incorrecto o no solicitado"
                }), 400

        report_id = f"REP-{uuid.uuid4().hex[:8]}"

        # 2. Manejo y Validación Antifraude de Foto
        foto_nombre = "default.png"
        archivo = None

        if not request.is_json:
            archivo = request.files.get('foto')
            if archivo:
                resultado_validacion = validar_imagen(archivo, coleccion_fotos_validadas)
                advertencias = resultado_validacion.get("advertencias", [])

                if not resultado_validacion.get("valida"):
                    if coleccion_fotos_validadas is not None:
                        log_rechazo = crear_log_validacion(resultado_validacion, archivo, reporte_id=None)
                        log_rechazo["persistida"] = False
                        coleccion_fotos_validadas.insert_one(log_rechazo)

                    conn.rollback()
                    return jsonify({
                        "valida": False,
                        "error": "Imagen detectada como no válida o fraudulenta",
                        "motivo": resultado_validacion.get("motivo"),
                    }), 400

                extension = resultado_validacion.get("formato", "png").lower()
                foto_nombre = f"img_{uuid.uuid4().hex}.{extension}"
                foto_guardada = os.path.join(PHOTOS_PATH, foto_nombre)
                archivo.save(foto_guardada)

                if coleccion_fotos_validadas is not None:
                    log_aprobado = crear_log_validacion(resultado_validacion, archivo, reporte_id=report_id)
                    log_aprobado["persistida"] = True
                    coleccion_fotos_validadas.insert_one(log_aprobado)
                    mongo_log_guardada = True

        status_reporte = data.get('status', 'LOST')

        # 3. Guardar/Actualizar identidad del usuario en MySQL
        query_user = "INSERT IGNORE INTO t1_users (email, user_id, last_lat, last_lon) VALUES (%s, %s, %s, %s)"
        cursor.execute(query_user, (email_actual, user_id, lat, lon))

        # 4. Si el usuario es nuevo, creamos su perfil en MongoDB secundario
        if usuario_nuevo and coleccion_perfiles is not None:
            coleccion_perfiles.insert_one({
                "email_usuario": email_actual,
                "rol": "BUSCADOR",
                "emblema": "NUEVO",
                "fecha_registro": datetime.now().isoformat()
            })
            print("✅ Perfil de gamificación creado en MongoDB Secundario")

        # 5. Insertar el reporte en MySQL
        sec_q = data.get('security_question', 'N/A')
        sec_a = data.get('security_answer', 'N/A')

        query_reporte = """
            INSERT INTO report_index
            (id, user_id, email, desc_short, category, lat, lon, status, photo_url, phone, security_question, security_answer, status_logico)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
        """
        cursor.execute(query_reporte, (
            report_id, user_id, email_actual, data.get('description', 'Sin desc'),
            data.get('category', 'OTROS'), lat, lon, status_reporte, f"/photos/{foto_nombre}",
            encriptar(telefono_raw), sec_q, encriptar(sec_a)
        ))
        cursor.execute(
            "INSERT INTO report_rate_events (email) VALUES (%s)",
            (email_actual,)
        )
        cursor.execute(
            """
            SELECT UNIX_TIMESTAMP(DATE_ADD(created_at, INTERVAL 5 DAY)) AS expires_at_epoch,
                   GREATEST(
                       0,
                       TIMESTAMPDIFF(SECOND, NOW(), DATE_ADD(created_at, INTERVAL 5 DAY))
                   ) AS seconds_until_expiry
            FROM report_index
            WHERE id = %s
            """,
            (report_id,)
        )
        expiration = cursor.fetchone()
        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        if foto_guardada and os.path.isfile(foto_guardada):
            try:
                os.remove(foto_guardada)
            except OSError as cleanup_error:
                print(f"❌ No se pudo limpiar la foto {foto_guardada}: {cleanup_error}")
        if mongo_log_guardada and coleccion_fotos_validadas is not None:
            try:
                coleccion_fotos_validadas.delete_many({"reporte_id": report_id})
            except Exception as cleanup_error:
                print(f"❌ No se pudo limpiar el registro Mongo de {report_id}: {cleanup_error}")
        print(f"❌ Error al guardar reporte: {e}")
        return jsonify({"error": "Error al guardar", "detalle": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # 6. Motores en segundo plano (Geocercas y Gamificación)
    threading.Thread(target=procesar_geofencing, args=(lat, lon, data.get('description'), email_actual)).start()
    threading.Thread(target=evaluar_rango_usuario, args=(email_actual,)).start()

    return jsonify({
        "status": "success",
        "id": report_id,
        "advertencias": advertencias,
        "expires_at_epoch": expiration["expires_at_epoch"],
        "seconds_until_expiry": expiration["seconds_until_expiry"]
    }), 201


@app.route('/api/validar_imagen', methods=['POST'])
def validar_imagen_endpoint():
    """Valida una foto para que otro nodo pueda decidir si crea el reporte."""
    archivo = request.files.get('foto')
    resultado = validar_imagen(archivo, coleccion_fotos_validadas)
    if coleccion_fotos_validadas is not None:
        coleccion_fotos_validadas.insert_one(crear_log_validacion(resultado, archivo))
    resultado["aprobada"] = resultado["valida"]
    return jsonify(resultado), 200 if resultado["valida"] else 400

@app.route('/api/reportes/<path:report_id>', methods=['DELETE'])
def borrar_reporte(report_id):
    """Borrado Lógico del reporte"""
    try:
        conn = get_mysql_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE report_index SET status_logico = 'INACTIVO' WHERE id = %s", (report_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Reporte no encontrado"}), 404
        return jsonify({"status": "deleted", "id": report_id}), 200
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# ==========================================
#     ENDPOINTS SECUNDARIOS Y CONFIGURACIÓN
# ==========================================

@app.route('/api/puntos-seguros', methods=['GET'])
def puntos_seguros():
    """Catálogo de puntos seguros de encuentro"""
    try:
        conn = get_mysql_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM puntos_seguros")
        resultados = cursor.fetchall()
        return jsonify(resultados), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/config', methods=['GET'])
def config():
    """Configuración global del cliente para colores en el mapa"""
    return jsonify({
        "colores_mapa": {
            "pin_propio": "#2563EB",
            "pin_ajeno": "#EF4444",
            "pin_seguro": "#10B981"
        }
    }), 200

@app.route('/api/mis-alertas', methods=['GET'])
def mis_alertas():
    """Buzón de alertas de proximidad del Harvester"""
    email = request.args.get('email')
    if not email:
        return jsonify([]), 200
    try:
        conn = get_mysql_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM t7_buzon WHERE to_email = %s ORDER BY id DESC LIMIT 50", (email,))
        resultados = cursor.fetchall()
        return jsonify(resultados), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# ==========================================
#     ENDPOINTS DE COMUNIDAD Y GAMIFICACIÓN
# ==========================================

@app.route('/api/usuario/tipo', methods=['GET', 'POST'])
def gestionar_tipo():
    """Gestiona el rol/clasificación del usuario en MongoDB"""
    email = request.args.get('email')
    if request.method == 'POST':
        tipo = request.json.get('tipo')
        coleccion_perfiles.update_one({"email_usuario": email}, {"$set": {"rol": tipo}}, upsert=True)
        return jsonify({"status": "updated"}), 200
    else:
        perfil = coleccion_perfiles.find_one({"email_usuario": email})
        return jsonify({"tipo": perfil.get("rol", "BUSCADOR") if perfil else "BUSCADOR"}), 200

@app.route('/api/comentarios', methods=['GET'])
def get_comentarios():
    """Obtiene los comentarios de un reporte específico"""
    rid = request.args.get('report_id')
    if not rid:
        return jsonify([]), 200
    try:
        conn = get_mysql_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM t8_comentarios WHERE report_id = %s ORDER BY timestamp ASC", (rid,))
        res = cursor.fetchall()
        return jsonify(res), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/comentar', methods=['POST'])
def post_comentario():
    """Añade un nuevo comentario a un reporte"""
    data = request.json
    if not data or not data.get('report_id') or not data.get('text'):
        return jsonify({"error": "Faltan datos"}), 400
    try:
        conn = get_mysql_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO t8_comentarios (id, report_id, user_name, text, timestamp) VALUES (%s, %s, %s, %s, %s)",
            (f"COM-{uuid.uuid4().hex[:4]}", data.get('report_id'), data.get('user_name', 'Anónimo'), data.get('text'), int(time.time()))
        )
        conn.commit()
        return jsonify({"status": "ok"}), 201
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/perfil', methods=['GET'])
def obtener_perfil():
    """Trae el perfil del usuario desde MongoDB"""
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Falta el correo"}), 400

    perfil = coleccion_perfiles.find_one({"email_usuario": email}, {"_id": 0})
    if perfil:
        return jsonify(perfil), 200
    return jsonify({"error": "Perfil no encontrado"}), 404

# ==========================================
#     ARCHIVOS ESTÁTICOS
# ==========================================

@app.route('/photos/<path:filename>')
def serve_photos(filename):
    """Sirve las fotos subidas a la web"""
    return send_from_directory(PHOTOS_PATH, filename)

if __name__ == '__main__':
    print("🚀 API Principal de LostNet iniciada en el puerto 5000.")
    print("🌍 Orquestando MySQL (Local) y MongoDB (Secundario)...")
    # Solo para desarrollo local: en producción la API corre con Gunicorn.
    app.run(host='0.0.0.0', port=5000, threaded=True)  # nosec B104
