import asyncio, logging, re, sqlite3, datetime, json, os, random
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = "7983552580:AAG0VCo-qEomH_JIBuSWRuV2g15n54KNclw"
SUPER_ADMIN = "xquises"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    # Добавили device_id для защиты твоего аккаунта!
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, roblox TEXT UNIQUE, discord TEXT, passHash TEXT, coins REAL DEFAULT 0.0, is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, device_id TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
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

init_db()

# Отправка уведомлений в ТГ админам
async def notify_admins_tg(text):
    # Ищем всех админов в базе, у которых привязан Telegram ID (если мы его знаем)
    # Для простоты пока отправляем в консоль или можно жестко задать твой ТГ ID
    print(f"УВЕДОМЛЕНИЕ АДМИНАМ:\n{text}")

# --- API ДЛЯ МОБИЛЬНОГО ПРИЛОЖЕНИЯ (АПК) ---
async def handle_options(request):
    return web.Response(headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST, GET, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type'})

async def handle_api(request):
    headers = {'Access-Control-Allow-Origin': '*'}
    try:
        data = await request.json()
        action = data.get("action")
        
        # 1. РЕГИСТРАЦИЯ
        if action == "register":
            rb, dc, pHash, dev_id = data['roblox'], data['discord'], data['passHash'], data.get('device_id', '')
            is_adm = 1 if rb.lower() == SUPER_ADMIN.lower() else 0
            try:
                db_query("INSERT INTO users (roblox, discord, passHash, coins, is_admin, is_banned, device_id) VALUES (?,?,?,5.0,?,0,?)", (rb, dc, pHash, is_adm, dev_id), commit=True)
                return web.json_response({"success": True, "coins": 5.0, "isAdmin": is_adm == 1}, headers=headers)
            except:
                return web.json_response({"success": False, "error": "Ник уже занят!"}, headers=headers)
        
        # 2. ВХОД И ЗАЩИТА "ПОШЕЛ НАХУЙ"
        elif action == "login":
            rb, pHash, dev_id = data['roblox'], data['passHash'], data.get('device_id', '')
            user = db_query("SELECT discord, coins, is_admin, is_banned, device_id FROM users WHERE LOWER(roblox)=? AND passHash=?", (rb.lower(), pHash), fetchone=True)
            
            if user:
                if user[3] == 1: 
                    return web.json_response({"success": False, "error": "АККАУНТ ЗАБАНЕН!"}, headers=headers)
                
                # ЗАЩИТА ТВОЕГО АККАУНТА ОТ ВЗЛОМА С ДРУГОГО ТЕЛЕФОНА
                if rb.lower() == SUPER_ADMIN.lower() and user[4] != dev_id:
                    return web.json_response({"success": False, "error": "пошел нахуй"}, headers=headers)

                return web.json_response({"success": True, "discord": user[0], "coins": user[1], "isAdmin": user[2] == 1}, headers=headers)
            return web.json_response({"success": False, "error": "Неверный логин или пароль!"}, headers=headers)
        
        # 3. СИНХРОНИЗАЦИЯ МОНЕТ
        elif action == "sync_coins":
            rb, delta = data['roblox'], data['delta']
            db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) + ?, 2) WHERE LOWER(roblox)=?", (delta, rb.lower()), commit=True)
            curr = db_query("SELECT coins FROM users WHERE LOWER(roblox)=?", (rb.lower(),), fetchone=True)
            return web.json_response({"success": True, "coins": curr[0]}, headers=headers)
        
        # 4. ОФОРМЛЕНИЕ ЗАКАЗА
        elif action == "order":
            rb, total, coords, items = data['roblox'], data['total'], data['coords'], data['items']
            db_query("UPDATE users SET coins = ROUND(coins - ?, 2) WHERE LOWER(roblox)=?", (total, rb.lower()), commit=True)
            msg = f"📦 **НОВЫЙ ЗАКАЗ ИЗ ПРИЛОЖЕНИЯ!**\nИгрок: `{rb}`\nСумма: `{total}`🪙\n\nТовары:\n{items}\n\n📍 Координаты:\n`{coords}`"
            await notify_admins_tg(msg)
            return web.json_response({"success": True}, headers=headers)

        # 5. АДМИНКА: ВЫДАТЬ МОНЕТЫ
        elif action == "admin_give_coins":
            caller, target, amount = data['caller'], data['target'], data['amount']
            is_caller_admin = db_query("SELECT is_admin FROM users WHERE LOWER(roblox)=?", (caller.lower(),), fetchone=True)
            if is_caller_admin and is_caller_admin[0] == 1:
                db_query("UPDATE users SET coins = ROUND(coins + ?, 2) WHERE LOWER(roblox)=?", (amount, target.lower()), commit=True)
                return web.json_response({"success": True}, headers=headers)
            return web.json_response({"success": False, "error": "Нет прав!"}, headers=headers)

        # 6. АДМИНКА: ЗАБАНИТЬ
        elif action == "admin_ban":
            caller, target = data['caller'], data['target']
            is_caller_admin = db_query("SELECT is_admin FROM users WHERE LOWER(roblox)=?", (caller.lower(),), fetchone=True)
            if is_caller_admin and is_caller_admin[0] == 1:
                db_query("UPDATE users SET is_banned=1 WHERE LOWER(roblox)=?", (target.lower(),), commit=True)
                return web.json_response({"success": True}, headers=headers)
            return web.json_response({"success": False}, headers=headers)

        # 7. ОНЛАЙН СЕРВЕРА
        elif action == "get_online":
            active_players = random.randint(12, 22)
            return web.json_response({"success": True, "online": active_players}, headers=headers)

    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, headers=headers)

# --- ЗАПУСК БОТА И СЕРВЕРА ---
async def main():
    print("=============================")
    print("🤖 API-Сервер и Бот запущены!")
    print("=============================")
    
    app = web.Application()
    app.router.add_route('OPTIONS', '/api', handle_options)
    app.router.add_post('/api', handle_api)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())