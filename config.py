import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_id: int
    tz: str
    country: str

def load_config() -> Config:
    token = (os.getenv("BOT_TOKEN") or "").strip()
    admin = (os.getenv("ADMIN_ID") or "").strip()
    tz = (os.getenv("TZ") or "Asia/Tashkent").strip()
    country = (os.getenv("COUNTRY") or "UZ").strip()

    if not token:
        raise RuntimeError("BOT_TOKEN yo‘q")
    if not admin.isdigit():
        raise RuntimeError("ADMIN_ID raqam bo‘lishi kerak")

    return Config(
        bot_token=token,
        admin_id=int(admin),
        tz=tz,
        country=country,
    )
