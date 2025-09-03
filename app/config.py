from pydantic import BaseModel
import os
from dotenv import load_dotenv

class Settings(BaseModel):
    bot_token: str
    admin_ids: list[int] = []
    whitelist_ids: list[int] = []
    default_assignee_username: str = "@kykyzh1"

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        token = os.getenv("BOT_TOKEN", "")
        admins = [int(x) for x in os.getenv("ADMIN_IDS","").replace(" ","").split(",") if x]
        wl = [int(x) for x in os.getenv("WHITELIST_IDS","").replace(" ","").split(",") if x]
        if not wl: wl = admins.copy()
        default_user = os.getenv("DEFAULT_ASSIGNEE_USERNAME", "@kykyzh1")
        return cls(bot_token=token, admin_ids=admins, whitelist_ids=wl, default_assignee_username=default_user)

settings = Settings.load()
