# -*- coding: utf-8 -*-
"""DrawCode 智能图号系统 - 启动入口"""
import os

from backend.app import create_app
from backend import db as D


def main():
    app = create_app()
    port = int(os.environ.get("DRAWCODE_PORT", "9862"))
    host = os.environ.get("DRAWCODE_HOST", "0.0.0.0")
    print(f"* DrawCode 启动于 http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}")
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=12)
    except ImportError:
        app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
