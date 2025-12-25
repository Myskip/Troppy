"""
环境变量加载器

从 .env 文件加载环境变量，并提供获取 Troopy 相关配置的函数。
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Union


def load_dotenv(dotenv_path: Optional[Union[str, Path]] = None) -> bool:
    """
    从 .env 文件加载环境变量到 os.environ

    参数:
        dotenv_path: .env 文件路径，默认为项目根目录下的 .env 文件

    返回:
        bool: 是否成功加载了文件（文件存在且可读）
    """
    # 转换为 Path 对象
    if dotenv_path is None:
        # 默认在当前目录的父目录中查找 .env 文件（项目根目录）
        current_dir = Path(__file__).parent
        project_root = current_dir.parent
        dotenv_path = project_root / ".env"
    elif isinstance(dotenv_path, str):
        dotenv_path = Path(dotenv_path)
    # 如果已经是 Path 对象，则直接使用

    if not dotenv_path.exists():
        return False

    try:
        # Path 对象可以直接传递给 open()
        with open(dotenv_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue

                # 解析 KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # 移除值两端的引号
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]

                    # 如果环境变量尚未设置，则设置它
                    if key and key not in os.environ:
                        os.environ[key] = value
        return True
    except Exception as e:
        print(f"警告: 加载 .env 文件时出错: {e}", file=sys.stderr)
        return False


def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    获取环境变量，优先从 os.environ 获取，如果不存在则返回默认值

    参数:
        key: 环境变量名
        default: 默认值

    返回:
        str 或 None: 环境变量值或默认值
    """
    return os.environ.get(key, default)


def get_troopy_config() -> Dict[str, Any]:
    """
    获取 Troopy 配置

    返回包含以下键的字典:
        - api_url: TROOPY_API_URL 环境变量或默认值
        - api_key: TROOPY_API_KEY 环境变量或默认值
        - model: TROOPY_DEFAULT_MODEL 环境变量或默认值

    默认值使用硬编码的默认配置
    """
    # 首先尝试加载 .env 文件
    load_dotenv()

    # 硬编码的默认值（与原始 TroopyConfig 保持一致）
    default_api_url = "https://api.deepseek.com/v1"
    default_api_key = "sk-0236f3009d1b4bb8b2a47c62929f9c88"
    default_model = "deepseek-reasoner"

    return {
        "api_url": get_env_var("TROOPY_API_URL", default_api_url),
        "api_key": get_env_var("TROOPY_API_KEY", default_api_key),
        "model": get_env_var("TROOPY_DEFAULT_MODEL", default_model),
    }


def init_env():
    """
    初始化环境变量

    自动加载 .env 文件（如果存在）
    """
    load_dotenv()


# 模块导入时自动初始化
init_env()


if __name__ == "__main__":
    # 测试代码
    config = get_troopy_config()
    print("Troopy 配置:")
    print(f"  API URL: {config['api_url']}")
    print(f"  API KEY: {'*' * min(8, len(config['api_key'] or ''))}...")
    print(f"  Model: {config['model']}")

    # 显示当前环境变量
    print("\n相关环境变量:")
    for key in ["TROOPY_API_URL", "TROOPY_API_KEY", "TROOPY_DEFAULT_MODEL"]:
        value = os.environ.get(key)
        if value:
            masked = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "***"
            print(f"  {key}: {masked}")
        else:
            print(f"  {key}: (未设置)")