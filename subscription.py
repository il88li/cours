# subscription.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from database import get_user, set_referrer, increment_invites, mark_invite_rewarded, set_invite_message_shown
from database import get_user, add_or_update_user  # لإضافة مستخدم
from config import REQUIRED_CHANNEL, ADMIN_IDS
import config

logger = logging.getLogger(__name__)

async def is_user_subscribed(bot, user_id: int, channel: str) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status not in ['left', 'kicked']
    except TelegramError as e:
        logger.error(f"❌ Subscription check failed for {user_id}: {e}")
        return False

async def check_subscription_and_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user(user_id)

    if user_data.get('blocked', 0):
        await update.effective_message.reply_text("⛔ لقد تم حظرك من استخدام البوت.")
        return False

    subscribed = await is_user_subscribed(context.bot, user_id, REQUIRED_CHANNEL)
    if not subscribed:
        keyboard = [[InlineKeyboardButton("✅ تحقق مني", callback_data="verify_subscription")]]
        await update.effective_message.reply_text(
            "❗ يجب الاشتراك في القناة أولاً لاستخدام البوت.\n"
            f"🔗 رابط القناة: https://t.me/{REQUIRED_CHANNEL[1:]}\n\n"
            "بعد الاشتراك، اضغط على زر 'تحقق مني'.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return False

    # تحديث الاشتراك إذا كان جديداً
    if not user_data.get('is_subscribed', 0):
        from database import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_subscribed = 1 WHERE user_id = ?', (user_id,))
            conn.commit()
        user_data['is_subscribed'] = 1

    # مكافأة الداعي إذا كان مدعواً ولم يكافأ بعد
    referrer_id = user_data.get('referrer_id')
    if referrer_id and not user_data.get('invite_rewarded', 0):
        referrer = get_user(referrer_id)
        if referrer and not referrer.get('blocked', 0) and referrer_id != user_id:
            increment_invites(referrer_id)
            mark_invite_rewarded(user_id)
            await context.bot.send_message(
                chat_id=ADMIN_IDS[0],
                text=f"✅ تم اشتراك مدعو جديد!\n"
                     f"الداعي: {referrer_id}\n"
                     f"المدعو: {user_id}\n"
                     f"إجمالي دعوات الداعي الآن: {referrer.get('invites_count', 0) + 1}"
            )
            if (referrer.get('invites_count', 0) + 1 >= 5) or referrer.get('exempt_from_invites', 0):
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text="🎉 تهانينا! لقد أكملت دعوة 5 أشخاص وأصبح بإمكانك استخدام البوت بحرية."
                )

    return True  # مستوفي الشروط

async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and args[0].startswith("ref_"):
        referrer_id = args[0][4:]
        try:
            referrer_id = int(referrer_id)
            set_referrer(update.effective_user.id, referrer_id)
        except ValueError:
            pass
