# Guía de instalación y ejecución con Docker

Este documento explica cómo levantar el proyecto **ANPR-VISION-MICROSERVICE** usando **Docker** y **Docker Compose**.

---
solo prueba
## 1. Requisitos previos
- Tener instalado **Docker Engine** y **Docker Compose**.
- Verificar con:
```bash
docker --version
docker compose version
```


## 2. Construir la imagen
```bash
docker compose build
```

---

## 3. Levantar el servicio
```bash
docker compose up
```
o en segundo plano:
```bash
docker compose up -d
```

---

## 4. Acceder a la API
- Navegador: [http://localhost:8000](http://localhost:8000)
- Documentación Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 5. Detener el servicio
```bash
docker compose down
```
