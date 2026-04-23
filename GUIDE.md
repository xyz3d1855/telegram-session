# Telegram 账号管理与监听工具开发指南

本指南将介绍如何使用 Python 的 `Telethon` 库开发一个集账号状态检测、历史记录导出及实时消息监听于一体的工具。

## 1. 环境准备

### 依赖库安装
```bash
pip install telethon cryptg
```
*注：`cryptg` 可以显著提高加密/解密速度。*

### 获取 API 凭据
1. 访问 [my.telegram.org](https://my.telegram.org)。
2. 登录后选择 "API development tools"。
3. 创建一个应用以获取 `api_id` 和 `api_hash`。

## 2. 核心模块实现

### 2.1 客户端初始化与代理配置
使用 `StringSession` 可以将登录状态保存为字符串，避免频繁生成 `.session` 文件，方便在不同机器间迁移。

```python
from telethon import TelegramClient
from telethon.sessions import StringSession

async def get_client(session_str, api_id, api_hash, proxy=None):
    client = TelegramClient(StringSession(session_str), api_id, api_hash, proxy=proxy)
    await client.connect()
    return client
```

### 2.2 账号状态检测逻辑
通过向官方的 `@SpamBot` 发送 `/start` 并分析回显，可以判断账号是否处于限制（Limited）或冻结状态。

```python
async def check_status(client):
    spambot = await client.get_entity("@SpamBot")
    await client.send_message(spambot, "/start")
    await asyncio.sleep(2) # 等待回传
    msgs = await client.get_messages(spambot, limit=1)
    # 分析 msgs[0].raw_text 中的关键词如 "limited", "restricted"
```

### 2.3 消息导出（迭代器模式）
使用 `client.iter_messages` 可以高效地遍历数万条历史记录，而不会阻塞内存。

```python
async def export_history(client, target_id):
    async for msg in client.iter_messages(target_id):
        print(msg.date, msg.text)
```

### 2.4 实时监听（事件驱动）
利用 Telethon 的装饰器 `events.NewMessage` 实现异步监听。

```python
@client.on(events.NewMessage(from_users=target_id))
async def handler(event):
    print(f"收到来自 {target_id} 的新消息: {event.message.text}")
```

## 3. 安全建议 (重要)

1. **脱敏处理**：在发布到 GitHub 之前，务必移除所有硬编码的 `api_id`、`api_hash`、手机号以及自定义的设备标识信息。
2. **配置文件隔离**：使用 `config.json` 或 `.env` 文件存储敏感信息，并在 `.gitignore` 中忽略它们。
3. **频率控制**：在循环请求（如检测状态）中加入 `asyncio.sleep`，防止触发 Telegram 的 `FloodWaitError`。
4. **代理安全**：如果使用 SOCKS5 代理，确保代理服务器的稳定性。

## 4. 目录结构推荐
```text
project/
│── sessions/          # 存储各个账号的 json 格式 session 字符串
│── main.py            # 主程序
│── config.json        # 配置文件（不上传）
│── config.json.example # 配置文件示例（上传）
│── .gitignore         # 忽略 sessions/ 和 config.json
└── README.md
```
