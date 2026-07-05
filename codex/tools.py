import os
import subprocess

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

def execute_command(cmd: str) -> str:
    """
    在当前电脑终端执行系统命令
    ⚠️ 注意：这是一个高危操作，但既然是本地私人管家，我们就给它最高权限。
    """
    try:
        # 设定 15 秒超时，防止脚本卡死
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return result.stdout.strip() or "命令执行成功，无输出内容。"
        else:
            return f"命令执行失败 (退出码 {result.returncode}):\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return f"命令执行超时 (15秒)。"
    except Exception as e:
        return f"执行命令时发生异常：{str(e)}"