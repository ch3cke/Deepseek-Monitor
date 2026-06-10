import argparse
from datetime import datetime

from app.aggregator import aggregate_usage, build_api_keys_payload, refresh_active_api_keys
from app.config import load_config
from app.events import build_managed_users_payload, evaluate_users
from app.extractor import extract_amount_csv
from app.notifier import build_notifier
from app.notifications import build_summary_email
from app.platform_client import PlatformClient
from app.storage import build_storage


def resolve_billing_period():
    now = datetime.now()
    return (
        now.month,
        now.year,
    )


def collect_usage_snapshot(config, platform_client):
    month, year = resolve_billing_period()
    active_api_keys_by_name = platform_client.list_api_keys_by_name()
    amount = extract_amount_csv(platform_client.request_usage_export(month, year))
    result = aggregate_usage(amount, config.monitored_users, active_api_keys_by_name)
    return month, year, active_api_keys_by_name, result


def run_monitor():
    config = load_config()
    platform_client = PlatformClient(config)
    storage = build_storage(config)
    notifier = build_notifier(config)

    startup_message = storage.startup_message()
    if startup_message:
        print(startup_message)
    state = storage.get_state()

    month, year, active_api_keys_by_name, result = collect_usage_snapshot(
        config,
        platform_client,
    )

    events, archived_keys = evaluate_users(
        result=result,
        state=state,
        month=month,
        year=year,
        default_budget_limit=config.default_budget_limit,
        default_warning_threshold=config.default_warning_threshold,
        delete_api_key=platform_client.delete_api_key,
        send_email=notifier.notify,
    )

    if archived_keys:
        active_api_keys_by_name = platform_client.list_api_keys_by_name()
        refresh_active_api_keys(result, active_api_keys_by_name)

    managed_users = build_managed_users_payload(
        config.monitored_users,
        state,
        config.default_budget_limit,
        config.default_warning_threshold,
    )
    api_keys_payload = build_api_keys_payload(
        config.monitored_users,
        active_api_keys_by_name,
        archived_keys,
    )

    response = storage.push_snapshot(
        result=result,
        month=month,
        year=year,
        managed_users=managed_users,
        api_keys=api_keys_payload,
        events=events,
    )
    if response and not response.get("skipped"):
        print(f"Uploaded to {storage.name}: {response}")


def run_summary():
    config = load_config()
    platform_client = PlatformClient(config)
    notifier = build_notifier(config)
    month, year, _active_api_keys_by_name, result = collect_usage_snapshot(
        config,
        platform_client,
    )
    subject, body = build_summary_email(result, month, year)
    notifier.notify(subject, body)


def build_parser():
    parser = argparse.ArgumentParser(description="DeepSeek monitor entrypoint")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["monitor", "summary"],
        default="monitor",
        help="Command to run.",
    )
    return parser


def main():
    args = build_parser().parse_args()
    if args.command == "summary":
        run_summary()
        return
    run_monitor()


if __name__ == "__main__":
    main()
