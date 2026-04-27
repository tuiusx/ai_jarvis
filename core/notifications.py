import json
import os
from urllib import parse, request


class CriticalNotifier:
    SEVERITY_ORDER = {
        "info": 0,
        "warning": 1,
        "error": 2,
        "critical": 3,
    }

    def __init__(
        self,
        enabled: bool = False,
        channel: str = "console",
        telegram_token_env: str = "JARVIS_TELEGRAM_BOT_TOKEN",
        telegram_chat_id_env: str = "JARVIS_TELEGRAM_CHAT_ID",
        min_severity: str = "critical",
        webhook_url: str = "",
        webhook_token_env: str = "JARVIS_WEBHOOK_TOKEN",
    ):
        self.enabled = bool(enabled)
        self.channel = str(channel or "console").lower()
        self.telegram_token_env = telegram_token_env
        self.telegram_chat_id_env = telegram_chat_id_env
        self.min_severity = str(min_severity or "critical").lower()
        if self.min_severity not in self.SEVERITY_ORDER:
            self.min_severity = "critical"
        self.webhook_url = str(webhook_url or "").strip()
        self.webhook_token_env = str(webhook_token_env or "JARVIS_WEBHOOK_TOKEN")

    def notify(self, entry: dict):
        if not self.enabled:
            return False
        severity = str(entry.get("severity", "")).lower()
        if self.SEVERITY_ORDER.get(severity, -1) < self.SEVERITY_ORDER.get(self.min_severity, 3):
            return False

        message = (
            f"[{severity.upper()}] {entry.get('event', 'unknown')} - "
            f"{json.dumps(entry.get('data', {}), ensure_ascii=False)}"
        )

        channels = [item.strip() for item in self.channel.split(",") if item.strip()]
        if not channels:
            channels = ["console"]

        delivered = False
        for channel in channels:
            if channel == "telegram":
                delivered = self._notify_telegram(message) or delivered
                continue
            if channel == "webhook":
                delivered = self._notify_webhook(entry) or delivered
                continue
            print(message)
            delivered = True
        return delivered

    def _notify_telegram(self, message: str):
        token = os.getenv(self.telegram_token_env, "").strip()
        chat_id = os.getenv(self.telegram_chat_id_env, "").strip()
        if not token or not chat_id:
            return False

        payload = parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req = request.Request(url=url, data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with request.urlopen(req, timeout=5):  # nosec B310
                return True
        except Exception:
            return False

    def _notify_webhook(self, entry: dict):
        if not self.webhook_url:
            return False

        token = os.getenv(self.webhook_token_env, "").strip()
        body = json.dumps(entry, ensure_ascii=False).encode("utf-8")
        req = request.Request(url=self.webhook_url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with request.urlopen(req, timeout=5):  # nosec B310
                return True
        except Exception:
            return False
