# Guía de instalación y configuración en Windows (Python 3.12.3)

Este documento explica cómo configurar el entorno local en **Windows** para ejecutar el proyecto **ANPR-VISION-MICROSERVICE**.

---

## 1. Instalar Python 3.12.3

1. Ir a la página oficial: [Python Downloads](https://www.python.org/downloads/release/python-3123/)
2. Descargar el instalador para Windows (ejemplo: `Windows installer (64-bit)`).
3. Ejecutar el instalador y marcar la casilla **"Add Python to PATH"**.
4. Verificar la instalación desde PowerShell:
   ```powershell
   python --version
   ```

---

## 2. Actualizar pip
```powershell
python -m pip install --upgrade pip
```

---

## 3. Crear entorno virtual
```powershell
cd ANPR-VISION-MICROSERVICE
python -m venv .venv

o

py -3.12 -m venv .venv
```

---

## 4. Activar entorno virtual
En PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

En CMD clásico:
```cmd
.venv\Scripts\activate.bat
```

---

## 5. Instalar dependencias
```powershell
pip install -r requirements.txt
```

---

## 6. Ejecutar el proyecto
```powershell
py -m src.workers.main_worker
```
o con Uvicorn:
```powershell
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

huggingface-cli download keremberke/yolov5n-license-plate best.pt --local-dir ./model --local-dir-use-symlinks False

```

pip install "torch==2.2.2+cpu" "torchvision==0.15.2+cpu" "torchaudio==2.2.2+cpu" -f https://download.pytorch.org/whl/torch_stable.html



pip install --upgrade pip setuptools wheel
pip install "torch==2.2.2+cpu" -f https://download.pytorch.org/whl/torch_stable.html
# instala torchvision y torchaudio compatibles con torch 2.2.2 (CPU)
pip install "torchvision==0.17.2+cpu" "torchaudio==2.2.2+cpu" -f https://download.pytorch.org/whl/torch_stable.html
python -c "import torch, torchvision, torchaudio; print('torch', torch.__version__, 'cuda=', torch.cuda.is_available(), 'torch.version.cuda=', torch.version.cuda); print('torchvision', torchvision.__version__); print('torchaudio', torchaudio.__version__)"
