import os
import subprocess
import asyncio

def read_file(filepath: str) -> str:
    """读取本地文件内容"""
    try:
        if not os.path.exists(filepath):
            return f"错误：文件 {filepath} 不存在"
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"读取文件时出错：{str(e)}"

def list_dir(path: str) -> str:
    """列出指定目录下的所有文件和文件夹"""
    try:
        if not os.path.exists(path):
            return f"错误：目录 {path} 不存在"
        items = os.listdir(path)
        return "\n".join(items) if items else "（空目录）"
    except Exception as e:
        return f"读取目录时出错：{str(e)}"

async def execute_command(cmd: str) -> str:
    """
    在当前电脑终端执行系统命令
    🔒 安全机制：执行前会在服务器终端弹出确认框，需要手动输入 yes 才会执行
    """
    # 在运行 python server.py 的那个黑框框里打印提示
    print(f"\n{'='*60}")
    print(f"🤖 AI 请求执行命令:")
    print(f"   {cmd}")
    print(f"{'='*60}")
    
    # 获取事件循环，在单独的线程里等待用户输入（不会卡死网页）
    loop = asyncio.get_event_loop()
    # 这里会暂停，等待你在终端输入 yes 或 直接回车
    confirm = await loop.run_in_executor(None, input, "👉 允许执行吗？(输入 yes 允许，直接回车拒绝): ")
    
    if confirm.lower() != 'yes':
        return "❌ 用户已拒绝执行该命令，命令未运行。"
    
    # ---------- 只有你输入了 yes，下面才会执行 ----------
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return result.stdout.strip() or "✅ 命令执行成功，无输出内容。"
        else:
            return f"❌ 命令执行失败 (退出码 {result.returncode}):\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return f"⏰ 命令执行超时 (15秒)。"
    except Exception as e:
        return f"💥 执行命令时发生异常：{str(e)}"
