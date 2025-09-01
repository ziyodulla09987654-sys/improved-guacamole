# main.py
# Simple Registration Bot without database
# Sends collected registration info directly to admin after user confirms

import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from zoneinfo import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Contact,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ----------------------- Config -----------------------
BOT_TOKEN = "7832412035:AAFVc6186iqlNE_HS60u11tdCzC8pvCQ02c"
ADMIN_ID = 6427405038

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")

# ----------------------- Constants -----------------------
COURSES = {
    "english": "🇬🇧 Ingliz tili",
    "german": "🇩🇪 Nemis tili",
    "math": "🧮 Matematika",
    "uzbek": "🇺🇿 Ona tili",
    "history": "📜 Tarix",
    "biology": "🧬 Biologiya",
    "chemistry": "⚗️ Kimyo",
}
COURSES_WITH_LEVEL = {"english", "german"}

LEVELS = {
    "A1": "A1 • Beginner",
    "A2": "A2 • Elementary",
    "B1": "B1 • Intermediate",
    "B2": "B2 • Upper-Intermediate",
    "C1": "C1 • Advanced",
    "C2": "C2 • Proficient",
}

SECTIONS_ENGLISH = {
    "kids": "👶 Kids",
    "general": "📘 General",
    "cefr": "🧭 CEFR",
    "ielts": "🎓 IELTS",
}
SECTIONS_GERMAN = {
    "kids": "👶 Kids",
    "general": "📘 General",
    "certificate": "🏅 Certificate",
}
SECTIONS_OTHERS = {
    "kids": "👶 Kids",
    "general": "📘 General",
    "certificate": "🏅 Certificate",
}

# ----------------------- Helpers: Keyboards -----------------------
def kb_register() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Ro'yxatdan o'tish", callback_data="reg:start")]])

def kb_courses() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    items = list(COURSES.items())
    for i in range(0, len(items), 2):
        row = []
        for key, label in items[i : i + 2]:
            row.append(InlineKeyboardButton(label, callback_data=f"reg:course:{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="reg:cancel")])
    return InlineKeyboardMarkup(rows)

def kb_levels() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(LEVELS["A1"], callback_data="reg:level:A1"),
            InlineKeyboardButton(LEVELS["A2"], callback_data="reg:level:A2"),
        ],
        [
            InlineKeyboardButton(LEVELS["B1"], callback_data="reg:level:B1"),
            InlineKeyboardButton(LEVELS["B2"], callback_data="reg:level:B2"),
        ],
        [
            InlineKeyboardButton(LEVELS["C1"], callback_data="reg:level:C1"),
            InlineKeyboardButton(LEVELS["C2"], callback_data="reg:level:C2"),
        ],
        [InlineKeyboardButton("⬅️ Ortga (Kurslar)", callback_data="reg:back:courses")],
    ]
    return InlineKeyboardMarkup(rows)

def kb_sections(course_key: str) -> InlineKeyboardMarkup:
    if course_key == "english":
        sections = SECTIONS_ENGLISH
        back = "reg:back:levels"
    elif course_key == "german":
        sections = SECTIONS_GERMAN
        back = "reg:back:levels"
    else:
        sections = SECTIONS_OTHERS
        back = "reg:back:courses"

    rows: List[List[InlineKeyboardButton]] = []
    items = list(sections.items())
    for i in range(0, len(items), 2):
        row = []
        for key, label in items[i : i + 2]:
            row.append(InlineKeyboardButton(label, callback_data=f"reg:section:{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Ortga", callback_data=back)])
    rows.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="reg:cancel")])
    return InlineKeyboardMarkup(rows)

def kb_review() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data="reg:confirm"),
                InlineKeyboardButton("✏️ O‘zgartirish", callback_data="reg:edit"),
            ],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="reg:cancel")],
        ]
    )

def kb_edit_menu(course_key: str) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton("📚 Kurs", callback_data="reg:edit:course"),
        InlineKeyboardButton("🗂 Bo‘lim", callback_data="reg:edit:section"),
    ]
    row2 = [
        InlineKeyboardButton("👤 Ism familiya", callback_data="reg:edit:name"),
        InlineKeyboardButton("🎂 Yosh", callback_data="reg:edit:age"),
    ]
    row3 = [InlineKeyboardButton("📱 Telefon", callback_data="reg:edit:phone")]
    rows = [row1, row2, row3]
    if course_key in COURSES_WITH_LEVEL:
        rows.insert(1, [InlineKeyboardButton("📊 Daraja", callback_data="reg:edit:level")])
    rows.append([InlineKeyboardButton("⬅️ Ortga (Ko‘rib chiqish)", callback_data="reg:back:review")])
    return InlineKeyboardMarkup(rows)

# ----------------------- Validators -----------------------
NAME_REGEX = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ'`-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ'`-]+)+$")


def valid_full_name(s: str) -> bool:
    s = s.strip()
    return bool(NAME_REGEX.match(s)) and (2 <= len(s.split()) <= 5)


def valid_age(s: str) -> bool:
    if not s.isdigit():
        return False
    n = int(s)
    return 3 <= n <= 100


PHONE_REGEX = re.compile(r"^\+998\d{9}$")


def normalize_phone(text: str) -> Optional[str]:
    t = text.strip().replace(" ", "")
    if t.startswith("998") and len(t) == 12:
        t = "+" + t
    if PHONE_REGEX.match(t):
        return t
    return None


# ----------------------- Content Builders -----------------------
def build_review_text(d: Dict[str, Any]) -> str:
    course_label = COURSES.get(d.get("course_key", ""), d.get("course_label", ""))
    level_label = d.get("level_label")
    section_label = d.get("section_label")
    full_name = d.get("full_name", "")
    age = d.get("age", "")
    phone = d.get("phone", "")

    lines = [
        "🧾 *Ma’lumotlarni ko‘rib chiqing:*",
        f"• 📚 *Kurs:* {course_label}",
        f"• 🗂 *Bo‘lim:* {section_label}",
        f"• 👤 *Ism familiya:* {full_name}",
        f"• 🎂 *Yosh:* {age}",
        f"• 📱 *Telefon:* {phone}",
    ]
    if d.get("course_key") in COURSES_WITH_LEVEL and level_label:
        lines.insert(2, f"• 📊 *Daraja:* {level_label}")

    return "\n".join(lines)


def build_admin_text(d: Dict[str, Any], u) -> str:
    course_label = COURSES.get(d.get("course_key", ""), d.get("course_label", ""))
    level_label = d.get("level_label")
    section_label = d.get("section_label")
    full_name = d.get("full_name", "")
    age = d.get("age", "")
    phone = d.get("phone", "")

    username = f"@{u.username}" if u.username else "@None"
    tnow = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "🔔 *Yangi o‘quvchi ro‘yxatdan o‘tdi*",
        f"👤 *Ism:* {full_name}",
        f"🎂 *Yosh:* {age}",
        f"📱 *Telefon:* {phone}",
        f"📚 *Kurs:* {course_label}",
        f"🗂 *Bo‘lim:* {section_label}",
    ]
    if d.get("course_key") in COURSES_WITH_LEVEL and level_label:
        lines.insert(6, f"📊 *Daraja:* {level_label}")

    lines += [
        f"🆔 *Telegram ID:* {u.id}",
        f"👤 *Username:* {username}",
        f"📅 *Sana:* {tnow} (Asia/Tashkent)",
    ]
    return "\n".join(lines)


# ----------------------- Flow Helpers -----------------------
async def goto_courses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 Qaysi *kurs*da o‘qimoqchisiz?\n"
        "_Iltimos, quyidagilardan birini tanlang._"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=kb_courses(),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(text, reply_markup=kb_courses(), parse_mode="Markdown")
    context.user_data["step"] = "choose_course"


async def goto_levels(query, context):
    await query.edit_message_text(
        "📊 Iltimos, *darajangizni* tanlang:",
        reply_markup=kb_levels(),
        parse_mode="Markdown",
    )
    context.user_data["step"] = "choose_level"


async def goto_sections(query, context):
    course_key = context.user_data.get("course_key")
    await query.edit_message_text(
        "🗂 Iltimos, *bo‘lim*ni tanlang:",
        reply_markup=kb_sections(course_key),
        parse_mode="Markdown",
    )
    context.user_data["step"] = "choose_section"


async def ask_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "✍️ *Iltimos, to‘liq ism-familiyangizni kiriting.*\n"
        "_Masalan: Alamazon Olividinov_"
    )
    await update.effective_chat.send_message(msg, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    context.user_data["step"] = "ask_name"


async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message("🎂 *Yoshingizni kiriting:*", parse_mode="Markdown")
    context.user_data["step"] = "ask_age"


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.effective_chat.send_message(
        "📞 *Telefon raqamingizni kiriting* (format: `+998XXXXXXXXX`) yoki pastdagi tugma orqali yuboring.",
        parse_mode="Markdown",
        reply_markup=kb,
    )
    context.user_data["step"] = "ask_phone"


async def show_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = build_review_text(context.user_data)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=kb_review(), parse_mode="Markdown")
    else:
        await update.effective_chat.send_message(text, reply_markup=kb_review(), parse_mode="Markdown")
    context.user_data["step"] = "review"


# ----------------------- Handlers -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "Assalomu alaykum!\n"
        "*Welcome to ITeach Academy* 🎓\n\n"
        "Bizning o‘quv jamoamizga qo‘shilish va ro‘yxatdan o‘tish uchun pastdagi tugmani bosing."
    )
    await update.message.reply_text(welcome, reply_markup=kb_register(), parse_mode="Markdown")
    context.user_data.clear()


async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    await query.answer()
    logging.info("Callback data: %s", data)

    if data == "reg:cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Ro‘yxatdan o‘tish bekor qilindi.")
        return

    if data == "reg:start":
        await goto_courses(update, context)
        return

    if data == "reg:back:courses":
        context.user_data.pop("level_key", None)
        context.user_data.pop("level_label", None)
        context.user_data.pop("section_key", None)
        context.user_data.pop("section_label", None)
        await goto_courses(update, context)
        return

    if data == "reg:back:levels":
        context.user_data.pop("section_key", None)
        context.user_data.pop("section_label", None)
        await goto_levels(query, context)
        return

    if data == "reg:back:review":
        await show_review(update, context)
        return

    if data.startswith("reg:course:"):
        course_key = data.split(":")[2]
        if course_key not in COURSES:
            await query.edit_message_text("Noto‘g‘ri kurs tanlandi. Qaytadan urinib ko‘ring.")
            return
        context.user_data["course_key"] = course_key
        context.user_data["course_label"] = COURSES[course_key]
        context.user_data.pop("level_key", None)
        context.user_data.pop("level_label", None)
        context.user_data.pop("section_key", None)
        context.user_data.pop("section_label", None)

        if course_key in COURSES_WITH_LEVEL:
            await goto_levels(query, context)
        else:
            await goto_sections(query, context)
        return

    if data.startswith("reg:level:"):
        level_key = data.split(":")[2]
        if level_key not in LEVELS:
            await query.edit_message_text("Noto‘g‘ri daraja tanlandi. Qaytadan urinib ko‘ring.")
            return
        context.user_data["level_key"] = level_key
        context.user_data["level_label"] = LEVELS[level_key]
        await goto_sections(query, context)
        return

    if data.startswith("reg:section:"):
        section_key = data.split(":")[2]
        course_key = context.user_data.get("course_key")
        valid_keys = (
            SECTIONS_ENGLISH
            if course_key == "english"
            else SECTIONS_GERMAN
            if course_key == "german"
            else SECTIONS_OTHERS
        )
        if section_key not in valid_keys:
            await query.edit_message_text("Noto‘g‘ri bo‘lim tanlandi. Qaytadan urinib ko‘ring.")
            return
        context.user_data["section_key"] = section_key
        context.user_data["section_label"] = valid_keys[section_key]
        await ask_full_name(update, context)
        return

    if data == "reg:confirm":
        required = ["course_key", "course_label", "section_label", "full_name", "age", "phone"]
        if context.user_data.get("course_key") in COURSES_WITH_LEVEL:
            required.append("level_label")
        missing = [k for k in required if not context.user_data.get(k)]
        if missing:
            await query.edit_message_text(
                "Ma’lumotlar yetarli emas. Iltimos, /start buyrug‘i bilan qaytadan boshlang."
            )
            context.user_data.clear()
            return

        # Send registration data to admin
        user = update.effective_user
        summary_text = build_admin_text(context.user_data, user)
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=summary_text, parse_mode="Markdown")
        except Exception as e:
            logging.warning(f"Adminga habar yuborishda xato: {e}")

        await query.edit_message_text(
            "🎉 *Tabriklaymiz!* Siz ro‘yxatdan o‘tdingiz.\nTez orada siz bilan telefon raqamingiz orqali bog‘lanamiz.",
            parse_mode="Markdown",
        )

        context.user_data.clear()
        return

    if data == "reg:edit":
        course_key = context.user_data.get("course_key", "")
        await query.edit_message_text(
            "Qaysi *bo‘limni* o‘zgartiramiz?",
            reply_markup=kb_edit_menu(course_key),
            parse_mode="Markdown",
        )
        context.user_data["step"] = "edit_menu"
        return

    if data.startswith("reg:edit:"):
        field = data.split(":")[2]
        context.user_data["edit_field"] = field

        if field == "course":
            await goto_courses(update, context)
            return
        if field == "level":
            await goto_levels(query, context)
            return
        if field == "section":
            await goto_sections(query, context)
            return
        if field == "name":
            await query.edit_message_text("✍️ Yangi *ism-familiya*ni kiriting:", parse_mode="Markdown")
            context.user_data["step"] = "ask_name"
            return
        if field == "age":
            await query.edit_message_text("🎂 Yangi *yosh*ni kiriting:", parse_mode="Markdown")
            context.user_data["step"] = "ask_age"
            return
        if field == "phone":
            kb = ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Raqamni ulashish", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await query.edit_message_text(
                "📞 Yangi *telefon*ni kiriting (format: `+998XXXXXXXXX`) yoki pastdagi tugma orqali yuboring.",
                parse_mode="Markdown",
            )
            await update.effective_chat.send_message("Telefonni yuboring:", reply_markup=kb)
            context.user_data["step"] = "ask_phone"
            return


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")
    text = (update.message.text or "").strip()

    if step == "ask_name":
        if not valid_full_name(text):
            await update.message.reply_text(
                "❌ To‘liq ism-familiya kiriting.\nMasalan: *Alamazon Olividinov*",
                parse_mode="Markdown",
            )
            return
        context.user_data["full_name"] = text
        await ask_age(update, context)
        return

    if step == "ask_age":
        if not valid_age(text):
            await update.message.reply_text("❌ Yosh faqat 3–100 oralig‘ida bo‘lishi kerak. Qayta kiriting:")
            return
        context.user_data["age"] = int(text)
        await ask_phone(update, context)
        return

    if step == "ask_phone":
        normalized = normalize_phone(text)
        if not normalized:
            await update.message.reply_text(
                "❌ Noto‘g‘ri format. Iltimos, *+998XXXXXXXXX* shaklida kiriting yoki pastdagi tugmadan foydalaning.",
                parse_mode="Markdown",
            )
            return
        context.user_data["phone"] = normalized
        await show_review(update, context)
        return

    await update.message.reply_text(
        "Iltimos, /start buyrug‘i bilan boshlang yoki jarayon tugmalaridan foydalaning."
    )


async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")
    contact: Contact = update.message.contact
    phone = contact.phone_number if contact else None
    if step != "ask_phone" or not phone:
        return
    normalized = normalize_phone(phone)
    if not normalized:
        await update.message.reply_text(
            "❌ Telefon raqamingiz *+998XXXXXXXXX* formatida bo‘lishi kerak. Qayta yuboring.",
            parse_mode="Markdown",
        )
        return
    context.user_data["phone"] = normalized
    await update.message.reply_text("✔️ Qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    await show_review(update, context)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Jarayon bekor qilindi. Qayta boshlash uchun /start bosing.", reply_markup=ReplyKeyboardRemove()
    )


# ----------------------- App bootstrap -----------------------
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel_cmd))
    application.add_handler(CallbackQueryHandler(cb_handler, pattern=r"^reg:"))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
