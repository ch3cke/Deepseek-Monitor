import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    auth: str
    monitored_users: list[str]
    default_budget_limit: float
    default_warning_threshold: float
    cloudflare_ingest_url: str
    ingest_token: str
    deepseek_intercom_device_id: str
    deepseek_hwwafsesid: str
    deepseek_hwwafsetime: str
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    sender_email: str
    receiver_email: str
    feishu_bot_webhook_url: str = ""
    feishu_bot_secret: str = ""
    feishu_bot_keyword: str = ""
    feishu_bot_message_type: str = "text"
    usage_month: int | None = None
    usage_year: int | None = None

    @property
    def cloudflare_base_url(self):
        if "/api/ingest" not in self.cloudflare_ingest_url:
            raise RuntimeError("CLOUDFLARE_INGEST_URL must end with /api/ingest")
        return self.cloudflare_ingest_url.rsplit("/api/ingest", 1)[0]

    @property
    def headers(self):
        return {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "authorization": f"Bearer {self.auth}",
            "priority": "u=1, i",
            "referer": "https://platform.deepseek.com/usage",
            "user-agent": "Mozilla/5.0",
        }

    @property
    def cookies(self):
        return {
            "intercom-device-id-guh50jw4": self.deepseek_intercom_device_id,
            "HWWAFSESID": self.deepseek_hwwafsesid,
            "HWWAFSESTIME": self.deepseek_hwwafsetime,
        }

    @property
    def email_enabled(self):
        return all([
            self.smtp_server,
            self.smtp_username,
            self.smtp_password,
            self.sender_email,
            self.receiver_email,
        ])

    @property
    def feishu_enabled(self):
        return bool(self.feishu_bot_webhook_url)


def parse_monitored_users(raw_users):
    return [
        user.strip()
        for user in raw_users.split(",")
        if user.strip()
    ]


def load_config(*, require_cloudflare=True):
    monitored_users = parse_monitored_users(os.getenv("MONITORED_USERS", ""))
    required = [
        "AUTH",
        "MONITORED_USERS",
        "DEEPSEEK_INTERCOM_DEVICE_ID",
        "DEEPSEEK_HWWAFSESID",
        "DEEPSEEK_HWWAFSESTIME",
    ]
    if require_cloudflare:
        required.extend(["CLOUDFLARE_INGEST_URL", "INGEST_TOKEN"])

    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    config = AppConfig(
        auth=os.getenv("AUTH", ""),
        monitored_users=monitored_users,
        default_budget_limit=float(os.getenv("DEFAULT_BUDGET_LIMIT", "100")),
        default_warning_threshold=float(os.getenv("DEFAULT_WARNING_THRESHOLD", "80")),
        cloudflare_ingest_url=os.getenv("CLOUDFLARE_INGEST_URL", ""),
        ingest_token=os.getenv("INGEST_TOKEN", ""),
        deepseek_intercom_device_id=os.getenv("DEEPSEEK_INTERCOM_DEVICE_ID", ""),
        deepseek_hwwafsesid=os.getenv("DEEPSEEK_HWWAFSESID", ""),
        deepseek_hwwafsetime=os.getenv("DEEPSEEK_HWWAFSESTIME", ""),
        smtp_server=os.getenv("SMTP_SERVER", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "465")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        sender_email=os.getenv("SENDER_EMAIL", ""),
        receiver_email=os.getenv("RECEIVER_EMAIL", ""),
        feishu_bot_webhook_url=os.getenv("FEISHU_BOT_WEBHOOK_URL", ""),
        feishu_bot_secret=os.getenv("FEISHU_BOT_SECRET", ""),
        feishu_bot_keyword=os.getenv("FEISHU_BOT_KEYWORD", ""),
        feishu_bot_message_type=os.getenv("FEISHU_BOT_MESSAGE_TYPE", "text"),
        usage_month=int(os.getenv("USAGE_MONTH")) if os.getenv("USAGE_MONTH") else None,
        usage_year=int(os.getenv("USAGE_YEAR")) if os.getenv("USAGE_YEAR") else None,
    )

    if config.default_warning_threshold >= config.default_budget_limit:
        raise RuntimeError("DEFAULT_WARNING_THRESHOLD must be smaller than DEFAULT_BUDGET_LIMIT.")

    if config.feishu_bot_message_type not in {"text", "post", "interactive"}:
        raise RuntimeError("FEISHU_BOT_MESSAGE_TYPE must be one of: text, post, interactive.")

    return config
