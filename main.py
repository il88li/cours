# main.py
import logging
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters
)
from config import TOKEN
from database import init_db
from handlers import start, about_bot, main_menu_callback, verify_subscription_callback, handle_text
from courses import handle_course_selection, navigate_video
from admin import (
    admin_panel, admin_callback_handler, handle_admin_text,
    new_course_start, new_course_name, receive_video, done_adding_videos,
    achievement_type, achievement_content, achievement_caption, skip_caption,
    article_title, article_content,
    COURSE_NAME, RECEIVE_VIDEOS, ACHIEVEMENT_TYPE, ACHIEVEMENT_CONTENT, ACHIEVEMENT_CAPTION,
    ARTICLE_TITLE, ARTICLE_CONTENT
)
from donations import process_stars_amount
import asyncio

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    init_db()
    logger.info("✅ Database initialized.")

    app = Application.builder().token(TOKEN).build()

    # محادثة إضافة كورس جديد
    course_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback_handler, pattern="^admin_new_course$")],
        states={
            COURSE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_course_name)],
            RECEIVE_VIDEOS: [
                MessageHandler(filters.VIDEO, receive_video),
                CommandHandler('done', done_adding_videos)
            ]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: u.message.reply_text("تم الإلغاء."))]
    )
    app.add_handler(course_conv)

    # محادثة إضافة إنجاز
    achievement_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(achievement_type, pattern="^achievement_type_")],
        states={
            ACHIEVEMENT_CONTENT: [MessageHandler(filters.ALL, achievement_content)],
            ACHIEVEMENT_CAPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, achievement_caption),
                CommandHandler('skip', skip_caption)
            ]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: u.message.reply_text("تم الإلغاء."))]
    )
    app.add_handler(achievement_conv)

    # محادثة إضافة مقال
    article_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback_handler, pattern="^admin_new_article$")],
        states={
            ARTICLE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, article_title)],
            ARTICLE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, article_content)]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: u.message.reply_text("تم الإلغاء."))]
    )
    app.add_handler(article_conv)

    # أوامر عامة
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    # معالجات الكولباك
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_"))
    app.add_handler(CallbackQueryHandler(verify_subscription_callback, pattern="^verify_subscription$"))
    app.add_handler(CallbackQueryHandler(handle_course_selection, pattern="^(course_|page_|back_to_main)"))
    app.add_handler(CallbackQueryHandler(navigate_video, pattern="^(prev_video|next_video)$"))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(show_articles, pattern="^articles_page_"))
    app.add_handler(CallbackQueryHandler(show_achievements, pattern="^achievements_page_"))

    # معالجات النصوص
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))

    # معالجة الدفع (مجرد رسالة)
    # لا نحتاج إلى معالج منفصل لأن donate_stars يرسل رسالة توجيه فقط

    app.add_error_handler(error_handler)

    logger.info("🚀 Bot is starting...")
    app.run_polling()

async def error_handler(update, context):
    logger.error("Exception while handling an update:", exc_info=context.error)

if __name__ == "__main__":
    main()
