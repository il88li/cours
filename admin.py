# admin.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import (
    get_courses, delete_course, add_course, add_video,
    get_all_users_ids, set_user_blocked, set_user_exempt,
    is_invite_system_enabled, set_setting,
    add_achievement, delete_achievement, get_achievements,
    add_article, delete_article, get_articles
)
from config import ADMIN_IDS, CHANNEL_ID
import logging
import asyncio

logger = logging.getLogger(__name__)

# حالات المحادثات
COURSE_NAME, RECEIVE_VIDEOS = range(2)
ACHIEVEMENT_TYPE, ACHIEVEMENT_CONTENT, ACHIEVEMENT_CAPTION = range(2, 5)
ARTICLE_TITLE, ARTICLE_CONTENT = range(5, 7)

# ------------------------------------------------
# لوحة الأدمن الرئيسية
# ------------------------------------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر مخصص للمشرفين فقط.")
        return

    invite_status = "مفعل" if is_invite_system_enabled() else "معطل"
    toggle_text = "🔄 تعطيل نظام الدعوات" if is_invite_system_enabled() else "🔄 تفعيل نظام الدعوات"

    keyboard = [
        [InlineKeyboardButton("➕ كورس جديد", callback_data="admin_new_course")],
        [InlineKeyboardButton("➖ حذف كورس", callback_data="admin_delete_course")],
        [InlineKeyboardButton("🏆 إضافة إنجاز", callback_data="admin_new_achievement")],
        [InlineKeyboardButton("📝 إضافة مقال (المداد)", callback_data="admin_new_article")],
        [InlineKeyboardButton("📢 إذاعة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🚫 حظر عضو", callback_data="admin_ban_user")],
        [InlineKeyboardButton("🆓 عفو من الرابط", callback_data="admin_exempt_user")],
        [InlineKeyboardButton(toggle_text, callback_data="admin_toggle_invite")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"لوحة التحكم (نظام الدعوات: {invite_status}):", reply_markup=reply_markup)

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("غير مصرح.")
        return

    data = query.data

    # إضافة كورس جديد
    if data == "admin_new_course":
        await query.edit_message_text("أرسل اسم الكورس الجديد:")
        return COURSE_NAME  # سيتم التعامل معها في ConversationHandler

    # حذف كورس
    elif data == "admin_delete_course":
        courses = get_courses()
        if not courses:
            await query.edit_message_text("لا توجد كورسات.")
            return
        keyboard = []
        for course in courses:
            keyboard.append([InlineKeyboardButton(course['name'], callback_data=f"del_course_{course['id']}")])
        keyboard.append([InlineKeyboardButton("إلغاء", callback_data="admin_cancel")])
        await query.edit_message_text("اختر الكورس للحذف:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    elif data.startswith("del_course_"):
        course_id = int(data.split("_")[2])
        delete_course(course_id)
        await query.edit_message_text("✅ تم حذف الكورس بنجاح.")

    # إضافة إنجاز
    elif data == "admin_new_achievement":
        keyboard = [
            [InlineKeyboardButton("📝 نص", callback_data="achievement_type_text")],
            [InlineKeyboardButton("🖼 صورة", callback_data="achievement_type_photo")],
            [InlineKeyboardButton("🎥 فيديو", callback_data="achievement_type_video")],
            [InlineKeyboardButton("إلغاء", callback_data="admin_cancel")]
        ]
        await query.edit_message_text("اختر نوع الإنجاز:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    # إضافة مقال
    elif data == "admin_new_article":
        await query.edit_message_text("أرسل عنوان المقال:")
        return ARTICLE_TITLE

    # إذاعة
    elif data == "admin_broadcast":
        await query.edit_message_text("أرسل الرسالة التي تريد إذاعتها لجميع المستخدمين:")
        context.user_data['broadcast_mode'] = True
        return ConversationHandler.END

    # حظر عضو
    elif data == "admin_ban_user":
        await query.edit_message_text("أرسل معرف المستخدم (user_id) لحظره:")
        context.user_data['ban_mode'] = True
        return ConversationHandler.END

    # إعفاء
    elif data == "admin_exempt_user":
        await query.edit_message_text("أرسل معرف المستخدم (user_id) لإعفائه من نظام الدعوات:")
        context.user_data['exempt_mode'] = True
        return ConversationHandler.END

    # تبديل نظام الدعوات
    elif data == "admin_toggle_invite":
        current = is_invite_system_enabled()
        new_value = 'false' if current else 'true'
        set_setting('invite_system_enabled', new_value)
        status = "معطل" if current else "مفعل"
        await query.edit_message_text(f"✅ تم {status} نظام الدعوات.")

    elif data == "admin_cancel":
        await query.edit_message_text("تم الإلغاء.")
        return ConversationHandler.END

# ------------------------------------------------
# محادثة إضافة كورس جديد
# ------------------------------------------------
async def new_course_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text("أرسل اسم الكورس الجديد:")
    return COURSE_NAME

async def new_course_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    course_name = update.message.text.strip()
    if not course_name:
        await update.message.reply_text("الاسم لا يمكن أن يكون فارغاً. أعد الإرسال:")
        return COURSE_NAME

    context.user_data['new_course_name'] = course_name
    context.user_data['videos'] = []
    await update.message.reply_text(
        "الآن أرسل الفيديوهات واحداً تلو الآخر.\n"
        "عند الانتهاء أرسل /done"
    )
    return RECEIVE_VIDEOS

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video:
        await update.message.reply_text("الرجاء إرسال فيديو فقط.")
        return RECEIVE_VIDEOS

    video = update.message.video
    file_id = video.file_id

    try:
        sent_message = await context.bot.send_video(chat_id=CHANNEL_ID, video=file_id)
        message_id = sent_message.message_id
        context.user_data['videos'].append({'file_id': file_id, 'message_id': message_id})
        await update.message.reply_text(f"✅ تم استقبال الفيديو {len(context.user_data['videos'])}. أرسل التالي أو /done للإنهاء.")
    except Exception as e:
        logger.error(f"Failed to forward video to channel: {e}")
        await update.message.reply_text("حدث خطأ أثناء حفظ الفيديو، حاول مرة أخرى.")
    return RECEIVE_VIDEOS

async def done_adding_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END

    course_name = context.user_data.get('new_course_name')
    videos = context.user_data.get('videos', [])

    if not course_name or not videos:
        await update.message.reply_text("لم يتم إضافة أي فيديوهات. إلغاء العملية.")
        return ConversationHandler.END

    course_id = add_course(course_name)
    for idx, vid in enumerate(videos, start=1):
        add_video(course_id, vid['file_id'], vid['message_id'], idx)

    await update.message.reply_text(f"✅ تم إضافة الكورس '{course_name}' مع {len(videos)} فيديو.")
    context.user_data.pop('new_course_name', None)
    context.user_data.pop('videos', None)
    return ConversationHandler.END

# ------------------------------------------------
# محادثة إضافة إنجاز
# ------------------------------------------------
async def achievement_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # achievement_type_text, achievement_type_photo, achievement_type_video

    if data == "achievement_type_text":
        context.user_data['achievement_type'] = 'text'
        await query.edit_message_text("أرسل النص الذي تريد عرضه في الإنجاز:")
        return ACHIEVEMENT_CONTENT
    elif data == "achievement_type_photo":
        context.user_data['achievement_type'] = 'photo'
        await query.edit_message_text("أرسل الصورة (كصورة وليس ملف):")
        return ACHIEVEMENT_CONTENT
    elif data == "achievement_type_video":
        context.user_data['achievement_type'] = 'video'
        await query.edit_message_text("أرسل الفيديو (كفيديو وليس ملف):")
        return ACHIEVEMENT_CONTENT
    else:
        return ConversationHandler.END

async def achievement_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    atype = context.user_data.get('achievement_type')
    if atype == 'text':
        content = update.message.text
        if not content:
            await update.message.reply_text("الرجاء إرسال نص غير فارغ.")
            return ACHIEVEMENT_CONTENT
        context.user_data['achievement_content'] = content
        await update.message.reply_text("أرسل التعليق (اختياري، أو أرسل /skip لتخطي):")
        return ACHIEVEMENT_CAPTION
    elif atype == 'photo':
        if not update.message.photo:
            await update.message.reply_text("الرجاء إرسال صورة.")
            return ACHIEVEMENT_CONTENT
        file_id = update.message.photo[-1].file_id
        context.user_data['achievement_content'] = file_id
        await update.message.reply_text("أرسل التعليق (اختياري، أو أرسل /skip لتخطي):")
        return ACHIEVEMENT_CAPTION
    elif atype == 'video':
        if not update.message.video:
            await update.message.reply_text("الرجاء إرسال فيديو.")
            return ACHIEVEMENT_CONTENT
        file_id = update.message.video.file_id
        context.user_data['achievement_content'] = file_id
        await update.message.reply_text("أرسل التعليق (اختياري، أو أرسل /skip لتخطي):")
        return ACHIEVEMENT_CAPTION
    else:
        return ConversationHandler.END

async def achievement_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '/skip':
        caption = ""
    else:
        caption = update.message.text

    atype = context.user_data['achievement_type']
    content = context.user_data['achievement_content']
    add_achievement(atype, content, caption)
    await update.message.reply_text("✅ تم إضافة الإنجاز بنجاح.")
    context.user_data.clear()
    return ConversationHandler.END

async def skip_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await achievement_caption(update, context)

# ------------------------------------------------
# محادثة إضافة مقال
# ------------------------------------------------
async def article_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("الرجاء إدخال عنوان غير فارغ.")
        return ARTICLE_TITLE
    context.user_data['article_title'] = title
    await update.message.reply_text("أرسل محتوى المقال (نص طويل):")
    return ARTICLE_CONTENT

async def article_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = update.message.text.strip()
    if not content:
        await update.message.reply_text("الرجاء إدخال محتوى غير فارغ.")
        return ARTICLE_CONTENT
    title = context.user_data['article_title']
    add_article(title, content)
    await update.message.reply_text("✅ تم إضافة المقال بنجاح.")
    context.user_data.clear()
    return ConversationHandler.END

# ------------------------------------------------
# معالجة النصوص للأدمن (إذاعة، حظر، إعفاء)
# ------------------------------------------------
async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    text = update.message.text

    # إذاعة
    if context.user_data.get('broadcast_mode'):
        users = get_all_users_ids()
        success = failed = 0
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                success += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)
        await update.message.reply_text(f"✅ تمت الإذاعة.\nنجح: {success}\nفشل: {failed}")
        context.user_data['broadcast_mode'] = False
        return

    # حظر
    if context.user_data.get('ban_mode'):
        try:
            target_id = int(text.strip())
            set_user_blocked(target_id, True)
            await update.message.reply_text(f"✅ تم حظر المستخدم {target_id}.")
        except:
            await update.message.reply_text("❌ معرف غير صالح.")
        context.user_data['ban_mode'] = False
        return

    # إعفاء
    if context.user_data.get('exempt_mode'):
        try:
            target_id = int(text.strip())
            set_user_exempt(target_id, True)
            await update.message.reply_text(f"✅ تم إعفاء المستخدم {target_id} من نظام الدعوات.")
        except:
            await update.message.reply_text("❌ معرف غير صالح.")
        context.user_data['exempt_mode'] = False
        return
