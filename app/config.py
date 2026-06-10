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
    storage_backend: str
    cloudflare_ingest_url: str
    ingest_token: str
    feishu_app_id: str
    feishu_app_secret: str
    feishu_bitable_app_token: str
    feishu_bitable_users_table_id: str
    feishu_bitable_api_keys_table_id: str
    feishu_bitable_usage_table_id: str
    feishu_bitable_events_table_id: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_managed_users_table: str
    supabase_api_keys_table: str
    supabase_usage_records_table: str
    supabase_events_table: str
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

    @property
    def cloudflare_storage_enabled(self):
        return bool(self.cloudflare_ingest_url and self.ingest_token)

    @property
    def cloudflare_storage_partially_configured(self):
        return bool(self.cloudflare_ingest_url) != bool(self.ingest_token)

    @property
    def feishu_bitable_storage_enabled(self):
        return all([
            self.feishu_app_id,
            self.feishu_app_secret,
            self.feishu_bitable_app_token,
            self.feishu_bitable_users_table_id,
            self.feishu_bitable_api_keys_table_id,
            self.feishu_bitable_usage_table_id,
            self.feishu_bitable_events_table_id,
        ])

    @property
    def feishu_bitable_storage_partially_configured(self):
        configured = [
            self.feishu_app_id,
            self.feishu_app_secret,
            self.feishu_bitable_app_token,
            self.feishu_bitable_users_table_id,
            self.feishu_bitable_api_keys_table_id,
            self.feishu_bitable_usage_table_id,
            self.feishu_bitable_events_table_id,
        ]
        return any(configured) and not all(configured)

    @property
    def cloudflare_base_url(self):
        if not self.cloudflare_storage_enabled:
            raise RuntimeError(
                "Cloudflare storage is disabled because CLOUDFLARE_INGEST_URL or INGEST_TOKEN is missing."
            )
        if "/api/ingest" not in self.cloudflare_ingest_url:
            raise RuntimeError("CLOUDFLARE_INGEST_URL must end with /api/ingest")
        return self.cloudflare_ingest_url.rsplit("/api/ingest", 1)[0]

    @property
    def feishu_bitable_tables(self):
        return {
            "managed_users": self.feishu_bitable_users_table_id,
            "api_keys": self.feishu_bitable_api_keys_table_id,
            "usage_records": self.feishu_bitable_usage_table_id,
            "events": self.feishu_bitable_events_table_id,
        }

    @property
    def supabase_storage_enabled(self):
        return all([
            self.supabase_url,
            self.supabase_service_role_key,
            self.supabase_managed_users_table,
            self.supabase_api_keys_table,
            self.supabase_usage_records_table,
            self.supabase_events_table,
        ])

    @property
    def supabase_storage_partially_configured(self):
        configured = [
            self.supabase_url,
            self.supabase_service_role_key,
        ]
        return any(configured) and not self.supabase_storage_enabled

    @property
    def supabase_base_url(self):
        return self.supabase_url.rstrip("/") + "/rest/v1"

    @property
    def supabase_tables(self):
        return {
            "managed_users": self.supabase_managed_users_table,
            "api_keys": self.supabase_api_keys_table,
            "usage_records": self.supabase_usage_records_table,
            "events": self.supabase_events_table,
        }

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


def load_config():
    monitored_users = parse_monitored_users(os.getenv("MONITORED_USERS", ""))
    required = [
        "AUTH",
        "MONITORED_USERS",
    ]

    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    config = AppConfig(
        auth=os.getenv("AUTH", ""),
        monitored_users=monitored_users,
        default_budget_limit=float(os.getenv("DEFAULT_BUDGET_LIMIT", "100")),
        default_warning_threshold=float(os.getenv("DEFAULT_WARNING_THRESHOLD", "80")),
        storage_backend=os.getenv("STORAGE_BACKEND", "feishu_bitable").strip().lower() or "auto",
        cloudflare_ingest_url=os.getenv("CLOUDFLARE_INGEST_URL", ""),
        ingest_token=os.getenv("INGEST_TOKEN", ""),
        feishu_app_id=os.getenv("FEISHU_APP_ID", ""),
        feishu_app_secret=os.getenv("FEISHU_APP_SECRET", ""),
        feishu_bitable_app_token=os.getenv("FEISHU_BITABLE_APP_TOKEN", ""),
        feishu_bitable_users_table_id=os.getenv("FEISHU_BITABLE_USERS_TABLE_ID", ""),
        feishu_bitable_api_keys_table_id=os.getenv("FEISHU_BITABLE_API_KEYS_TABLE_ID", ""),
        feishu_bitable_usage_table_id=os.getenv("FEISHU_BITABLE_USAGE_TABLE_ID", ""),
        feishu_bitable_events_table_id=os.getenv("FEISHU_BITABLE_EVENTS_TABLE_ID", ""),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        supabase_managed_users_table=os.getenv("SUPABASE_MANAGED_USERS_TABLE", "managed_users"),
        supabase_api_keys_table=os.getenv("SUPABASE_API_KEYS_TABLE", "api_keys"),
        supabase_usage_records_table=os.getenv("SUPABASE_USAGE_RECORDS_TABLE", "usage_records"),
        supabase_events_table=os.getenv("SUPABASE_EVENTS_TABLE", "events"),
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
    )

    if config.default_warning_threshold >= config.default_budget_limit:
        raise RuntimeError("DEFAULT_WARNING_THRESHOLD must be smaller than DEFAULT_BUDGET_LIMIT.")

    if config.feishu_bot_message_type not in {"text", "post", "interactive"}:
        raise RuntimeError("FEISHU_BOT_MESSAGE_TYPE must be one of: text, post, interactive.")

    if config.storage_backend not in {"auto", "none", "cloudflare", "feishu_bitable", "supabase"}:
        raise RuntimeError("STORAGE_BACKEND must be one of: auto, none, cloudflare, feishu_bitable, supabase.")

    if config.cloudflare_storage_enabled and "/api/ingest" not in config.cloudflare_ingest_url:
        raise RuntimeError("CLOUDFLARE_INGEST_URL must end with /api/ingest.")

    if config.supabase_storage_enabled and not config.supabase_url.startswith("http"):
        raise RuntimeError("SUPABASE_URL must be a valid HTTPS base URL.")

    return config
