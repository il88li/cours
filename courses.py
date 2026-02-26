# courses.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from database import get_courses, get_videos
from keyboards import courses_navigation_keyboard, back_to_main_button
from subscription import check_subscription_and_invite, is_user_subscribed
import config
import logging

logger = logging.getLogger(__name__)

async def is_user_qualified(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """التحقق من أن المستخدم مؤهل لاستخدام الكورسات."""
    from database import get_user, is_invite_system_enabled
    user_id = update.effective_user.id
    user = get_user(user_id)

    if user.get('blocked', 0):
        await update.effective_message.reply_text("⛔ أنت محظور.")
        return False

    # تأكد من الاشتراك (يتم إعادة التوجيه إذا لم يكن مشتركاً)
    from subscription import check_subscription_and_invite
    if not await check_subscription_and_invite(update, context):
        return False

    # إذا كان نظام الدعوات معطلاً أو معفى أو مكتمل
    if (not is_invite_system_enabled() or
        user.get('exempt_from_invites', 0) or
        user.get('invites_count', 0) >= 5):
        return True

    # غير مؤهل: أعد توجيهه إلى الدعوات
    await check_subscription_and_invite(update, context)
    return False

async def show_courses(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    if not await is_user_qualified(update, context):
        return

    courses = get_courses()
    if not courses:
        await update.effective_message.reply_text("لا توجد كورسات متاحة حالياً.")
        return

    per_page = 5
    total_pages = (len(courses) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    current_courses = courses[start:end]

    keyboard = []
    for course in current_courses:
        keyboard.append([InlineKeyboardButton(course['name'], callback_data=f"course_{course['id']}")])

    # أزرار التنقل
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي ➡️", callback_data=f"page_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text("اختر الكورس:", reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text("اختر الكورس:", reply_markup=reply_markup)

async def handle_course_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not await is_user_qualified(update, context):
        return

    if data.startswith("course_"):
        course_id = int(data.split("_")[1])
        context.user_data['current_course'] = course_id
        context.user_data['video_index'] = 0
        await show_video(update, context)
    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        await show_courses(update, context, page)
    elif data == "back_to_main":
        # سيتم التعامل معها في handlers
        pass

async def show_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    course_id = context.user_data.get('current_course')
    video_index = context.user_data.get('video_index', 0)

    if course_id is None:
        await query.edit_message_text("حدث خطأ، الرجاء البدء من جديد.")
        return

    videos = get_videos(course_id)
    if not videos:
        await query.edit_message_text("هذا الكورس لا يحتوي على فيديوهات.")
        return

    if video_index < 0 or video_index >= len(videos):
        video_index = 0
        context.user_data['video_index'] = 0

    video = videos[video_index]
    file_id = video['file_id']

    keyboard = []
    nav_row = []
    if video_index > 0:
        nav_row.append(InlineKeyboardButton("⏪ السابق", callback_data="prev_video"))
    if video_index < len(videos) - 1:
        nav_row.append(InlineKeyboardButton("التالي ⏩", callback_data="next_video"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text("جاري تحميل الفيديو...")
        await context.bot.send_video(
            chat_id=update.effective_chat.id,
            video=file_id,
            caption=f"الجزء {video_index+1} من {len(videos)}",
            reply_markup=reply_markup
        )
        await query.message.delete()
    except TelegramError as e:
        logger.error(f"Failed to send video: {e}")
        await query.edit_message_text("حدث خطأ أثناء إرسال الفيديو. حاول مرة أخرى.")

async def navigate_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await is_user_qualified(update, context):
        return

    action = query.data
    video_index = context.user_data.get('video_index', 0)

    if action == "prev_video":
        context.user_data['video_index'] = max(0, video_index - 1)
    elif action == "next_video":
        context.user_data['video_index'] = video_index + 1

    await show_video(update, context)
