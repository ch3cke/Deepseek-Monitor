from app.config import AppConfig
from app.ingest_client import IngestClient
from app.storage.base import StorageBackend


class CloudflareStorage(StorageBackend):
    name = "cloudflare"

    def __init__(self, config: AppConfig):
        self.config = config
        self.client = IngestClient(config)

    def startup_message(self):
        return "Cloudflare storage enabled."

    def get_state(self):
        return self.client.get_state()

    def push_snapshot(self, result, month, year, managed_users, api_keys, events):
        return self.client.push_snapshot(
            result=result,
            month=month,
            year=year,
            managed_users=managed_users,
            api_keys=api_keys,
            events=events,
        )
