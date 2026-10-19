import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
import requests
import time
import os
import uuid

# ==== ВАШИ ДАННЫЕ ====
VK_TOKEN = "vk1.a.mKFSjiuCaAzcIRsR6GA-r3wwISYsZOkxOmS206DCzKOTFurcWlSr5mm9FgojBVXcURWJa3hVS_qmsod2t__QwIMy9MRYUyGY167W8w2Z3LD-aQyIcUvmZMorlO8qxBoXPq5phGJ0tJQ7aFcGblRuFwW0oOCoZOd2vECs8MJ9CteJ51PRzbGhut_Genkz4a_dFtMZ3uz1RjT5a78Ei0Gwfg"
TG_TOKEN = "8866177597:AAEdJqpL6SqXGnX2q1eOKTHUwHCqkkDkOHs"
TG_CHAT_ID = 1163289840  # ваш id из @userinfobot
PROXY_URL = "https://autumn-band-ae30.korchemkins0.workers.dev"
# PROXY_URL = "https://api.telegram.org"
# =====================


DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()


# ---------- ВСПОМОГАТЕЛЬНОЕ ----------

def tg_url(method):
    return f"{PROXY_URL}/bot{TG_TOKEN}/{method}"


def send_text(text):
    try:
        r = requests.post(tg_url("sendMessage"), json={
            "chat_id": TG_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=30)
        if r.status_code != 200:
            print(f"TG text error: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Ошибка отправки текста: {e}")


def send_file(method, file_path, field_name, mime_type, caption=None):
    """Отправка одиночного файла в Telegram с подписью"""
    try:
        with open(file_path, "rb") as f:
            files = {field_name: (os.path.basename(file_path), f, mime_type)}
            data = {"chat_id": TG_CHAT_ID}
            if caption:
                data["caption"] = caption
                data["parse_mode"] = "HTML"

            r = requests.post(tg_url(method), data=data, files=files, timeout=120)
            if r.status_code != 200:
                print(f"TG {method} error: {r.status_code} - {r.text}")
            else:
                print(f"Отправлено: {method} ({os.path.basename(file_path)})")
    except Exception as e:
        print(f"Ошибка отправки файла {method}: {e}")


def download_file(url, ext):
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(DOWNLOAD_DIR, filename)
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)
    return path


def safe_delete(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def get_user_name(user_id):
    try:
        info = vk.users.get(user_ids=user_id)[0]
        return f"{info['first_name']} {info['last_name']}"
    except Exception:
        return f"id{user_id}"


# ---------- ОБРАБОТКА ----------

def handle_message(event):
    if event.from_me:
        return

    text = event.text or ""
    sender = get_user_name(event.user_id)
    header = f"📩 <b>{sender}</b>"

    # Нет вложений — просто текст
    if not event.attachments:
        send_text(f"{header}\n{text}" if text else header)
        return

    try:
        msg = vk.messages.getById(message_ids=event.message_id)["items"][0]
    except Exception as e:
        print(f"Ошибка getById: {e}")
        if text:
            send_text(f"{header}\n{text}")
        return

    temp_files = []
    caption_used = False

    for attach in msg.get("attachments", []):
        a_type = attach.get("type")

        # ---- ФОТО ----
        if a_type == "photo":
            sizes = attach["photo"]["sizes"]
            url = max(sizes, key=lambda x: x["width"])["url"]
            try:
                path = download_file(url, "jpg")
                temp_files.append(path)
                if text and not caption_used:
                    cap = f"{header}\n{text}"
                    caption_used = True
                else:
                    cap = f"{header}\n📷 Фото"
                send_file("sendPhoto", path, "photo", "image/jpeg", caption=cap)
            except Exception as e:
                print(f"Ошибка фото: {e}")

        # ---- ГОЛОСОВОЕ ----
        elif a_type == "audio_message":
            am = attach["audio_message"]
            url = am.get("link_ogg") or am.get("link_mp3")
            ext = "ogg" if am.get("link_ogg") else "mp3"
            mime = "audio/ogg" if ext == "ogg" else "audio/mpeg"
            try:
                path = download_file(url, ext)
                temp_files.append(path)
                cap = f"{header}\n🎤 Голосовое"
                send_file("sendVoice", path, "voice", mime, caption=cap)
            except Exception as e:
                print(f"Ошибка голосового: {e}")

        # ---- ДОКУМЕНТ ----
        elif a_type == "doc":
            doc = attach["doc"]
            ext = doc.get("ext", "bin")
            url = doc["url"]
            try:
                if ext == "ogg":
                    path = download_file(url, "ogg")
                    temp_files.append(path)
                    cap = f"{header}\n🎤 Голосовое"
                    send_file("sendVoice", path, "voice", "audio/ogg", caption=cap)
                else:
                    path = download_file(url, ext)
                    temp_files.append(path)
                    cap = f"{header}\n📎 Документ: {doc.get('title', 'файл')}"
                    send_file("sendDocument", path, "document",
                              "application/octet-stream", caption=cap)
            except Exception as e:
                print(f"Ошибка документа: {e}")

        # ---- ВИДЕО / КРУЖОК ----
        elif a_type == "video":
            video = attach.get("video", {})
            video_url = None
            files_field = video.get("files") or {}
            for key in ("mp4_240", "mp4_360", "mp4_480", "mp4_720"):
                if files_field.get(key):
                    video_url = files_field[key]
                    break

            if video_url:
                try:
                    path = download_file(video_url, "mp4")
                    temp_files.append(path)
                    cap = f"{header}\n🎥 Видео"
                    send_file("sendVideoNote", path, "video_note", "video/mp4", caption=cap)
                except Exception as e:
                    print(f"Ошибка видео: {e}")
            else:
                send_text(f"{header}\n🎥 [видео — ссылка недоступна]")

        # ---- СТИКЕР / ГРАФФИТИ ----
        elif a_type in ("sticker", "graffiti"):
            images = attach[a_type].get("images", [])
            if images:
                url = max(images, key=lambda x: x.get("width", 0))["url"]
                try:
                    path = download_file(url, "png")
                    temp_files.append(path)
                    label = "🖼 Граффити" if a_type == "graffiti" else "😀 Стикер"
                    cap = f"{header}\n{label}"
                    send_file("sendPhoto", path, "photo", "image/png", caption=cap)
                except Exception as e:
                    print(f"Ошибка стикера: {e}")

        # ---- ПОСТ ИЗ ГРУППЫ ----
        elif a_type == "wall":
            wall = attach.get("wall", {})
            owner_id = wall.get("from_id") or wall.get("owner_id")
            post_id = wall.get("id")
            wall_text = wall.get("text", "")
            link = f"https://vk.com/wall{owner_id}_{post_id}"
            msg_text = f"{header}\n📝 <b>Пост из VK</b>\n{wall_text}\n{link}"
            send_text(msg_text)
            caption_used = True

        # ---- КОММЕНТАРИЙ ----
        elif a_type == "wall_reply":
            reply = attach.get("wall_reply", {})
            owner_id = reply.get("owner_id")
            reply_id = reply.get("id")
            reply_text = reply.get("text", "")
            link = f"https://vk.com/wall{owner_id}_{reply.get('post_id', '')}?reply={reply_id}"
            msg_text = f"{header}\n💬 <b>Комментарий из VK</b>\n{reply_text}\n{link}"
            send_text(msg_text)
            caption_used = True

    # Текст, который не прикрепился к вложениям
    if text and not caption_used:
        send_text(f"{header}\n{text}")

    for p in temp_files:
        safe_delete(p)


def main():
    longpoll = VkLongPoll(vk_session)
    print("Бот запущен, слушаю...")
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            try:
                handle_message(event)
            except Exception as e:
                print(f"Ошибка обработки: {e}")


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(f"Критическая ошибка: {e}. Перезапуск через 10 сек...")
            time.sleep(10)