# Imagen base con Python 3.12 (la versión usada y validada en desarrollo).
# Se usa Docker en vez del build nativo de Render porque el sandbox nativo
# tiene el filesystem en solo lectura (falla apt-get y la compilación de
# wheels como pydantic-core con Rust) y además Render eligió Python 3.14,
# para el que no hay wheels de pydantic-core.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Librerías de sistema que OpenCV necesita en runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libsm6 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Primero las dependencias (aprovecha la caché de capas de Docker).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Después el código.
COPY . .

# Render provee $PORT en runtime; arrancamos uvicorn en ese puerto
# (default 8000 para ejecución local con docker run sin -e PORT).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
