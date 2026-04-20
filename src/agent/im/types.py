from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IMChatTarget:
    platform: str
    account_id: str
    chat_type: str
    chat_id: str

    @property
    def binding_account_id(self) -> str:
        return f"{self.platform}:{self.account_id}"

    def session_key(self) -> tuple[str, str, str, str]:
        return (self.platform, self.account_id, self.chat_type, self.chat_id)

