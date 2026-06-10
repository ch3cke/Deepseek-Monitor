import base64
import hashlib
import hmac
import time

import requests

from app.config import AppConfig
from app.notifier.base import NotificationChannel


def build_feishu_text_payload(title, body, keyword=""):
    parts = [part for part in [keyword.strip(), title.strip(), body.strip()] if part]
    text = "\n\n".join(parts)
    return {
        "msg_type": "text",
        "content": {
            "text": text,
        },
    }


def build_feishu_post_payload(title, body, keyword=""):
    first_line = f"{keyword.strip()} {title}".strip() if keyword else title
    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": [
                        [{"tag": "text", "text": first_line}],
                        [{"tag": "text", "text": body}],
                    ],
                }
            }
        },
    }


def build_feishu_interactive_payload(title, body, keyword=""):
    visible_title = f"{keyword.strip()} {title}".strip() if keyword else title
    return {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True,
                "enable_forward": True,
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": visible_title,
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": body.replace("\n", "\n"),
                    },
                }
            ],
        },
    }


def build_feishu_signature(secret, timestamp=None):
    effective_timestamp = str(timestamp or int(time.time()))
    string_to_sign = f"{effective_timestamp}\n{secret}"
    digest = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = base64.b64encode(digest).decode("utf-8")
    return effective_timestamp, sign


def build_feishu_payload(title, body, message_type="text", keyword="", secret=""):
    if message_type == "interactive":
        payload = build_feishu_interactive_payload(title, body, keyword)
    elif message_type == "post":
        payload = build_feishu_post_payload(title, body, keyword)
    else:
        payload = build_feishu_text_payload(title, body, keyword)

    if secret:
        timestamp, sign = build_feishu_signature(secret)
        payload["timestamp"] = timestamp
        payload["sign"] = sign

    return payload


def send_feishu_bot_message(
    url,
    title,
    body,
    *,
    keyword="",
    secret="",
    message_type="text",
    timeout=15,
):
    if not url:
        return None

    payload = build_feishu_payload(
        title=title,
        body=body,
        message_type=message_type,
        keyword=keyword,
        secret=secret,
    )
    response = requests.post(
        url,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json() if response.content else {"ok": True}


class FeishuBotNotifier(NotificationChannel):
    name = "feishu_bot"

    def __init__(self, config: AppConfig):
        self.config = config

    @property
    def enabled(self):
        return self.config.feishu_enabled

    def notify(self, subject, body):
        return send_feishu_bot_message(
            self.config.feishu_bot_webhook_url,
            subject,
            body,
            keyword=self.config.feishu_bot_keyword,
            secret=self.config.feishu_bot_secret,
            message_type=self.config.feishu_bot_message_type,
        )
