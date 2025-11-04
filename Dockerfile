# ================================
#   ANPR-VISION MICRO (Runtime)
#   Basado en imagen precompilada con dependencias
# ================================

FROM anibal2504/anpr-python-deps:3.12-v0

# Establecer directorio de trabajo
WORKDIR /app

# Copiar únicamente el código fuente del microservicio
# (No requirements.txt, ya vienen instalados en la imagen base)
COPY . .

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1 \
    APP_ENV=production

# Comando por defecto: ejecutar el worker principal
CMD ["python", "-m", "src.workers.main_worker"]

