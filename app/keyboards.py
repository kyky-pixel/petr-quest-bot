from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Профиль"), KeyboardButton(text="🗺 Квесты")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие…",
        selective=True,
        is_persistent=True,
    )

def quest_actions_kb(qid: int, state: str) -> InlineKeyboardMarkup:
    rows = []
    if state in ("pending",):
        rows.append([
            InlineKeyboardButton(text="✅ Принять", callback_data=f"q:accept:{qid}"),
            InlineKeyboardButton(text="📤 Сдать",    callback_data=f"q:submit:{qid}"),
            InlineKeyboardButton(text="❌ Отказаться", callback_data=f"q:decline:{qid}")
        ])
    elif state in ("accepted",):
        rows.append([
            InlineKeyboardButton(text="📤 Сдать",    callback_data=f"q:submit:{qid}"),
            InlineKeyboardButton(text="❌ Отказаться", callback_data=f"q:decline:{qid}")
        ])
    elif state in ("rejected",):
        rows.append([
            InlineKeyboardButton(text="📤 Сдать снова", callback_data=f"q:submit:{qid}")
        ])
    elif state in ("submitted",):
        rows.append([ InlineKeyboardButton(text="⏳ На проверке", callback_data="noop") ])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text="—", callback_data="noop")]])

def admin_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Выдать Пете")],
            [KeyboardButton(text="📝 Ожидают проверки")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Админ-панель",
        selective=True,
        is_persistent=True,
    )

def admin_review_kb(qid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"qa:approve:{qid}"),
        InlineKeyboardButton(text="❌ Отклонить",   callback_data=f"qa:reject:{qid}")
    ]])
