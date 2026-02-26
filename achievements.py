# achievements.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_achievements
from keyboards import achievements_navigation_keyboard, back_to_main_button
import logging

logger = logging.getLogger(__name__)

async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    achievements = get_achievements()
    if not achievements:
        await update.effective_message.reply_text(
            "لا توجد إنجازات بعد.",
            reply_markup=back_to_main_button()
        )
        return

    per_page = 3  # عدد الإنجازات في الصفحة الواحدة
    total_pages = (len(achievements) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    current = achievements[start:end]

    for ach in current:
        caption = ach['caption'] or ""
        if ach['type'] == 'text':
            await update.effective_message.reply_text(
                f"📝 {caption}\n\n{ach['content']}",
                reply_markup=back_to_main_button() if ach == current[-1] else None
            )
        elif ach['type'] == 'photo':
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=ach['content'],
                caption=caption,
                reply_markup=back_to_main_button() if ach == current[-1] else None
            )
        elif ach['type'] == 'video':
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=ach['content'],
                caption=caption,
                reply_markup=back_to_main_button() if ach == current[-1] else None
            )

    # إذا كان هناك أكثر من صفحة، نعرض أزرار التنقل بعد آخر إنجاز
    if total_pages > 1:
        await update.effective_message.reply_text(
            "لتصفح المزيد:",
            reply_markup=achievements_navigation_keyboard(page, total_pages)
        )
