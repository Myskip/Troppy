import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class TroopyConfig:
    """Troopy 配置类"""
    api_url: str | None
    api_key: str | None
    model: str | None


def get_troopy_config() -> TroopyConfig:
    """
    获取 Troopy 配置

    返回包含以下字段的数据类:
        - api_url: TROOPY_API_URL 环境变量
        - api_key: TROOPY_API_KEY 环境变量
        - model: TROOPY_MODEL 环境变量
    """
    return TroopyConfig(
        api_url=os.getenv("TROOPY_API_URL"),
        api_key=os.getenv("TROOPY_API_KEY"),
        model=os.getenv("TROOPY_MODEL"),
    )


load_dotenv()
