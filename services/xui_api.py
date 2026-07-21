import httpx
import uuid
import json
import aiosqlite
import config

async def create_user_in_xui(email: str):
    if not config.XUI_API_TOKEN:
        raise Exception("Ошибка: XUI_API_TOKEN не задан в файле .env!")
        
    new_uuid = str(uuid.uuid4())
    
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": config.XUI_BASE_URL,
        "Referer": f"{config.XUI_BASE_URL}/",
        "Authorization": f"Bearer {config.XUI_API_TOKEN}",
        "Cookie": f"3x-ui={config.XUI_API_TOKEN}"
    }

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        print("[DEBUG] Создание клиента через новый API /clients/add...")
        
        # Формируем payload согласно новой документации
        client_settings = {
            "email": email,
            "id": new_uuid,  # UUID для VLESS
            "flow": config.CLIENT_FLOW, 
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": 0, # 0 означает бесконечно
            "enable": True
        }
        
        payload = {
            "client": client_settings,
            "inboundIds": [config.XUI_INBOUND_ID] # Передаем как массив
        }

        add_url = f"{config.XUI_BASE_URL}{config.XUI_ADD_CLIENT_PATH}"
        print(f"[DEBUG] Отправляю запрос на: {add_url}")
        
        add_resp = await client.post(
            add_url,
            json=payload,
            headers=headers
        )

        if add_resp.status_code != 200:
            print(f"Ошибка API добавления: Status: {add_resp.status_code}, Body: {add_resp.text}")
            raise Exception("Не удалось добавить клиента через API.")

    # Обновляем статистику в БД (оставляем для надежности)
    try:
        async with aiosqlite.connect(config.XUI_DB_PATH) as db:
            cursor = await db.execute("PRAGMA table_info(client_traffics)")
            columns_info = await cursor.fetchall()
            columns = [col[1] for col in columns_info]
            
            insert_cols = ['email', 'enable'] 
            insert_values = [email, 1]
            
            if 'upload' in columns: insert_cols.append('upload'); insert_values.append(0)
            if 'download' in columns: insert_cols.append('download'); insert_values.append(0)
            if 'total' in columns: insert_cols.append('total'); insert_values.append(0)
            if 'up' in columns: insert_cols.append('up'); insert_values.append(0)
            if 'down' in columns: insert_cols.append('down'); insert_values.append(0)
            if 'expiry_time' in columns: insert_cols.append('expiry_time'); insert_values.append(0)
            
            placeholders = ', '.join(['?'] * len(insert_values))
            cols_str = ', '.join(insert_cols)
            
            sql = f"INSERT OR IGNORE INTO client_traffics ({cols_str}) VALUES ({placeholders})"
            
            await db.execute(sql, insert_values)
            await db.commit()
            print(f"[DEBUG] Статистика обновлена.")
            
    except Exception as e:
        print(f"[WARNING] Ошибка статистики: {e}")

    print("[DEBUG] Готово.")
    return new_uuid

async def get_online_clients():
    """Получает список email подключенных в данный момент клиентов"""
    if not config.XUI_API_TOKEN:
        raise Exception("Ошибка: XUI_API_TOKEN не задан в файле .env!")
        
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": config.XUI_BASE_URL,
        "Referer": f"{config.XUI_BASE_URL}/",
        "Authorization": f"Bearer {config.XUI_API_TOKEN}",
        "Cookie": f"3x-ui={config.XUI_API_TOKEN}"
    }

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        url = f"{config.XUI_BASE_URL}/panel/api/clients/onlines"
        resp = await client.post(url, json={}, headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                return data.get("obj", [])
        return []



async def get_all_clients():
    """Получает список всех клиентов из панели"""
    if not config.XUI_API_TOKEN:
        raise Exception("Ошибка: XUI_API_TOKEN не задан в файле .env!")
        
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": config.XUI_BASE_URL,
        "Referer": f"{config.XUI_BASE_URL}/",
        "Authorization": f"Bearer {config.XUI_API_TOKEN}",
        "Cookie": f"3x-ui={config.XUI_API_TOKEN}"
    }

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        url = f"{config.XUI_BASE_URL}/panel/api/clients/list"
        resp = await client.get(url, headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                return data.get("obj", [])
        return []

async def delete_client(email: str):
    """Удаляет клиента из панели по email"""
    if not config.XUI_API_TOKEN:
        raise Exception("Ошибка: XUI_API_TOKEN не задан в файле .env!")
        
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": config.XUI_BASE_URL,
        "Referer": f"{config.XUI_BASE_URL}/",
        "Authorization": f"Bearer {config.XUI_API_TOKEN}",
        "Cookie": f"3x-ui={config.XUI_API_TOKEN}"
    }

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        url = f"{config.XUI_BASE_URL}/panel/api/clients/del/{email}"
        resp = await client.post(url, json={}, headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            return data.get("success", False)
        return False
