from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏳ Bugungi vaqtlar")],
            [KeyboardButton(text="🍽 Og‘iz ochish duosi"), KeyboardButton(text="🌙 Og‘iz yopish duosi")],
            [KeyboardButton(text="📍 Shahar"), KeyboardButton(text="🔔 Eslatma sozlash")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyudan tanlang…"
    )

def stop_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛑 To‘xtatish")]],
        resize_keyboard=True,
        input_field_placeholder="To‘xtatish uchun bosing…"
    )

def reminder_inline(minutes: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➖ 5", callback_data="rem:-5"),
                InlineKeyboardButton(text=f"{minutes} min", callback_data="rem:noop"),
                InlineKeyboardButton(text="➕ 5", callback_data="rem:+5"),
            ],
            [
                InlineKeyboardButton(text="✅ Saqlash", callback_data="rem:save"),
            ],
        ]
    )

def city_inline():
    cities = [
        ("Tashkent", "Toshkent"),
        ("Samarkand", "Samarqand"),
        ("Bukhara", "Buxoro"),
        ("Andijan", "Andijon"),
        ("Fergana", "Farg‘ona"),
        ("Namangan", "Namangan"),
        ("Jizzakh", "Jizzax"),
        ("Navoi", "Navoiy"),
        ("Gulistan", "Sirdaryo (Guliston)"),
        ("Karshi", "Qashqadaryo (Qarshi)"),
        ("Termez", "Surxondaryo (Termiz)"),
        ("Urgench", "Xorazm (Urganch)"),
        ("Nukus", "Qoraqalpog‘iston (Nukus)"),
    ]
    rows = [[InlineKeyboardButton(text=uz, callback_data=f"city:{en}")] for en, uz in cities]
    rows.append([InlineKeyboardButton(text="✍️ O‘zim yozaman", callback_data="city:custom")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
