import asyncio, sqlite3, json, os, random
from aiohttp import web

SUPER_ADMIN_ROBLOX = "kmaar585"

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, roblox TEXT UNIQUE, discord TEXT, passHash TEXT, coins REAL DEFAULT 0.0, is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, device_id TEXT, status TEXT DEFAULT 'pending')")
    c.execute("CREATE TABLE IF NOT EXISTS two_fa (id INTEGER PRIMARY KEY AUTOINCREMENT, roblox TEXT, device_id TEXT, status TEXT DEFAULT 'pending')")
    c.execute("CREATE TABLE IF NOT EXISTS reset_tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, roblox TEXT, discord TEXT, new_pass TEXT DEFAULT '', status TEXT DEFAULT 'pending')")
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
            is_adm = 1 if rb.lower() == SUPER_ADMIN_ROBLOX.lower() else 0
            status = 'approved' if is_adm == 1 else 'pending'
            try:
                db_query("INSERT INTO users (roblox, discord, passHash, coins, is_admin, is_banned, device_id, status) VALUES (?,?,?,5.0,?,0,?,?)", (rb, dc, pHash, is_adm, dev_id, status), commit=True)
                return web.json_response({"success": True, "status": status, "isAdmin": is_adm == 1}, headers=headers)
            except:
                return web.json_response({"success": False, "error": "Ник уже занят!"}, headers=headers)
        
        # 2. ВХОД И 2FA ДЛЯ Kmaar585
        elif action == "login":
            rb, pHash, dev_id = data['roblox'], data['passHash'], data.get('device_id', '')
            user = db_query("SELECT discord, coins, is_admin, is_banned, device_id, status FROM users WHERE LOWER(roblox)=? AND passHash=?", (rb.lower(), pHash), fetchone=True)
            
            if user:
                if user[3] == 1: return web.json_response({"success": False, "error": "АККАУНТ ЗАБАНЕН!"}, headers=headers)
                
                # Проверка 2FA для аккаунта Kmaar585
                if rb.lower() == SUPER_ADMIN_ROBLOX.lower():
                    owner_dev = user[4]
                    if not owner_dev:
                        # Первый вход — привязываем устройство
                        db_query("UPDATE users SET device_id=? WHERE LOWER(roblox)=?", (dev_id, rb.lower()), commit=True)
                    elif owner_dev != dev_id:
                        # Вход с ЧУЖОГО устройства — проверяем разрешение в двухфакторке
                        tfa = db_query("SELECT status FROM two_fa WHERE roblox=? AND device_id=?", (rb.lower(), dev_id), fetchone=True)
                        if not tfa:
                            db_query("INSERT INTO two_fa (roblox, device_id, status) VALUES (?,?,'pending')", (rb.lower(), dev_id), commit=True)
                            return web.json_response({"success": False, "error": "pending_2fa"}, headers=headers)
                        elif tfa[0] == 'pending':
                            return web.json_response({"success": False, "error": "pending_2fa"}, headers=headers)
                        elif tfa[0] == 'rejected':
                            return web.json_response({"success": False, "error": "пошел нахуй"}, headers=headers)

                return web.json_response({"success": True, "discord": user[0], "coins": user[1], "isAdmin": user[2] == 1, "status": user[5]}, headers=headers)
            return web.json_response({"success": False, "error": "Неверный логин или пароль!"}, headers=headers)
        
        # 3. 2FA: ПОЛУЧИТЬ ЗАПРОСЫ НА ВХОД (Для Kmaar585)
        elif action == "get_2fa_requests":
            rows = db_query("SELECT id, device_id FROM two_fa WHERE status='pending'", fetchall=True)
            return web.json_response({"success": True, "requests": [{"id": r[0], "device_id": r[1]} for r in rows]}, headers=headers)

        # 4. 2FA: РАЗРЕШИТЬ / ЗАБЛОКИРОВАТЬ ВХОД
        elif action == "resolve_2fa":
            req_id, decision = data['req_id'], data['decision']
            st = 'approved' if decision == 'approve' else 'rejected'
            db_query("UPDATE two_fa SET status=? WHERE id=?", (st, req_id), commit=True)
            return web.json_response({"success": True}, headers=headers)

        # 5. СБРОС ПАРОЛЯ: ЗАЯВКА ОТ ИГРОКА
        elif action == "request_password_reset":
            rb, dc = data['roblox'], data['discord']
            db_query("INSERT INTO reset_tickets (roblox, discord, status) VALUES (?,?,'pending')", (rb, dc), commit=True)
            return web.json_response({"success": True}, headers=headers)

        # 6. АДМИНКА: СПИСОК ЗАЯВОК НА СБРОС ПАРОЛЕЙ
        elif action == "get_reset_tickets":
            rows = db_query("SELECT id, roblox, discord FROM reset_tickets WHERE status='pending'", fetchall=True)
            return web.json_response({"success": True, "tickets": [{"id": r[0], "roblox": r[1], "discord": r[2]} for r in rows]}, headers=headers)

        # 7. АДМИНКА: СБРОСИТЬ ПАРОЛЬ ИГРОКУ
        elif action == "resolve_password_reset":
            t_id, rb, new_pass = data['ticket_id'], data['roblox'], data['new_pass']
            pHash = data['new_pass_hash']
            db_query("UPDATE users SET passHash=? WHERE LOWER(roblox)=?", (pHash, rb.lower()), commit=True)
            db_query("UPDATE reset_tickets SET status='resolved', new_pass=? WHERE id=?", (new_pass, t_id), commit=True)
            return web.json_response({"success": True}, headers=headers)

        # 8. СИНХРОНИЗАЦИЯ МОНЕТ
        elif action == "sync_coins":
            rb, delta = data['roblox'], data['delta']
            db_query("UPDATE users SET coins = ROUND(COALESCE(coins, 0) + ?, 2) WHERE LOWER(roblox)=?", (delta, rb.lower()), commit=True)
            curr = db_query("SELECT coins FROM users WHERE LOWER(roblox)=?", (rb.lower(),), fetchone=True)
            return web.json_response({"success": True, "coins": curr[0]}, headers=headers)
        
        # 9. ОФОРМЛЕНИЕ ЗАКАЗА
        elif action == "order":
            rb, total, coords, items = data['roblox'], data['total'], data['coords'], data['items']
            db_query("UPDATE users SET coins = ROUND(coins - ?, 2) WHERE LOWER(roblox)=?", (total, rb.lower()), commit=True)
            return web.json_response({"success": True}, headers=headers)

        # 10. АДМИНКА: ЗАЯВКИ НА РЕГИСТРАЦИЮ
        elif action == "get_pending":
            rows = db_query("SELECT roblox, discord FROM users WHERE status='pending'", fetchall=True)
            return web.json_response({"success": True, "users": [{"roblox": r[0], "discord": r[1]} for r in rows]}, headers=headers)

        elif action == "resolve_pending":
            rb, decision = data['target'], data['decision']
            new_status = 'approved' if decision == 'approve' else 'rejected'
            db_query("UPDATE users SET status=? WHERE LOWER(roblox)=?", (new_status, rb.lower()), commit=True)
            return web.json_response({"success": True}, headers=headers)

        # 11. АДМИНКА: МОНЕТЫ И БАНЫ
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

        # 12. ОНЛАЙН СЕРВЕРА
        elif action == "get_online":
            return web.json_response({"success": True, "online": random.randint(14, 26)}, headers=headers)

    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, headers=headers)

async def handle_root(request):
    return web.Response(text="Trident Mops Master Server is Live! 🚀")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_route('OPTIONS', '/api', handle_options)
    app.router.add_post('/api', handle_api)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    print("🚀 API-Сервер запущен на порту", port)
    await site.start()
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())