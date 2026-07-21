from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def get_confirm_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, создать", callback_data="confirm_create")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_create")]
        ]
    )

def get_admin_moderation_kb(request_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{request_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{request_id}")
            ]
        ]
    )

def get_main_menu_keyboard():
    """Основное меню пользователя (кнопки внизу экрана)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🆕 Запросить доступ")],
            [KeyboardButton(text="🔑 Мой конфиг")]
        ],
        resize_keyboard=True,
        is_persistent=True # Чтобы кнопки всегда были видны
    )
