import socket
import subprocess
import datetime
import urllib.request

def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))  # ОС выделит свободный порт
    port = s.getsockname()[1]
    s.close()
    return port

def get_local_ip():
    # Получаем локальный IP адрес машины
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
    # Запрашиваем публичный IP через внешний сервис
    try:
        with urllib.request.urlopen('https://api.ipify.org') as response:
            ip = response.read().decode('utf-8')
    except Exception:
        ip = 'Не удалось получить публичный IP'
    return ip

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def run_server():
    port = find_free_port()
    HOST = ''  # слушать на всех интерфейсах

    local_ip = get_local_ip()
    public_ip = get_public_ip()

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
                while True:
                    data = conn.recv(4096)
                    if not data:
                        log("Соединение закрыто админом")
                        break
                    cmd = data.decode().strip()
                    log(f"Получена команда: {cmd}")

                    if cmd.lower() == 'exit':
                        log("Получена команда выхода. Завершение работы.")
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

if __name__ == '__main__':
    run_server()