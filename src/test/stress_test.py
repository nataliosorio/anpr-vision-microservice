import subprocess
import time
import psutil
import threading

LOG_INTERVAL = 5  # segundos

def monitor_cpu():
    while True:
        cpu = psutil.cpu_percent(interval=1)
        print(f"🔋 CPU Usage: {cpu}%")
        time.sleep(LOG_INTERVAL)

def monitor_threads():
    while True:
        t = threading.enumerate()
        print(f"🧵 Threads activos: {len(t)}")
        time.sleep(LOG_INTERVAL)

def monitor_fps():
    import sqlite3
    conn = sqlite3.connect("anpr_micro.db")
    cur = conn.cursor()

    while True:
        try:
            cur.execute("SELECT camera_id, last_fps FROM cameras")
            rows = cur.fetchall()
            for cam, fps in rows:
                print(f"📸 Cam {cam} → {fps} FPS")
        except:
            pass
        time.sleep(LOG_INTERVAL)

def main():
    # iniciar microservicio
    print("🚀 Iniciando microservicio...")
    p = subprocess.Popen(["python", "-m", "src.workers.main_worker"])

    # lanzar monitores
    threading.Thread(target=monitor_cpu, daemon=True).start()
    threading.Thread(target=monitor_threads, daemon=True).start()
    # threading.Thread(target=monitor_fps, daemon=True).start()

    print("📊 Monitores iniciados. Ejecutando stress...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Terminando...")
        p.terminate()

if __name__ == "__main__":
    main()
