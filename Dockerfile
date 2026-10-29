FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py image_validator.py migrar_fragmento.py purge_expired_reports.py ./

# Usuario sin privilegios para ejecutar la API
RUN useradd --create-home lostnet && mkdir -p /app/photos && chown -R lostnet /app
USER lostnet

EXPOSE 5001
CMD ["gunicorn", "-b", "0.0.0.0:5001", "--workers", "1", "--threads", "4", "api:app"]
