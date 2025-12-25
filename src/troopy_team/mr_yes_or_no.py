from ..agent import TroopyAgent
from ..agent import LLMClient


class MrYesOrNo(TroopyAgent):
    def __init__(self, llm_client: LLMClient):
        system_message = """你只会说yes or no,**无论对方说任何东西,你只会说yes or no**.你能确定对的就是yes，能确定错的就说no，不能确认的就说or."""
        super().__init__("Mr.YesOrNo", "assistant", llm_client, system_message)
