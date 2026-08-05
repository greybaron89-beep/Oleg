import asyncio, sqlite3, json, os, random
from aiohttp import web
import aiohttp

# ТВОИ НАСТРОЙКИ
BOT_TOKEN = "7983552580:AAG0VCo-qEomH_JIBuSWRuV2g15n54KNclw"
# Впиши сюда свой числовой Telegram ID, чтобы сервер знал, куда кидать смски!
MY_TELEGRAM_ID = "ТВОЙ_ID_ЗДЕСЬ" 
SUPER_ADMIN = "xquises"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, roblox TEXT UNIQUE, discord TEXT, passHash TEXT, coins REAL DEFAULT 0.0, is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, device_id TEXT, status TEXT DEFAULT 'pending')")
    conn.commit()
    conn.close()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute(query, params)
    res = None
    if fetchone: res = c.fetchone()
    if fetchall: res = c.fetchall()
    if commit: conn.commit()
    conn.close()
    return res

init_db()

# --- ОТПРАВКА СМС В ТЕЛЕГРАМ (БЕЗ БОТА, НАПРЯМУЮ) ---
async def send_tg_notification(text):
    if MY_TELEGRAM_ID == "ТВОЙ_ID_ЗДЕСЬ": return # Если ID не указан, не отправляем
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={"chat_id": MY_TELEGRAM_ID, "text": text, "parse_mode": "Markdown"})

# --- API ДЛЯ ПРИЛОЖЕНИЯ ---
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
            status = 'approved' if is_adm == 1 else 'pending'
            try:
                db_query("INSERT INTO users (roblox, discord, passHash, coins, is_admin, is_banned, device_id, status) VALUES (?,?,?,5.0,?,0,?,?)", (rb, dc, pHash, is_adm, dev_id, status), commit=True)
                if is_adm == 0:
                    await send_tg_notification(f"📥 **НОВАЯ ЗАЯВКА В ПРИЛОЖЕНИИ!**\nRoblox: `{rb}`\nDiscord: `{dc}`\nЗайдите в АПК, чтобы одобрить!")
                return web.json_response({"success": True, "status": status, "isAdmin": is_adm == 1}, headers=headers)
            except:
                return web.json_response({"success": False, "error": "Ник уже занят!"}, headers=headers)
        
        # 2. ВХОД И ЗАЩИТА
        elif action == "login":
            rb, pHash, dev_id = data['roblox'], data['passHash'], data.get('device_id', '')
            user = db_query("SELECT discord, coins, is_admin, is_banned, device_id, status FROM users WHERE LOWER(roblox)=? AND passHash=?", (rb.lower(), pHash), fetchone=True)
            
            if user:
                if user[3] == 1: return web.json_response({"success": False, "error": "АККАУНТ ЗАБАНЕН!"}, headers=headers)
                # Защита твоего аккаунта
                if rb.lower() == SUPER_ADMIN.lower() and user[4] != dev_id:
                    return web.json_response({"success": False, "error": "пошел нахуй"}, headers=headers)
                
                return web.json_response({"success": True, "discord": user[0], "coins": user[1], "isAdmin": user[2] == 1, "status": user[5]}, headers=headers)
            return web.json_response({"success": False, "error": "Неверный логин или пароль!"}, headers=headers)
        
        # 3. СИНХРОНИЗАЦИЯ МОНЕТ
        elif action == "sync_coins":
            rb, delta = data['roblox'], data['delta']
            db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) + ?, 2) WHERE LOWER(roblox)=?", (delta, rb.lower()), commit=True)
            curr = db_query("SELECT coins FROM users WHERE LOWER(roblox)=?", (rb.lower(),), fetchone=True)
            return web.json_response({"success": True, "coins": curr[0]}, headers=headers)
        
        # 4. ЗАКАЗ ИЗ МАГАЗИНА
        elif action == "order":
            rb, total, coords, items = data['roblox'], data['total'], data['coords'], data['items']
            db_query("UPDATE users SET coins = ROUND(coins - ?, 2) WHERE LOWER(roblox)=?", (total, rb.lower()), commit=True)
            await send_tg_notification(f"📦 **НОВЫЙ ЗАКАЗ!**\nИгрок: `{rb}`\nСумма: `{total}`🪙\nТовары:\n{items}\n📍 Координаты: `{coords}`")
            return web.json_response({"success": True}, headers=headers)

        # 5. АДМИНКА: ПОЛУЧИТЬ ЗАЯВКИ
        elif action == "get_pending":
            rows = db_query("SELECT roblox, discord FROM users WHERE status='pending'", fetchall=True)
            return web.json_response({"success": True, "users": [{"roblox": r[0], "discord": r[1]} for r in rows]}, headers=headers)

        # 6. АДМИНКА: ОДОБРИТЬ/ОТКЛОНИТЬ
        elif action == "resolve_pending":
            rb, decision = data['target'], data['decision']
            new_status = 'approved' if decision == 'approve' else 'rejected'
            db_query("UPDATE users SET status=? WHERE LOWER(roblox)=?", (new_status, rb.lower()), commit=True)
            return web.json_response({"success": True}, headers=headers)

        # 7. АДМИНКА: МОНЕТЫ И БАНЫ
        elif action == "admin_action":
            caller, target, act_type, val = data['caller'], data['target'], data['type'], data.get('val', 0)
            is_adm = db_query("SELECT is_admin FROM users WHERE LOWER(roblox)=?", (caller.lower(),), fetchone=True)
            if is_adm and is_adm[0] == 1:
                if act_type == "coins":
                    db_query("UPDATE users SET coins = ROUND(coins + ?, 2) WHERE LOWER(roblox)=?", (val, target.lower()), commit=True)
                elif act_type == "ban":
                    db_query("UPDATE users SET is_banned=1 WHERE LOWER(roblox)=?", (target.lower(),), commit=True)
                return web.json_response({"success": True}, headers=headers)
            return web.json_response({"success": False, "error": "Нет прав!"}, headers=headers)

        # 8. ОНЛАЙН
        elif action == "get_online":
            return web.json_response({"success": True, "online": random.randint(12, 22)}, headers=headers)

    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, headers=headers)

async def handle_root(request):
    return web.Response(text="API Server is running perfectly! 🚀")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_route('OPTIONS', '/api', handle_options)
    app.router.add_post('/api', handle_api)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    print("🚀 Сервер запущен на порту", port)
    await site.start()
    
    # Бесконечный цикл, чтобы сервер не выключался
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())