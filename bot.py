import asyncio, logging, re, sqlite3, datetime, random
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = "7983552580:AAG0VCo-qEomH_JIBuSWRuV2g15n54KNclw"
CHANNEL_ID = "@TridentMopsPrivat"
CHANNEL_LINK = "https://t.me/TridentMopsPrivat"
SUPER_ADMIN_USERNAME = "xquises"
HARDCODED_ADMINS = ["xquises", "rustexremakeuser"]
ACTIVE_ADMIN_IDS = set()

BAD_WORDS = ["порно", "porno", "sex", "секс", "хуй", "пизд", "нах", "пох", "бля", "ебат", "fuck", "pussy", "dick", "shit", "chlen", "член"]

SHOP_ITEMS = {
    "bur": ("🔧 Бур", 0.5),
    "m4": ("🔫 Эмка", 1.0),
    "scar": ("🔫 Скар", 2.0),
    "wood": ("🪵 Дерево (500)", 0.5),
    "iron": ("⚙️ Железо (100)", 1.0),
    "c4": ("💥 С4", 2.5),
    "satchel": ("💣 Сачель", 1.0)
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- ВАЛИДАЦИЯ ---
def is_clean_text(text: str) -> bool:
    lower_t = text.lower()
    for w in BAD_WORDS:
        if w in lower_t: return False
    return True

def is_valid_roblox(nick: str) -> bool:
    if not is_clean_text(nick): return False
    return bool(re.match(r"^[a-zA-Z0-9_]{3,20}$", nick))

def is_valid_discord(discord: str) -> bool:
    if not is_clean_text(discord): return False
    return bool(re.match(r"^[a-zA-Z0-9._#]{2,32}$", discord))

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE, username TEXT, roblox TEXT, discord TEXT, avatar_id TEXT, reg_date TEXT, coins REAL DEFAULT 0.0, status TEXT DEFAULT 'pending')")
    c.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, username TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS blacklist (user_id INTEGER PRIMARY KEY, reason TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    try: c.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'approved'")
    except: pass
    c.execute("INSERT OR IGNORE INTO settings VALUES ('server_status', '🟢 Сервер работает!')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('admin_code', 'mops2025')")
    c.execute("INSERT OR REPLACE INTO settings VALUES ('rules', '📜 **Правила приватного сервера:**\n\n1. Без читов\n2. Уважать всех\n3. Маму любить')")
    conn.commit()
    conn.close()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute(query, params)
    res = None
    if fetchone: res = c.fetchone()
    if fetchall: res = c.fetchall()
    if commit: conn.commit()
    conn.close()
    return res

def is_superadmin(user): return bool(user.username and user.username.lower() == SUPER_ADMIN_USERNAME.lower())
def is_admin(user):
    if is_superadmin(user) or (user.username and user.username.lower() in [u.lower() for u in HARDCODED_ADMINS]): return True
    return bool(db_query("SELECT 1 FROM admins WHERE user_id=?", (user.id,), fetchone=True))
def is_banned(user_id): return bool(db_query("SELECT 1 FROM blacklist WHERE user_id=?", (user_id,), fetchone=True))

def get_all_admin_ids():
    rows = db_query("SELECT user_id FROM admins", fetchall=True)
    a_ids = set(r[0] for r in rows) if rows else set()
    a_ids.update(ACTIVE_ADMIN_IDS)
    u_rows = db_query("SELECT user_id, username FROM users", fetchall=True)
    h_admins = [SUPER_ADMIN_USERNAME.lower()] + [u.lower() for u in HARDCODED_ADMINS]
    if u_rows:
        for uid, un in u_rows:
            if un and un.lower() in h_admins: a_ids.add(uid)
    return list(a_ids)

init_db()

# --- СОСТОЯНИЯ ---
class Reg(StatesGroup): roblox = State(); discord = State(); avatar = State()
class EditProfile(StatesGroup): roblox = State(); discord = State(); avatar = State()
class Rep(StatesGroup): offender = State(); reason = State(); media = State()
class Supp(StatesGroup): q = State()
class LFG(StatesGroup): desc = State()
class ShopState(StatesGroup): waiting_coords = State()
class Adm(StatesGroup): broadcast_choice = State(); broadcast_all = State(); broadcast_single_user = State(); broadcast_single_msg = State(); reply = State(); status = State(); search = State(); code_enter = State(); ban = State(); unban = State(); coin_user = State(); coin_amount = State(); direct_msg = State()

def get_user_keyboard():
    btns = [
        [KeyboardButton(text="🎰 Казино"), KeyboardButton(text="⛏ Копать")],
        [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="👤 Мой профиль")],
        [KeyboardButton(text="🏆 Топ-10"), KeyboardButton(text="🚨 Репорт")],
        [KeyboardButton(text="🔍 Найти тимейта"), KeyboardButton(text="🌐 Статус приватки")],
        [KeyboardButton(text="📜 Правила приватки"), KeyboardButton(text="🛠 Техподдержка")]
    ]
    return ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)

def get_main_keyboard(user):
    if not is_admin(user): return get_user_keyboard()
    btns = [
        [KeyboardButton(text="🎰 Казино"), KeyboardButton(text="⛏ Копать")],
        [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="👤 Мой профиль")],
        [KeyboardButton(text="🏆 Топ-10"), KeyboardButton(text="🚨 Репорт")],
        [KeyboardButton(text="🔍 Найти тимейта"), KeyboardButton(text="🌐 Статус приватки")],
        [KeyboardButton(text="📜 Правила приватки"), KeyboardButton(text="🛠 Техподдержка")],
        [KeyboardButton(text="💰 Балансы игроков"), KeyboardButton(text="⚙️ Изменить статус")],
        [KeyboardButton(text="🔎 Поиск игрока"), KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔄 Обновить меню всем")],
        [KeyboardButton(text="⛔ Баны")]
    ]
    return ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)

def cancel_kb(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

async def check_sub(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ["member", "administrator", "creator"]
    except: return False

async def notify_admins(text, photo=None, video=None, reply_markup=None):
    admin_list = get_all_admin_ids()
    for a_id in admin_list:
        try:
            if photo: await bot.send_photo(a_id, photo, caption=text, parse_mode="Markdown", reply_markup=reply_markup)
            elif video: await bot.send_video(a_id, video, caption=text, parse_mode="Markdown", reply_markup=reply_markup)
            else: await bot.send_message(a_id, text, parse_mode="Markdown", reply_markup=reply_markup)
        except: pass

@dp.message(F.text == "❌ Отмена")
async def process_cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("Действие отменено.", reply_markup=get_main_keyboard(msg.from_user))

# 1. СТАРТ
@dp.message(CommandStart())
async def cmd_start(msg: types.Message, state: FSMContext):
    if is_banned(msg.from_user.id): return await msg.answer("❌ Вы заблокированы!")
    await state.clear()
    user = msg.from_user
    
    # Автоматом заносим админа в базу
    if is_admin(user):
        ACTIVE_ADMIN_IDS.add(user.id)
        db_query("INSERT OR REPLACE INTO admins VALUES (?,?)", (user.id, user.username or "Админ"), commit=True)
        return await msg.answer(f"👑 Добро пожаловать, Админ @{user.username or user.first_name}!\nВы авторизованы.", reply_markup=get_main_keyboard(user))

    row = db_query("SELECT status FROM users WHERE user_id=?", (user.id,), fetchone=True)
    if row:
        st = row[0]
        if st == 'approved':
            return await msg.answer("👋 С возвращением в меню!", reply_markup=get_main_keyboard(user))
        elif st == 'pending':
            return await msg.answer("⏳ **Ваша заявка всё ещё на рассмотрении у Администрации.** Пожалуйста, ожидайте!")

    if await check_sub(user.id):
        await msg.answer("👋 **Привет! Подписка подтверждена.**\n\nНапишите ваш настоящий ник Roblox (только английские буквы и цифры):")
        await state.set_state(Reg.roblox)
    else:
        ikb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на наш канал", url=CHANNEL_LINK)],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
        ])
        await msg.answer("⚠️ **Для продолжения обязательно подпишитесь на наш канал:**", reply_markup=ikb)

@dp.callback_query(F.data == "check_sub")
async def cb_sub(cb: types.CallbackQuery, state: FSMContext):
    user = cb.from_user
    if is_banned(user.id): return await cb.answer("Вы забанены!", show_alert=True)
    if is_admin(user):
        ACTIVE_ADMIN_IDS.add(user.id)
        db_query("INSERT OR REPLACE INTO admins VALUES (?,?)", (user.id, user.username or "Админ"), commit=True)
        await cb.message.delete()
        return await cb.message.answer(f"👑 Добро пожаловать, Админ @{user.username or user.first_name}!", reply_markup=get_main_keyboard(user))
    
    if await check_sub(user.id):
        await cb.message.delete()
        await cb.message.answer("🎉 **Подписка подтверждена!**\n\nНапишите ваш настоящий ник Roblox (только английские буквы и цифры):")
        await state.set_state(Reg.roblox)
    else: await cb.answer("❌ Вы всё ещё не подписались на наш канал!", show_alert=True)

# 2. РЕГИСТРАЦИЯ
@dp.message(Reg.roblox)
async def reg_roblox(msg: types.Message, state: FSMContext):
    if msg.text and msg.text.startswith("/"):
        await state.clear()
        return await msg.answer("❌ Регистрация отменена.")
    
    nick = msg.text.strip() if msg.text else ""
    if not is_valid_roblox(nick):
        return await msg.answer("❌ **Некорректный ник Roblox!**\nИспользуйте только английские буквы и цифры (3-20 символов).\n\nПопробуйте ещё раз:")
    
    await state.update_data(roblox=nick)
    await msg.answer("Напишите ваш настоящий Discord tag:")
    await state.set_state(Reg.discord)

@dp.message(Reg.discord)
async def reg_discord(msg: types.Message, state: FSMContext):
    if msg.text and msg.text.startswith("/"):
        await state.clear()
        return await msg.answer("❌ Регистрация отменена.")
    
    dc = msg.text.strip() if msg.text else ""
    if not is_valid_discord(dc):
        return await msg.answer("❌ **Некорректный Discord tag!**\nПопробуйте ещё раз:")
    
    await state.update_data(discord=dc)
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_avatar")]])
    await msg.answer("📸 **Отправьте ФОТО для вашей аватарки профиля** (или нажмите 'Пропустить'):", reply_markup=ikb)
    await state.set_state(Reg.avatar)

@dp.callback_query(F.data == "skip_avatar", Reg.avatar)
async def cb_skip_avatar(cb: types.CallbackQuery, state: FSMContext):
    await finish_reg(cb.from_user, state, avatar_id=None, msg_obj=cb.message)
    await cb.answer()

@dp.message(Reg.avatar, F.photo)
async def proc_reg_avatar_photo(msg: types.Message, state: FSMContext):
    await finish_reg(msg.from_user, state, avatar_id=msg.photo[-1].file_id, msg_obj=msg)

@dp.message(Reg.avatar)
async def proc_reg_avatar_text(msg: types.Message, state: FSMContext):
    if msg.text and msg.text.startswith("/"):
        await state.clear()
        return await msg.answer("❌ Регистрация отменена.")
    if msg.text and "пропустить" in msg.text.lower():
        await finish_reg(msg.from_user, state, avatar_id=None, msg_obj=msg)
    else: await msg.answer("Пожалуйста, отправьте ФОТО или нажмите '⏩ Пропустить':")

async def finish_reg(user, state, avatar_id, msg_obj):
    data = await state.get_data()
    rb, dc = data.get("roblox"), data.get("discord")
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    
    db_query("INSERT INTO users (user_id, username, roblox, discord, avatar_id, reg_date, coins, status) VALUES (?,?,?,?,?,?,0.0,'pending') ON CONFLICT(user_id) DO UPDATE SET roblox=?, discord=?, avatar_id=?, status='pending'", (user.id, user.username or "нет_юзернейма", rb, dc, avatar_id, now, rb, dc, avatar_id), commit=True)
    
    card = (
        "📥 **НОВАЯ ЗАЯВКА НА ПРИВАТКУ!**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Telegram: @{user.username or 'нет_юзернейма'}\n"
        f"🆔 ID: `{user.id}`\n"
        f"🎮 Roblox: `{rb}`\n"
        f"💬 Discord: `{dc}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *Выберите действие ниже:*"
    )
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"app_{user.id}"), InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej_{user.id}")],
        [InlineKeyboardButton(text="💬 Написать игроку", callback_data=f"adm_msg_{user.id}")]
    ])
    await notify_admins(card, photo=avatar_id, reply_markup=ikb)
    
    await state.clear()
    await msg_obj.answer("⏳ **Ваша заявка успешно отправлена Администрации!**\nОжидайте одобрения доступа.")

# --- ОДОБРЕНИЕ И ОТКАЗ ---
@dp.callback_query(F.data.startswith("app_"))
async def cb_approve_user(cb: types.CallbackQuery):
    uid = int(cb.data.split("_")[1])
    db_query("UPDATE users SET status='approved' WHERE user_id=?", (uid,), commit=True)
    try:
        dummy_u = types.User(id=uid, is_bot=False, first_name="")
        await bot.send_message(uid, "🎉 **Ваша заявка одобрена Администрацией!**\nДобро пожаловать на сервер!", reply_markup=get_main_keyboard(dummy_u))
    except: pass
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(f"✅ Пользователь `{uid}` одобрен!")
    await cb.answer()

@dp.callback_query(F.data.startswith("rej_"))
async def cb_reject_user(cb: types.CallbackQuery):
    uid = int(cb.data.split("_")[1])
    db_query("UPDATE users SET status='rejected' WHERE user_id=?", (uid,), commit=True)
    try: await bot.send_message(uid, "❌ **Ваша заявка была отклонена Администрацией.**")
    except: pass
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(f"❌ Заявка пользователя `{uid}` отклонена.")
    await cb.answer()

@dp.callback_query(F.data.startswith("adm_msg_"))
async def cb_adm_direct_msg(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.split("_")[2])
    await state.update_data(target_msg_uid=uid)
    await cb.message.answer(f"✍️ Напишите сообщение для пользователя (ID: `{uid}`):", reply_markup=cancel_kb())
    await state.set_state(Adm.direct_msg)
    await cb.answer()

@dp.message(Adm.direct_msg)
async def proc_adm_direct_msg(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = data.get("target_msg_uid")
    try:
        await bot.send_message(uid, f"🔔 **Сообщение от Администрации:**\n\n{msg.text}")
        await msg.answer("✅ Сообщение доставлено!", reply_markup=get_main_keyboard(msg.from_user))
    except Exception as e:
        await msg.answer(f"❌ Ошибка отправки: {e}", reply_markup=get_main_keyboard(msg.from_user))
    await state.clear()

# --- КАЗИНО (ВНУТРИ БОТА) ---
@dp.message(F.text == "🎰 Казино")
async def casino_menu(msg: types.Message):
    if is_banned(msg.from_user.id): return
    c = db_query("SELECT coins FROM users WHERE user_id = ?", (msg.from_user.id,), fetchone=True)
    coins = round(c[0], 2) if c and c[0] else 0.0
    txt = f"🎰 **КАЗИНО МОПСОВ**\n💰 Ваш баланс: **{coins}** монет\n\nВыберите игру:"
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Слоты (1.0 🪙)", callback_data="bot_slots")],
        [InlineKeyboardButton(text="🎲 Кости (0.5 🪙)", callback_data="bot_dice")],
        [InlineKeyboardButton(text="🪙 Орёл или Решка (0.5 🪙)", callback_data="bot_flip")]
    ])
    await msg.answer(txt, parse_mode="Markdown", reply_markup=ikb)

@dp.callback_query(F.data == "bot_slots")
async def cb_bot_slots(cb: types.CallbackQuery):
    uid = cb.from_user.id
    c = db_query("SELECT coins FROM users WHERE user_id = ?", (uid,), fetchone=True)
    coins = round(c[0], 2) if c and c[0] else 0.0
    if coins < 1.0: return await cb.answer("❌ Нужен минимум 1.0 монета!", show_alert=True)
    
    db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) - 1.0, 2) WHERE user_id = ?", (uid,), commit=True)
    await cb.answer("🎰 Крутим барабаны...")
    dice = await bot.send_dice(chat_id=uid, emoji="🎰")
    await asyncio.sleep(2.5)
    
    if dice.dice.value == 64:
        db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) + 10.0, 2) WHERE user_id = ?", (uid,), commit=True)
        await cb.message.answer("🎉 **ДЖЕКПОТ 777!** Вы выиграли **10.0 монет**! 🏆")
    elif dice.dice.value in [1, 22, 43]:
        db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) + 2.0, 2) WHERE user_id = ?", (uid,), commit=True)
        await cb.message.answer("✨ Удвоение! Вы выиграли **2.0 монеты**!")
    else: await cb.message.answer("😢 Не повезло! Попробуйте еще раз.")

@dp.callback_query(F.data == "bot_dice")
async def cb_bot_dice(cb: types.CallbackQuery):
    uid = cb.from_user.id
    c = db_query("SELECT coins FROM users WHERE user_id = ?", (uid,), fetchone=True)
    coins = round(c[0], 2) if c and c[0] else 0.0
    if coins < 0.5: return await cb.answer("❌ Нужно минимум 0.5 монет!", show_alert=True)
    
    db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) - 0.5, 2) WHERE user_id = ?", (uid,), commit=True)
    await cb.answer("🎲 Бросаем кубик...")
    dice = await bot.send_dice(chat_id=uid, emoji="🎲")
    await asyncio.sleep(2.5)
    
    if dice.dice.value >= 4:
        db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) + 1.0, 2) WHERE user_id = ?", (uid,), commit=True)
        await cb.message.answer(f"🎉 Выпало `{dice.dice.value}`! Вы выбили **1.0 монету**!")
    else: await cb.message.answer(f"😢 Выпало `{dice.dice.value}`. Вы проиграли 0.5 монет.")

@dp.callback_query(F.data == "bot_flip")
async def cb_bot_flip_menu(cb: types.CallbackQuery):
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪙 Орёл", callback_data="flip_heads"), InlineKeyboardButton(text="👑 Решка", callback_data="flip_tails")]
    ])
    await cb.message.answer("🪙 Ставка 0.5 монет. Выберите сторону:", reply_markup=ikb)
    await cb.answer()

@dp.callback_query(F.data.startswith("flip_"))
async def cb_bot_flip_play(cb: types.CallbackQuery):
    uid = cb.from_user.id
    choice = cb.data.split("_")[1]
    c = db_query("SELECT coins FROM users WHERE user_id = ?", (uid,), fetchone=True)
    coins = round(c[0], 2) if c and c[0] else 0.0
    if coins < 0.5: return await cb.answer("❌ Нужно минимум 0.5 монет!", show_alert=True)
    
    db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) - 0.5, 2) WHERE user_id = ?", (uid,), commit=True)
    win_choice = "heads" if random.random() < 0.5 else "tails"
    
    if choice == win_choice:
        db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) + 1.0, 2) WHERE user_id = ?", (uid,), commit=True)
        await cb.message.answer(f"🎉 **ПОБЕДА!** Выпал {'🪙 Орёл' if win_choice=='heads' else '👑 Решка'}! Вы получаете **1.0 монету**!")
    else: await cb.message.answer(f"😢 **ПРОИГРЫШ!** Выпал {'🪙 Орёл' if win_choice=='heads' else '👑 Решка'}.")
    await cb.answer()

# --- КЛИКЕР И МАГАЗИН ---
@dp.message(F.text == "⛏ Копать")
async def tap_clicker(msg: types.Message):
    if is_banned(msg.from_user.id): return
    uid = msg.from_user.id
    db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) + 0.01, 2) WHERE user_id = ?", (uid,), commit=True)
    c = db_query("SELECT coins FROM users WHERE user_id = ?", (uid,), fetchone=True)
    coins = round(c[0], 2) if c and c[0] else 0.01
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⛏ Копать еще (+0.01)", callback_data="tap_coin")]])
    await msg.answer(f"⛏ **Вы накопали руду!**\n\n💰 Ваш баланс: **{coins}** монет.", reply_markup=ikb)

@dp.callback_query(F.data == "tap_coin")
async def cb_tap_coin(cb: types.CallbackQuery):
    uid = cb.from_user.id
    if is_banned(uid): return await cb.answer("Вы забанены!", show_alert=True)
    db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) + 0.01, 2) WHERE user_id = ?", (uid,), commit=True)
    c = db_query("SELECT coins FROM users WHERE user_id = ?", (uid,), fetchone=True)
    coins = round(c[0], 2) if c and c[0] else 0.01
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⛏ Копать еще (+0.01)", callback_data="tap_coin")]])
    try: await cb.message.edit_text(f"⛏ **Вы накопали руду!**\n\n💰 Ваш баланс: **{coins}** монет.", reply_markup=ikb)
    except: pass
    await cb.answer("+0.01 монетка!")

@dp.message(F.text == "🛒 Магазин")
async def open_shop(msg: types.Message, state: FSMContext):
    if is_banned(msg.from_user.id): return
    c = db_query("SELECT coins FROM users WHERE user_id = ?", (msg.from_user.id,), fetchone=True)
    coins = round(c[0], 2) if c and c[0] else 0.0
    if coins < 5.0: return await msg.answer(f"❌ **Магазин доступен только от 5 монет!**\n\n💰 Ваш баланс: **{coins}** монет.\nИспользуйте кнопку **«⛏ Копать»**, чтобы натапать минимум 5 монет!")
    
    data = await state.get_data()
    cart = data.get("cart", {})
    txt = f"🛒 **МАГАЗИН ПРЕДМЕТОВ**\n💰 Ваш баланс: **{coins}** монет\n\nВыберите предмет для добавления в корзину:"
    btns = []
    for code, (name, price) in SHOP_ITEMS.items():
        cnt = cart.get(code, 0)
        label = f"{name} — {price} монет" + (f" ({cnt} шт)" if cnt > 0 else "")
        btns.append([InlineKeyboardButton(text=label, callback_data=f"buy_{code}")])
    btns.append([InlineKeyboardButton(text="🛒 Корзина / Оформить", callback_data="view_cart"), InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")])
    await msg.answer(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("buy_"))
async def cb_buy_item(cb: types.CallbackQuery, state: FSMContext):
    code = cb.data.split("_")[1]
    data = await state.get_data()
    cart = data.get("cart", {})
    cart[code] = cart.get(code, 0) + 1
    await state.update_data(cart=cart)
    await cb.answer(f"Добавлено: {SHOP_ITEMS[code][0]}")
    c = db_query("SELECT coins FROM users WHERE user_id = ?", (cb.from_user.id,), fetchone=True)
    coins = round(c[0], 2) if c and c[0] else 0.0
    btns = []
    for item_code, (name, price) in SHOP_ITEMS.items():
        cnt = cart.get(item_code, 0)
        label = f"{name} — {price} монет" + (f" ({cnt} шт)" if cnt > 0 else "")
        btns.append([InlineKeyboardButton(text=label, callback_data=f"buy_{item_code}")])
    btns.append([InlineKeyboardButton(text="🛒 Корзина / Оформить", callback_data="view_cart"), InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")])
    try: await cb.message.edit_text(f"🛒 **МАГАЗИН ПРЕДМЕТОВ**\n💰 Ваш баланс: **{coins}** монет\n\nВыберите предмет для добавления в корзину:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    except: pass

@dp.callback_query(F.data == "clear_cart")
async def cb_clear_cart(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(cart={})
    await cb.answer("🗑 Корзина очищена!")

@dp.callback_query(F.data == "view_cart")
async def cb_view_cart(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})
    if not cart: return await cb.answer("Ваша корзина пуста!", show_alert=True)
    total = sum(SHOP_ITEMS[code][1] * cnt for code, cnt in cart.items() if code in SHOP_ITEMS)
    lines = [f"• {SHOP_ITEMS[code][0]} x{cnt} = `{round(SHOP_ITEMS[code][1]*cnt,2)}` монет" for code, cnt in cart.items() if cnt > 0 and code in SHOP_ITEMS]
    c = db_query("SELECT coins FROM users WHERE user_id = ?", (cb.from_user.id,), fetchone=True)
    coins = round(c[0], 2) if c and c[0] else 0.0
    txt = f"🛒 **ВАША КОРЗИНА:**\n\n" + "\n".join(lines) + f"\n\n💰 Итого к оплате: **{round(total, 2)}** монет\n💳 Ваш баланс: **{coins}** монет"
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Заказать", callback_data="checkout_cart")],[InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")]])
    await cb.message.answer(txt, parse_mode="Markdown", reply_markup=ikb)
    await cb.answer()

@dp.callback_query(F.data == "checkout_cart")
async def cb_checkout(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})
    total = round(sum(SHOP_ITEMS[code][1] * cnt for code, cnt in cart.items() if code in SHOP_ITEMS), 2)
    c = db_query("SELECT coins FROM users WHERE user_id = ?", (cb.from_user.id,), fetchone=True)
    coins = round(c[0], 2) if c and c[0] else 0.0
    if coins < total: return await cb.answer(f"❌ Недостаточно монет! Нужно {total}, у вас {coins}", show_alert=True)
    await cb.message.answer("📸 **Скиньте 1 фото где координаты вашего дома:**", reply_markup=cancel_kb())
    await state.set_state(ShopState.waiting_coords)
    await cb.answer()

@dp.message(ShopState.waiting_coords, F.photo)
async def proc_order_coords(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})
    total = round(sum(SHOP_ITEMS[code][1] * cnt for code, cnt in cart.items() if code in SHOP_ITEMS), 2)
    user = msg.from_user
    db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) - ?, 2) WHERE user_id = ?", (total, user.id), commit=True)
    order_items = [f"• {SHOP_ITEMS[code][0]} x{cnt}" for code, cnt in cart.items() if cnt > 0 and code in SHOP_ITEMS]
    
    u_info = db_query("SELECT roblox, discord FROM users WHERE user_id = ?", (user.id,), fetchone=True)
    rb_nick = u_info[0] if u_info else "Неизвестно"
    dc_tag = u_info[1] if u_info else "Неизвестно"
    
    admin_card = (
        "📦 **НОВЫЙ ЗАКАЗ ИЗ МАГАЗИНА!**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Telegram: @{user.username or 'нет'}\n"
        f"🆔 ID: `{user.id}`\n"
        f"🎮 Roblox: `{rb_nick}`\n"
        f"💬 Discord: `{dc_tag}`\n\n"
        f"🛒 **Заказ:**\n" + "\n".join(order_items) + f"\n\n💰 Потрачено монет: **{total}**\n"
        "━━━━━━━━━━━━━━━━━━━━\n📍 *Координаты дома на фото ниже!*"
    )
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Написать заказчику", url=f"https://t.me/{user.username}")]]) if user.username else None
    await notify_admins(admin_card, photo=msg.photo[-1].file_id, reply_markup=ikb)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад в меню", callback_data="go_main_menu")]])
    await msg.answer("✅ **Ждите вашего заказа**\nВ случае того если вы заказали и вас зарейдили мы вам все отдадим", reply_markup=kb)

@dp.callback_query(F.data == "go_main_menu")
async def cb_go_main(cb: types.CallbackQuery):
    await cb.message.answer("Главное меню:", reply_markup=get_main_keyboard(cb.from_user))
    await cb.answer()

# --- ПРОФИЛЬ, ТОП-10 И ПРАВИЛА ---
@dp.message(F.text == "👤 Мой профиль")
async def profile(msg: types.Message):
    if is_banned(msg.from_user.id): return
    r = db_query("SELECT username, roblox, discord, avatar_id, reg_date, coins FROM users WHERE user_id=?", (msg.from_user.id,), fetchone=True)
    if not r:
        if is_admin(msg.from_user):
            return await msg.answer(f"👑 **ПРОФИЛЬ АДМИНИСТРАТОРА:**\n\n🆔 ID: `{msg.from_user.id}`\n👤 Юзернейм: @{msg.from_user.username or 'нет'}\nСтатус: Авторизован как Админ", parse_mode="Markdown")
        return await msg.answer("❌ Вы еще не прошли регистрацию! Напишите /start")
    
    un, rb, dc, av_id, rdate, coins = r
    coins = round(coins, 2) if coins else 0.0
    txt = f"👤 **ВАШ ПРОФИЛЬ:**\n\n🆔 Telegram ID: `{msg.from_user.id}`\n👤 Юзернейм: @{un}\n🎮 Roblox: `{rb}`\n💬 Discord: `{dc}`\n💰 Баланс: **{coins}** монет\n📅 Дата регистрации: `{rdate or 'Неизвестно'}`"
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Сменить Roblox", callback_data="ch_roblox"), InlineKeyboardButton(text="✏️ Сменить Discord", callback_data="ch_discord")],
        [InlineKeyboardButton(text="🖼 Сменить/Поставить аватарку", callback_data="ch_avatar")]
    ])
    if av_id:
        try: return await msg.answer_photo(photo=av_id, caption=txt, parse_mode="Markdown", reply_markup=ikb)
        except: pass
    await msg.answer(txt, parse_mode="Markdown", reply_markup=ikb)

@dp.callback_query(F.data == "ch_avatar")
async def cb_ch_av(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("🖼 Отправьте ФОТО для аватарки профиля:", reply_markup=cancel_kb())
    await state.set_state(EditProfile.avatar)
    await cb.answer()

@dp.message(EditProfile.avatar, F.photo)
async def ed_avatar(msg: types.Message, state: FSMContext):
    db_query("UPDATE users SET avatar_id=? WHERE user_id=?", (msg.photo[-1].file_id, msg.from_user.id), commit=True)
    await state.clear()
    await msg.answer("✅ Аватарка профиля обновлена!", reply_markup=get_main_keyboard(msg.from_user))

@dp.callback_query(F.data == "ch_roblox")
async def cb_ch_roblox(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("Введите новый Roblox ник (английские буквы):", reply_markup=cancel_kb())
    await state.set_state(EditProfile.roblox)
    await cb.answer()

@dp.message(EditProfile.roblox)
async def ed_roblox(msg: types.Message, state: FSMContext):
    nick = msg.text.strip()
    if not is_valid_roblox(nick): return await msg.answer("❌ Некорректный ник Roblox! Попробуйте снова:")
    db_query("UPDATE users SET roblox=? WHERE user_id=?", (nick, msg.from_user.id), commit=True)
    await state.clear()
    await msg.answer("✅ Ник Roblox обновлен!", reply_markup=get_main_keyboard(msg.from_user))

@dp.callback_query(F.data == "ch_discord")
async def cb_ch_dc(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("Введите новый Discord tag:", reply_markup=cancel_kb())
    await state.set_state(EditProfile.discord)
    await cb.answer()

@dp.message(EditProfile.discord)
async def ed_dc(msg: types.Message, state: FSMContext):
    dc = msg.text.strip()
    if not is_valid_discord(dc): return await msg.answer("❌ Некорректный Discord tag! Попробуйте снова:")
    db_query("UPDATE users SET discord=? WHERE user_id=?", (dc, msg.from_user.id), commit=True)
    await state.clear()
    await msg.answer("✅ Discord обновлен!", reply_markup=get_main_keyboard(msg.from_user))

@dp.message(F.text == "🏆 Топ-10")
async def top10(msg: types.Message):
    rows = db_query("SELECT roblox, discord, username, reg_date FROM users WHERE status='approved' ORDER BY id ASC LIMIT 10", fetchall=True)
    if not rows: return await msg.answer("В топе пока пусто!")
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    t = "🏆 **ТОП-10 ПЕРВЫХ ЗАРЕГИСТРИРОВАННЫХ ИГРОКОВ:**\n\n"
    for idx, (rb, dc, un, rdate) in enumerate(rows):
        m = medals[idx] if idx < 10 else f"{idx+1}."
        t += f"{m} **Roblox:** `{rb}` | **Discord:** `{dc}` (@{un})\n📅 Зарегался: `{rdate or 'неизвестно'}`\n\n"
    await msg.answer(t, parse_mode="Markdown")

@dp.message(F.text == "📜 Правила приватки")
async def rules(msg: types.Message):
    r = db_query("SELECT value FROM settings WHERE key='rules'", fetchone=True)
    await msg.answer(r[0] if r else "Правила не заданы.", parse_mode="Markdown")

@dp.message(F.text == "🌐 Статус приватки")
async def status(msg: types.Message):
    s = db_query("SELECT value FROM settings WHERE key='server_status'", fetchone=True)
    await msg.answer(f"🌐 **Статус сервера:**\n\n{s[0] if s else '🟢 Сервер работает!'}", parse_mode="Markdown")

# --- РАССЫЛКА И СООБЩЕНИЯ ОТ АДМИНОВ ---
@dp.message(F.text == "📢 Рассылка")
async def bc_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user): return
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Всем игрокам", callback_data="bc_all")],
        [InlineKeyboardButton(text="👤 Определенному человеку", callback_data="bc_single")]
    ])
    await msg.answer("📢 **Выберите тип рассылки:**", reply_markup=ikb)

@dp.callback_query(F.data == "bc_all")
async def cb_bc_all(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("📢 Введите текст/фото/видео для рассылки всем игрокам:", reply_markup=cancel_kb())
    await state.set_state(Adm.broadcast_all)
    await cb.answer()

@dp.message(Adm.broadcast_all)
async def bc_all_proc(msg: types.Message, state: FSMContext):
    u_ids = [r[0] for r in db_query("SELECT user_id FROM users WHERE status='approved'", fetchall=True)]
    await msg.answer(f"⏳ Рассылаем по `{len(u_ids)}` пользователям...")
    s, e = 0, 0
    p = msg.photo[-1].file_id if msg.photo else None
    v = msg.video.file_id if msg.video else None
    t = "📢 **ОФИЦИАЛЬНОЕ СООБЩЕНИЕ ОТ АДМИНИСТРАЦИИ:**\n\n" + (msg.caption or msg.text or "")
    
    for u_id in u_ids:
        try:
            if p: await bot.send_photo(u_id, p, caption=t, parse_mode="Markdown")
            elif v: await bot.send_video(u_id, v, caption=t, parse_mode="Markdown")
            else: await bot.send_message(u_id, t, parse_mode="Markdown")
            s += 1
            await asyncio.sleep(0.04)
        except: e += 1
    await state.clear()
    await msg.answer(f"✅ **Рассылка завершена!**\nУспешно: `{s}` | Ошибок: `{e}`", reply_markup=get_main_keyboard(msg.from_user))

@dp.callback_query(F.data == "bc_single")
async def cb_bc_single(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("👤 Введите ник игрока (Roblox, Discord или TG юзернейм):", reply_markup=cancel_kb())
    await state.set_state(Adm.broadcast_single_user)
    await cb.answer()

@dp.message(Adm.broadcast_single_user)
async def bc_single_user_proc(msg: types.Message, state: FSMContext):
    q = f"%{msg.text.strip()}%"
    row = db_query("SELECT user_id, username, roblox FROM users WHERE roblox LIKE ? OR discord LIKE ? OR username LIKE ?", (q,q,q), fetchone=True)
    if not row: return await msg.answer("❌ Игрок не найден в базе! Попробуйте снова:", reply_markup=cancel_kb())
    
    uid, un, rb = row
    await state.update_data(single_target_uid=uid, single_target_rb=rb)
    await msg.answer(f"👤 Игрок найден: @{un} (Roblox: `{rb}`)\n\nВведите сообщение/фото/видео для этого игрока:", reply_markup=cancel_kb())
    await state.set_state(Adm.broadcast_single_msg)

@dp.message(Adm.broadcast_single_msg)
async def bc_single_msg_proc(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    uid, rb = data.get("single_target_uid"), data.get("single_target_rb")
    p = msg.photo[-1].file_id if msg.photo else None
    v = msg.video.file_id if msg.video else None
    t = "📢 **ОФИЦИАЛЬНОЕ СООБЩЕНИЕ ОТ АДМИНИСТРАЦИИ:**\n\n" + (msg.caption or msg.text or "")
    
    try:
        if p: await bot.send_photo(uid, p, caption=t, parse_mode="Markdown")
        elif v: await bot.send_video(uid, v, caption=t, parse_mode="Markdown")
        else: await bot.send_message(uid, t, parse_mode="Markdown")
        await msg.answer(f"✅ Сообщение отправлено игроку `{rb}`!", reply_markup=get_main_keyboard(msg.from_user))
    except Exception as ex:
        await msg.answer(f"❌ Ошибка отправки: {ex}", reply_markup=get_main_keyboard(msg.from_user))
    await state.clear()

# --- LFG, СУППОРТ И РЕПОРТЫ ---
@dp.message(F.text == "🔍 Найти тимейта")
async def lfg_start(msg: types.Message, state: FSMContext):
    if is_banned(msg.from_user.id): return
    await msg.answer("🔍 **Поиск тимейтов:**\nНапишите ваше сообщение (например: Ищу +2 в дс):", reply_markup=cancel_kb())
    await state.set_state(LFG.desc)

@dp.message(LFG.desc)
async def lfg_proc(msg: types.Message, state: FSMContext):
    user = msg.from_user
    txt = msg.text.strip()
    if len(txt) < 5 or not is_clean_text(txt): return await msg.answer("Непристойные слова или короткое сообщение! Опишите подробнее:", reply_markup=cancel_kb())
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Написать", url=f"https://t.me/{user.username}")]]) if user.username else None
    b_txt = f"🎮 **НОВЫЙ ПОИСК ТИМЕЙТА!**\nИгрок: @{user.username or 'без_юзернейма'}\nСообщение: {txt}"
    for u_id in [r[0] for r in db_query("SELECT user_id FROM users WHERE status='approved'", fetchall=True)]:
        if u_id != user.id:
            try: await bot.send_message(u_id, b_txt, reply_markup=ikb, parse_mode="Markdown")
            except: pass
    await state.clear()
    await msg.answer("✅ Объявление отправлено!", reply_markup=get_main_keyboard(user))

@dp.message(F.text == "🛠 Техподдержка")
async def supp_start(msg: types.Message, state: FSMContext):
    await msg.answer("🛠 Напишите ваш вопрос:", reply_markup=cancel_kb())
    await state.set_state(Supp.q)

@dp.message(Supp.q)
async def supp_proc(msg: types.Message, state: FSMContext):
    user = msg.from_user
    ikb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Ответить", callback_data=f"rep_sp_{user.id}")]])
    await notify_admins(f"📩 **ВОПРОС В ТЕХПОДДЕРЖКУ!**\nОт: @{user.username or 'без_юзернейма'} (ID: `{user.id}`)\nВопрос: {msg.text}", reply_markup=ikb)
    await state.clear()
    await msg.answer("✅ Вопрос отправлен админам!", reply_markup=get_main_keyboard(user))

@dp.callback_query(F.data.startswith("rep_sp_"))
async def cb_rep_sp(cb: types.CallbackQuery, state: FSMContext):
    t_id = int(cb.data.split("_")[2])
    await state.update_data(target_id=t_id)
    await cb.message.answer(f"✍️ Ответ для ID `{t_id}`:", reply_markup=cancel_kb())
    await state.set_state(Adm.reply)
    await cb.answer()

@dp.message(Adm.reply)
async def adm_send_rep(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    t_id = data.get("target_id")
    try: await bot.send_message(t_id, f"🔔 **Ответ от Администрации:**\n\n{msg.text}", parse_mode="Markdown")
    except: pass
    await state.clear()
    await msg.answer("✅ Ответ отправлен!", reply_markup=get_main_keyboard(msg.from_user))

@dp.message(F.text == "🚨 Репорт")
async def rep_start(msg: types.Message, state: FSMContext):
    await msg.answer("Напишите ник нарушителя:", reply_markup=cancel_kb())
    await state.set_state(Rep.offender)

@dp.message(Rep.offender)
async def rep_off(msg: types.Message, state: FSMContext):
    await state.update_data(offender=msg.text.strip())
    await msg.answer("Напишите причину репорта:", reply_markup=cancel_kb())
    await state.set_state(Rep.reason)

@dp.message(Rep.reason)
async def rep_reas(msg: types.Message, state: FSMContext):
    await state.update_data(reason=msg.text.strip())
    await msg.answer("Отправьте фото или видео (доказательство):", reply_markup=cancel_kb())
    await state.set_state(Rep.media)

@dp.message(Rep.media, F.photo | F.video)
async def rep_med(msg: types.Message, state: FSMContext):
    d = await state.get_data()
    u = msg.from_user
    txt = f"🚨 **РЕПОРТ!**\nПодал: @{u.username or 'нет'} (ID: `{u.id}`)\nНарушитель: `{d['offender']}`\nПричина: {d['reason']}"
    p = msg.photo[-1].file_id if msg.photo else None
    v = msg.video.file_id if msg.video else None
    await notify_admins(txt, photo=p, video=v)
    await state.clear()
    await msg.answer("Репорт отправлен админам! 🐶🚨", reply_markup=get_main_keyboard(u))

# --- АДМИН-КОДЫ И МЕНЮ ---
@dp.message(Command("admin"))
async def enter_code_start(msg: types.Message, state: FSMContext):
    await msg.answer("🔑 Введите секретный админ-код:", reply_markup=cancel_kb())
    await state.set_state(Adm.code_enter)

@dp.message(Adm.code_enter)
async def enter_code_proc(msg: types.Message, state: FSMContext):
    real_code = db_query("SELECT value FROM settings WHERE key='admin_code'", fetchone=True)[0]
    if msg.text.strip() == real_code:
        u = msg.from_user
        db_query("INSERT OR REPLACE INTO admins VALUES (?,?)", (u.id, u.username or "нет"), commit=True)
        ACTIVE_ADMIN_IDS.add(u.id)
        await state.clear()
        await msg.answer("🎉 Код верный! Вы получили админку!", reply_markup=get_main_keyboard(u))
    else: await msg.answer("❌ Неверный код! Попробуйте снова:", reply_markup=cancel_kb())

@dp.message(F.text == "🔄 Обновить меню всем")
async def refresh_menus(msg: types.Message):
    if not is_admin(msg.from_user): return
    u_rows = db_query("SELECT user_id FROM users WHERE status='approved'", fetchall=True) or []
    a_rows = db_query("SELECT user_id FROM admins", fetchall=True) or []
    all_ids = set(r[0] for r in u_rows + a_rows)
    all_ids.update(ACTIVE_ADMIN_IDS)
    
    await msg.answer(f"⏳ Обновляем меню `{len(all_ids)}` юзерам...")
    cnt = 0
    u_kb = get_user_keyboard()
    for u_id in all_ids:
        try:
            dummy_u = types.User(id=u_id, is_bot=False, first_name="")
            kb_to_send = get_main_keyboard(dummy_u) if is_admin(dummy_u) else u_kb
            await bot.send_message(u_id, "🔄 Меню обновлено!", reply_markup=kb_to_send)
            cnt += 1
            await asyncio.sleep(0.04)
        except: pass
    await msg.answer(f"✅ Обновлено у `{cnt}` юзеров!", reply_markup=get_main_keyboard(msg.from_user))

@dp.message(F.text == "⛔ Баны")
async def ban_menu(msg: types.Message):
    if not is_admin(msg.from_user): return
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Забанить ID", callback_data="bn_u")],
        [InlineKeyboardButton(text="✅ Разбанить ID", callback_data="un_u")],
        [InlineKeyboardButton(text="📋 Список забаненных", callback_data="ls_b")]
    ])
    await msg.answer("⛔ Управление банами:", reply_markup=ikb)

@dp.callback_query(F.data == "bn_u")
async def cb_bn(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("Введите Telegram ID для бана:", reply_markup=cancel_kb())
    await state.set_state(Adm.ban)
    await cb.answer()

@dp.message(Adm.ban)
async def proc_bn(msg: types.Message, state: FSMContext):
    if not msg.text.strip().isdigit(): return await msg.answer("❌ Введите числовой ID!")
    uid = int(msg.text.strip())
    db_query("INSERT OR REPLACE INTO blacklist VALUES (?, 'Нарушение')", (uid,), commit=True)
    await state.clear()
    await msg.answer(f"🚫 Пользователь `{uid}` забанен!", reply_markup=get_main_keyboard(msg.from_user))

@dp.callback_query(F.data == "un_u")
async def cb_un(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("Введите Telegram ID для разбана:", reply_markup=cancel_kb())
    await state.set_state(Adm.unban)
    await cb.answer()

@dp.message(Adm.unban)
async def proc_un(msg: types.Message, state: FSMContext):
    if not msg.text.strip().isdigit(): return await msg.answer("❌ Введите числовой ID!")
    uid = int(msg.text.strip())
    db_query("DELETE FROM blacklist WHERE user_id=?", (uid,), commit=True)
    await state.clear()
    await msg.answer(f"✅ Пользователь `{uid}` разбанен!", reply_markup=get_main_keyboard(msg.from_user))

@dp.callback_query(F.data == "ls_b")
async def cb_ls_b(cb: types.CallbackQuery):
    rows = db_query("SELECT user_id, reason FROM blacklist", fetchall=True)
    if not rows: await cb.message.answer("Забаненных нет!")
    else:
        t = "📋 **Черный список:**\n\n"
        for u_id, r in rows: t += f"🚫 ID: `{u_id}` | {r}\n"
        await cb.message.answer(t, parse_mode="Markdown")
    await cb.answer()

@dp.message(F.text == "📊 Статистика")
async def stats(msg: types.Message):
    if not is_admin(msg.from_user): return
    tot = db_query("SELECT COUNT(*) FROM users WHERE status='approved'", fetchone=True)[0]
    bn = db_query("SELECT COUNT(*) FROM blacklist", fetchone=True)[0]
    await msg.answer(f"📊 **СТАТИСТИКА:**\n\nИгроков одобрено: **{tot}**\nЗабанено: **{bn}**\nАдминов онлайн: **{len(ACTIVE_ADMIN_IDS)}**", parse_mode="Markdown")

@dp.message(F.text == "⚙️ Изменить статус")
async def ch_status_menu(msg: types.Message):
    if not is_admin(msg.from_user): return
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Онлайн", callback_data="st_online")],
        [InlineKeyboardButton(text="🟡 Ивент", callback_data="st_event")],
        [InlineKeyboardButton(text="🔴 Техработы", callback_data="st_tech")],
        [InlineKeyboardButton(text="✏️ Свой текст", callback_data="st_custom")]
    ])
    await msg.answer("Выберите новый статус:", reply_markup=ikb)

@dp.callback_query(F.data.startswith("st_"))
async def cb_st(cb: types.CallbackQuery, state: FSMContext):
    act = cb.data.split("_")[1]
    if act == "online":
        db_query("UPDATE settings SET value='🟢 Сервер работает в обычном режиме!' WHERE key='server_status'", commit=True)
        await cb.message.edit_text("✅ Статус: 🟢 Онлайн")
    elif act == "event":
        db_query("UPDATE settings SET value='🟡 На сервере проходит ИВЕНТ!' WHERE key='server_status'", commit=True)
        await cb.message.edit_text("✅ Статус: 🟡 Ивент")
    elif act == "tech":
        db_query("UPDATE settings SET value='🔴 Сервер на техработах.' WHERE key='server_status'", commit=True)
        await cb.message.edit_text("✅ Статус: 🔴 Техработы")
    elif act == "custom":
        await cb.message.answer("Введите ваш текст для статуса:", reply_markup=cancel_kb())
        await state.set_state(Adm.status)
    await cb.answer()

@dp.message(Adm.status)
async def proc_custom_status(msg: types.Message, state: FSMContext):
    db_query("UPDATE settings SET value=? WHERE key='server_status'", (msg.text.strip(),), commit=True)
    await state.clear()
    await msg.answer("✅ Статус обновлен!", reply_markup=get_main_keyboard(msg.from_user))

@dp.message(F.text == "🔎 Поиск игрока")
async def srch_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user): return
    await msg.answer("Введите ник Roblox/Discord/TG:", reply_markup=cancel_kb())
    await state.set_state(Adm.search)

@dp.message(Adm.search)
async def srch_proc(msg: types.Message, state: FSMContext):
    q = f"%{msg.text.strip()}%"
    rows = db_query("SELECT user_id, username, roblox, discord, coins FROM users WHERE roblox LIKE ? OR discord LIKE ? OR username LIKE ?", (q,q,q), fetchall=True)
    await state.clear()
    kb = get_main_keyboard(msg.from_user)
    if not rows: return await msg.answer("❌ Игрок не найден.", reply_markup=kb)
    t = f"🔎 **Результаты поиска:**\n\n"
    for u_id, un, r, d, c in rows: t += f"👤 @{un} (ID: `{u_id}`)\n🎮 Roblox: `{r}`\n💬 Discord: `{d}`\n💰 Монет: **{round(c or 0.0, 2)}**\n---\n"
    await msg.answer(t, parse_mode="Markdown", reply_markup=kb)

async def main():
    print("=============================")
    print("🤖 Бот Trident Mops запущен!")
    print("=============================")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())