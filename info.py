import requests
import subprocess
import time

COMMAND_URL = "https://raw.githubusercontent.com/username/repo/main/command.txt"
last_cmd = ""

# Карта цифровых команд на реальные команды ОС (пример для Windows)
COMMANDS = {
    "1": "shutdown /s /t 5",                 # Выключить ПК через 5 секунд
    "2": "taskkill /F /IM chrome.exe",      # Закрыть все процессы Chrome (вкладки)
    "3": "notepad.exe",                      # Запустить Блокнот
    "4": "calc.exe",                        # Запустить Калькулятор
    "5": "ipconfig",                        # Показать конфигурацию сети
    "6": "dir",                            # Показать список файлов текущей папки
    "7": "explorer.exe",                    # Открыть Проводник
    "8": "mspaint.exe",                     # Запустить Paint
    "9": "taskmgr.exe",                     # Запустить Диспетчер задач
    "10": "echo Hello from command 10",     # Просто вывод в консоль
}

print("[CLIENT] Запущен, ожидаю команд...")

while True:
    try:
        cmd = requests.get(COMMAND_URL, timeout=5).text.strip()

        if cmd and cmd != last_cmd:
            print(f"[CLIENT] Получена команда: {cmd}")
            last_cmd = cmd

            if cmd in COMMANDS:
                real_cmd = COMMANDS[cmd]
                print(f"[CLIENT] Выполняю: {real_cmd}")
                subprocess.Popen(real_cmd, shell=True)
            else:
                print("[CLIENT] Команда не распознана.")

        else:
            print("[CLIENT] Нет новой команды или команда не изменилась.")

    except Exception as e:
        print("[CLIENT] Ошибка:", e)

    time.sleep(10)
