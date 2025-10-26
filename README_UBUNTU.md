# Guía de instalación y configuración en Ubuntu (Python 3.12.3)

Este documento explica cómo configurar el entorno local en **Ubuntu/Linux** para ejecutar el proyecto **ANPR-VISION-MICROSERVICE**.

---

## 1. Instalar Python 3.12.3

Actualizar repositorios:
```bash
sudo apt update && sudo apt upgrade -y
```

Verificar la instalación:
```bash
python3.12 --version
```

---

## 2. Actualizar pip
```bash
python3.12 -m pip install --upgrade pip
```

---

## 3. Crear entorno virtual
```bash
cd ANPR-VISION-MICROSERVICE
python3.12 -m venv .venv
```

---

## 4. Activar entorno virtual
```bash
source .venv/bin/activate
```

---

## 5. Instalar dependencias
```bash
pip install -r requirements.txt
```

---

## 6. Ejecutar el proyecto
```bash
python src/workers/main_worker.py
```
o con Uvicorn:
```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```


pip install "torch==2.2.2+cpu" "torchvision==0.15.2+cpu" "torchaudio==2.2.2+cpu" -f https://download.pytorch.org/whl/torch_stable.html
