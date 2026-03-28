import os, re, json, logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

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
        [["📋 Мои записи", "📊 Отчёт за месяц"], ["❓ Помощь"]],
        resize_keyboard=True
    )

def parse_date(s):
    """Пробует разные форматы даты, возвращает YYYY-MM-DD или None"""
    s = s.strip()
    today = datetime.now()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y",
                "%d.%m", "%d/%m", "%d-%m"):
        try:
            d = datetime.strptime(s, fmt)
            if d.year == 1900:
                d = d.replace(year=today.year)
            return d.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def smart_parse(text):
    """
    Умный парсер: ищет в тексте имя, дату и часы в любом порядке.
    Возвращает (name, date_str, hours) или None.
    """
    # Разбиваем по любому разделителю: |, -, /
    parts = [p.strip() for p in re.split(r"[|\-/,;]+", text) if p.strip()]
    
    # Также пробуем разбить просто по пробелам если частей < 3
    if len(parts) < 3:
        parts = text.split()

    date_str = None
    hours_val = None
    name_parts = []

    for part in parts:
        # Проверяем дату
        if date_str is None:
            d = parse_date(part)
            if d:
                date_str = d
                continue
        # Проверяем число (часы)
        if hours_val is None:
            try:
                h = float(part.replace(",", "."))
                if 0 < h <= 24:
                    hours_val = h
                    continue
            except ValueError:
                pass
        # Остальное — имя
        name_parts.append(part)

    name = " ".join(name_parts).strip()

    if name and date_str and hours_val is not None:
        return name, date_str, hours_val
    return None

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👷 *Учёт рабочего времени*\n\n"
        "Просто напиши имя, дату и часы — в любом формате!\n\n"
        "Примеры:\n"
        "`Anzor 2026-03-28 8`\n"
        "`Anzor | 28.03 | 8`\n"
        "`Anzor 28/03/2026 7.5`\n"
        "`Anzor - 28.03 - 8`\n",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Как пользоваться:*\n\n"
        "Пиши в *любом* формате:\n"
        "`Anzor 28.03 8`\n"
        "`Anzor | 2026-03-28 | 8`\n"
        "`Anzor - 28/03/2026 - 7.5`\n\n"
        "📋 *Мои записи* — все записи за текущий месяц\n"
        "📊 *Отчёт за месяц* — итоги по сотрудникам и дням\n\n"
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

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "📋 Мои записи": return await show_records(update, ctx)
    if text == "📊 Отчёт за месяц": return await show_report(update, ctx)
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

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
