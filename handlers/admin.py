from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database import async_session_maker
from models import Request, User
from services import xui_api, utils
import config
import asyncio
import subprocess
import urllib.parse

router = Router()

@router.callback_query(F.data.startswith("approve_"))
async def approve_request(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[1])
    
    async with async_session_maker() as session:
        # 1. Получаем заявку
        result = await session.execute(select(Request).where(Request.id == req_id))
        req = result.scalar_one_or_none()

        if not req or req.status != "pending":
            await callback.answer("Заявка уже обработана или не найдена.")
            return

        # 2. Получаем пользователя
        user_result = await session.execute(select(User).where(User.id == req.user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден.")
            return

        # 3. Создаем логин - в xui это email
        if user.username:
            clean_username = user.username.lstrip('@')
            email = f"{clean_username}@from_bot"
        else:
            email = f"tg_{user.telegram_id}@from_bot"

        try:
            # 4. Создаем пользователя в xui
            uuid = await xui_api.create_user_in_xui(email)

            # 5. Обновляем статус заявки
            req.status = "active"
            req.uuid = uuid
            await session.commit()

            # 6. Генерируем ссылку
            link = utils.generate_vless_link(uuid, f"VLESS-{user.telegram_id}")

            # 7. Отправляем пользователю
            await callback.bot.send_message(
                user.telegram_id,
                f"🎉 <b>Ваша заявка одобрена!</b>\n\n"
                "Ваша ссылка:\n\n"
                f"<code>{link}</code>",
                parse_mode="HTML"
            )

            panel_link = f'<a href="{config.XUI_BASE_URL}/panel/inbounds">Панель X-UI</a>'

            # 8. Сообщаем админу
            await callback.message.edit_text(
                f"✅ Заявка #{req_id} одобрена.\n"
                f"Пользователь: @{user.username or user.telegram_id}\n"
                f"Email: {email}\n"
                f"UUID: {uuid}\n\n"
                f"⚠️ Для ручного редактирования зайдите в {panel_link}",
                parse_mode="HTML"
            )
            await callback.answer("Одобрено")

        except Exception as e:
            await callback.answer(f"Ошибка: {e}")
            print(f"Error: {e}")

@router.callback_query(F.data.startswith("reject_"))
async def reject_request(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[1])
    
    async with async_session_maker() as session:
        await session.execute(update(Request).where(Request.id == req_id).values(status="rejected"))
        await session.commit()

        await callback.message.edit_text(f"❌ Заявка #{req_id} отклонена.")
        await callback.answer("Отклонено")

@router.callback_query(F.data == "cancel_create")
async def cancel_create(callback: CallbackQuery):
    await callback.message.edit_text("❌ Вы отменили создание заявки.")
    await callback.answer("Отменено")

# --- НОВЫЕ ФУНКЦИИ ДЛЯ ПЕРЕЗАГРУЗКИ ---

@router.message(Command("reset_xray"))
async def cmd_reset_xray(message: Message):
    """
    Команда для админа: Показывает кнопку для ручной перезагрузки Xray.
    """
    if message.from_user.id not in config.ADMINS_ID:
        await message.answer("⛔ Эта команда только для администраторов.")
        return

    # Формируем клавиатуру
    kb = InlineKeyboardBuilder()
    kb.button(text="⚠️ ПЕРЕЗАГРУЗИТЬ XRAY", callback_data="exec_reset_xray")
    kb.button(text="Отмена", callback_data="cancel_reset")
    
    await message.answer(
        "Вы уверены, что хотите перезагрузить ядро Xray?\n\n"
        "Это прервет текущие соединения на несколько секунд.",
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data == "exec_reset_xray")
async def exec_reset_xray(callback: CallbackQuery):
    """
    Обработка нажатия кнопки. Выполняет systemctl restart x-ui.
    """
    # Ответ пользователю, чтобы не висело "часики"
    await callback.answer("⏳ Перезагружаю Xray...", show_alert=False)

    try:
        print("[DEBUG] Перезагрузка Xray через команду админа...")
        
        # Запускаем процесс в асинхронном режиме, чтобы не блокировать бота
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "restart",
            "x-ui",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            # Уведомляем админа об успехе
            try:
                await callback.message.edit_text(
                    f"✅ Xray успешно перезагружен!\n\n"
                    f"Статус: Активен.\n"
                    f"Настройки применены."
                )
            except Exception:
                # Если сообщение уже нельзя редактировать, шлем новое
                await callback.bot.send_message(
                    callback.message.chat.id,
                    "✅ Xray успешно перезагружен!"
                )
        else:
            await callback.message.edit_text(
                f"❌ Ошибка перезагрузки!\n\n"
                f"Код: {proc.returncode}\n"
                f"Ошибка: {stderr.decode()}"
            )

    except Exception as e:
        await callback.answer("Ошибка при выполнении команды")
        await callback.message.reply_text(f"⚠️ Не удалось выполнить команду: {e}")

@router.callback_query(F.data == "cancel_reset")
async def cancel_reset(callback: CallbackQuery):
    await callback.message.edit_text("❌ Операция отменена.")
    await callback.answer("Отменено")


# --- НОВЫЕ ФУНКЦИИ: ОНЛАЙН И РАССЫЛКА ---

class BroadcastState(StatesGroup):
    waiting_for_message = State()

@router.message(Command("online"))
async def cmd_online(message: Message):
    """Команда для админа: Показывает кто сейчас онлайн в VPN"""
    if message.from_user.id not in config.ADMINS_ID:
        await message.answer("⛔ Эта команда только для администраторов.")
        return

    await message.answer("⏳ Запрашиваю список онлайн у панели...")
    try:
        emails = await xui_api.get_online_clients()
        
        if not emails:
            await message.answer("🟢 Сейчас нет подключенных пользователей.")
            return

        online_list = []
        for email in emails:
            # Парсим email, который мы генерировали: username@from_bot или tg_12345@from_bot
            if email.startswith("tg_") and email.endswith("@from_bot"):
                tg_id = email.replace("tg_", "").replace("@from_bot", "")
                online_list.append(f"👤 ID: {tg_id}")
            else:
                username = email.replace("@from_bot", "")
                online_list.append(f"👤 @{username}")
        
        text = f"🟢 <b>Подключенные пользователи ({len(online_list)}):</b>\n\n" + "\n".join(online_list)
        await message.answer(text, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении списка: {e}")

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    """Команда для админа: Начинает процесс рассылки"""
    if message.from_user.id not in config.ADMINS_ID:
        await message.answer("⛔ Эта команда только для администраторов.")
        return

    await message.answer(
        "📤 <b>Режим рассылки запущен.</b>\n\n"
        "Отправьте мне сообщение (текст, фото, видео), которое нужно разослать всем пользователям бота.\n\n"
        "Для отмены отправьте /cancel"
    )
    await state.set_state(BroadcastState.waiting_for_message)

@router.message(Command("cancel"))
async def cmd_cancel_broadcast(message: Message, state: FSMContext):
    """Отмена рассылки"""
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("❌ Рассылка отменена.")

@router.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    """Выполняет саму рассылку"""
    await state.clear()
    if message.from_user.id not in config.ADMINS_ID:
        return
        
    async with async_session_maker() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
    total = len(users)
    await message.answer(f"⏳ Начинаю рассылку для {total} пользователей...")
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            # copy_to позволяет переслать сообщение со всем содержимым (текст, картинки, кнопки)
            await message.copy_to(chat_id=user.telegram_id)
            success += 1
            # Задержка, чтобы Телеграм не забанил бота за спам (лимит ~30 сообщений в секунду)
            await asyncio.sleep(0.05) 
        except Exception as e:
            failed += 1
            print(f"Не удалось отправить сообщение пользователю {user.telegram_id}: {e}")
            
    await message.answer(f"✅ Рассылка завершена!\n\nДоставлено: {success}\nНе доставлено (заблокировали бота): {failed}")


# --- НОВЫЕ ФУНКЦИИ: СПИСОК ВСЕХ КЛИЕНТОВ И УДАЛЕНИЕ ---

@router.message(Command("all_clients"))
async def cmd_all_clients(message: Message):
    """Команда для админа: Показывает всех клиентов панели"""
    if message.from_user.id not in config.ADMINS_ID:
        await message.answer("⛔ Эта команда только для администраторов.")
        return

    await message.answer("⏳ Получаю список всех клиентов из панели...")
    try:
        clients = await xui_api.get_all_clients()
        
        if not clients:
            await message.answer("В панели нет клиентов.")
            return

        text = f"📋 <b>Все клиенты в панели ({len(clients)}):</b>\n\n"
        for item in clients:
            # В новом API /clients/list объекты плоские, читаем напрямую
            email = item.get("email", "Нет email")
            enable = "🟢" if item.get("enable") else "🔴"
            
            # Трафик может лежать внутри объекта traffic
            traffic = item.get("traffic", {}) or {}
            up = traffic.get("up", 0)
            down = traffic.get("down", 0)
            
            # Лимит трафика может быть в поле totalGB
            total_gb = item.get("totalGB", traffic.get("total", 0))
            
            used = (up + down) / 1024 / 1024 / 1024
            limit = f" / {total_gb / 1024 / 1024 / 1024:.1f} GB" if total_gb > 0 else " / Без лимита"
            
            text += f"{enable} <code>{email}</code> - {used:.2f} GB{limit}\n"
            
            # Если сообщение слишком длинное (лимит Телеграма ~4096 символов), разбиваем
            if len(text) > 3800:
                await message.answer(text, parse_mode="HTML")
                text = ""
                
        if text:
            await message.answer(text, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении списка: {e}")

@router.message(Command("del_client"))
async def cmd_del_client(message: Message):
    """Команда для админа: Запрос на удаление клиента. Формат: /del_client email"""
    if message.from_user.id not in config.ADMINS_ID:
        await message.answer("⛔ Эта команда только для администраторов.")
        return

    # Разбиваем сообщение, чтобы достать email
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование:\n`/del_client email@from_bot`", parse_mode="Markdown")
        return
        
    email = args[1].strip()
    
    # Формируем клавиатуру подтверждения
    kb = InlineKeyboardBuilder()
    # Кодируем email в URL-формат, чтобы спецсимволы не сломали callback_data
    encoded_email = urllib.parse.quote(email)
    kb.button(text="🗑 Да, удалить", callback_data=f"exec_del_client:{encoded_email}")
    kb.button(text="❌ Отмена", callback_data="cancel_reset")
    
    await message.answer(
        f"⚠️ <b>Вы уверены, что хотите удалить клиента?</b>\n\n"
        f"Email: <code>{email}</code>\n\n"
        f"Клиент будет удален из панели. Если он был создан ботом, его заявка будет закрыта.",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("exec_del_client:"))
async def callback_exec_del_client(callback: CallbackQuery):
    """Обработка нажатия кнопки удаления клиента"""
    if callback.from_user.id not in config.ADMINS_ID:
        await callback.answer("⛔ Нет прав")
        return
        
    encoded_email = callback.data.split(":", 1)[1]
    email = urllib.parse.unquote(encoded_email)
    
    await callback.answer("⏳ Удаляю...")
    
    try:
        # 1. Удаляем из панели X-UI
        success = await xui_api.delete_client(email)
        
        if success:
            # 2. Если это пользователь бота, закрываем его заявку в БД
            async with async_session_maker() as session:
                # Так как мы не храним email в БД, ищем по uuid, который генерировали
                # Но проще обновить все активные заявки, email которых соответствует шаблону
                # Если email заканчивается на @from_bot, обновляем статус
                if "@from_bot" in email:
                    prefix = email.replace("@from_bot", "")
                    if prefix.startswith("tg_"):
                        tg_id_str = prefix.replace("tg_", "")
                        user_result = await session.execute(select(User).where(User.telegram_id == int(tg_id_str)))
                    else:
                        user_result = await session.execute(select(User).where(User.username == prefix.lstrip('@')))
                    
                    user = user_result.scalar_one_or_none()
                    if user:
                        await session.execute(
                            update(Request).where(Request.user_id == user.id, Request.status == "active").values(status="deleted", uuid=None)
                        )
                        await session.commit()

            await callback.message.edit_text(f"✅ Клиент <code>{email}</code> успешно удален из панели.", parse_mode="HTML")
        else:
            await callback.message.edit_text(f"❌ Не удалось удалить клиента {email}. Проверьте логи бота.")
            
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при удалении: {e}")



@router.message(Command("commands"))
async def cmd_admin_commands(message: Message):
    """Команда для админа: Выводит список всех доступных админ-команд"""
    if message.from_user.id not in config.ADMINS_ID:
        await message.answer("⛔ Эта команда только для администраторов.")
        return

    text = (
        "🛠 <b>Список админ-команд:</b>\n\n"
        "<b>Управление сервером:</b>\n"
        "🔴 /reset_xray — Перезагрузить ядро Xray\n"
        "🟢 /online — Показать, кто сейчас подключен к VPN\n\n"
        
        "<b>Управление клиентами:</b>\n"
        "📋 /all_clients — Список всех клиентов в панели 3X-UI\n"
        "🗑 /del_client &lt;email&gt; — Удалить клиента (пример: /del_client igor@from_bot)\n\n"
        
        "<b>Управление ботом:</b>\n"
        "📤 /broadcast — Сделать рассылку всем пользователям бота\n"
        "📖 /commands — Показать это сообщение"
    )
    
    await message.answer(text, parse_mode="HTML")
