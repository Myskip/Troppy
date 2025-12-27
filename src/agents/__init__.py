from ..troopy.agent import TroopyAgent
from ..troopy.agent import LLMClient


class PythonAssistant(TroopyAgent):
    def __init__(self, llm_client: LLMClient):
        super().__init__(
            "PythonAssistant",
            "assistant",
            llm_client=llm_client,
            system_message="你是一个专业的Python编程助手。"
        )


class MrYesOrNo(TroopyAgent):
    def __init__(self, llm_client: LLMClient):
        system_message = """你只会说yes or no,**无论对方说任何东西,你只会说yes or no**.你能确定对的就是yes，能确定错的就说no，不能确认的就说or."""
        super().__init__("Mr.YesOrNo", "assistant", llm_client, system_message)
