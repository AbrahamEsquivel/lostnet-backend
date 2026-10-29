# LostNet API

API REST de LostNet (Flask) con su pipeline de CI/CD en GitHub Actions.

## Estructura

| Ruta | Contenido |
|---|---|
| `api.py` | API principal (reportes, geovallado, comentarios, alertas) |
| `image_validator.py` | Validación antifraude de imágenes |
| `migrar_fragmento.py` | Migración de fragmentos de usuarios de MySQL a MongoDB |
| `purge_expired_reports.py` | Purga de reportes vencidos (se ejecuta con cron) |
| `db/schema.sql` | Estructura de las tablas usada por las pruebas de integración |
| `tests/unit/` | Pruebas unitarias (sin bases de datos) |
| `tests/integration/` | Pruebas de integración contra MySQL y MongoDB reales |
| `.github/workflows/ci.yml` | Pipeline de CI/CD |
| `Dockerfile` | Imagen de la API |

## Configuración

La API lee su configuración de variables de entorno (ver `.env.example`).
Las contraseñas y la clave `secret.key` **nunca** se suben al repositorio.

## Pipeline (4C)

| Etapa | Job | Herramienta |
|---|---|---|
| Descarga del código | todos | `actions/checkout` |
| Entorno y dependencias | todos | `actions/setup-python`, `pip` |
| Pruebas unitarias | `pruebas-unitarias` | pytest, pytest-cov |
| Pruebas de integración | `pruebas-integracion` | pytest + servicios MySQL 8.4 y MongoDB 7 |
| Análisis estático | `analisis-estatico` | Ruff |
| Análisis de vulnerabilidades | `vulnerabilidades` | pip-audit, Bandit |
| Empaquetado | `empaquetado` | Docker → GitHub Container Registry |
| Despliegue (opcional) | `despliegue` | runner self-hosted en el servidor |

## Ejecutar las pruebas localmente

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/unit -v

# Integración (requiere MySQL con db/schema.sql cargado y MongoDB)
export MYSQL_HOST=127.0.0.1 MYSQL_USER=root MYSQL_PASSWORD=... MONGO_URI=mongodb://127.0.0.1:27017/
pytest tests/integration -v
```
