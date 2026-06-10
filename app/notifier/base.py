from abc import ABC, abstractmethod


class NotificationChannel(ABC):
    name = "unknown"

    @property
    def enabled(self):
        return True

    @abstractmethod
    def notify(self, subject, body):
        raise NotImplementedError
