import os, re, json, logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "data.json"

ADVANCE_FILE = "advances.json"

def load_advances():
    if os.path.exists(ADVANCE_FILE):
        with open(ADVANCE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_advances(data):
    with open(ADVANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

# ─── Данные ─────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_available_months(data):
    """Возвращает все месяцы, за которые есть данные (отсортированные, свежие сначала)"""
    months = set()
    for key in data.keys():
        _, date = key.rsplit("|", 1)
        months.add(date.strip()[:7])  # "2026-03"
    return sorted(months, reverse=True)

# ─── Клавиатура ─────────────────────────────────────────────────────
def main_keyboard():
    return ReplyKeyboardMarkup(
        [["📋 Мои записи", "📊 Отчёт за месяц"],
         ["👤 По сотруднику", "💶 Авансы"],
         ["❓ Помощь"]],
        resize_keyboard=True
    )

def month_selector_keyboard(months, callback_prefix):
    """Кнопки выбора месяца"""
    buttons = []
    for m in months:
        year, mon = m.split("-")
        label = f"{MONTHS_RU[int(mon)]} {year}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{callback_prefix}:{m}")])
    return InlineKeyboardMarkup(buttons)

# ─── Парсинг ────────────────────────────────────────────────────────
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

def parse_advance(text):
    """
    Рабочий сам пишет:
      аванс Anzor 500
      аванс Anzor 500 28.03
      аванс Anzor 28.03 500
      avans Anzor 500
    """
    text = text.strip()
    lower = text.lower()
    if not (lower.startswith("аванс") or lower.startswith("avans")):
        return None
    rest = re.sub(r"^(аванс|avans)\s*", "", text, flags=re.IGNORECASE).strip()
    parts = [p.strip() for p in re.split(r"[\s|,;]+", rest) if p.strip()]

    date_str, amount, name_parts = None, None, []
    for part in parts:
        if date_str is None:
            d = parse_date(part)
            if d:
                date_str = d
                continue
        if amount is None:
            try:
                v = float(part.replace(",", "."))
                if v > 0:
                    amount = v
                    continue
            except ValueError:
                pass
        name_parts.append(part)

    name = " ".join(name_parts).strip()
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    if name and amount is not None:
        return name, date_str, amount
    return None

def get_available_advance_months(data):
    months = set()
    for key in data.keys():
        # key = "Name|date|idx"
        parts = key.split("|")
        if len(parts) >= 2:
            months.add(parts[1][:7])
    return sorted(months, reverse=True)

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
        "📋 *Мои записи* — записи за выбранный месяц\n"
        "📊 *Отчёт за месяц* — итоги по всем сотрудникам\n"
        "👤 *По сотруднику* — детальный отчёт по дням\n\n"
        "💡 Повторная запись за тот же день — суммируется.\n"
        "📅 Можно смотреть любой прошлый месяц!\n\n"
        "💶 *Аванс (пишет сам рабочий):*\n"
        "`аванс Anzor 500`\n"
        "`аванс Anzor 500 28.03`",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ─── Мои записи — выбор месяца ──────────────────────────────────────
async def show_records(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    months = get_available_months(data)
    if not months:
        await update.message.reply_text("📭 Нет записей.", reply_markup=main_keyboard())
        return
    await update.message.reply_text(
        "📋 *Выбери месяц:*",
        parse_mode="Markdown",
        reply_markup=month_selector_keyboard(months, "records")
    )

async def show_records_month(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    month_key = query.data.replace("records:", "")
    data = load_data()
    year, mon = month_key.split("-")
    label = f"{MONTHS_RU[int(mon)]} {year}"

    lines, total = [], 0
    for key, hours in sorted(data.items()):
        name, date = key.rsplit("|", 1)
        if date.strip().startswith(month_key):
            lines.append(f"👷 {name.strip()} — {date.strip()} — *{hours} ч*")
            total += hours

    if not lines:
        await query.edit_message_text(f"📭 Нет записей за {label}.")
        return

    text = f"📋 *Записи за {label}:*\n\n" + "\n".join(lines) + f"\n\n*Итого: {total} ч*"
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="records_back")]])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn)

async def records_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    months = get_available_months(data)
    await query.edit_message_text(
        "📋 *Выбери месяц:*",
        parse_mode="Markdown",
        reply_markup=month_selector_keyboard(months, "records")
    )

# ─── Отчёт за месяц — выбор месяца ─────────────────────────────────
async def show_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    months = get_available_months(data)
    if not months:
        await update.message.reply_text("📭 Нет данных.", reply_markup=main_keyboard())
        return
    await update.message.reply_text(
        "📊 *Выбери месяц для отчёта:*",
        parse_mode="Markdown",
        reply_markup=month_selector_keyboard(months, "report")
    )

async def show_report_month(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    month_key = query.data.replace("report:", "")
    data = load_data()
    year, mon = month_key.split("-")
    label = f"{MONTHS_RU[int(mon)]} {year}"

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
        await query.edit_message_text(f"📭 Нет данных за {label}.")
        return

    emp_lines = "\n".join([f"  👷 {n}: *{h} ч*" for n, h in sorted(by_emp.items(), key=lambda x: -x[1])])
    day_lines = "\n".join([f"  📅 {d}: *{h} ч*" for d, h in sorted(by_day.items())])
    text = (f"📊 *Отчёт за {label}*\n\n"
            f"*По сотрудникам:*\n{emp_lines}\n\n"
            f"*По дням:*\n{day_lines}\n\n"
            f"🔢 *Всего часов: {total}*")
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="report_back")]])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn)

async def report_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    months = get_available_months(data)
    await query.edit_message_text(
        "📊 *Выбери месяц для отчёта:*",
        parse_mode="Markdown",
        reply_markup=month_selector_keyboard(months, "report")
    )

# ─── Авансы ─────────────────────────────────────────────────────────
async def advances_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_advances()
    months = get_available_advance_months(data)
    if not months:
        await update.message.reply_text("📭 Авансов пока нет.", reply_markup=main_keyboard())
        return
    await update.message.reply_text(
        "💵 *Выбери месяц для просмотра авансов:*",
        parse_mode="Markdown",
        reply_markup=month_selector_keyboard(months, "adv")
    )

async def advances_month(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    month_key = query.data.replace("adv:", "")
    data = load_advances()
    year, mon = month_key.split("-")
    label = f"{MONTHS_RU[int(mon)]} {year}"

    # Группируем по сотруднику
    by_emp = {}
    total_all = 0
    for key, amount in data.items():
        parts = key.split("|")
        if len(parts) < 2:
            continue
        name, date = parts[0].strip(), parts[1].strip()
        if not date.startswith(month_key):
            continue
        by_emp.setdefault(name, []).append((date, amount))
        total_all += amount

    if not by_emp:
        await query.edit_message_text(f"📭 Авансов за {label} нет.")
        return

    lines = []
    for name, entries in sorted(by_emp.items()):
        subtotal = sum(a for _, a in entries)
        lines.append(f"👷 *{name}* — итого: *{subtotal:g} €*")
        for date, amount in sorted(entries):
            try:
                d = datetime.strptime(date, "%Y-%m-%d")
                nice = d.strftime("%d.%m.%Y")
            except:
                nice = date
            lines.append(f"  📅 {nice} — {amount:g} €")

    text = (f"💶 *Авансы SolarexpertDE за {label}*\n\n"
            + "\n".join(lines) +
            f"\n\n💰 *Всего выдано: {total_all:g} €*")
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="adv_back")]])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn)

async def advances_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_advances()
    months = get_available_advance_months(data)
    await query.edit_message_text(
        "💵 *Выбери месяц для просмотра авансов:*",
        parse_mode="Markdown",
        reply_markup=month_selector_keyboard(months, "adv")
    )

# ─── По сотруднику — выбор месяца ───────────────────────────────────
async def by_employee_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data:
        await update.message.reply_text("📭 Нет данных.", reply_markup=main_keyboard())
        return
    months = get_available_months(data)
    await update.message.reply_text(
        "👤 *Сначала выбери месяц:*",
        parse_mode="Markdown",
        reply_markup=month_selector_keyboard(months, "emp_month")
    )

async def emp_month_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """После выбора месяца — показываем список сотрудников"""
    query = update.callback_query
    await query.answer()
    month_key = query.data.replace("emp_month:", "")
    ctx.user_data["emp_month"] = month_key  # запоминаем выбранный месяц

    data = load_data()
    # Только те сотрудники, у которых есть записи за этот месяц
    names = sorted(set(
        key.rsplit("|", 1)[0].strip()
        for key, _ in data.items()
        if key.rsplit("|", 1)[1].strip().startswith(month_key)
    ))
    if not names:
        year, mon = month_key.split("-")
        await query.edit_message_text(f"📭 Нет данных за {MONTHS_RU[int(mon)]} {year}.")
        return

    year, mon = month_key.split("-")
    buttons = [[InlineKeyboardButton(f"👷 {name}", callback_data=f"emp:{name}")] for name in names]
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="emp_month_back")])
    await query.edit_message_text(
        f"👤 *Выбери сотрудника ({MONTHS_RU[int(mon)]} {year}):*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def employee_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    name = query.data.replace("emp:", "")
    data = load_data()

    # Берём месяц из памяти, если нет — текущий
    month_key = ctx.user_data.get("emp_month", datetime.now().strftime("%Y-%m"))
    year, mon = month_key.split("-")
    label = f"{MONTHS_RU[int(mon)]} {year}"

    entries = [
        (date.strip(), hours)
        for key, hours in data.items()
        for emp, date in [key.rsplit("|", 1)]
        if emp.strip() == name and date.strip().startswith(month_key)
    ]

    if not entries:
        await query.edit_message_text(f"📭 У *{name}* нет записей за {label}.", parse_mode="Markdown")
        return

    entries.sort(key=lambda x: x[0])
    total = sum(h for _, h in entries)
    days = len(entries)

    day_map = {"Mon": "Пн", "Tue": "Вт", "Wed": "Ср", "Thu": "Чт", "Fri": "Пт", "Sat": "Сб", "Sun": "Вс"}
    lines = []
    for date, hours in entries:
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
            nice = d.strftime("%d.%m.%Y (%a)")
            for en, ru in day_map.items():
                nice = nice.replace(en, ru)
        except:
            nice = date
        lines.append(f"  📅 {nice} — *{hours} ч*")

    text = (
        f"👷 *{name}*\n"
        f"📆 {label}\n\n"
        + "\n".join(lines) +
        f"\n\n📊 Рабочих дней: *{days}*\n"
        f"⏱ Итого часов: *{total} ч*"
    )
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="emp_back")]])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn)

async def employee_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Назад к списку сотрудников (того же месяца)"""
    query = update.callback_query
    await query.answer()
    month_key = ctx.user_data.get("emp_month", datetime.now().strftime("%Y-%m"))
    data = load_data()
    names = sorted(set(
        key.rsplit("|", 1)[0].strip()
        for key, _ in data.items()
        if key.rsplit("|", 1)[1].strip().startswith(month_key)
    ))
    year, mon = month_key.split("-")
    buttons = [[InlineKeyboardButton(f"👷 {name}", callback_data=f"emp:{name}")] for name in names]
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="emp_month_back")])
    await query.edit_message_text(
        f"👤 *Выбери сотрудника ({MONTHS_RU[int(mon)]} {year}):*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def emp_month_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Назад к выбору месяца для сотрудников"""
    query = update.callback_query
    await query.answer()
    data = load_data()
    months = get_available_months(data)
    await query.edit_message_text(
        "👤 *Сначала выбери месяц:*",
        parse_mode="Markdown",
        reply_markup=month_selector_keyboard(months, "emp_month")
    )

# ─── Обработка сообщений ────────────────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "📋 Мои записи":    return await show_records(update, ctx)
    if text == "📊 Отчёт за месяц": return await show_report(update, ctx)
    if text == "👤 По сотруднику":  return await by_employee_menu(update, ctx)
    if text == "💵 Авансы":         return await advances_menu(update, ctx)
    if text == "❓ Помощь":         return await help_cmd(update, ctx)

    # Проверяем аванс первым
    adv = parse_advance(text)
    if adv:
        name, date, amount = adv
        advances = load_advances()
        # Уникальный ключ: имя|дата|порядковый номер (чтобы несколько авансов в один день не суммировались, а хранились отдельно)
        idx = sum(1 for k in advances if k.startswith(f"{name}|{date}|"))
        key = f"{name}|{date}|{idx}"
        advances[key] = amount
        save_advances(advances)
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
            nice_date = d.strftime("%d.%m.%Y")
        except:
            nice_date = date
        await update.message.reply_text(
            f"💶 Аванс записан!\n👷 *{name}* — {nice_date} — *{amount:g} €*",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return

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

    # Авансы
    app.add_handler(CallbackQueryHandler(advances_month, pattern="^adv:"))
    app.add_handler(CallbackQueryHandler(advances_back,  pattern="^adv_back$"))

    # Мои записи
    app.add_handler(CallbackQueryHandler(show_records_month, pattern="^records:"))
    app.add_handler(CallbackQueryHandler(records_back,       pattern="^records_back$"))

    # Отчёт
    app.add_handler(CallbackQueryHandler(show_report_month,  pattern="^report:"))
    app.add_handler(CallbackQueryHandler(report_back,        pattern="^report_back$"))

    # По сотруднику
    app.add_handler(CallbackQueryHandler(emp_month_selected, pattern="^emp_month:"))
    app.add_handler(CallbackQueryHandler(emp_month_back,     pattern="^emp_month_back$"))
    app.add_handler(CallbackQueryHandler(employee_detail,    pattern="^emp:"))
    app.add_handler(CallbackQueryHandler(employee_back,      pattern="^emp_back$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
