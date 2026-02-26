# articles.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_articles
from keyboards import articles_navigation_keyboard, back_to_main_button
import logging

logger = logging.getLogger(__name__)

async def show_articles(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    articles = get_articles()
    if not articles:
        await update.effective_message.reply_text(
            "لا توجد مقالات بعد.",
            reply_markup=back_to_main_button()
        )
        return

    per_page = 1  # مقالة واحدة في كل صفحة
    total_pages = (len(articles) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    current = articles[start:end]

    for art in current:
        text = f"📖 *{art['title']}*\n\n{art['content']}"
        await update.effective_message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=back_to_main_button() if art == current[-1] and total_pages <= 1 else None
        )

    if total_pages > 1:
        await update.effective_message.reply_text(
            "لتصفح المزيد:",
            reply_markup=articles_navigation_keyboard(page, total_pages)
        )
