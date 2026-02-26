# donations.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import DONATION_TARGET
from keyboards import back_to_main_button

async def donate_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # رسالة عاطفية طويلة تشرح حاجتنا للدعم
    message = (
        "💖 *رسالة إلى قلبك الطيب*\n\n"
        "عزيزي الداعم،\n\n"
        "نحن نقدر لك اهتمامك بدعم هذا المشروع التعليمي الذي يهدف لمساعدة الشباب العربي في تطوير مهاراتهم وتعلم البرمجة مجانًا. فريق العمل يعمل بجد لتوفير محتوى مميز، ودعمك المادي ولو بالقليل يساعدنا على الاستمرار وتحسين الخدمة.\n\n"
        "إذا كنت ترغب بدعمنا، يمكنك إرسال نجوم تيليجرام إلى حساب المدير:\n"
        f"🔗 {DONATION_TARGET}\n\n"
        "أي مبلغ مهما كان صغيراً سيكون له أثر كبير في استمرارية العطاء.\n"
        "شكراً جزيلاً لك من أعماق قلوبنا ❤️"
    )

    # زر لفتح المحادثة مع المدير مباشرة
    keyboard = [
        [InlineKeyboardButton("💰 إرسال النجوم", url=f"https://t.me/{DONATION_TARGET[1:]}")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
