from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database import async_session_maker
from models import Request, User
from services import xui_api, utils
import keyboards
import config

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(telegram_id=message.from_user.id, username=message.from_user.username)
            session.add(user)
            await session.commit()
        
        await message.answer(
            f"Привет, {message.from_user.first_name}!\n"
            "Я бот для управления VLESS доступом.\n\n"
            "Используйте кнопки внизу экрана для управления.",
            reply_markup=keyboards.get_main_menu_keyboard()
        )

# --- Обработка кнопок меню ---

@router.message(F.text == "🆕 Запросить доступ")
async def menu_request_account(message: Message):
    # Просто вызываем уже готовую функцию
    await cmd_request(message)

@router.message(F.text == "🔑 Мой конфиг")
async def menu_my_account(message: Message):
    # Просто вызываем уже готовую функцию
    await cmd_my_account(message)

# --- Логика команд ---

@router.message(Command("request_account"))
async def cmd_request(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()

        if not user:
            user = User(telegram_id=message.from_user.id, username=message.from_user.username)
            session.add(user)
            await session.commit()
            await session.refresh(user)

        result = await session.execute(
            select(Request).where(Request.user_id == user.id, Request.status == "active")
        )
        req = result.scalar_one_or_none()
        
        if req:
            await message.answer("У вас уже есть активный аккаунт.", reply_markup=keyboards.get_main_menu_keyboard())
            return

        new_req = Request(user_id=user.id, status="pending")
        session.add(new_req)
        await session.commit()
        
        await message.answer(
            "Вы хотите запросить новый VLESS аккаунт?", 
            reply_markup=keyboards.get_confirm_keyboard()
        )

@router.callback_query(F.data == "confirm_create")
async def confirm_request(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(telegram_id=user_id, username=callback.from_user.username)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
        result = await session.execute(
            select(Request).where(Request.user_id == user.id, Request.status == "active")
        )
        if result.scalar_one_or_none():
            await callback.answer("У вас уже есть активный аккаунт.")
            return

        new_req = Request(user_id=user.id, status="pending")
        session.add(new_req)
        await session.commit()
        await session.refresh(new_req)

        text = (
            f"🆕 <b>Новая заявка!</b>\n"
            f"👤 Пользователь: @{user.username or 'скрыт'} (ID: {user.telegram_id})\n"
            f"📅 Время: {new_req.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"🆔 ID заявки: {new_req.id}"
        )
        
        for admin_id in config.ADMINS_ID:
            try:
                await callback.bot.send_message(
                    admin_id, 
                    text, 
                    parse_mode="HTML",
                    reply_markup=keyboards.get_admin_moderation_kb(new_req.id)
                )
            except Exception as e:
                print(f"Не удалось уведомить админа {admin_id}: {e}")

        await callback.message.edit_text("✅ Заявка отправлена на модерацию.")
        await callback.answer("Успешно")

@router.callback_query(F.data == "cancel_create")
async def cancel_create(callback: CallbackQuery):
    await callback.message.edit_text("❌ Вы отменили создание заявки.")
    await callback.answer("Отменено")

@router.message(F.text == "🔑 Мой конфиг")
async def menu_my_account(message: Message):
    await cmd_my_account(message)

@router.message(Command("my_account"))
async def cmd_my_account(message: Message):
    async with async_session_maker() as session:
        # Получаем юзера и его активную заявку
        user_result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user_result.scalar_one_or_none()

        result = await session.execute(
            select(Request).where(
                Request.user_id == user.id, 
                Request.status == "active"
            )
        )
        req = result.scalar_one_or_none()
        
        if not req:
            await message.answer("У вас нет активного аккаунта.", reply_markup=keyboards.get_main_menu_keyboard())
            return

        # Формируем email, чтобы проверить в панели
        if user.username:
            clean_username = user.username.lstrip('@')
            email = f"{clean_username}@from_bot"
        else:
            email = f"tg_{user.telegram_id}@from_bot"

        # Отправляем сообщение ожидания
        wait_msg = await message.answer("⏳ Проверяю статус вашего аккаунта в панели...")
        
        try:
            # Проверяем, существует ли клиент в панели
            exists = await xui_api.check_client_exists(email)
            
            if not exists:
                # Если клиента нет в панели (удалили вручную), обновляем БД бота
                req.status = "deleted"
                req.uuid = None
                await session.commit()
                
                await wait_msg.edit_text(
                    "❗️ <b>Ваш аккаунт был отозван или удален администратором.</b>\n\n"
                    "Вы можете запросить новый доступ.",
                    reply_markup=keyboards.get_main_menu_keyboard()
                )
                return

            # Если все отлично, отдаем конфиг
            link = utils.generate_vless_link(req.uuid, f"VLESS-{req.user_id}")
            
            await wait_msg.delete()
            await message.answer(
                f"🔑 <b>Ваша конфигурация:</b>\n\n"
                f"<code>{link}</code>",
                parse_mode="HTML",
                reply_markup=keyboards.get_main_menu_keyboard()
            )
            
        except Exception as e:
            await wait_msg.edit_text("⚠️ Произошла ошибка при проверке статуса. Попробуйте позже.")
            print(f"Ошибка проверки клиента {email}: {e}")
