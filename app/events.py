from app.notifications import build_notification_body, sanitize_user_info
from app.utils.time import now_iso


def get_user_state(state, user_name):
    return state.get("users", {}).get(user_name, {})


def build_period_key(month, year):
    return f"{year:04d}-{month:02d}"


def build_event_key(user_name, event_type, period_key, scope):
    return "|".join([user_name, event_type, period_key, scope or "none"])


def has_event_key(state, event_key):
    for event in state.get("events", []):
        if event.get("event_key") == event_key:
            return True
    return False


def create_event(
    user_name,
    event_type,
    period_key,
    month,
    year,
    scope,
    reason,
    user_info,
    api_key_identity="",
    payload=None,
):
    return {
        "event_key": build_event_key(user_name, event_type, period_key, scope),
        "created_at": now_iso(),
        "month": int(month),
        "year": int(year),
        "period_key": period_key,
        "user_name": user_name,
        "api_key_identity": api_key_identity,
        "event_type": event_type,
        "reason": reason,
        "cost": float(user_info.get("cost", 0)),
        "tokens": int(user_info.get("tokens", 0)),
        "requests": int(user_info.get("requests", 0)),
        "payload": payload if payload is not None else sanitize_user_info(user_info),
    }


def evaluate_users(
    result,
    state,
    month,
    year,
    default_budget_limit,
    default_warning_threshold,
    delete_api_key,
    send_email,
):
    period_key = build_period_key(month, year)
    events = []
    archived_keys = []

    for user_name, user_info in result.get("users", {}).items():
        user_state = get_user_state(state, user_name)
        if (user_state.get("status") or "active") == "disabled":
            print(f"Skipping disabled user: {user_name}")
            continue

        budget_limit = float(user_state.get("budget_limit") or default_budget_limit)
        warning_threshold = float(
            user_state.get("warning_threshold") or default_warning_threshold
        )
        cost = float(user_info.get("cost", 0))
        tokens = int(user_info.get("tokens", 0))
        if cost <= 0 and tokens <= 0:
            continue

        active_api_keys = user_info.get("active_api_keys", [])
        active_scope = ",".join(
            sorted(
                api_key["api_key_identity"]
                for api_key in active_api_keys
                if api_key.get("api_key_identity")
            )
        )

        if warning_threshold <= cost < budget_limit:
            warning_scope = active_scope or user_name
            warning_key = build_event_key(user_name, "warning", period_key, warning_scope)
            if not has_event_key(state, warning_key):
                events.append(
                    create_event(
                        user_name=user_name,
                        event_type="warning",
                        period_key=period_key,
                        month=month,
                        year=year,
                        scope=warning_scope,
                        reason=(
                            f"cost {cost:.2f} >= warning_threshold {warning_threshold:.2f}"
                        ),
                        user_info=user_info,
                    )
                )
                send_email(
                    "DeepSeek usage warning",
                    build_notification_body(
                        user_name,
                        user_info,
                        budget_limit,
                        warning_threshold,
                    ),
                )

        if cost < budget_limit:
            continue

        if not active_api_keys:
            print(f"User {user_name} is over budget but has no active API key to delete.")
            continue

        deleted_any = False
        for api_key in active_api_keys:
            api_key_identity = api_key.get("api_key_identity", "")
            if not api_key_identity:
                continue

            delete_key = build_event_key(
                user_name,
                "delete_api",
                period_key,
                api_key_identity,
            )
            if has_event_key(state, delete_key):
                continue

            block_key = build_event_key(user_name, "block", period_key, api_key_identity)
            if not has_event_key(state, block_key):
                events.append(
                    create_event(
                        user_name=user_name,
                        event_type="block",
                        period_key=period_key,
                        month=month,
                        year=year,
                        scope=api_key_identity,
                        reason=f"cost {cost:.2f} >= budget_limit {budget_limit:.2f}",
                        user_info=user_info,
                        api_key_identity=api_key_identity,
                    )
                )

            delete_api_key(api_key)

            events.append(
                create_event(
                    user_name=user_name,
                    event_type="delete_api",
                    period_key=period_key,
                    month=month,
                    year=year,
                    scope=api_key_identity,
                    reason="platform api key deleted after budget limit reached",
                    user_info=user_info,
                    api_key_identity=api_key_identity,
                    payload={
                        "deleted": True,
                        "api_key_identity": api_key_identity,
                    },
                )
            )
            archived_keys.append({
                **api_key,
                "status": "used",
                "deleted_at": now_iso(),
                "final_cost": round(cost, 4),
                "final_tokens": tokens,
                "final_requests": int(user_info.get("requests", 0)),
            })
            deleted_any = True

        if deleted_any:
            send_email(
                "DeepSeek API key deleted after budget limit reached",
                build_notification_body(
                    user_name,
                    user_info,
                    budget_limit,
                    warning_threshold,
                ),
            )

    return events, archived_keys


def build_managed_users_payload(
    monitored_users,
    state,
    default_budget_limit,
    default_warning_threshold,
):
    payload = []
    for user_name in monitored_users:
        user_state = get_user_state(state, user_name)
        payload.append({
            "name": user_name,
            "budget_limit": float(
                user_state.get("budget_limit") or default_budget_limit
            ),
            "warning_threshold": float(
                user_state.get("warning_threshold") or default_warning_threshold
            ),
            "status": user_state.get("status") or "active",
        })
    return payload
