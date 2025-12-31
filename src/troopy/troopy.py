import asyncio
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import print_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from .agent import TroopyAgent
from .agent import LLMClient
from .agent import OpenAICompatibleClient
from ..config import env_loader
from ..agents import PythonAssistant


class TroopyConfig:
    """
    Troopy 配置类

    从环境变量加载配置，如果未设置则使用默认值。
    优先级: 环境变量 > .env 文件 > 硬编码默认值
    """
    # 配置将在类定义后从 env_loader 加载
    api_url: str
    api_key: str
    model: str


# 从 env_loader 加载配置并设置类属性
_config = env_loader.get_troopy_config()
TroopyConfig.api_url = _config["api_url"]
TroopyConfig.api_key = _config["api_key"]
TroopyConfig.model = _config["model"]


class TroopyMgr:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            python_assistant = PythonAssistant(llm_client=OpenAICompatibleClient(
                api_base=TroopyConfig.api_url,
                api_key=TroopyConfig.api_key,
                model=TroopyConfig.model
            ))
            self.agents = {python_assistant.id: python_assistant}
            self.agents = {}
            self.agents[python_assistant.id] = python_assistant
            # self.agents = {python_assistant.id: python_assistant}
            self.current_troopy: TroopyAgent = python_assistant
            self.initialized = True

    @classmethod
    def instance(cls) -> "TroopyMgr":
        return TroopyMgr()

    @property
    def current_agent(self) -> TroopyAgent:
        return self.current_troopy

    @classmethod
    async def get_instance(cls):
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # def create_agent(self, name: str, role: str, llm_client: OpenAICompatibleClient, system_message: str = "") -> TroopyAgent:
    #     """创建一个新的Agent"""
    #     agent = TroopyAgent(name, role, llm_client, system_message)
    #     self.agents[agent.id] = agent
    #     return agent


class Troopy:
    """Troopy REPL 交互类"""

    # 定义自动补全关键词
    COMPLETER_WORDS = ['help', 'status', 'exit',
                       'process', 'task', 'context', "quit"]

    # 定义样式 (2025年流行的深色系)
    STYLE_DICT = {
        'completion-menu.completion': 'bg:#008888 #ffffff',
        'completion-menu.completion.current': 'bg:#00aaaa #000000',
        'scrollbar.background': 'bg:#88aaaa',
        'scrollbar.button': 'bg:#222222',
        'status': 'bg:#444444 #ffffff italic',
        'prompt': '#00ff00 bold',
        'agent': '#00aaaa bold',
    }

    def __init__(self):
        """初始化 Troopy REPL"""
        self.completer = WordCompleter(self.COMPLETER_WORDS, ignore_case=True)
        self.style = Style.from_dict(self.STYLE_DICT)
        self.key_bindings = KeyBindings()
        self.is_processing = False

        # 设置 ESC 键绑定
        @self.key_bindings.add(Keys.Escape)
        def _(event):
            """按下 ESC 键时取消当前正在处理的请求"""
            if self.is_processing:
                TroopyMgr.instance().current_agent.cancel_request()
                print_formatted_text(
                    HTML('<ansired>\n[请求已被取消]</ansired>'), style=self.style)
                # 强制刷新输出
                event.app.renderer.render(None, in_layout=False)

        self.session = PromptSession(
            history=InMemoryHistory(),
            completer=self.completer,
            style=self.style,
            key_bindings=self.key_bindings
        )

    async def ask_agent(self, text: str) -> str:
        """模拟一个耗时的异步后台任务"""
        self.is_processing = True
        try:
            response = TroopyMgr.instance().current_agent.send_message(text)
            print_formatted_text(
                HTML(
                    f'<agent><b>{TroopyMgr.instance().current_agent.name}:</b> </agent>'), style=self.style)
            print(f"{response}")
            return f"{response}"
        except Exception as e:
            if "已被取消" in str(e):
                # 请求被取消，移除用户消息（因为响应没有添加）
                current_agent = TroopyMgr.instance().current_agent
                if current_agent.conversation_history and current_agent.conversation_history[-1]["role"] == "user":
                    current_agent.conversation_history.pop()
                return ""
            raise
        finally:
            self.is_processing = False

    def get_bottom_toolbar(self) -> HTML:
        """获取底部状态栏内容"""
        if self.is_processing:
            return HTML('<b>[Status]</b> <ansiyellow>处理中...</ansiyellow> | 按 <ESC> 取消 | 输入 "exit" 退出')
        return HTML('<b>[Status]</b> 准备就绪 | 输入 "exit" 退出')

    async def process_input(self, user_input: str) -> bool:
        """
        处理用户输入
        返回 True 表示继续运行，False 表示退出
        """
        user_input = user_input.strip()

        if not user_input:
            return True

        if user_input.lower() in ('exit', 'quit'):
            return False

        # 处理context命令
        if user_input.lower() == 'context':
            # 获取当前agent的对话历史
            current_agent = TroopyMgr.instance().current_agent
            conversation_history = current_agent.get_conversation_history()

            # 输出对话历史
            print_formatted_text(
                HTML('<b><u>当前对话历史:</u></b>'), style=self.style)

            for i, message in enumerate(conversation_history):
                role = message['role']
                content = message['content']
                print_formatted_text(
                    HTML(f'<b>{i+1}. {role}:</b> {content}'), style=self.style)

            return True

        # 处理异步指令
        result = await self.ask_agent(user_input)

        return True

    async def run(self):

        banner = HTML('<b>Troopy</b> v1.0.0\n<b>Model</b>: GLM4.7')
        print_formatted_text(banner, style=self.style)

        while True:
            try:
                user_input = await self.session.prompt_async(
                    HTML(
                        f'<prompt>[{TroopyMgr.instance().current_agent.name}]>>> </prompt>'),
                    bottom_toolbar=self.get_bottom_toolbar()
                )

                should_continue = await self.process_input(user_input)
                if not should_continue:
                    break

            except KeyboardInterrupt:
                continue  # Ctrl+C 清空当前行
            except EOFError:
                break     # Ctrl+D 退出

        print("程序已安全关闭。")

    @classmethod
    async def async_main(cls):
        """异步入口点"""
        troopy = cls()

        await troopy.run()


if __name__ == "__main__":
    try:
        asyncio.run(Troopy.async_main())
    except KeyboardInterrupt:
        pass
