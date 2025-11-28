import subprocess
import time
import psutil
import threading
import sqlite3
import os
import signal
import sys

from src.infrastructure.Camera.camera_repository import CameraRepository
from src.domain.Models.camera import Camera


LOG_INTERVAL = 5   # cada 5 seg se imprimen métricas
CAMERAS = 5        # número de cámaras fake a simular
VIDEO_FILE = "camera.mp4"  # usa el mismo video para todas


# ==========================================================
# CREAR CÁMARAS FAKE EN DB SI NO EXISTEN
# ==========================================================
def setup_fake_cameras():
    repo = CameraRepository()
    existing = repo.get_all()

    if len(existing) >= CAMERAS:
        print("📸 Cámaras ya existen en DB, no se crean nuevas.")
        return

    print("⚠️ Creando cámaras fake en la base de datos...")

    for i in range(1, CAMERAS + 1):
        cam = Camera(
            camera_id=str(i),
            name=f"FakeCam-{i}",
            parking_id=1,
            url=f"fake://{VIDEO_FILE}"
        )
        repo.save(cam)

    print(f"🎥 {CAMERAS} cámaras fake registradas correctamente.\n")


# ==========================================================
# MONITOR DE CPU GLOBAL
# ==========================================================
def monitor_cpu():
    print("🟢 CPU Monitor listo.")
    while True:
        cpu = psutil.cpu_percent(interval=1)
        print(f"🔋 CPU Usage: {cpu}%")
        time.sleep(LOG_INTERVAL)


# ==========================================================
# MONITOR DE THREADS
# ==========================================================
def monitor_threads():
    print("🟢 Thread Monitor listo.")
    while True:
        t = threading.enumerate()
        print(f"🧵 Threads activos: {len(t)}")
        time.sleep(LOG_INTERVAL)


# ==========================================================
# MONITOR DE FPS REGISTRADOS POR CADA CÁMARA
# ==========================================================
def monitor_fps():
    print("🟢 FPS Monitor listo.")
    conn = sqlite3.connect("anpr_micro.db")
    cur = conn.cursor()

    while True:
        try:
            cur.execute("SELECT camera_id, last_fps FROM cameras ORDER BY camera_id")
            rows = cur.fetchall()

            if rows:
                for cam, fps in rows:
                    print(f"📸 Cam {cam} → {fps:.2f} FPS")
            else:
                print("⚠️ Aún no hay métricas de FPS.")
        except Exception as ex:
            print(f"⚠️ Error monitor_fps: {ex}")

        time.sleep(LOG_INTERVAL)


# ==========================================================
# MONITOR DE THROUGHPUT KAFKA (EVENTOS/S)
# ==========================================================
def monitor_kafka_throughput():
    """
    KafkaPublisher en tu micro imprime logs por evento.
    Aquí simulamos throughput leyendo del archivo de logs del micro.
    """
    print("🟢 Kafka Throughput Monitor listo.")

    log_file = "micro.log"
    events_prev = 0

    # si no existe el archivo se crea
    open(log_file, "a").close()

    while True:
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()
                events = sum(1 for line in lines if "Published detection" in line)
        except:
            events = 0

        diff = events - events_prev
        events_prev = events

        print(f"📡 Kafka Throughput: {diff}/s")

        time.sleep(LOG_INTERVAL)


# ==========================================================
# CORRER EL MICROSERVICIO
# ==========================================================
def start_microservice():
    print("🚀 Iniciando microservicio ANPR...")

    p = subprocess.Popen(
        ["python", "-m", "src.workers.main_worker"],
        stdout=open("micro.log", "w"),
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid  # permite matar todo el grupo de procesos
    )
    return p


# ==========================================================
# KILL CLEAN
# ==========================================================
def terminate_process(p):
    print("🛑 Terminando microservicio...")
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except:
        pass


# ==========================================================
# MAIN RUNNER
# ==========================================================
def main():
    print("\n======================")
    print("   🧪 STRESS RUNNER   ")
    print("======================\n")

    # 1. Crear cámaras fake
    setup_fake_cameras()

    # 2. Iniciar microservice
    p = start_microservice()

    time.sleep(3)
    print("📊 Monitores iniciados...\n")

    # 3. Lanzar monitores
    threading.Thread(target=monitor_cpu, daemon=True).start()
    threading.Thread(target=monitor_threads, daemon=True).start()
    threading.Thread(target=monitor_fps, daemon=True).start()
    # threading.Thread(target=monitor_kafka_throughput, daemon=True).start()

    # 4. Mantener runner vivo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        terminate_process(p)
        print("👋 Stress Test finalizado.")


if __name__ == "__main__":
    main()
