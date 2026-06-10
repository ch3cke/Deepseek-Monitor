from abc import ABC, abstractmethod


def empty_state():
    return {"users": {}, "events": []}


class StorageBackend(ABC):
    name = "unknown"

    @property
    def enabled(self):
        return True

    def startup_message(self):
        return None

    @abstractmethod
    def get_state(self):
        raise NotImplementedError

    @abstractmethod
    def push_snapshot(self, result, month, year, managed_users, api_keys, events):
        raise NotImplementedError
