import os
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from app.aggregator import aggregate_usage
from app.config import load_config
from app.events import evaluate_users
from app.main import run_monitor
from app.notifier.manager import NotificationManager
from app.notifier.webhook import (
    build_feishu_interactive_payload,
    build_feishu_payload,
    build_feishu_signature,
    build_feishu_text_payload,
)
from app.storage import build_storage
from app.storage.cloudflare import CloudflareStorage
from app.storage.feishu_bitable import FeishuBitableStorage
from app.storage.noop import NoopStorage
from app.storage.supabase import SupabaseStorage
from app.utils.api_keys import build_platform_key_record


class MainTests(unittest.TestCase):
    def setUp(self):
        self.monitored_users = ["alice"]
        self.default_budget_limit = 100.0
        self.default_warning_threshold = 80.0
        self.active_api_keys_by_name = {
            "alice": [
                {
                    "name": "alice",
                    "sensitive_id": "sid-1",
                    "created_at": "2026-06-01T00:00:00Z",
                    "redacted_key": "sk-...-1",
                }
            ]
        }

    def test_sum_cost_aggregates_multiple_keys_under_one_user(self):
        frame = pd.DataFrame(
            [
                {
                    "price": 1,
                    "amount": 10,
                    "api_key_name": "alice",
                    "api_key": "key-a",
                    "model": "m1",
                    "type": "output_tokens",
                },
                {
                    "price": 1,
                    "amount": 1,
                    "api_key_name": "alice",
                    "api_key": "key-a",
                    "model": "m1",
                    "type": "request_count",
                },
                {
                    "price": 1,
                    "amount": 20,
                    "api_key_name": "alice",
                    "api_key": "key-b",
                    "model": "m2",
                    "type": "output_tokens",
                },
                {
                    "price": 1,
                    "amount": 2,
                    "api_key_name": "alice",
                    "api_key": "key-b",
                    "model": "m2",
                    "type": "request_count",
                },
            ]
        )

        result = aggregate_usage(frame, self.monitored_users, self.active_api_keys_by_name)

        self.assertEqual(result["summary"]["cost"], 33.0)
        self.assertEqual(result["users"]["alice"]["cost"], 33.0)
        self.assertEqual(len(result["users"]["alice"]["api_keys"]), 2)
        self.assertEqual(result["users"]["alice"]["tokens"], 30)
        self.assertEqual(result["users"]["alice"]["requests"], 3)

    def test_warning_emits_once_per_period_scope(self):
        result = {
            "users": {
                "alice": {
                    "cost": 85.0,
                    "tokens": 1000,
                    "requests": 10,
                    "models": {},
                    "api_keys": [{"api_key_label": "key-a", "cost": 85.0, "tokens": 1000, "requests": 10, "models": {}}],
                    "active_api_keys": [
                        build_platform_key_record(
                            "alice",
                            self.active_api_keys_by_name["alice"][0],
                        )
                    ],
                }
            }
        }
        state = {"users": {}, "events": []}

        send_email = Mock()
        events, archived_keys = evaluate_users(
            result,
            state,
            6,
            2026,
            self.default_budget_limit,
            self.default_warning_threshold,
            delete_api_key=lambda _api_key: {"ok": True},
            send_email=send_email,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "warning")
        self.assertEqual(archived_keys, [])
        send_email.assert_called_once()

        state["events"] = [{"event_key": events[0]["event_key"]}]
        send_email.reset_mock()
        repeated_events, archived_keys = evaluate_users(
            result,
            state,
            6,
            2026,
            self.default_budget_limit,
            self.default_warning_threshold,
            delete_api_key=lambda _api_key: {"ok": True},
            send_email=send_email,
        )

        self.assertEqual(repeated_events, [])
        self.assertEqual(archived_keys, [])
        send_email.assert_not_called()

    def test_budget_limit_deletes_key_and_marks_it_used(self):
        result = {
            "users": {
                "alice": {
                    "cost": 100.0,
                    "tokens": 1500,
                    "requests": 12,
                    "models": {},
                    "api_keys": [{"api_key_label": "key-a", "cost": 100.0, "tokens": 1500, "requests": 12, "models": {}}],
                    "active_api_keys": [
                        build_platform_key_record(
                            "alice",
                            self.active_api_keys_by_name["alice"][0],
                        )
                    ],
                }
            }
        }
        state = {"users": {}, "events": []}

        delete_api_key = Mock(return_value={"ok": True})
        send_email = Mock()
        events, archived_keys = evaluate_users(
            result,
            state,
            6,
            2026,
            self.default_budget_limit,
            self.default_warning_threshold,
            delete_api_key=delete_api_key,
            send_email=send_email,
        )

        self.assertEqual(delete_api_key.call_count, 1)
        self.assertEqual([event["event_type"] for event in events], ["block", "delete_api"])
        self.assertEqual(len(archived_keys), 1)
        self.assertEqual(archived_keys[0]["status"], "used")
        self.assertEqual(archived_keys[0]["final_cost"], 100.0)
        send_email.assert_called_once()

    def test_feishu_payload_uses_text_message(self):
        payload = build_feishu_text_payload("Alert", "body text")

        self.assertEqual(payload["msg_type"], "text")
        self.assertEqual(payload["content"]["text"], "Alert\n\nbody text")

    def test_feishu_payload_supports_keyword_and_interactive_card(self):
        payload = build_feishu_interactive_payload("Alert", "body text", keyword="[bot]")

        self.assertEqual(payload["msg_type"], "interactive")
        self.assertEqual(payload["card"]["header"]["title"]["content"], "[bot] Alert")

    def test_feishu_payload_includes_signature_when_secret_is_set(self):
        payload = build_feishu_payload(
            title="Alert",
            body="body text",
            message_type="text",
            keyword="",
            secret="secret-value",
        )

        self.assertIn("timestamp", payload)
        self.assertIn("sign", payload)
        self.assertTrue(payload["timestamp"])
        self.assertTrue(payload["sign"])

    def test_feishu_signature_is_stable_for_fixed_timestamp(self):
        timestamp, sign = build_feishu_signature("secret-value", timestamp="123456")

        self.assertEqual(timestamp, "123456")
        self.assertEqual(sign, "Cnbwb2bjy+b6lxJUZIpTT1lHVWS/su4FnB9b7XsfgG0=")

    def test_load_config_disables_storage_when_cloudflare_vars_are_missing(self):
        with patch.dict(
            os.environ,
            {
                "AUTH": "token",
                "MONITORED_USERS": "alice,bob",
            },
            clear=True,
        ):
            config = load_config()

        self.assertFalse(config.cloudflare_storage_enabled)
        self.assertFalse(config.cloudflare_storage_partially_configured)
        self.assertFalse(config.feishu_bitable_storage_enabled)
        self.assertFalse(config.feishu_bitable_storage_partially_configured)
        self.assertFalse(config.supabase_storage_enabled)
        self.assertFalse(config.supabase_storage_partially_configured)

    def test_load_config_marks_partial_storage_config(self):
        with patch.dict(
            os.environ,
            {
                "AUTH": "token",
                "MONITORED_USERS": "alice,bob",
                "CLOUDFLARE_INGEST_URL": "https://example.workers.dev/api/ingest",
            },
            clear=True,
        ):
            config = load_config()

        self.assertFalse(config.cloudflare_storage_enabled)
        self.assertTrue(config.cloudflare_storage_partially_configured)

    def test_load_config_marks_feishu_bitable_storage_as_enabled(self):
        with patch.dict(
            os.environ,
            {
                "AUTH": "token",
                "MONITORED_USERS": "alice,bob",
                "FEISHU_APP_ID": "cli_xxx",
                "FEISHU_APP_SECRET": "secret_xxx",
                "FEISHU_BITABLE_APP_TOKEN": "app_token_xxx",
                "FEISHU_BITABLE_USERS_TABLE_ID": "tbl_users",
                "FEISHU_BITABLE_API_KEYS_TABLE_ID": "tbl_api_keys",
                "FEISHU_BITABLE_USAGE_TABLE_ID": "tbl_usage",
                "FEISHU_BITABLE_EVENTS_TABLE_ID": "tbl_events",
            },
            clear=True,
        ):
            config = load_config()

        self.assertTrue(config.feishu_bitable_storage_enabled)
        self.assertFalse(config.feishu_bitable_storage_partially_configured)

    def test_load_config_marks_supabase_storage_as_enabled(self):
        with patch.dict(
            os.environ,
            {
                "AUTH": "token",
                "MONITORED_USERS": "alice,bob",
                "SUPABASE_URL": "https://project.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
                "SUPABASE_MANAGED_USERS_TABLE": "managed_users",
                "SUPABASE_API_KEYS_TABLE": "api_keys",
                "SUPABASE_USAGE_RECORDS_TABLE": "usage_records",
                "SUPABASE_EVENTS_TABLE": "events",
            },
            clear=True,
        ):
            config = load_config()

        self.assertTrue(config.supabase_storage_enabled)
        self.assertFalse(config.supabase_storage_partially_configured)

    def test_build_storage_returns_noop_backend_when_storage_is_disabled(self):
        config = Mock(
            storage_backend="auto",
            cloudflare_storage_enabled=False,
            cloudflare_storage_partially_configured=False,
            feishu_bitable_storage_enabled=False,
            feishu_bitable_storage_partially_configured=False,
            supabase_storage_enabled=False,
            supabase_storage_partially_configured=False,
        )

        storage = build_storage(config)

        self.assertIsInstance(storage, NoopStorage)

    def test_build_storage_returns_cloudflare_backend_when_storage_is_enabled(self):
        config = Mock(
            storage_backend="auto",
            cloudflare_storage_enabled=True,
            cloudflare_storage_partially_configured=False,
            feishu_bitable_storage_enabled=False,
            feishu_bitable_storage_partially_configured=False,
            supabase_storage_enabled=False,
            supabase_storage_partially_configured=False,
        )

        storage = build_storage(config)

        self.assertIsInstance(storage, CloudflareStorage)

    def test_build_storage_auto_prefers_cloudflare_over_other_backends(self):
        config = Mock(
            storage_backend="auto",
            cloudflare_storage_enabled=True,
            cloudflare_storage_partially_configured=False,
            feishu_bitable_storage_enabled=True,
            feishu_bitable_storage_partially_configured=False,
            supabase_storage_enabled=True,
            supabase_storage_partially_configured=False,
        )

        storage = build_storage(config)

        self.assertIsInstance(storage, CloudflareStorage)

    def test_build_storage_returns_feishu_bitable_backend_when_requested(self):
        config = Mock(
            storage_backend="feishu_bitable",
            cloudflare_storage_enabled=False,
            cloudflare_storage_partially_configured=False,
            feishu_bitable_storage_enabled=True,
            feishu_bitable_storage_partially_configured=False,
            supabase_storage_enabled=False,
            supabase_storage_partially_configured=False,
        )

        storage = build_storage(config)

        self.assertIsInstance(storage, FeishuBitableStorage)

    def test_build_storage_returns_supabase_backend_when_requested(self):
        config = Mock(
            storage_backend="supabase",
            cloudflare_storage_enabled=False,
            cloudflare_storage_partially_configured=False,
            feishu_bitable_storage_enabled=False,
            feishu_bitable_storage_partially_configured=False,
            supabase_storage_enabled=True,
            supabase_storage_partially_configured=False,
        )

        storage = build_storage(config)

        self.assertIsInstance(storage, SupabaseStorage)

    def test_notification_manager_notifies_all_enabled_channels(self):
        email_channel = Mock(enabled=True)
        email_channel.notify.return_value = {"ok": True, "channel": "email"}
        feishu_channel = Mock(enabled=True)
        feishu_channel.notify.return_value = {"ok": True, "channel": "feishu_bot"}
        disabled_channel = Mock(enabled=False)

        manager = NotificationManager([email_channel, feishu_channel, disabled_channel])
        results = manager.notify("Alert", "body text")

        email_channel.notify.assert_called_once_with("Alert", "body text")
        feishu_channel.notify.assert_called_once_with("Alert", "body text")
        disabled_channel.notify.assert_not_called()
        self.assertEqual(len(results), 2)

    @patch("app.main.collect_usage_snapshot", return_value=(6, 2026, {}, {"users": {}}))
    @patch("app.main.evaluate_users", return_value=([], []))
    @patch("app.main.build_notifier")
    @patch("app.main.build_storage")
    @patch("app.main.PlatformClient")
    @patch("app.main.load_config")
    def test_run_monitor_uses_storage_factory_instead_of_direct_ingest_client(
        self,
        load_config_mock,
        _platform_client_mock,
        build_storage_mock,
        build_notifier_mock,
        _evaluate_users_mock,
        _collect_usage_snapshot_mock,
    ):
        load_config_mock.return_value = Mock(
            monitored_users=["alice"],
            default_budget_limit=100.0,
            default_warning_threshold=80.0,
        )
        storage = Mock()
        storage.name = "mock_storage"
        storage.startup_message.return_value = "Cloudflare storage enabled."
        storage.get_state.return_value = {"users": {}, "events": []}
        storage.push_snapshot.return_value = {"ok": True}
        build_storage_mock.return_value = storage
        build_notifier_mock.return_value = Mock(notify=Mock())

        run_monitor()

        build_storage_mock.assert_called_once()
        storage.get_state.assert_called_once()
        storage.push_snapshot.assert_called_once()


if __name__ == "__main__":
    unittest.main()
