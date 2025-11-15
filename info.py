import socket
import threading
import time
import sys


PORT = 54726  # фиксированный порт для проверки


def diag_log(msg):
    print(f"[DIAG] {msg}")


def server_thread():
    diag_log("Создаем сокет...")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        s.bind(("", PORT))
    except Exception as e:
        diag_log(f"ОШИБКА BIND: {e}")
        sys.exit(1)

    diag_log(f"Порт {PORT} успешно открыт и привязан.")
    s.listen(1)
    diag_log("LISTEN успешно выполнен.")

    diag_log(">>> ОЖИДАЮ ПОДКЛЮЧЕНИЯ В ACCEPT()...")
    try:
        conn, addr = s.accept()
    except Exception as e:
        diag_log(f"ОШИБКА ACCEPT: {e}")
        sys.exit(1)

    diag_log(f"ПОДКЛЮЧЕНИЕ ПРИНЯТО! {addr}")
    conn.sendall(b"CONNECTED_OK")
    conn.close()
    s.close()


def main():
    diag_log("=== ТЕСТОВЫЙ СЕРВЕР ДЛЯ ПРОВЕРКИ ПОДКЛЮЧЕНИЯ ===")
    diag_log(f"Используем порт: {PORT}")

    t = threading.Thread(target=server_thread)
    t.start()

    # Проверка доступности порта через OS
    time.sleep(1)
    diag_log("Проверяем, действительно ли порт слушает...")

    import subprocess
    try:
        out = subprocess.check_output(
            f"netstat -ano | findstr {PORT}",
            shell=True
        ).decode()
        diag_log("Результат netstat:")
        print(out)
    except:
        diag_log("netstat ничего не показал.")

    diag_log("Теперь попробуй ПОДКЛЮЧИТЬСЯ АДМИНОМ.")
    diag_log("Если accept НЕ сработает → значит проблема до подключения.")

    t.join()


if __name__ == "__main__":
    main()
