from app.storage.cloudflare import CloudflareStorage
from app.storage.feishu_bitable import FeishuBitableStorage
from app.storage.noop import NoopStorage
from app.storage.supabase import SupabaseStorage


def build_storage(config):
    if config.storage_backend == "none":
        return NoopStorage("Storage backend disabled by STORAGE_BACKEND=none.")

    if config.storage_backend == "cloudflare":
        if not config.cloudflare_storage_enabled:
            return NoopStorage(
                "Storage backend cloudflare requested, but CLOUDFLARE_INGEST_URL and INGEST_TOKEN are not both configured."
            )
        return CloudflareStorage(config)

    if config.storage_backend == "feishu_bitable":
        if not config.feishu_bitable_storage_enabled:
            return NoopStorage(
                "Storage backend feishu_bitable requested, but FEISHU_APP_ID/FEISHU_APP_SECRET/FEISHU_BITABLE_* are not fully configured."
            )
        return FeishuBitableStorage(config)

    if config.storage_backend == "supabase":
        if not config.supabase_storage_enabled:
            return NoopStorage(
                "Storage backend supabase requested, but SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY/SUPABASE_*_TABLE are not fully configured."
            )
        return SupabaseStorage(config)

    if config.cloudflare_storage_enabled:
        return CloudflareStorage(config)

    if config.supabase_storage_enabled:
        return SupabaseStorage(config)

    if config.feishu_bitable_storage_enabled:
        return FeishuBitableStorage(config)

    if config.cloudflare_storage_partially_configured:
        return NoopStorage(
            "Cloudflare storage disabled: both CLOUDFLARE_INGEST_URL and INGEST_TOKEN are required."
        )

    if config.feishu_bitable_storage_partially_configured:
        return NoopStorage(
            "Feishu Bitable storage disabled: FEISHU_APP_ID/FEISHU_APP_SECRET/FEISHU_BITABLE_* must all be configured."
        )

    if config.supabase_storage_partially_configured:
        return NoopStorage(
            "Supabase storage disabled: SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY/SUPABASE_*_TABLE must all be configured."
        )

    return NoopStorage("No storage backend enabled: running without persisted state.")


__all__ = [
    "CloudflareStorage",
    "FeishuBitableStorage",
    "NoopStorage",
    "SupabaseStorage",
    "build_storage",
]
