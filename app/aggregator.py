from collections import defaultdict

import pandas as pd

from app.utils.api_keys import build_platform_key_record
from app.utils.formatting import redact_value


def compute_model_summary(model_group):
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
    return {
        "cost": round(cost, 4),
        "tokens": tokens,
        "requests": requests_count,
    }


def aggregate_usage(df, monitored_users, active_api_keys_by_name):
    df = df.copy()

    required_cols = {"price", "amount", "api_key_name", "api_key", "model", "type"}
    missing = required_cols - set(df.columns)
    if missing:
        raise RuntimeError(f"amount CSV is missing columns: {sorted(missing)}")

    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["cost"] = df["price"] * df["amount"]

    monitored_df = df[df["api_key_name"].isin(set(monitored_users))]
    result = {"users": {}, "summary": {"cost": 0.0, "tokens": 0, "requests": 0}}

    for user_name, user_group in monitored_df.groupby("api_key_name"):
        user_cost = 0.0
        user_tokens = 0
        user_requests = 0
        aggregated_models = defaultdict(lambda: {"cost": 0.0, "tokens": 0, "requests": 0})
        api_keys = []

        for api_key_label, key_group in user_group.groupby("api_key"):
            key_cost = float(key_group["cost"].sum())
            key_tokens = int(
                key_group[
                    key_group["type"].isin([
                        "output_tokens",
                        "input_cache_hit_tokens",
                        "input_cache_miss_tokens",
                    ])
                ]["amount"].sum()
            )
            key_requests = int(
                key_group[key_group["type"] == "request_count"]["amount"].sum()
            )

            key_models = {}
            for model_name, model_group in key_group.groupby("model"):
                summary = compute_model_summary(model_group)
                key_models[model_name] = summary

                aggregate = aggregated_models[model_name]
                aggregate["cost"] += summary["cost"]
                aggregate["tokens"] += summary["tokens"]
                aggregate["requests"] += summary["requests"]

            api_keys.append({
                "api_key_label": redact_value(api_key_label),
                "cost": round(key_cost, 4),
                "tokens": key_tokens,
                "requests": key_requests,
                "models": key_models,
            })

            user_cost += key_cost
            user_tokens += key_tokens
            user_requests += key_requests

        active_api_key =build_platform_key_record(user_name, active_api_keys_by_name.get(user_name))


        models = {
            model_name: {
                "cost": round(model_info["cost"], 4),
                "tokens": model_info["tokens"],
                "requests": model_info["requests"],
            }
            for model_name, model_info in aggregated_models.items()
        }

        result["users"][user_name] = {
            "cost": round(user_cost, 4),
            "tokens": user_tokens,
            "requests": user_requests,
            "models": models,
            "api_keys": sorted(api_keys, key=lambda item: item["cost"], reverse=True),
            "active_api_key": active_api_key,
        }

        result["summary"]["cost"] += user_cost
        result["summary"]["tokens"] += user_tokens
        result["summary"]["requests"] += user_requests

    result["summary"]["cost"] = round(result["summary"]["cost"], 4)
    return result


def refresh_active_api_keys(result, active_api_keys_by_name):
    for user_name, user_info in result.get("users", {}).items():
        user_info["active_api_key"] = build_platform_key_record(user_name, active_api_keys_by_name.get(user_name))



def build_api_keys_payload(monitored_users, active_api_keys_by_name, archived_keys):
    items = {}
    for user_name in monitored_users:
        record = build_platform_key_record(user_name,  active_api_keys_by_name.get(user_name), status="active")
        items[record["api_key_identity"]] = record

    for record in archived_keys:
        items[record["api_key_identity"]] = record

    return list(items.values())
