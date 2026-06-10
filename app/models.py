from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmailNotification:
    subject: str
    body: str


@dataclass
class WebhookNotification:
    url: str
    title: str
    body: str


@dataclass
class MonitorArtifacts:
    result: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)
    archived_keys: list[dict[str, Any]] = field(default_factory=list)
