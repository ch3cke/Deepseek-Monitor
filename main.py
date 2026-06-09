import os
import io
import json
import zipfile
import smtplib
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

MONITORED_USERS = [
    u.strip()
    for u in os.getenv("MONITORED_USERS", "").split(",")
    if u.strip()
]

DEFAULT_BUDGET_LIMIT = float(os.getenv("DEFAULT_BUDGET_LIMIT", "100"))
DEFAULT_WARNING_THRESHOLD = float(os.getenv("DEFAULT_WARNING_THRESHOLD", "80"))

auth = os.getenv("AUTH")

cookies = {
    "intercom-device-id-guh50jw4": os.getenv("DEEPSEEK_INTERCOM_DEVICE_ID", ""),
    "HWWAFSESID": os.getenv("DEEPSEEK_HWWAFSESID", ""),
    "HWWAFSESTIME": os.getenv("DEEPSEEK_HWWAFSESTIME", ""),
}

headers = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,ko;q=0.7,ja;q=0.6",
    "authorization": f"Bearer {auth}",
    "priority": "u=1, i",
    "referer": "https://platform.deepseek.com/usage",
    "user-agent": "Mozilla/5.0",
}

platform_api_keys = {}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def require_env():
    required = [
        "AUTH",
        "MONITORED_USERS",
        "CLOUDFLARE_INGEST_URL",
        "INGEST_TOKEN",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"缺少环境变量: {', '.join(missing)}")


def request_json(method, url, **kwargs):
    response = requests.request(method, url, timeout=60, **kwargs)
    response.raise_for_status()
    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(f"接口返回不是 JSON: {response.text[:500]}") from exc


def cloudflare_request(path, method="GET", json_body=None):
    ingest_url = os.getenv("CLOUDFLARE_INGEST_URL")
    token = os.getenv("INGEST_TOKEN")

    # CLOUDFLARE_INGEST_URL 通常是 https://xxx.workers.dev/api/ingest
    base_url = ingest_url.rsplit("/api/ingest", 1)[0]
    url = f"{base_url}{path}"

    response = requests.request(
        method,
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=json_body,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def get_cloudflare_state():
    return cloudflare_request("/api/state", "GET")


def update_platform_api_keys():
    global platform_api_keys

    data = request_json(
        "GET",
        "https://platform.deepseek.com/api/v0/users/get_api_keys",
        cookies=cookies,
        headers=headers,
    )

    api_keys = (
        data.get("data", {})
        .get("biz_data", {})
        .get("api_keys", [])
    )

    platform_api_keys = {}
    for api_key in api_keys:
        name = api_key.get("name")
        if name:
            platform_api_keys[name] = api_key


def request_data(month, year):
    response = requests.get(
        "https://platform.deepseek.com/api/v0/usage/export",
        params={"month": month, "year": year},
        cookies=cookies,
        headers=headers,
        timeout=120,
    )
    response.raise_for_status()
    return response


def extract_csv_from_zip(res):
    cost = None
    amount = None

    with zipfile.ZipFile(io.BytesIO(res.content)) as z:
        csv_files = [
            name for name in z.namelist()
            if name.lower().endswith(".csv")
        ]

        for csv_name in csv_files:
            with z.open(csv_name) as f:
                if "cost" in csv_name.lower():
                    cost = pd.read_csv(f)
                elif "amount" in csv_name.lower():
                    amount = pd.read_csv(f)

    if amount is None:
        raise RuntimeError("ZIP 中未找到 amount CSV，无法统计用量。")

    return cost, amount


def sum_cost(df):
    df = df.copy()

    required_cols = {"price", "amount", "api_key_name", "api_key", "model", "type"}
    missing = required_cols - set(df.columns)
    if missing:
        raise RuntimeError(f"amount CSV 缺少字段: {sorted(missing)}")

    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["cost"] = df["price"] * df["amount"]

    result = {}
    total_cost = 0
    total_tokens = 0
    total_requests = 0

    for (user, api_key), user_group in df.groupby(["api_key_name", "api_key"]):
        if user not in MONITORED_USERS:
            continue

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
                        "input_cache_miss_tokens",
                    ])
                ]["amount"].sum()
            )

            requests_count = int(
                model_group[model_group["type"] == "request_count"]["amount"].sum()
            )

            models[model] = {
                "cost": round(cost, 4),
                "tokens": tokens,
                "requests": requests_count,
            }

            user_cost += cost
            user_tokens += tokens
            user_requests += requests_count

        result[user] = {
            "api_key": api_key,
            "cost": round(user_cost, 4),
            "tokens": user_tokens,
            "requests": user_requests,
            "models": models,
        }

        total_cost += user_cost
        total_tokens += user_tokens
        total_requests += user_requests

    return {
        "users": result,
        "summary": {
            "cost": round(total_cost, 4),
            "tokens": total_tokens,
            "requests": total_requests,
        },
    }


def build_api_keys_payload():
    items = []

    for user_name in MONITORED_USERS:
        key = platform_api_keys.get(user_name)
        if not key:
            continue

        items.append({
            "user_name": user_name,
            "sensitive_id": key.get("sensitive_id"),
            "redacted_key": key.get("redacted_key") or key.get("sensitive_id"),
            "platform_created_at": key.get("created_at"),
            "status": "active",
        })

    return items


def delete_api(name):
    api_key = platform_api_keys.get(name)
    if not api_key:
        raise RuntimeError(f"平台上找不到用户 {name} 的 active API Key，无法删除。")

    sensitive_id = api_key.get("sensitive_id")
    created_at = api_key.get("created_at")

    response = requests.post(
        "https://platform.deepseek.com/api/v0/users/edit_api_keys",
        cookies=cookies,
        headers=headers,
        json={
            "action": "delete",
            "name": None,
            "redacted_key": f"{sensitive_id}",
            "created_at": created_at,
        },
        timeout=60,
    )
    response.raise_for_status()

    update_platform_api_keys()
    return response.json()


def send_email(subject, body):
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", 465))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SENDER_EMAIL")
    receiver = os.getenv("RECEIVER_EMAIL")

    if not all([smtp_server, smtp_user, smtp_pass, sender, receiver]):
        print("注意: 邮箱配置不完整，跳过发送邮件。")
        return

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

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

    if level == "warning":
        subject = "⚠️ DeepSeek API 用量预警"
        lines.append(subject)
    elif level == "block":
        subject = "🚫 DeepSeek API 用量超限且 API Key 已回收通知"
        lines.append(subject)
        lines.append("【重要警告】该账户消费金额已达到额度上限，系统已自动删除对应 API Key，并将其归档为 used。")
    else:
        subject = "📊 DeepSeek API 用量统计"
        lines.append(subject)

    lines.append("")

    for user, info in user_info.items():
        lines.append(
            f"用户：{user}\n"
            f"  - 消费金额：¥{info.get('cost', 0):.2f}\n"
            f"  - Token 数：{info.get('tokens', 0):,}\n"
            f"  - 请求次数：{info.get('requests', 0):,}\n"
            f"  - API Key：{info.get('api_key', '')}"
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


def has_event(state, user_name, event_type, api_key_identity):
    events = state.get("events", [])
    for event in events:
        if (
            event.get("user_name") == user_name
            and event.get("event_type") == event_type
            and event.get("api_key_identity") == api_key_identity
        ):
            return True
    return False


def get_user_state(state, user_name):
    users = state.get("users", {})
    return users.get(user_name, {})


def get_api_key_identity(user_name):
    key = platform_api_keys.get(user_name) or {}
    return "|".join([
        str(user_name),
        str(key.get("sensitive_id") or ""),
        str(key.get("created_at") or ""),
    ])


def evaluate_users(result, state):
    events = []

    for user, info in result.get("users", {}).items():
        user_state = get_user_state(state, user)

        if user_state.get("status") == "blocked":
            print(f"用户 {user} 在 D1 中已是 blocked 状态，跳过治理动作。")
            continue

        budget_limit = float(user_state.get("budget_limit") or DEFAULT_BUDGET_LIMIT)
        warning_threshold = float(user_state.get("warning_threshold") or DEFAULT_WARNING_THRESHOLD)

        cost = float(info.get("cost", 0))
        tokens = int(info.get("tokens", 0))
        api_key_identity = get_api_key_identity(user)

        if tokens <= 0:
            continue

        if cost >= budget_limit:
            if has_event(state, user, "block", api_key_identity):
                print(f"用户 {user} 当前 API Key 已记录过 block 事件，跳过重复删除。")
                continue

            reason = f"cost {cost:.2f} >= budget_limit {budget_limit:.2f}"

            block_event = {
                "created_at": now_iso(),
                "user_name": user,
                "api_key_identity": api_key_identity,
                "event_type": "block",
                "reason": reason,
                "cost": cost,
                "tokens": tokens,
                "requests": int(info.get("requests", 0)),
                "payload": info,
            }
            events.append(block_event)

            delete_resp = delete_api(user)

            events.append({
                "created_at": now_iso(),
                "user_name": user,
                "api_key_identity": api_key_identity,
                "event_type": "delete_api",
                "reason": "platform api key deleted",
                "cost": cost,
                "tokens": tokens,
                "requests": int(info.get("requests", 0)),
                "payload": delete_resp,
            })

            warning_words({user: info}, "block")

        elif cost >= warning_threshold:
            if has_event(state, user, "warning", api_key_identity):
                print(f"用户 {user} 当前 API Key 已发送过 warning，跳过重复预警。")
                continue

            reason = f"cost {cost:.2f} >= warning_threshold {warning_threshold:.2f}"

            events.append({
                "created_at": now_iso(),
                "user_name": user,
                "api_key_identity": api_key_identity,
                "event_type": "warning",
                "reason": reason,
                "cost": cost,
                "tokens": tokens,
                "requests": int(info.get("requests", 0)),
                "payload": info,
            })

            warning_words({user: info}, "warning")

        else:
            warning_words({user: info}, "normal")

    return events


def push_to_cloudflare(result, month, year, events):
    ingest_url = os.getenv("CLOUDFLARE_INGEST_URL")
    token = os.getenv("INGEST_TOKEN")

    payload = {
        "month": int(month),
        "year": int(year),
        "recorded_at": now_iso(),
        "managed_users": [
            {
                "name": name,
                "budget_limit": DEFAULT_BUDGET_LIMIT,
                "warning_threshold": DEFAULT_WARNING_THRESHOLD,
                "status": "active",
            }
            for name in MONITORED_USERS
        ],
        "api_keys": build_api_keys_payload(),
        "result": result,
        "events": events,
    }

    response = requests.post(
        ingest_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    print("已上传到 Cloudflare D1:", response.json())


def run():
    require_env()

    update_platform_api_keys()

    now = datetime.now()
    month = int(os.getenv("USAGE_MONTH", now.month))
    year = int(os.getenv("USAGE_YEAR", now.year))

    _, amount = extract_csv_from_zip(request_data(month, year))
    result = sum_cost(amount)

    # 从 Cloudflare D1 读取已有状态，用于避免重复 warning/delete。
    state = get_cloudflare_state()

    # 根据 D1 状态评估动作。Python 不再使用本地数据库。
    events = evaluate_users(result, state)

    # 把最新 usage、api_keys、events 统一写入 D1。
    push_to_cloudflare(result, month, year, events)


if __name__ == "__main__":
    run()
