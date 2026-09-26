# -*- coding: utf-8 -*-
"""DrawCode 智能图号系统 - 启动入口"""
import os

from backend.app import create_app
from backend import db as D


def _hush_waitress_socket_noise():
    """过滤 waitress 因客户端提前断连刷出的 Socket error 堆栈（无害噪音）。

    客户端取消下载/关闭页面时内核写响应失败，waitress 会记录
    TimeoutError / ConnectionError 堆栈并自动关闭该 channel，属正常行为。
    此处把这类记录改为单行 WARN 提示，其余 waitress 日志照常输出。"""
    import logging

    class _Pretty(logging.Filter):
        NOISE = (TimeoutError, ConnectionError, BrokenPipeError)

        def filter(self, rec):
            if rec.exc_info and rec.exc_info[0] and issubclass(rec.exc_info[0], self.NOISE):
                print(f"[waitress] 客户端提前断开连接（已自动回收，无影响）: {rec.getMessage()}")
                return False
            if "socket error" in rec.getMessage().lower():
                print(f"[waitress] 客户端连接异常（已自动回收，无影响）: {rec.getMessage()}")
                return False
            return True

    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s"))
    h.addFilter(_Pretty())
    lg = logging.getLogger("waitress")
    lg.handlers.clear()
    lg.addHandler(h)
    lg.propagate = False


def main():
    app = create_app()
    port = int(os.environ.get("DRAWCODE_PORT", "9862"))
    host = os.environ.get("DRAWCODE_HOST", "0.0.0.0")
    print(f"* DrawCode 启动于 http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}")
    try:
        from waitress import serve
        _hush_waitress_socket_noise()
        serve(app, host=host, port=port, threads=12)
    except ImportError:
        app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
