import socket
import subprocess
import datetime
import urllib.request
import threading
import sys
import os
import io

try:
    import pystray
    from PIL import Image, ImageDraw, ImageGrab
except ImportError:
    pystray = None

import psutil
import platform
import mss
import numpy as np
import cv2
import time


def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def get_public_ip():
    try:
        with urllib.request.urlopen('https://api.ipify.org') as response:
            ip = response.read().decode('utf-8')
    except Exception:
        ip = 'Не удалось получить публичный IP'
    return ip


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def create_image():
    width = 64
    height = 64
    color1 = (0, 0, 0)
    color2 = (0, 200, 0)

    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.ellipse((8, 8, width - 8, height - 8), fill=color2)
    return image


def minimize_to_tray(icon):
    icon.run_detached()


def send_file(conn, filename):
    if not os.path.isfile(filename):
        conn.sendall(b'ERROR: file not found')
        return
    conn.sendall(b'READY')
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            conn.sendall(chunk)
    conn.sendall(b'__END__')


def receive_file(conn, filename):
    conn.sendall(b'READY')
    with open(filename, 'wb') as f:
        while True:
            chunk = conn.recv(4096)
            if chunk.endswith(b'__END__'):
                f.write(chunk[:-7])
                break
            f.write(chunk)
    conn.sendall(b'UPLOAD_DONE')


def screenshot(conn):
    log("Делаем скриншот...")
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = sct.grab(monitor)
        img_pil = Image.frombytes('RGB', img.size, img.rgb)
        buf = io.BytesIO()
        img_pil.save(buf, format='PNG')
        data = buf.getvalue()
        conn.sendall(b'READY')
        # Отправляем размер
        conn.sendall(len(data).to_bytes(8, 'big'))
        # Отправляем данные
        conn.sendall(data)
        conn.sendall(b'__END__')
    log("Скриншот отправлен.")


def record_video(conn, seconds):
    log(f"Запись видео {seconds} секунд...")
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    filename = "temp_video.avi"

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        width = monitor['width']
        height = monitor['height']

        out = cv2.VideoWriter(filename, fourcc, 15.0, (width, height))

        start_time = time.time()
        while (time.time() - start_time) < seconds:
            img = sct.grab(monitor)
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            out.write(frame)

        out.release()

    send_file(conn, filename)
    os.remove(filename)
    log("Видео отправлено.")


def get_process_list():
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            processes.append(f"{proc.info['pid']}: {proc.info['name']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return "\n".join(processes)


def get_system_info():
    info = []
    info.append(f"Платформа: {platform.system()} {platform.release()}")
    info.append(f"Процессор: {platform.processor()}")
    info.append(f"Архитектура: {platform.architecture()[0]}")
    info.append(f"Память: {round(psutil.virtual_memory().total / (1024 ** 3), 2)} GB")
    info.append(f"Доступно памяти: {round(psutil.virtual_memory().available / (1024 ** 3), 2)} GB")
    info.append(f"Загрузка CPU: {psutil.cpu_percent(interval=1)} %")
    return "\n".join(info)


def run_server():
    port = find_free_port()
    HOST = ''

    local_ip = get_local_ip()
    public_ip = get_public_ip()

    icon = None
    if pystray:
        icon = pystray.Icon('server_tray', create_image(), 'Python Server')

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
            s.listen(1)
            log(f"Сервер поднят и слушает на порту {port}")
            log(f"Локальный IP для подключения: {local_ip}")
            log(f"Публичный IP для подключения: {public_ip}")
            log("Ждем подключения админа...")

            conn, addr = s.accept()
            with conn:
                log(f"Подключился админ: {addr}")

                if icon:
                    threading.Thread(target=minimize_to_tray, args=(icon,), daemon=True).start()

                while True:
                    data = conn.recv(4096)
                    if not data:
                        log("Соединение закрыто админом")
                        break
                    cmd = data.decode(errors='replace').strip()
                    log(f"Получена команда: {cmd}")

                    if cmd.lower() == 'exit':
                        log("Получена команда выхода. Завершение работы.")
                        break

                    # Обработка upload/download
                    if cmd.startswith('upload '):
                        filename = cmd[7:].strip()
                        receive_file(conn, filename)
                        continue

                    if cmd.startswith('download '):
                        filename = cmd[9:].strip()
                        send_file(conn, filename)
                        continue

                    if cmd == 'screenshot':
                        screenshot(conn)
                        continue

                    if cmd.startswith('record'):
                        parts = cmd.split()
                        seconds = 5
                        if len(parts) > 1 and parts[1].isdigit():
                            seconds = int(parts[1])
                        record_video(conn, seconds)
                        continue

                    if cmd == 'processes':
                        plist = get_process_list()
                        conn.sendall(plist.encode())
                        continue

                    if cmd == 'sysinfo':
                        sinfo = get_system_info()
                        conn.sendall(sinfo.encode())
                        continue

                    if cmd == 'shutdown':
                        log("Получена команда выключения системы.")
                        if platform.system() == "Windows":
                            subprocess.Popen("shutdown /s /t 1", shell=True)
                        else:
                            subprocess.Popen("shutdown now", shell=True)
                        break

                    # Выполняем команду в системе
                    try:
                        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
                        response = output.decode(errors='replace')
                    except subprocess.CalledProcessError as e:
                        response = f"Ошибка выполнения команды:\n{e.output.decode(errors='replace')}"
                    except Exception as e:
                        response = f"Исключение при выполнении: {str(e)}"

                    conn.sendall(response.encode())

        except Exception as e:
            log(f"Ошибка сервера: {e}")
        finally:
            if icon:
                icon.stop()


def on_quit(icon, item):
    icon.stop()
    sys.exit()


def main():
    icon = None
    if pystray:
        icon = pystray.Icon('server_tray', create_image(), 'Python Server')
        icon.menu = pystray.Menu(pystray.MenuItem('Выход', on_quit))
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    if icon:
        icon.run()
    else:
        thread.join()


if __name__ == '__main__':
    main()
