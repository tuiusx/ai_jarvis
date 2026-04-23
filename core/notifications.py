import json
import os
from urllib import parse, request


class CriticalNotifier:
    def __init__(
        self,
        enabled: bool = False,
        channel: str = "console",
        telegram_token_env: str = "JARVIS_TELEGRAM_BOT_TOKEN",
        telegram_chat_id_env: str = "JARVIS_TELEGRAM_CHAT_ID",
    ):
        self.enabled = bool(enabled)
        self.channel = str(channel or "console").lower()
        self.telegram_token_env = telegram_token_env
        self.telegram_chat_id_env = telegram_chat_id_env

    def notify(self, entry: dict):
        if not self.enabled:
            return False
        if str(entry.get("severity", "")).lower() != "critical":
            return False

        message = (
            f"[CRITICAL] {entry.get('event', 'unknown')} - "
            f"{json.dumps(entry.get('data', {}), ensure_ascii=False)}"
        )

        if self.channel == "telegram":
            return self._notify_telegram(message)

        print(message)
        return True

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
