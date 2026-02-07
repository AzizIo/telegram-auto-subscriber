import asyncio
import os
import random
import ctypes
from colorama import Fore, Style, init
from telethon.tl.types import DialogFilter
from telethon.tl.types import DialogFilter
from telethon.tl.functions.messages import GetDialogFiltersRequest, UpdateDialogFilterRequest
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    UserAlreadyParticipantError,
    InviteHashInvalidError,
    InviteHashExpiredError,
    SessionPasswordNeededError
)

from telethon.tl.types import InputPeerSelf

from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import (
    ImportChatInviteRequest,
    GetDialogFiltersRequest,
    UpdateDialogFilterRequest
)
from telethon.tl.types import DialogFilter
init()

CHATS_FILE = "chats.txt"
SESSIONS_DIR = 'Sessions'
API_ID = ''
API_HASH = ''
FOLDER_NAME = "Auto Subs"

# ================== ТАЙМИНГИ ==================

JOIN_DELAY_MIN = 60
JOIN_DELAY_MAX = 180

BATCH_SIZE = 25
BATCH_PAUSE_MIN = 600
BATCH_PAUSE_MAX = 1200

# ================== INIT ==================

if not os.path.exists(SESSIONS_DIR):
    os.makedirs(SESSIONS_DIR)

# ================== УТИЛИТЫ ==================

async def connect_account():
    print("Настройки аккаунта")
    print("[1] Подключить новый аккаунт")
    print("[2] Выбрать существующую сессию")

    choice = input("Ваш выбор: ").strip()
    client = None
    account_name = None

    if choice == '1':
        phone = input("Введите номер телефона: ")
        session_file = os.path.join(SESSIONS_DIR, f"{phone}.session")

        client = TelegramClient(
            session_file,
            API_ID,
            API_HASH,
            device_model='Desktop',
            system_version='Windows 10',
            app_version='4.7.3 x64',
            lang_code='en',
            system_lang_code='en-US'
        )

        await client.connect()

        if not await client.is_user_authorized():
            await client.send_code_request(phone)
            try:
                code = input("Введите код: ")
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                password = input("Пароль 2FA: ")
                await client.sign_in(password=password)

    elif choice == '2':
        session_files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]

        if not session_files:
            print("Сессии не найдены.")
            return None, None

        print("\nДоступные сессии:")
        for i, f in enumerate(session_files):
            print(f"{i + 1}. {f}")

        idx = int(input("Выберите сессию: ")) - 1
        session_file = os.path.join(SESSIONS_DIR, session_files[idx])

        client = TelegramClient(
            session_file,
            API_ID,
            API_HASH,
            device_model='Desktop',
            system_version='Windows 10',
            app_version='4.7.3 x64',
            lang_code='en',
            system_lang_code='en-US'
        )

        await client.connect()

    else:
        print("Неверный выбор.")
        return None, None

    if not await client.is_user_authorized():
        print("Не удалось авторизоваться.")
        return None, None

    me = await client.get_me()
    account_name = me.first_name
    print(f"Подключен аккаунт: {account_name}")

    return client, account_name

def load_chats():
    if not os.path.exists(CHATS_FILE):
        print("Файл chats.txt не найден")
        return []

    with open(CHATS_FILE, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def extract_invite(link: str):
    if "joinchat/" in link:
        return link.split("joinchat/")[1]
    if "+" in link:
        return link.split("+")[1]
    return None


# ================== ПАПКА ==================


from telethon.tl.functions.messages import UpdateDialogFilterRequest
from telethon.tl.types import DialogFilter


async def create_folder(client):
    # получаем текущие папки
    filters = await client(GetDialogFiltersRequest())

    folder_id = None

    # ищем существующую папку с таким названием


    # если нет, создаем новую
    if folder_id is None:
        folder_id = len(filters)  # берём первый свободный ID
    me = await client.get_me()
    saved_peer = InputPeerSelf()
    # собираем всех пиров
    peers = []

    new_filter = DialogFilter(
        id=folder_id,
        title="NEW",
        pinned_peers=[],
        include_peers=[saved_peer],  # ✅ не пусто
        exclude_peers=[]
    )

    await client(UpdateDialogFilterRequest(id=folder_id, filter=new_filter))


    print(f"📁 Папка создана: NEW (id={folder_id})")

    return folder_id


async def add_to_folder(client, folder_id, entity):
    filters = await client(GetDialogFiltersRequest())
    dialog_filter = next(
        f for f in filters
        if isinstance(f, DialogFilter) and f.id == folder_id
    )

    peer = await client.get_input_entity(entity)

    if peer in dialog_filter.include_peers:
        return

    dialog_filter.include_peers.append(peer)

    # ⚠️ ТЕПЕРЬ id = folder_id (РЕДАКТИРОВАНИЕ)
    await client(UpdateDialogFilterRequest(
        id=folder_id,
        filter=dialog_filter
    ))

    print("📂 Добавлен в папку")


# ================== ПОДПИСКА ==================

async def join_chat(client, link: str):


    try:
        if link.startswith("@"):
            await client(JoinChannelRequest(link))
            return link.lstrip("@")

        if "t.me/" in link and "+" not in link:
            username = link.rsplit("/", 1)[-1]
            await client(JoinChannelRequest(username))
            return username

        invite = extract_invite(link)
        if invite:
            await client(ImportChatInviteRequest(invite))
            return invite

    except UserAlreadyParticipantError:
        print(f"{Fore.YELLOW}[✓] Уже участник{Style.RESET_ALL}")
        return None

    except (InviteHashInvalidError, InviteHashExpiredError):
        print(f"{Fore.RED}[X] Инвайт недействителен{Style.RESET_ALL}")

    except FloodWaitError as e:
        print(f"{Fore.RED}[!] FloodWait {e.seconds} сек{Style.RESET_ALL}")
        await asyncio.sleep(e.seconds + random.randint(10, 30))

    except Exception as e:
        print(f"{Fore.RED}[!] Ошибка: {e}{Style.RESET_ALL}")

    return None


# ================== ОСНОВНАЯ ЛОГИКА ==================

async def auto_subscribe(client):
    chats = load_chats()
    if not chats:
        return

    folder_id = await create_folder(client)

    joined_count = 0
    total = len(chats)
    print(f"\n▶ Запуск автоматической подписки")
    print(f"▶ Всего чатов: {total}")
    print(f"▶ delay: {JOIN_DELAY_MIN}-{JOIN_DELAY_MAX} сек")
    print(f"▶ пауза каждые {BATCH_SIZE}: 10–20 минут\n")
    for idx, link in enumerate(chats, 1):
        print(f"\n[{idx}/{total}] Вступаю: {link}")

        result = await join_chat(client, link)

        if result:
            entity = await client.get_entity(result)
            await add_to_folder(client, folder_id, entity)

        joined_count += 1

        if joined_count % BATCH_SIZE == 0:
            pause = random.randint(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
            print(f"\n⏸ Пауза {pause // 60} мин\n")
            await asyncio.sleep(pause)
            continue

        delay = random.randint(JOIN_DELAY_MIN, JOIN_DELAY_MAX)
        await asyncio.sleep(delay)

    print(f"{Fore.GREEN}✅ Готово{Style.RESET_ALL}")


# ================== MAIN ==================

async def main():
    client, account_name = await connect_account()
    if not client:
        return

    await auto_subscribe(client)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

