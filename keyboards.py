# keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📚 قائمة الكورسات", callback_data="main_courses")],
        [InlineKeyboardButton("🏆 معرض الإنجازات", callback_data="main_achievements")],
        [InlineKeyboardButton("📝 المداد", callback_data="main_articles")],
        [InlineKeyboardButton("ℹ️ عن البوت", callback_data="main_about"),
         InlineKeyboardButton("⭐ دعم البوت", callback_data="main_donate")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_main_button():
    keyboard = [[InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(keyboard)

def achievements_navigation_keyboard(page: int, total_pages: int):
    keyboard = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"achievements_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي ➡️", callback_data=f"achievements_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def articles_navigation_keyboard(page: int, total_pages: int):
    keyboard = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"articles_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي ➡️", callback_data=f"articles_page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def courses_navigation_keyboard(page: int, total_pages: int):
    keyboard = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي ➡️", callback_data=f"page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)
