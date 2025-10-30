# ================================
#   BUILD STAGE
# ================================
FROM python:3.12-slim AS build

WORKDIR /app

# Dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 wget curl netcat-traditional && \
    rm -rf /var/lib/apt/lists/*

# Copiar requerimientos
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copiar código fuente completo
COPY . .

# ================================
#   RUNTIME STAGE
# ================================
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 netcat-traditional && \
    rm -rf /var/lib/apt/lists/*

# Copiar entorno y dependencias
COPY --from=build /usr/local /usr/local
COPY --from=build /app /app

# Variables por defecto
ENV PYTHONUNBUFFERED=1 \
    APP_ENV=production

# Comando por defecto: worker
CMD ["python", "-m", "src.workers.main_worker"]

