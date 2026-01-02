# ESC 键取消请求设计文档

## 概述

本文档描述了 Troopy 中 ESC 键取消 LLM 请求功能的实现设计。

## 问题背景

### 原始问题
当用户发送消息给 LLM 等待响应时，`requests.post()` 是一个同步阻塞调用：
1. 主线程被阻塞在网络请求中
2. prompt_toolkit 的事件循环无法处理按键事件
3. 即使按下 ESC 键，也无法中断正在进行的请求

### 根本原因
prompt_toolkit 的按键绑定只在 `session.prompt_async()` 等待输入时生效。当执行 `await ask_agent()` 时，prompt 会话已结束，ESC 键绑定不再被处理。

## 解决方案

采用双层线程架构：

### 1. LLM 客户端层 (agent.py)

**ThreadPoolExecutor 执行 HTTP 请求**

```python
class OpenAICompatibleClient(LLMClient):
    def __init__(self, ...):
        self._cancel_event = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _do_request(self, url: str, payload: dict) -> str:
        """实际执行HTTP请求的内部方法（在线程中运行）"""
        response = requests.post(url, headers=self.headers, json=payload, timeout=300)
        # ... 处理响应

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # 在线程池中执行请求
        future = self._executor.submit(self._do_request, url, payload)

        # 轮询取消事件和请求完成
        while not future.done():
            if self._cancel_event.is_set():
                future.cancel()
                raise Exception("请求已被取消")
            time.sleep(0.05)  # 短暂休眠避免CPU占用过高
```

**关键点**：
- HTTP 请求在独立线程中执行
- 主线程定期检查 `_cancel_event`
- 一旦检测到取消信号，立即取消 Future 并抛出异常

### 2. REPL 交互层 (troopy.py)

**原始终端模式监听 ESC 键**

```python
class Troopy:
    def _start_esc_listener(self):
        """启动ESC键监听线程"""
        def listen_for_esc():
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())

            while self.is_processing:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)
                    if ch == '\x1b':  # ESC键
                        self._cancel_event.set()
                        TroopyMgr.instance().current_agent.cancel_request()
                        break

            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

        self._listener_thread = threading.Thread(target=listen_for_esc, daemon=True)
        self._listener_thread.start()

    async def ask_agent(self, text: str) -> str:
        self.is_processing = True
        self._start_esc_listener()  # 启动ESC监听线程
        try:
            # ... 执行请求
        finally:
            self._stop_esc_listener()  # 停止ESC监听线程
```

**关键点**：
- 使用 `termios` 和 `tty` 进入原始模式读取输入
- `select` 系统调用实现非阻塞检测
- 守护线程避免阻止程序退出

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     Troopy REPL 主线程                        │
│  ┌─────────────┐      ┌──────────────┐                    │
│  │ PromptSession│─────>│ process_input │                    │
│  └─────────────┘      └──────┬───────┘                    │
│                              │                               │
│                              v                               │
│                        ┌─────────────┐                      │
│                        │  ask_agent  │                      │
│                        └──────┬──────┘                      │
│                               │                              │
└───────────────────────────────┼──────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
         v                      v                      v
┌──────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ ESC监听线程       │   │ Executor线程池   │   │ LLM客户端线程   │
│ (原始终端模式)    │   │ (run_in_executor)│   │ (HTTP请求)      │
│                  │   │                 │   │                 │
│ select(stdin)    │   │ send_message()  │   │ requests.post() │
│ 检测 ESC (0x1b)  │   │                 │   │                 │
│         │         │   │                 │   │                 │
│         v         │   │                 │   │                 │
│ cancel_request() ─┴───┴──────────────────┴──> set _cancel_event│
└──────────────────┘                                         │
                                                              │
                                                              v
                                                    ┌─────────────────┐
                                                    │ 取消HTTP请求     │
                                                    │ 抛出异常         │
                                                    └─────────────────┘
```

## 数据流

### 正常流程
```
用户输入 -> prompt_async返回 -> process_input -> ask_agent
    -> 启动ESC监听线程
    -> run_in_executor(send_message)
        -> chat() -> 提交到ThreadPoolExecutor
            -> _do_request() -> requests.post() [阻塞在线程中]
    -> 轮询检查future.done()
    -> future.result() -> 返回响应
    -> 停止ESC监听线程
```

### 取消流程
```
用户按ESC -> ESC监听线程检测到'\x1b'
    -> cancel_request() -> _cancel_event.set()
    -> chat()中的while循环检测到
        -> future.cancel()
        -> raise Exception("请求已被取消")
    -> ask_agent捕获异常
        -> 清理对话历史中的用户消息
        -> 显示取消提示
    -> 停止ESC监听线程
```

## 关键技术点

### 1. 原始终端模式 (Raw Mode)
```python
old_settings = termios.tcgetattr(sys.stdin)
tty.setraw(sys.stdin.fileno())
# ... 读取输入
termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
```
- 禁用行缓冲和回显
- 立即读取单个字符
- 需要正确恢复设置避免终端混乱

### 2. 非阻塞 I/O
```python
if select.select([sys.stdin], [], [], 0.1)[0]:
    ch = sys.stdin.read(1)
```
- 超时 0.1 秒避免占用全部 CPU
- 只在有数据时才读取

### 3. 线程同步
```python
self._cancel_event = threading.Event()
```
- 跨线程通信的取消信号
- 线程安全的设置和检查

## 局限性和注意事项

### 1. HTTP 层取消限制
`future.cancel()` 只能取消尚未开始或正在等待的任务。如果 `requests.post()` 已经建立连接并等待响应：
- Python 线程层面的 `future.cancel()` 不会立即停止底层网络请求
- 实际网络请求可能在后台继续直到超时或完成

### 2. 终端兼容性
- `termios` 模块仅适用于 Unix-like 系统 (Linux, macOS)
- Windows 需要使用 `msvcrt` 或其他替代方案

### 3. 资源清理
- 必须确保终端设置在异常情况下也能恢复
- 监听线程使用 `daemon=True` 避免阻止程序退出

## 未来改进方向

1. **真正的 HTTP 取消**：使用支持取消的 HTTP 客户端（如 `httpx` 的异步版本）
2. **跨平台支持**：添加 Windows 平台的实现
3. **更优雅的 UI**：在处理期间显示可取消的进度指示器
4. **超时机制**：添加自动超时取消，避免无限等待

## 相关文件

- `src/troopy/agent.py` - LLM 客户端实现
- `src/troopy/troopy.py` - REPL 交互界面
- `CLAUDE.md` - 项目总览文档
