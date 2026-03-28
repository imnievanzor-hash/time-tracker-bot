import os
import json
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "data.json"

# ─── Хранилище данных ───────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Клавиатура ─────────────────────────────────────────────────────
def main_keyboard():
    return ReplyKeyboardMarkup(
        [["📋 Мои записи", "📊 Отчёт за месяц"], ["❓ Помощь"]],
        resize_keyboard=True
    )

# ─── Команды ────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👷 *Учёт рабочего времени*\n\n"
        "Введи данные в формате:\n"
        "`Имя | Дата | Часы`\n\n"
        "Пример:\n"
        "`Anzor | 2026-03-28 | 8`\n\n"
        "Или используй кнопки ниже 👇",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Как пользоваться:*\n\n"
        "➕ *Добавить запись:*\n"
        "`Имя | Дата | Часы`\n"
        "Пример: `Anzor | 2026-03-28 | 8`\n\n"
        "📋 *Мои записи* — все записи за текущий месяц\n"
        "📊 *Отчёт за месяц* — итоги по сотрудникам и дням\n\n"
        "💡 Если ввести запись повторно за тот же день — часы суммируются.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ─── Показать записи ────────────────────────────────────────────────
async def show_records(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now()
    month_key = f"{now.year}-{now.month:02d}"

    lines = []
    total = 0
    for key, hours in sorted(data.items()):
        name, date = key.rsplit("|", 1)
        if date.startswith(month_key):
            lines.append(f"👷 {name.strip()} — {date.strip()} — *{hours} ч*")
            total += hours

    if not lines:
        await update.message.reply_text("📭 Нет записей за этот месяц.", reply_markup=main_keyboard())
        return

    text = "📋 *Записи за текущий месяц:*\n\n" + "\n".join(lines)
    text += f"\n\n*Итого: {total} ч*"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

# ─── Отчёт ──────────────────────────────────────────────────────────
async def show_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now()
    month_key = f"{now.year}-{now.month:02d}"

    by_emp = {}
    by_day = {}
    total = 0

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

    text = (
        f"📊 *Отчёт за {now.strftime('%B %Y')}*\n\n"
        f"*По сотрудникам:*\n{emp_lines}\n\n"
        f"*По дням:*\n{day_lines}\n\n"
        f"🔢 *Всего часов: {total}*"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

# ─── Обработка сообщений ────────────────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "📋 Мои записи":
        return await show_records(update, ctx)
    if text == "📊 Отчёт за месяц":
        return await show_report(update, ctx)
    if text == "❓ Помощь":
        return await help_cmd(update, ctx)

    # Парсим формат: Имя | Дата | Часы
    if "|" in text:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 3:
            await update.message.reply_text("⚠️ Формат: `Имя | Дата | Часы`\nПример: `Anzor | 2026-03-28 | 8`", parse_mode="Markdown")
            return

        name, date, hours_str = parts
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            await update.message.reply_text("⚠️ Дата должна быть в формате `ГГГГ-ММ-ДД`\nПример: `2026-03-28`", parse_mode="Markdown")
            return

        try:
            hours = float(hours_str.replace(",", "."))
            if hours <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Часы должны быть числом больше 0.", parse_mode="Markdown")
            return

        data = load_data()
        key = f"{name}|{date}"
        old = data.get(key, 0)
        data[key] = round(old + hours, 2)
        save_data(data)

        msg = f"✅ Записано: *{name}* — {date} — *{data[key]} ч*"
        if old > 0:
            msg += f"\n_(было {old} ч, добавлено {hours} ч)_"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())
    else:
        await update.message.reply_text(
            "Не понял 🤔\nВведи данные в формате:\n`Имя | Дата | Часы`",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

# ─── Запуск ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
