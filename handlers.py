# handlers.py
from telegram import Update
from telegram.ext import ContextTypes
from keyboards import main_menu_keyboard, back_to_main_button
from courses import show_courses, show_video, navigate_video, handle_course_selection
from achievements import show_achievements
from articles import show_articles
from donations import donate_stars
from admin import admin_callback_handler
import config

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import add_or_update_user
    from subscription import handle_referral
    user = update.effective_user
    add_or_update_user(user.id, user.username, user.first_name, user.last_name)
    await handle_referral(update, context)

    # التحقق من الاشتراك والدعوات
    from subscription import check_subscription_and_invite
    if await check_subscription_and_invite(update, context):
        await update.message.reply_text(
            f"مرحباً {user.first_name}!",
            reply_markup=main_menu_keyboard()
        )

async def about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ *عن البوت التعليمي*\n\n"
        "هذا البوت مصمم لدعم الشباب والمهتمين بالتعلم عبر تقديم كورسات مجانية.\n"
        "للاستفسارات: @YourSupport"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=back_to_main_button())
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=back_to_main_button())

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "main_courses":
        await show_courses(update, context)
    elif data == "main_achievements":
        await show_achievements(update, context, 0)
    elif data == "main_articles":
        await show_articles(update, context, 0)
    elif data == "main_about":
        await about_bot(update, context)
    elif data == "main_donate":
        await donate_stars(update, context)
    elif data == "back_to_main":
        await query.edit_message_text("مرحباً بك مجدداً!", reply_markup=main_menu_keyboard())

async def verify_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    from subscription import check_subscription_and_invite
    if await check_subscription_and_invite(update, context):
        await update.effective_message.reply_text("✅ تم التحقق بنجاح!", reply_markup=main_menu_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # تجاهل أي نصوص من المستخدمين العاديين (لأن كل شيء يتم عبر الأزرار)
    pass
