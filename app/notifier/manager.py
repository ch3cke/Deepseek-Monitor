from app.notifier.email import EmailNotifier
from app.notifier.webhook import FeishuBotNotifier


class NotificationManager:
    def __init__(self, channels):
        self.channels = [channel for channel in channels if channel.enabled]

    @property
    def enabled(self):
        return bool(self.channels)

    def notify(self, subject, body):
        results = []
        for channel in self.channels:
            try:
                results.append(channel.notify(subject, body))
            except Exception as exc:
                print(f"Failed to notify via {channel.name}: {exc}")
                results.append({
                    "ok": False,
                    "channel": channel.name,
                    "error": str(exc),
                })
        return results


def build_notifier(config):
    return NotificationManager(
        [
            EmailNotifier(config),
            FeishuBotNotifier(config),
        ]
    )
