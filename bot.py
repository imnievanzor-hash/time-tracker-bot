import os, re, json, logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main_keyboard():
    return ReplyKeyboardMarkup(
        [["📋 Мои записи", "📊 Отчёт за месяц"],
         ["👤 По сотруднику", "❓ Помощь"]],
        resize_keyboard=True
    )

def parse_date(s):
    s = s.strip()
    today = datetime.now()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m", "%d/%m", "%d-%m"):
        try:
            d = datetime.strptime(s, fmt)
            if d.year == 1900:
                d = d.replace(year=today.year)
            return d.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def smart_parse(text):
    parts = [p.strip() for p in re.split(r"[|\-/,;]+", text) if p.strip()]
    if len(parts) < 3:
        parts = text.split()
    date_str, hours_val, name_parts = None, None, []
    for part in parts:
        if date_str is None:
            d = parse_date(part)
            if d:
                date_str = d
                continue
        if hours_val is None:
            try:
                h = float(part.replace(",", "."))
                if 0 < h <= 24:
                    hours_val = h
                    continue
            except ValueError:
                pass
        name_parts.append(part)
    name = " ".join(name_parts).strip()
    if name and date_str and hours_val is not None:
        return name, date_str, hours_val
    return None

# ─── Команды ────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👷 *Учёт рабочего времени*\n\n"
        "Просто напиши имя, дату и часы — в любом формате!\n\n"
        "Примеры:\n"
        "`Anzor 2026-03-28 8`\n"
        "`Anzor | 28.03 | 8`\n"
        "`Anzor - 28/03/2026 - 7.5`\n",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Как пользоваться:*\n\n"
        "Пиши в *любом* формате:\n"
        "`Anzor 28.03 8`\n"
        "`Anzor | 2026-03-28 | 8`\n"
        "`Anzor - 28/03 - 7.5`\n\n"
        "📋 *Мои записи* — все записи за текущий месяц\n"
        "📊 *Отчёт за месяц* — итоги по всем сотрудникам\n"
        "👤 *По сотруднику* — детальный отчёт по дням\n\n"
        "💡 Повторная запись за тот же день — суммируется.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def show_records(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now()
    month_key = f"{now.year}-{now.month:02d}"
    lines, total = [], 0
    for key, hours in sorted(data.items()):
        name, date = key.rsplit("|", 1)
        if date.startswith(month_key):
            lines.append(f"👷 {name.strip()} — {date.strip()} — *{hours} ч*")
            total += hours
    if not lines:
        await update.message.reply_text("📭 Нет записей за этот месяц.", reply_markup=main_keyboard())
        return
    text = "📋 *Записи за текущий месяц:*\n\n" + "\n".join(lines) + f"\n\n*Итого: {total} ч*"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def show_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now()
    month_key = f"{now.year}-{now.month:02d}"
    by_emp, by_day, total = {}, {}, 0
    for key, hours in data.items():
        name, date = key.rsplit("|", 1)
        name, date = name.strip(), date.strip()
        if not date.startswith(month_key):
            continue
        by_emp[name] = by_emp.get(name, 0) + hours
        by_day[date] = by_day.get(date, 0) + hours
        total += hours
    if not by_emp:
        await update.message.reply_text("📭 Нет данных за этот месяц.", reply_markup=main_keyboard())
        return
    emp_lines = "\n".join([f"  👷 {n}: *{h} ч*" for n, h in sorted(by_emp.items(), key=lambda x: -x[1])])
    day_lines = "\n".join([f"  📅 {d}: *{h} ч*" for d, h in sorted(by_day.items())])
    text = (f"📊 *Отчёт за {now.strftime('%B %Y')}*\n\n"
            f"*По сотрудникам:*\n{emp_lines}\n\n"
            f"*По дням:*\n{day_lines}\n\n"
            f"🔢 *Всего часов: {total}*")
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

# ─── По сотруднику ──────────────────────────────────────────────────
async def by_employee_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Показывает кнопки с именами всех сотрудников"""
    data = load_data()
    if not data:
        await update.message.reply_text("📭 Нет данных.", reply_markup=main_keyboard())
        return

    # Собираем уникальные имена
    names = sorted(set(key.rsplit("|", 1)[0].strip() for key in data.keys()))

    buttons = [[InlineKeyboardButton(f"👷 {name}", callback_data=f"emp:{name}")] for name in names]
    await update.message.reply_text(
        "👤 *Выбери сотрудника:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def employee_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Показывает все дни выбранного сотрудника"""
    query = update.callback_query
    await query.answer()

    name = query.data.replace("emp:", "")
    data = load_data()
    now = datetime.now()
    month_key = f"{now.year}-{now.month:02d}"

    # Все записи этого сотрудника за текущий месяц
    entries = []
    for key, hours in data.items():
        emp, date = key.rsplit("|", 1)
        if emp.strip() == name and date.strip().startswith(month_key):
            entries.append((date.strip(), hours))

    if not entries:
        await query.edit_message_text(f"📭 У *{name}* нет записей за этот месяц.", parse_mode="Markdown")
        return

    entries.sort(key=lambda x: x[0])
    total = sum(h for _, h in entries)
    days = len(entries)

    lines = []
    for date, hours in entries:
        # Красивый формат даты: 28.03.2026
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
            nice_date = d.strftime("%d.%m.%Y (%a)").replace(
                "Mon", "Пн").replace("Tue", "Вт").replace("Wed", "Ср").replace(
                "Thu", "Чт").replace("Fri", "Пт").replace("Sat", "Сб").replace("Sun", "Вс")
        except:
            nice_date = date
        lines.append(f"  📅 {nice_date} — *{hours} ч*")

    text = (
        f"👷 *{name}*\n"
        f"📆 {now.strftime('%B %Y')}\n\n"
        + "\n".join(lines) +
        f"\n\n📊 Рабочих дней: *{days}*\n"
        f"⏱ Итого часов: *{total} ч*"
    )
    # Кнопка назад
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="emp_back")]])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn)

async def employee_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Возврат к списку сотрудников"""
    query = update.callback_query
    await query.answer()
    data = load_data()
    names = sorted(set(key.rsplit("|", 1)[0].strip() for key in data.keys()))
    buttons = [[InlineKeyboardButton(f"👷 {name}", callback_data=f"emp:{name}")] for name in names]
    await query.edit_message_text(
        "👤 *Выбери сотрудника:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ─── Обработка сообщений ────────────────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "📋 Мои записи": return await show_records(update, ctx)
    if text == "📊 Отчёт за месяц": return await show_report(update, ctx)
    if text == "👤 По сотруднику": return await by_employee_menu(update, ctx)
    if text == "❓ Помощь": return await help_cmd(update, ctx)

    parsed = smart_parse(text)
    if parsed:
        name, date, hours = parsed
        data = load_data()
        key = f"{name}|{date}"
        old = data.get(key, 0)
        data[key] = round(old + hours, 2)
        save_data(data)
        msg = f"✅ *{name}* — {date} — *{data[key]} ч*"
        if old > 0:
            msg += f"\n_(было {old} ч, добавлено {hours} ч)_"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())
    else:
        await update.message.reply_text(
            "Не понял 🤔 Попробуй так:\n`Anzor 28.03 8`",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

# ─── Запуск ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(employee_detail, pattern="^emp:"))
    app.add_handler(CallbackQueryHandler(employee_back, pattern="^emp_back$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
