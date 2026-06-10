from app.utils.formatting import redact_value


def build_api_key_identity(user_name, sensitive_id, created_at):
    return "|".join([
        str(user_name or ""),
        str(sensitive_id or ""),
        str(created_at or ""),
    ])


def build_platform_key_record(
    user_name,
    api_key,
    status="active",
    deleted_at=None,
    final_cost=0,
    final_tokens=0,
    final_requests=0,
):
    sensitive_id = str(api_key.get("sensitive_id") or "")
    created_at = str(api_key.get("created_at") or api_key.get("platform_created_at") or "")
    return {
        "user_name": user_name,
        "api_key_identity": build_api_key_identity(user_name, sensitive_id, created_at),
        "sensitive_id": sensitive_id,
        "redacted_key": api_key.get("redacted_key") or redact_value(sensitive_id),
        "platform_created_at": created_at,
        "status": status,
        "deleted_at": deleted_at,
        "final_cost": round(float(final_cost or 0), 4),
        "final_tokens": int(final_tokens or 0),
        "final_requests": int(final_requests or 0),
    }
