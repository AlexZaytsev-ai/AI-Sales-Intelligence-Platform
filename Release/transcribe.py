
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "Release"
INCOMING = ROOT / "incoming"
SENT = ROOT / "sent"

SENT.mkdir(exist_ok=True)

# Читаем API-ключ
env_text = (ROOT / ".env").read_text(encoding="utf-8-sig").strip()
api_key = env_text.split("=", 1)[1]

# Находим все WAV-файлы
audio_files = sorted(INCOMING.glob("*.wav"))

if not audio_files:
    print("Новых записей нет")

for audio in audio_files:
    print(f"Обрабатываем: {audio.name}")

    try:
        # 1. Расшифровка
        subprocess.run([
            str(RELEASE / "whisper-cli.exe"),
            "-m", str(RELEASE / "ggml-small.bin"),
            "-f", str(audio),
            "-l", "ru",
            "-otxt",
            "-ng"
        ], cwd=RELEASE, check=True)

        # 2. Читаем расшифровку
        txt_file = Path(str(audio) + ".txt")
        transcript = txt_file.read_text(encoding="utf-8")

        # 3. Отправляем в n8n
        data = json.dumps({
            "call_id": audio.stem,
            "transcript": transcript
        }, ensure_ascii=False).encode("utf-8")

        request = urllib.request.Request(
            "https://ai.n8npractic.ru/webhook/ai-sales/transcript",
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key
            },
            method="POST"
        )

        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.load(response)

        if not isinstance(result, dict):
            raise RuntimeError("n8n вернул неожиданный формат ответа")

        if result.get("ID звонка") != audio.stem:
            raise RuntimeError("n8n не подтвердил завершение обработки звонка")

        print(f"Обработка подтверждена: {audio.stem}")

        # 4. Перемещаем отправленные файлы
        shutil.move(str(audio), str(SENT / audio.name))
        shutil.move(str(txt_file), str(SENT / txt_file.name))

        print(f"Отправлено: {audio.stem}")

    except Exception as error:
        print(f"Ошибка обработки {audio.name}: {error}")
