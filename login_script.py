import json
import asyncio
from pyppeteer import launch
import aiofiles
import random
import requests
import os

# 从环境变量中获取 Telegram Bot Token 和 Chat ID
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def delay_time(ms):
    await asyncio.sleep(ms / 1000)

# 全局浏览器实例
browser = None

# telegram消息
message = ""

def get_service_name(panel):
    if 'ct8' in panel:
        return 'CT8'
    elif 'panel' in panel:
        try:
            panel_number = int(panel.split('panel')[1].split('.')[0])
            return f'S{panel_number}'
        except ValueError:
            return 'Unknown'
    return 'Unknown'

async def login(username, password, panel):
    global browser

    page = None
    service_name = get_service_name(panel)
    try:
        if not browser:
            browser = await launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])

        page = await browser.newPage()
        url = f'https://{panel}/login/?next=/'
        await page.goto(url)

        username_input = await page.querySelector('#id_username')
        if username_input:
            await page.evaluate('''(input) => input.value = ""''', username_input)

        await page.type('#id_username', username)
        await page.type('#id_password', password)

        login_button = await page.querySelector('#submit')
        if login_button:
            await login_button.click()
        else:
            raise Exception('无法找到登录按钮')

        await page.waitForNavigation()

        is_logged_in = await page.evaluate('''() => {
            const logoutButton = document.querySelector('a[href="/logout/"]');
            return logoutButton !== null;
        }''')

        return is_logged_in

    except Exception as e:
        print(f'{service_name}账号 {username} 登录时出现错误: {e}')
        return False

    finally:
        if page:
            await page.close()

async def shutdown_browser():
    global browser
    if browser:
        await browser.close()
        browser = None

async def send_telegram_message(messages):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    headers = {'Content-Type': 'application/json'}

    for msg in messages:
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': msg
        }
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                print(f"发送消息到 Telegram 失败: {response.text}")
        except Exception as e:
            print(f"发送消息到 Telegram 时出错: {e}")
        await asyncio.sleep(0.5)  # 避免发送过快

async def main():
    global message

    try:
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        accounts = json.loads(accounts_json)
    except Exception as e:
        print(f'读取 accounts.json 文件时出错: {e}')
        return

    # 初始化消息
    message = "账号列表\n\n"
    account_lines = []

    for account in accounts:
        username = account['username']
        password = account['password']
        panel = account['panel']

        # 执行登录但不记录结果
        await login(username, password, panel)

        # 添加账号和密码到列表
        account_lines.append(f"- {username}: {password}")

        delay = random.randint(1000, 8000)
        await delay_time(delay)

    # 分批发送消息（每批限制在 4000 字符以内）
    messages = []
    current_message = message
    for line in account_lines:
        if len(current_message) + len(line) + 1 > 4000:  # 预留换行符
            messages.append(current_message)
            current_message = "账号列表（续）\n\n"
        current_message += line + "\n"
    if current_message.strip() != "账号列表（续）":
        messages.append(current_message)

    await send_telegram_message(messages)
    print(f'所有账号登录完成！')
    await shutdown_browser()

if __name__ == '__main__':
    asyncio.run(main())
