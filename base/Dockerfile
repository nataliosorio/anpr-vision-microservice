# ================================
#  ANPR-VISION MICRO BASE IMAGE
#  Python 3.12.10 (Bookworm, full)
# ================================

FROM python:3.12.10-bookworm

WORKDIR /app

# Evitar prompts interactivos y mejorar rendimiento
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 🔧 Dependencias del sistema necesarias para OpenCV, Torch, YOLO, EasyOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config cmake \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libjpeg-dev libpng-dev libtiff-dev \
    libfreetype6-dev libatlas-base-dev \
    netcat-traditional wget curl git && \
    rm -rf /var/lib/apt/lists/*

# Copiar el archivo de requerimientos
COPY requirements.txt .

# 🐍 Instalar dependencias Python (preferentemente binarias precompiladas)
RUN pip install --upgrade pip setuptools wheel && \
    pip install --prefer-binary -r requirements.txt

# Imagen final base
CMD ["python3"]

