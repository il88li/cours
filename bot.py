"""
بوت تعليمي متكامل - نسخة نهائية مع إغلاق ثغرات الدعوات
- منع دعوة النفس
- منع احتساب نفس المستخدم أكثر من مرة
- تدفق متكامل للاشتراك والدعوات
متوافق مع Python 3.10 و python-telegram-bot==20.7
"""

import logging
import sqlite3
import asyncio
import sys
from typing import Dict, List, Optional

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

# -------------------- الإعدادات الأساسية --------------------
TOKEN = "8476324781:AAHI_Q5-4DULI5PRndMUVMdkqIy3olVelFg"
CHANNEL_ID = -1003091756917
REQUIRED_CHANNEL = "@iIl337"
ADMIN_IDS = [6689435577]

COURSE_NAME, RECEIVE_VIDEOS = range(2)

# إعداد logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.info(f"🚀 Python version: {sys.version}")

# -------------------- قاعدة البيانات --------------------
DATABASE = 'courses.db'

def get_db():
    class ConnectionContextManager:
        def __enter__(self):
            self.conn = sqlite3.connect(DATABASE)
            self.conn.row_factory = sqlite3.Row
            return self.conn
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.conn.close()
    return ConnectionContextManager()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        # جدول الكورسات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # جدول الفيديوهات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                video_order INTEGER NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
            )
        ''')
        # جدول المستخدمين (مع إضافة invite_rewarded)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_subscribed BOOLEAN DEFAULT 0,
                invites_count INTEGER DEFAULT 0,
                exempt_from_invites BOOLEAN DEFAULT 0,
                blocked BOOLEAN DEFAULT 0,
                referrer_id INTEGER,
                invite_message_shown BOOLEAN DEFAULT 0,
                invite_rewarded BOOLEAN DEFAULT 0
            )
        ''')
        # جدول الإعدادات العامة
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                       ('invite_system_enabled', 'true'))
        conn.commit()

# -------------------- دوال الإعدادات --------------------
def get_setting(key: str, default: str = None) -> str:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row['value'] if row else default

def set_setting(key: str, value: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
        conn.commit()

def is_invite_system_enabled() -> bool:
    return get_setting('invite_system_enabled', 'true').lower() == 'true'

# -------------------- دوال المستخدمين --------------------
def add_or_update_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute('''
                UPDATE users
                SET username = ?, first_name = ?, last_name = ?
                WHERE user_id = ?
            ''', (username, first_name, last_name, user_id))
        else:
            cursor.execute('''
                INSERT INTO users (
                    user_id, username, first_name, last_name, joined_at,
                    is_subscribed, invites_count, exempt_from_invites, blocked,
                    invite_message_shown, invite_rewarded
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 0, 0, 0, 0, 0, 0)
            ''', (user_id, username, first_name, last_name))
        conn.commit()

def get_user(user_id: int) -> Dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        else:
            return {
                'user_id': user_id,
                'username': None,
                'first_name': None,
                'last_name': None,
                'joined_at': None,
                'is_subscribed': 0,
                'invites_count': 0,
                'exempt_from_invites': 0,
                'blocked': 0,
                'referrer_id': None,
                'invite_message_shown': 0,
                'invite_rewarded': 0
            }

def set_user_blocked(user_id: int, blocked: bool = True):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET blocked = ? WHERE user_id = ?', (1 if blocked else 0, user_id))
        conn.commit()

def set_user_exempt(user_id: int, exempt: bool = True):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET exempt_from_invites = ? WHERE user_id = ?', (1 if exempt else 0, user_id))
        conn.commit()

def increment_invites(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET invites_count = invites_count + 1 WHERE user_id = ?', (user_id,))
        conn.commit()

def set_referrer(user_id: int, referrer_id: int):
    """تعيين من دعا هذا المستخدم، مع منع دعوة النفس وعدم تغيير الداعي بعد تعيينه."""
    if user_id == referrer_id:
        return  # منع دعوة النفس
    with get_db() as conn:
        cursor = conn.cursor()
        # نتحقق أولاً إذا كان للمستخدم داعي سابق
        cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row and row['referrer_id'] is not None:
            return  # لديه داعي بالفعل، لا نغير
        cursor.execute('UPDATE users SET referrer_id = ? WHERE user_id = ?', (referrer_id, user_id))
        conn.commit()

def set_invite_message_shown(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET invite_message_shown = 1 WHERE user_id = ?', (user_id,))
        conn.commit()

def mark_invite_rewarded(user_id: int):
    """تسجيل أن هذا المستخدم تمت مكافأة داعيه عليه (مرة واحدة فقط)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET invite_rewarded = 1 WHERE user_id = ?', (user_id,))
        conn.commit()

def get_all_users_ids() -> List[int]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        return [row['user_id'] for row in cursor.fetchall()]

# -------------------- دوال الكورسات والفيديوهات --------------------
def get_courses() -> List[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM courses ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]

def get_videos(course_id: int) -> List[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, file_id, message_id, video_order
            FROM videos
            WHERE course_id=?
            ORDER BY video_order
        ''', (course_id,))
        return [dict(row) for row in cursor.fetchall()]

def add_course(name: str) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO courses (name) VALUES (?)', (name,))
        conn.commit()
        return cursor.lastrowid

def delete_course(course_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM courses WHERE id=?', (course_id,))
        conn.commit()

def add_video(course_id: int, file_id: str, message_id: int, video_order: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO videos (course_id, file_id, message_id, video_order)
            VALUES (?, ?, ?, ?)
        ''', (course_id, file_id, message_id, video_order))
        conn.commit()

# -------------------- التحقق من الاشتراك في القناة --------------------
async def is_user_subscribed(bot, user_id: int, channel: str) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status not in ['left', 'kicked']
    except TelegramError as e:
        logger.error(f"❌ Subscription check failed for {user_id}: {e}")
        return False

# -------------------- معالج /start --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_or_update_user(user.id, user.username, user.first_name, user.last_name)

    # معالجة رابط الدعوة (يتم تسجيله فقط إذا كان الداعي مختلفاً)
    args = context.args
    if args and args[0].startswith("ref_"):
        referrer_id = args[0][4:]
        try:
            referrer_id = int(referrer_id)
            set_referrer(user.id, referrer_id)  # الدالة تمنع دعوة النفس
        except ValueError:
            pass

    # ننتقل إلى خطوة التحقق من الاشتراك
    await check_subscription_and_invite(update, context)

async def check_subscription_and_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحقق من الاشتراك وعرض رسالة الدعوات مع منع التكرار."""
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    # 1. التحقق من الحظر
    if user_data.get('blocked', 0):
        await update.effective_message.reply_text("⛔ لقد تم حظرك من استخدام البوت.")
        return

    # 2. التحقق من الاشتراك في القناة
    subscribed = await is_user_subscribed(context.bot, user_id, REQUIRED_CHANNEL)
    if not subscribed:
        keyboard = [[InlineKeyboardButton("✅ تحقق مني", callback_data="verify_subscription")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.effective_message.reply_text(
            "❗ يجب الاشتراك في القناة أولاً لاستخدام البوت.\n"
            f"🔗 رابط القناة: https://t.me/{REQUIRED_CHANNEL[1:]}\n\n"
            "بعد الاشتراك، اضغط على زر 'تحقق مني'.",
            reply_markup=reply_markup
        )
        return

    # إذا كان مشتركاً، نحدّث حالة الاشتراك (إذا لم تكن محدثة)
    was_subscribed_before = user_data.get('is_subscribed', 0)
    if not was_subscribed_before:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_subscribed = 1 WHERE user_id = ?', (user_id,))
            conn.commit()
        user_data['is_subscribed'] = 1

    # 3. معالجة الدعوات (مرة واحدة فقط لكل مستخدم)
    # إذا كان هذا المستخدم مدعواً (لديه referrer_id) ولم يتم مكافأة الداعي من قبل
    referrer_id = user_data.get('referrer_id')
    if referrer_id and not user_data.get('invite_rewarded', 0):
        referrer = get_user(referrer_id)
        if referrer and not referrer.get('blocked', 0) and referrer_id != user_id:
            increment_invites(referrer_id)
            # تسجيل أن المكافأة تمت
            mark_invite_rewarded(user_id)
            # إشعار المدير
            await context.bot.send_message(
                chat_id=ADMIN_IDS[0],
                text=f"✅ تم اشتراك مدعو جديد!\n"
                     f"الداعي: {referrer_id}\n"
                     f"المدعو: {user_id}\n"
                     f"إجمالي دعوات الداعي الآن: {referrer.get('invites_count', 0) + 1}"
            )
            # إشعار الداعي إذا أكمل 5 دعوات
            if (referrer.get('invites_count', 0) + 1 >= 5) or referrer.get('exempt_from_invites', 0):
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text="🎉 تهانينا! لقد أكملت دعوة 5 أشخاص وأصبح بإمكانك استخدام البوت بحرية."
                )

    # 4. الآن نتعامل مع نظام الدعوات
    if not is_invite_system_enabled():
        await show_main_menu(update)
        return

    if user_data.get('exempt_from_invites', 0):
        await show_main_menu(update)
        return

    if user_data.get('invites_count', 0) >= 5:
        await show_main_menu(update)
        return

    # لم يكمل الدعوات بعد
    bot_username = (await context.bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    remaining = 5 - user_data.get('invites_count', 0)

    # إذا كانت هذه أول مرة يشاهد فيها رسالة الدعوات
    if not user_data.get('invite_message_shown', 0):
        long_message = (
            "🎁 *أهلاً بك في مجتمعنا التعليمي!*\n\n"
            "نحن نبذل جهداً كبيراً لتوفير محتوى تعليمي مجاني عالي الجودة، ونعتمد على دعمكم لنشر الفائدة.\n\n"
            "🌟 *لماذا نطلب منك دعوة 5 أشخاص؟*\n"
            "• لنتمكن من الوصول لأكبر عدد ممكن من الشباب المهتمين بالتعلم.\n"
            "• لضمان استمرارية البوت وتطويره.\n"
            "• لأن العلم النافع ينتشر بالمشاركة.\n\n"
            "🙏 *نقدّر تفهمك ونسألك مساعدتنا في نشر الخير.*\n\n"
            "▬ ▬ ▬ ▬ ▬ ▬ ▬ ▬ ▬ ▬\n"
            f"🔗 *رابط الدعوة الخاص بك:*\n`{invite_link}`\n\n"
            f"⏳ متبقي لديك *{remaining}* دعوات لتفعيل البوت.\n"
            "شارك الرابط مع أصدقائك، وعند اشتراكهم سيتم احتساب الدعوة تلقائياً (مرة واحدة فقط لكل صديق)."
        )
        await update.effective_message.reply_text(long_message, parse_mode=ParseMode.MARKDOWN)
        set_invite_message_shown(user_id)
    else:
        short_message = (
            f"🔗 رابط الدعوة الخاص بك:\n`{invite_link}`\n\n"
            f"⏳ متبقي لديك *{remaining}* دعوات لتفعيل البوت.\n"
            "شاركه مع أصدقائك."
        )
        await update.effective_message.reply_text(short_message, parse_mode=ParseMode.MARKDOWN)

async def show_main_menu(update: Update):
    """عرض القائمة الرئيسية للمستخدم المؤهل."""
    keyboard = [
        [KeyboardButton("📚 قائمة الكورسات")],
        [KeyboardButton("ℹ️ عن البوت"), KeyboardButton("⭐ دعم البوت بالنجوم")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.effective_message.reply_text(
        "مرحباً بك في البوت التعليمي! اختر ما تريد.",
        reply_markup=reply_markup
    )

# -------------------- معالج زر التحقق من الاشتراك --------------------
async def verify_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await check_subscription_and_invite(update, context)

# -------------------- دوال الكورسات (تتطلب صلاحية كاملة) --------------------
async def is_user_qualified(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """التحقق من أن المستخدم مؤهل لاستخدام الكورسات."""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if user.get('blocked', 0):
        await update.effective_message.reply_text("⛔ أنت محظور.")
        return False

    # يجب أن يكون مشتركاً
    subscribed = await is_user_subscribed(context.bot, user_id, REQUIRED_CHANNEL)
    if not subscribed:
        await check_subscription_and_invite(update, context)
        return False

    # تحديث الاشتراك إذا لزم
    if not user.get('is_subscribed', 0):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_subscribed = 1 WHERE user_id = ?', (user_id,))
            conn.commit()

    # إذا كان نظام الدعوات معطلاً أو معفى أو مكتمل
    if not is_invite_system_enabled() or user.get('exempt_from_invites', 0) or user.get('invites_count', 0) >= 5:
        return True

    # غير مؤهل: نعيد توجيهه إلى رسالة الدعوات
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

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"page_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])

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
    elif data == "main_menu":
        await show_main_menu(update)

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

    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])

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

# -------------------- عن البوت --------------------
async def about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *عن البوت التعليمي*\n\n"
        "هذا البوت مصمم لدعم الشباب والمهتمين بالتعلم عبر تقديم كورسات مجانية.\n"
        "للاستفسارات: @YourSupport",
        parse_mode=ParseMode.MARKDOWN
    )

# -------------------- دعم البوت بالنجوم --------------------
async def donate_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⭐ شكراً لاهتمامك بدعم البوت!\n"
        "الرجاء إرسال عدد النجوم الذي ترغب في التبرع به (رقم صحيح موجب)."
    )
    context.user_data['awaiting_stars'] = True

async def process_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_stars'):
        return

    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم صحيح موجب.")
        return

    context.user_data['awaiting_stars'] = False

    prices = [LabeledPrice("دعم البوت", amount)]

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="دعم البوت بالنجوم",
        description=f"تبرع بـ {amount} نجمة لدعم استمرارية البوت.",
        payload="donation_payload",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="donate"
    )

# -------------------- إدارة الأدمن --------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر مخصص للمشرفين فقط.")
        return

    invite_status = "مفعل" if is_invite_system_enabled() else "معطل"
    toggle_button_text = f"🔄 تعطيل نظام الدعوات" if is_invite_system_enabled() else f"🔄 تفعيل نظام الدعوات"

    keyboard = [
        [InlineKeyboardButton("➕ كورس جديد", callback_data="admin_new_course")],
        [InlineKeyboardButton("➖ حذف كورس", callback_data="admin_delete_course")],
        [InlineKeyboardButton("📢 إذاعة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🚫 حظر عضو", callback_data="admin_ban_user")],
        [InlineKeyboardButton("🆓 عفو من الرابط", callback_data="admin_exempt_user")],
        [InlineKeyboardButton(toggle_button_text, callback_data="admin_toggle_invite")]
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

    if data == "admin_new_course":
        await query.edit_message_text("أرسل اسم الكورس الجديد:")
        return ConversationHandler.END

    elif data == "admin_delete_course":
        courses = get_courses()
        if not courses:
            await query.edit_message_text("لا توجد كورسات.")
            return
        keyboard = []
        for course in courses:
            keyboard.append([InlineKeyboardButton(course['name'], callback_data=f"del_{course['id']}")])
        keyboard.append([InlineKeyboardButton("إلغاء", callback_data="admin_cancel")])
        await query.edit_message_text("اختر الكورس للحذف:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_"):
        course_id = int(data.split("_")[1])
        delete_course(course_id)
        await query.edit_message_text("✅ تم حذف الكورس بنجاح.")

    elif data == "admin_broadcast":
        await query.edit_message_text("أرسل الرسالة التي تريد إذاعتها لجميع المستخدمين:")
        context.user_data['broadcast_mode'] = True

    elif data == "admin_ban_user":
        await query.edit_message_text("أرسل معرف المستخدم (user_id) لحظره:")
        context.user_data['ban_mode'] = True

    elif data == "admin_exempt_user":
        await query.edit_message_text("أرسل معرف المستخدم (user_id) لإعفائه من نظام الدعوات:")
        context.user_data['exempt_mode'] = True

    elif data == "admin_toggle_invite":
        current = is_invite_system_enabled()
        new_value = 'false' if current else 'true'
        set_setting('invite_system_enabled', new_value)
        status = "معطل" if current else "مفعل"
        await query.edit_message_text(f"✅ تم {status} نظام الدعوات.")

    elif data == "admin_cancel":
        await query.edit_message_text("تم الإلغاء.")

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
            except TelegramError:
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

# -------------------- إضافة كورس جديد (محادثة) --------------------
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
    except TelegramError as e:
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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

# -------------------- معالجة النصوص العامة --------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📚 قائمة الكورسات":
        await show_courses(update, context)
    elif text == "ℹ️ عن البوت":
        await about_bot(update, context)
    elif text == "⭐ دعم البوت بالنجوم":
        await donate_stars(update, context)
    else:
        await update.message.reply_text("اختر أحد الأزرار من القائمة.")

# -------------------- معالجة الأخطاء العامة --------------------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="🔥 Unhandled exception:", exc_info=context.error)
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("عذراً، حدث خطأ غير متوقع. تم إبلاغ المشرف.")
    except:
        pass

# -------------------- تشغيل البوت --------------------
def main():
    init_db()
    logger.info("✅ Database initialized.")

    application = Application.builder().token(TOKEN).build()

    # محادثة إضافة كورس جديد
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback_handler, pattern="^admin_new_course$")],
        states={
            COURSE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_course_name)],
            RECEIVE_VIDEOS: [
                MessageHandler(filters.VIDEO, receive_video),
                CommandHandler('done', done_adding_videos)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(conv_handler)

    # أوامر عامة
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))

    # معالجات الرسائل النصية
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))

    # معالجات الكولباك
    application.add_handler(CallbackQueryHandler(verify_subscription_callback, pattern="^verify_subscription$"))
    application.add_handler(CallbackQueryHandler(handle_course_selection, pattern="^(course_|page_|main_menu)"))
    application.add_handler(CallbackQueryHandler(navigate_video, pattern="^(prev_video|next_video)$"))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))

    # معالجة الدعم بالنجوم
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_stars_amount))

    application.add_error_handler(error_handler)

    logger.info("🚀 Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main() 
