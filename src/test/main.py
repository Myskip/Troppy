import asyncio
from ..troopy.troopy import Troopy


def main():
    """同步入口点"""
    try:
        asyncio.run(Troopy.async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
