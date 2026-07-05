"""任务编排引擎启动入口"""

import os
import sys
from pathlib import Path

import uvicorn


def _load_dotenv() -> None:
    """自动加载项目根目录下的 .env 文件"""
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("\"'")
            if key not in os.environ:
                os.environ[key] = value


def main():
    _load_dotenv()
    print("任务编排引擎启动中...")
    print("Swagger 文档: http://localhost:8000/docs")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()
