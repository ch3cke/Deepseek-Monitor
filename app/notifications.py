def sanitize_user_info(user_info):
    return {
        "cost": round(float(user_info.get("cost", 0)), 4),
        "tokens": int(user_info.get("tokens", 0)),
        "requests": int(user_info.get("requests", 0)),
        "models": user_info.get("models", {}),
        "api_keys": user_info.get("api_keys", []),
        "active_api_keys": [
            {
                "api_key_identity": api_key.get("api_key_identity", ""),
                "redacted_key": api_key.get("redacted_key", ""),
                "status": api_key.get("status", "active"),
            }
            for api_key in user_info.get("active_api_keys", [])
        ],
    }


def build_notification_body(user_name, user_info, budget_limit, warning_threshold):
    lines = [
        f"user: {user_name}",
        f"cost: {float(user_info.get('cost', 0)):.2f}",
        f"warning_threshold: {warning_threshold:.2f}",
        f"budget_limit: {budget_limit:.2f}",
        f"tokens: {int(user_info.get('tokens', 0)):,}",
        f"requests: {int(user_info.get('requests', 0)):,}",
        "",
        "active_api_keys:",
    ]

    active_api_keys = user_info.get("active_api_keys", [])
    if active_api_keys:
        for api_key in active_api_keys:
            lines.append(
                f"  - {api_key.get('redacted_key', '')} "
                f"({api_key.get('api_key_identity', '')})"
            )
    else:
        lines.append("  - none")

    lines.append("")
    lines.append("usage_by_key:")

    for api_key in user_info.get("api_keys", []):
        lines.append(
            f"  - {api_key.get('api_key_label', '')}: "
            f"cost={api_key.get('cost', 0):.2f}, "
            f"tokens={int(api_key.get('tokens', 0)):,}, "
            f"requests={int(api_key.get('requests', 0)):,}"
        )

    return "\n".join(lines)


def build_summary_email(result, month, year):
    lines = [
        f"DeepSeek monthly summary for {year:04d}-{month:02d}",
        "",
    ]

    for user_name, user_info in sorted(
        result.get("users", {}).items(),
        key=lambda item: item[1].get("cost", 0),
        reverse=True,
    ):
        lines.append(
            f"{user_name}: "
            f"cost={float(user_info.get('cost', 0)):.2f}, "
            f"tokens={int(user_info.get('tokens', 0)):,}, "
            f"requests={int(user_info.get('requests', 0)):,}"
        )

    lines.append("")
    lines.append(
        "summary: "
        f"cost={float(result.get('summary', {}).get('cost', 0)):.2f}, "
        f"tokens={int(result.get('summary', {}).get('tokens', 0)):,}, "
        f"requests={int(result.get('summary', {}).get('requests', 0)):,}"
    )

    return (
        f"DeepSeek usage summary {year:04d}-{month:02d}",
        "\n".join(lines),
    )
