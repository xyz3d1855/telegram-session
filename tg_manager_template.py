import json
import os
import asyncio
import time
import socket
from dataclasses import dataclass, asdict
from typing import Optional, List
from telethon import TelegramClient, errors, events
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetHistoryRequest

# -------------------------- 默认配置 (建议通过 config.json 修改) --------------------------
DEFAULT_CONFIG = {
    "api_id": 0,           # 填入你的 API_ID
    "api_hash": "",        # 填入你的 API_HASH
    "app_title": "Telegram Manager Pro",
    "device_model": "PC-Windows-Manager",
    "system_version": "Windows 11",
    "app_version": "1.0.0",
    "proxy": {
        "use": False,
        "server": "127.0.0.1",
        "port": 7890,
        "user": "",
        "pass": ""
    },
    "target_user_id": 777000, # 默认监听服务账号
    "session_dir": "sessions",
    "status_cache": "status_cache.json"
}

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
    return DEFAULT_CONFIG

CONFIG = load_config()

# -------------------------- 工具函数 --------------------------
def check_proxy_connectivity():
    if not CONFIG["proxy"]["use"]: return True
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        res = sock.connect_ex((CONFIG["proxy"]["server"], CONFIG["proxy"]["port"]))
        sock.close()
        return res == 0
    except:
        return False

def init_dirs():
    if not os.path.exists(CONFIG["session_dir"]):
        os.makedirs(CONFIG["session_dir"])

def load_status_cache() -> dict:
    if os.path.exists(CONFIG["status_cache"]):
        try:
            with open(CONFIG["status_cache"], "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_status_cache(data: dict):
    with open(CONFIG["status_cache"], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# -------------------------- 数据结构 --------------------------
@dataclass
class LoginSession:
    session_string: str
    user_id: int
    phone: str
    login_time: float
    api_id: int

# -------------------------- 会话工具 --------------------------
def list_sessions() -> List[str]:
    init_dirs()
    return [f for f in os.listdir(CONFIG["session_dir"]) if f.endswith(".json")]

def load_session(file: str) -> Optional[LoginSession]:
    p = os.path.join(CONFIG["session_dir"], file)
    if not os.path.exists(p): return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        return LoginSession(**d)
    except: return None

def save_session(client: TelegramClient, phone: str, uid: int):
    p = os.path.join(CONFIG["session_dir"], f"{phone}.json")
    data = LoginSession(
        session_string=client.session.save(),
        user_id=uid,
        phone=phone,
        login_time=time.time(),
        api_id=CONFIG["api_id"]
    )
    with open(p, "w", encoding="utf-8") as f:
        json.dump(asdict(data), f, indent=2, ensure_ascii=False)

# -------------------------- 核心逻辑 --------------------------
async def make_client(session_str="") -> TelegramClient:
    proxy = None
    if CONFIG["proxy"]["use"]:
        proxy = {
            'proxy_type': 'socks5',
            'addr': CONFIG["proxy"]["server"],
            'port': CONFIG["proxy"]["port"],
            'username': CONFIG["proxy"]["user"],
            'password': CONFIG["proxy"]["pass"]
        }
    
    c = TelegramClient(
        StringSession(session_str), 
        CONFIG["api_id"], 
        CONFIG["api_hash"],
        device_model=CONFIG["device_model"],
        system_version=CONFIG["system_version"],
        app_version=CONFIG["app_version"],
        proxy=proxy
    )
    await c.connect()
    return c

async def check_account_status(session_str: str) -> str:
    client = await make_client(session_str)
    try:
        if not await client.is_user_authorized():
            return "失效"
        
        # 通过向 SpamBot 发送消息检测是否被限制
        spambot = await client.get_entity("@SpamBot")
        await client.send_message(spambot, "/start")
        await asyncio.sleep(2)
        
        msgs = await client.get_messages(spambot, limit=5)
        text = " ".join([m.raw_text.lower() for m in msgs if m.raw_text])
        
        # 关键词判定逻辑
        ban_keywords = ["limited", "restricted", "ban", "permanently", "deactivated"]
        if any(k in text for k in ban_keywords):
            return "限制/冻结"
        return "正常"
    except Exception as e:
        return f"异常: {str(e)}"
    finally:
        await client.disconnect()

async def export_history(client: TelegramClient, target_id: int):
    me = await client.get_me()
    filename = f"history_{target_id}_{me.phone}.txt"
    print(f"\n正在导出与 {target_id} 的历史记录...")
    
    lines = []
    async for msg in client.iter_messages(target_id, limit=None):
        date_str = msg.date.strftime("%Y-%m-%d %H:%M:%S")
        content = msg.raw_text if msg.raw_text else "[非文本消息]"
        lines.append(f"[{date_str}] {content}\n---")
    
    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"✅ 导出成功: {filename}")

async def listen_realtime(client: TelegramClient, target_id: int):
    me = await client.get_me()
    log_file = f"live_{target_id}_{me.phone}.txt"
    print(f"\n🎧 正在实时监听 {target_id} ... (Ctrl+C 停止)")

    @client.on(events.NewMessage(from_users=target_id))
    async def handler(event):
        msg = event.message
        time_str = msg.date.strftime("%Y-%m-%d %H:%M:%S")
        content = msg.raw_text if msg.raw_text else ""
        print(f"[{time_str}] 新消息: {content}")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time_str}] {content}\n---\n")

    await client.run_until_disconnected()

# -------------------------- 交互主循环 --------------------------
async def main():
    if CONFIG["api_id"] == 0:
        print("❌ 请先在 config.json 中配置 API_ID 和 API_HASH")
        return

    init_dirs()
    status_cache = load_status_cache()
    
    while True:
        sessions = list_sessions()
        print("\n" + "="*40)
        print("      Telegram 账号管理助手")
        print("="*40)
        for i, f in enumerate(sessions, 1):
            status = status_cache.get(f, "待检测")
            print(f"[{i}] {f} - 状态: {status}")
        
        print("\n[A] 添加账号  [C] 全体检测  [L] 实时监听  [E] 导出历史  [Q] 退出")
        choice = input("\n请选择操作: ").strip().upper()

        if choice == 'Q': break
        
        if choice == 'A':
            phone = input("请输入手机号(带+号): ").strip()
            client = await make_client()
            try:
                await client.start(phone=phone)
                me = await client.get_me()
                save_session(client, me.phone, me.id)
                print("✅ 账号添加成功")
            except Exception as e:
                print(f"❌ 添加失败: {e}")
            finally: await client.disconnect()

        elif choice == 'C':
            print("\n正在批量检测状态...")
            for f in sessions:
                sess = load_session(f)
                if sess:
                    res = await check_account_status(sess.session_string)
                    status_cache[f] = res
                    print(f" -> {f}: {res}")
            save_status_cache(status_cache)

        elif choice == 'L' or choice == 'E':
            idx = int(input("请选择账号序号: ")) - 1
            if 0 <= idx < len(sessions):
                sess = load_session(sessions[idx])
                client = await make_client(sess.session_string)
                if choice == 'L':
                    await listen_realtime(client, CONFIG["target_user_id"])
                else:
                    await export_history(client, CONFIG["target_user_id"])
                await client.disconnect()

if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
