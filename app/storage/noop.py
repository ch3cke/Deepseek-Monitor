from app.storage.base import StorageBackend, empty_state


class NoopStorage(StorageBackend):
    name = "none"

    def __init__(self, reason):
        self.reason = reason

    @property
    def enabled(self):
        return False

    def startup_message(self):
        return self.reason

    def get_state(self):
        return empty_state()

    def push_snapshot(self, result, month, year, managed_users, api_keys, events):
        return {
            "ok": False,
            "skipped": True,
            "backend": self.name,
            "reason": self.reason,
        }
