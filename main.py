###
# curl 'https://platform.deepseek.com/api/v0/usage/export?month=6&year=2026' \
#   -H 'accept: */*' \
#   -H 'accept-language: zh-CN,zh;q=0.9,en;q=0.8,ko;q=0.7,ja;q=0.6' \
#   -H 'authorization: Bearer xWwluvRTQehCnblvnYJhKUmGmDUojv/l8SReY/nly9CC9w2FL1wCJMPJFK3KQ0pG' \
#   -b 'intercom-device-id-guh50jw4=e508b61d-4cf0-4ab1-8e58-0547c5b97afd; HWWAFSESID=033b976c4caafa40ce; HWWAFSESTIME=1781007685706' \
#   -H 'priority: u=1, i' \
#   -H 'referer: https://platform.deepseek.com/usage' \
#   -H 'sec-ch-ua: "Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
#   -H 'sec-ch-ua-mobile: ?0' \
#   -H 'sec-ch-ua-platform: "macOS"' \
#   -H 'sec-fetch-dest: empty' \
#   -H 'sec-fetch-mode: cors' \
#   -H 'sec-fetch-site: same-origin' \
#   -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36' \
#   -H 'x-app-version: 1.0.0'
#
# ###
import os
import zipfile
import io

import pandas as pd
import requests
import smtplib
import sqlite3
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
load_dotenv()

auth = os.getenv("AUTH")
cookies = {
    'intercom-device-id-guh50jw4': 'e508b61d-4cf0-4ab1-8e58-0547c5b97afd',
    'HWWAFSESID': '033b976c4caafa40ce',
    'HWWAFSESTIME': '1781007685706',
}
headers = {
    'accept': '*/*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,ko;q=0.7,ja;q=0.6',
    'authorization': f"Bearer {auth}",
    'priority': 'u=1, i',
    'referer': 'https://platform.deepseek.com/usage',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    # 'cookie': 'intercom-device-id-guh50jw4=e508b61d-4cf0-4ab1-8e58-0547c5b97afd; HWWAFSESID=033b976c4caafa40ce; HWWAFSESTIME=1781007685706',
}

users = dict()

def update_users():
    response = requests.get('https://platform.deepseek.com/api/v0/users/get_api_keys', cookies=cookies, headers=headers)
    api_keys =  response.json().get('data').get('biz_data').get('api_keys')
    for api_key in api_keys:
        users[api_key.get('name')] = api_key

update_users()

def request_data(month, year):
    params = {
        'month': month,
        'year': year,
    }
    base_url = f"https://platform.deepseek.com/api/v0/usage/export"
    response = requests.get(base_url, params=params, cookies=cookies, headers=headers)
    return response

def extract_csv_from_zip(res):
    cost = []
    amount = []
    with zipfile.ZipFile(io.BytesIO(res.content)) as z:
        csv_files = [
            name for name in z.namelist()
            if name.lower().endswith(".csv")
        ]
        for csv_name in csv_files:
            if "cost" in csv_name:
                with z.open(csv_name) as f:
                    cost = pd.read_csv(f)
            elif "amount" in csv_name:
                with z.open(csv_name) as f:
                    amount = pd.read_csv(f)
    return cost, amount

    # Here you would typically make the actual HTTP request using a library like `requests`

def sum_cost(df):
    df = df.copy()

    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    df["cost"] = df["price"] * df["amount"]

    result = {}

    total_cost = 0
    total_tokens = 0
    total_requests = 0

    for (user, api_key), user_group in df.groupby(
        ["api_key_name", "api_key"]
    ):

        user_cost = 0
        user_tokens = 0
        user_requests = 0

        models = {}

        for model, model_group in user_group.groupby("model"):

            cost = float(model_group["cost"].sum())

            tokens = int(
                model_group[
                    model_group["type"].isin([
                        "output_tokens",
                        "input_cache_hit_tokens",
                        "input_cache_miss_tokens"
                    ])
                ]["amount"].sum()
            )

            requests = int(
                model_group[
                    model_group["type"] == "request_count"
                ]["amount"].sum()
            )

            models[model] = {
                "cost": round(cost, 4),
                "tokens": tokens,
                "requests": requests
            }

            user_cost += cost
            user_tokens += tokens
            user_requests += requests

        result[user] = {
            "cost": round(user_cost, 4),
            "tokens": user_tokens,
            "requests": user_requests,
            "models": models
        }

        total_cost += user_cost
        total_tokens += user_tokens
        total_requests += user_requests

    return {
        "users": result,
        "summary": {
            "cost": round(total_cost, 4),
            "tokens": total_tokens,
            "requests": total_requests
        }
    }

def delete_api(name):
    sensitive_id = users[name].get("sensitive_id")
    created_at = users[name].get("created_at")
    json_data = {
        'action': 'delete',
        'name': None,
        'redacted_key': f"{sensitive_id}",
        'created_at': created_at,
    }
    response = requests.post(
        'https://platform.deepseek.com/api/v0/users/edit_api_keys',
        cookies=cookies,
        headers=headers,
        json=json_data,
    )
    update_users()

    conn = sqlite3.connect('usage_history.db')
    c = conn.cursor()
    c.execute("UPDATE usage_records SET status = 'deleted' WHERE user = ?", (name,))
    conn.commit()
    conn.close()

def create_api(name):
    json_data = {
        'action': 'create',
        'name': name,
        'redacted_key': None,
        'created_at': None,
    }
    response = requests.post(
        'https://platform.deepseek.com/api/v0/users/edit_api_keys',
        cookies=cookies,
        headers=headers,
        json=json_data,
    )
    update_users()
    return {
        'name': name,
        'sensitive_id': response.json().get('sensitive_id'),
    }

def init_db():
    conn = sqlite3.connect('usage_history.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS usage_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user TEXT,
            cost REAL,
            tokens INTEGER,
            requests INTEGER,
            models_info TEXT
        )
    ''')
    try:
        c.execute('ALTER TABLE usage_records ADD COLUMN status TEXT DEFAULT "active"')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def save_to_db(result):
    conn = sqlite3.connect('usage_history.db')
    c = conn.cursor()
    users_data = result.get("users", {})
    for user, info in users_data.items():
        models_str = json.dumps(info.get("models", {}), ensure_ascii=False)
        
        c.execute("SELECT status FROM usage_records WHERE user = ? ORDER BY id DESC LIMIT 1", (user,))
        row = c.fetchone()
        status = row[0] if (row and row[0]) else 'active'

        c.execute('''
            INSERT INTO usage_records (user, cost, tokens, requests, models_info, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user, info.get("cost", 0), info.get("tokens", 0), info.get("requests", 0), models_str, status))
    conn.commit()
    conn.close()

def send_email(subject, body):
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", 465))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SENDER_EMAIL")
    receiver = os.getenv("RECEIVER_EMAIL")

    if not all([smtp_server, smtp_user, smtp_pass, sender, receiver]):
        print("注意: 邮箱配置不完整，跳过发送邮件。请检查 .env 的 SMTP_SERVER/SMTP_USERNAME 等配置。")
        return

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        print(f"邮件提醒已发送至: {receiver}")
    except Exception as e:
        print(f"发送提醒邮件失败: {e}")

def warning_words(user_info: dict[str, dict], level: str = "warning"):
    lines = []
    subject = ""

    if level == "warning":
        subject = "⚠️ DeepSeek API 用量预警"
        lines.append(subject)
    elif level == "block":
        subject = "🚫 DeepSeek API 用量超限且 Token 已删除通知"
        lines.append(subject)
        lines.append("【重要警告】因为该账户消费金额已经超过99元限制，为防止产生额外高额费用，系统已自动删除了对应的 API Token！如有需要请重新申请。")
    else:
        subject = "📊 DeepSeek API 用量统计"
        lines.append(subject)

    lines.append("")

    for user, info in user_info.items():

        cost = info.get("cost", 0)
        tokens = info.get("tokens", 0)
        requests = info.get("requests", 0)
        api_key = info.get("api_key", "")

        lines.append(
            f"用户：{user}\n"
            f"  - 消费金额：¥{cost:.2f}\n"
            f"  - Token 数：{tokens:,}\n"
            f"  - 请求次数：{requests:,}\n"
            f"  - API Key：{api_key}"
        )

        models = info.get("models", {})

        if models:
            lines.append("  - 模型使用情况：")

            for model, model_info in models.items():
                lines.append(
                    f"    • {model} "
                    f"(¥{model_info['cost']:.2f}, "
                    f"{model_info['tokens']:,} Tokens, "
                    f"{model_info['requests']} Requests)"
                )

        lines.append("")

    body = "\n".join(lines)
    print(body)
    
    if level in ["warning", "block"]:
        send_email(subject, body)

def check_users(cost_info):
    normal_users = dict()
    warning_users = dict()
    block_users = dict()
    for user, info in cost_info.get("users").items():
        if 80 > info.get('cost')  >= 0:
            warning_words({user: info}, "")
        if 99 >= info.get('cost') >= 80 and info.get('tokens') > 0:
            warning_words({user: info}, "warning")
        if info.get('cost') > 99 and info.get('tokens') > 0:
            delete_api(user)
            warning_words({user: info}, "block")

# 按装订区域中的绿色按钮以运行脚本。
if __name__ == '__main__':
    init_db()
    cost, amount = extract_csv_from_zip(request_data('6', '2026'))
    result = sum_cost(amount)
    save_to_db(result)
    check_users(result)
