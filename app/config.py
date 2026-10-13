import os
from dataclasses import dataclass
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_url: str


def get_settings() -> Settings:
    url = os.getenv("MAVUMBI_DB_URL")
    if not url:
        user = os.getenv("MYSQL_USER", "root")
        pw = quote_plus(os.getenv("MYSQL_PASSWORD", ""))
        host = os.getenv("MYSQL_HOST", "127.0.0.1")
        port = os.getenv("MYSQL_PORT", "3306")
        name = os.getenv("MYSQL_DATABASE", "mavumbi_club")
        url = f"mysql+pymysql://{user}:{pw}@{host}:{port}/{name}?charset=utf8mb4"
    return Settings(db_url=url)
