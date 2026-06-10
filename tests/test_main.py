import unittest
from unittest.mock import Mock

import pandas as pd

from app.aggregator import aggregate_usage
from app.events import evaluate_users
from app.notifier.webhook import (
    build_feishu_interactive_payload,
    build_feishu_payload,
    build_feishu_signature,
    build_feishu_text_payload,
)
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


if __name__ == "__main__":
    unittest.main()
