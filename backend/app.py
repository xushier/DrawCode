# -*- coding: utf-8 -*-
"""Flask 应用：认证、设置、仪表盘、操作记录、系统日志"""
import os
import re
import json
import threading
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, abort, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from . import db as D
from .tables import tables_bp

FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")


def create_app():
    D.init_db()

    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    app.json.ensure_ascii = False

    app.register_blueprint(tables_bp, url_prefix="/api")

    # ---------- 通用 ----------
    @app.errorhandler(404)
    def _nf(_e):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, message="接口不存在"), 404
        return send_index()

    @app.errorhandler(Exception)
    def _err(e):
        import traceback
        D.sys_log("ERROR", "SYSTEM", f"服务异常: {e}", traceback.format_exc()[-800:])
        return jsonify(ok=False, message=f"服务器内部错误: {e}"), 500

    @app.after_request
    def _no_store(resp):
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---------- 认证辅助 ----------
    def current_user():
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else auth
        if not token:
            return None
        row = D.query(
            "SELECT u.id, u.username, u.avatar FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token = ? "
            "AND s.expires_at > ?", (token, D.now_str()), one=True)
        return row

    def is_admin():
        u = current_user()
        return bool(u)

    def guest_ok():
        return D.get_setting("guest_mode") == "1"

    def can_read():
        return is_admin() or guest_ok()

    def req_user_name():
        u = current_user()
        return u["username"] if u else "访客"

    def admin_required(f):
        @wraps(f)
        def w(*a, **kw):
            if not is_admin():
                return jsonify(ok=False, message="需要管理员登录"), 401
            return f(*a, **kw)
        return w

    def read_required(f):
        @wraps(f)
        def w(*a, **kw):
            if not can_read():
                return jsonify(ok=False, message="请先登录"), 401
            return f(*a, **kw)
        return w

    @app.before_request
    def _inject_g():
        g.is_admin = is_admin
        g.can_read = can_read
        g.req_user_name = req_user_name

    # ---------- 认证 ----------
    @app.post("/api/auth/login")
    def login():
        body = request.get_json(force=True, silent=True) or {}
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        user = D.check_password(username, password)
        if not user:
            D.sys_log("WARN", "AUTH", f"登录失败: {username}")
            return jsonify(ok=False, message="账号或密码错误"), 401
        token = D.create_session(user["id"])
        D.log_op(username, "login")
        return jsonify(ok=True, token=token, user={
            "username": user["username"], "avatar": user["avatar"],
            "role": "admin"})

    @app.post("/api/auth/logout")
    def logout():
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else auth
        if token:
            D.execute("DELETE FROM sessions WHERE token=?", (token,))
        D.log_op(req_user_name(), "logout")
        return jsonify(ok=True)

    @app.get("/api/auth/status")
    def auth_status():
        settings = D.get_settings()
        names = D.site_names(settings["site_org"])
        u = current_user()
        return jsonify(
            ok=True,
            authed=bool(u),
            guest_mode=settings["guest_mode"] == "1",
            user={"username": u["username"], "avatar": u["avatar"],
                  "role": "admin"} if u else None,
            site={
                "name": names["full"],
                "subtitle": names["subtitle"],
                "org": names["org"],
                "version": D.VERSION,
                "changelog": D.CHANGELOG,
                "github": D.GITHUB_URL,
                "author": D.AUTHOR,
            })

    @app.post("/api/auth/password")
    @admin_required
    def change_password():
        body = request.get_json(force=True, silent=True) or {}
        old, new, confirm = body.get("old"), body.get("new"), body.get("confirm")
        if not new or len(new) < 4:
            return jsonify(ok=False, message="新密码至少 4 位"), 400
        if new != confirm:
            return jsonify(ok=False, message="两次输入的密码不一致"), 400
        u = current_user()
        row = D.query("SELECT * FROM users WHERE id=?", (u["id"],), one=True)
        if not check_password_hash(row["password_hash"], old or ""):
            return jsonify(ok=False, message="原密码错误"), 400
        D.execute("UPDATE users SET password_hash=? WHERE id=?",
                  (generate_password_hash(new), u["id"]))
        D.log_op(u["username"], "password_change")
        D.sys_log("INFO", "AUTH", "管理员修改了登录密码")
        return jsonify(ok=True, message="密码修改成功，请重新登录")

    @app.post("/api/auth/avatar")
    @admin_required
    def upload_avatar():
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify(ok=False, message="未选择文件"), 400
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            return jsonify(ok=False, message="仅支持图片格式"), 400
        u = current_user()
        name = f"admin_{int(datetime.now().timestamp())}{ext}"
        os.makedirs(D.AVATAR_DIR, exist_ok=True)
        f.save(os.path.join(D.AVATAR_DIR, name))
        # 清理旧头像
        for old in os.listdir(D.AVATAR_DIR):
            if old.startswith("admin_") and old != name:
                try:
                    os.remove(os.path.join(D.AVATAR_DIR, old))
                except OSError:
                    pass
        url = f"/uploads/avatars/{name}"
        D.execute("UPDATE users SET avatar=? WHERE id=?", (url, u["id"]))
        D.log_op(u["username"], "avatar_change")
        return jsonify(ok=True, avatar=url)

    # ---------- 设置 ----------
    @app.get("/api/settings")
    @admin_required
    def get_settings_api():
        return jsonify(ok=True, settings=D.get_settings())

    @app.put("/api/settings")
    @admin_required
    def put_settings():
        body = request.get_json(force=True, silent=True) or {}
        changed = []
        for k, v in (body or {}).items():
            if k in D.DEFAULT_SETTINGS:
                D.set_setting(k, v)
                changed.append(k)
        if "site_org" in changed or "guest_mode" in changed:
            D.log_op(current_user()["username"], "settings_update",
                     detail={"keys": changed})
        D.sys_log("INFO", "SETTINGS", f"更新设置: {', '.join(changed)}")
        return jsonify(ok=True)

    # ---------- 仪表盘 ----------
    @app.get("/api/dashboard")
    @read_required
    def dashboard():
        tables = D.query("SELECT id, name, is_system FROM tables ORDER BY id")
        counts = {r["table_id"]: r["c"] for r in D.query(
            "SELECT table_id, COUNT(*) c FROM records GROUP BY table_id")}
        total = sum(counts.values())

        def day_count(days):
            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
            row = D.query("SELECT COUNT(*) c FROM records WHERE created_at >= ?",
                          (start,), one=True)
            return row["c"]

        growth = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(29, -1, -1):
            d = today - timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            row = D.query("SELECT COUNT(*) c FROM records WHERE created_at LIKE ?",
                          (ds + "%",), one=True)
            growth.append({"date": ds, "count": row["c"]})

        recent = D.query(
            "SELECT r.id, r.table_id, r.data, r.created_at, t.name table_name "
            "FROM records r JOIN tables t ON t.id = r.table_id "
            "ORDER BY r.id DESC LIMIT 8")

        # 申请人排行
        counter = {}
        for r in D.query("SELECT data FROM records"):
            data = json.loads(r["data"])
            name = str(data.get("applicant") or "").strip()
            if name:
                counter[name] = counter.get(name, 0) + 1
        ranking = sorted(counter.items(), key=lambda x: -x[1])[:10]

        ops_total = D.query("SELECT COUNT(*) c FROM ops", one=True)["c"]
        return jsonify(ok=True, total=total, today=day_count(0), week=day_count(6),
                       ops_total=ops_total,
                       by_table=[{"id": t["id"], "name": t["name"],
                                  "count": counts.get(t["id"], 0)} for t in tables],
                       growth=growth,
                       recent=[dict(r, data=json.loads(r["data"])) for r in recent],
                       ranking=[{"name": k, "count": v} for k, v in ranking])

    # ---------- 操作记录 ----------
    @app.get("/api/ops")
    @admin_required
    def list_ops():
        cond, args = [], []
        kw = request.args.get("search", "").strip()
        if kw:
            cond.append("(user LIKE ? OR target LIKE ? OR table_name LIKE ? OR detail LIKE ?)")
            args += [f"%{kw}%"] * 4
        if request.args.get("action"):
            cond.append("action=?")
            args.append(request.args["action"])
        if request.args.get("table_id"):
            cond.append("table_id=?")
            args.append(request.args["table_id"])
        if request.args.get("user"):
            cond.append("user=?")
            args.append(request.args["user"])
        if request.args.get("start"):
            cond.append("created_at >= ?")
            args.append(request.args["start"])
        if request.args.get("end"):
            cond.append("created_at <= ?")
            args.append(request.args["end"] + " 23:59:59")
        where = ("WHERE " + " AND ".join(cond)) if cond else ""
        total = D.query(f"SELECT COUNT(*) c FROM ops {where}", tuple(args), one=True)["c"]
        page = max(1, int(request.args.get("page", 1)))
        size = min(200, max(1, int(request.args.get("page_size", 20))))
        rows = D.query(
            f"SELECT * FROM ops {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            tuple(args) + (size, (page - 1) * size))
        users = [r["user"] for r in D.query(
            "SELECT DISTINCT user FROM ops ORDER BY user")]
        actions = [r["action"] for r in D.query(
            "SELECT DISTINCT action FROM ops ORDER BY action")]
        return jsonify(ok=True, total=total, items=rows, page=page,
                       users=users, actions=actions)

    @app.delete("/api/ops")
    @admin_required
    def clear_ops():
        D.execute("DELETE FROM ops")
        D.log_op(current_user()["username"], "ops_clear")
        return jsonify(ok=True, message="操作记录已清空")

    # ---------- 系统日志 ----------
    @app.get("/api/syslogs")
    @admin_required
    def list_logs():
        cond, args = [], []
        kw = request.args.get("search", "").strip()
        if kw:
            cond.append("(message LIKE ? OR module LIKE ?)")
            args += [f"%{kw}%"] * 2
        if request.args.get("level"):
            cond.append("level=?")
            args.append(request.args["level"])
        if request.args.get("module"):
            cond.append("module=?")
            args.append(request.args["module"])
        if request.args.get("start"):
            cond.append("created_at >= ?")
            args.append(request.args["start"])
        if request.args.get("end"):
            cond.append("created_at <= ?")
            args.append(request.args["end"] + " 23:59:59")
        where = ("WHERE " + " AND ".join(cond)) if cond else ""
        total = D.query(f"SELECT COUNT(*) c FROM sys_logs {where}", tuple(args), one=True)["c"]
        page = max(1, int(request.args.get("page", 1)))
        size = min(200, max(1, int(request.args.get("page_size", 50))))
        rows = D.query(
            f"SELECT * FROM sys_logs {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            tuple(args) + (size, (page - 1) * size))
        return jsonify(ok=True, total=total, items=rows, page=page,
                       modules=sorted({r["module"] for r in
                                       D.query("SELECT DISTINCT module FROM sys_logs")}))

    @app.delete("/api/syslogs")
    @admin_required
    def clear_logs():
        D.execute("DELETE FROM sys_logs")
        D.log_op(current_user()["username"], "logs_clear")
        return jsonify(ok=True, message="系统日志已清空")

    # ---------- 通知 ----------
    @app.post("/api/notify/test")
    @admin_required
    def notify_test():
        from .notify import send_notification
        try:
            err = send_notification("test")
            if err:
                return jsonify(ok=False, message=err), 200
            return jsonify(ok=True, message="测试通知已发送")
        except Exception as e:
            return jsonify(ok=False, message=f"发送失败: {e}"), 200

    # ---------- 上传文件与前端 ----------
    @app.get("/uploads/<path:p>")
    def uploads(p):
        base = os.path.dirname(p)
        if base.startswith("..") or (os.path.sep in p and p.split(os.sep)[0] == ".."):
            abort(403)
        return send_from_directory(D.UPLOAD_DIR, p, max_age=3600)

    def send_index():
        index = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index):
            # HTML 禁用缓存，确保发版后浏览器总能拿到最新前端入口
            resp = send_from_directory(FRONTEND_DIST, "index.html", max_age=0)
            resp.headers["Cache-Control"] = "no-cache"
            return resp
        return "<h3>DrawCode</h3><p>前端未构建，请先执行 npm run build</p>", 200

    @app.get("/")
    def index():
        return send_index()

    @app.get("/<path:p>")
    def spa(p):
        if p.startswith("api/") or p.startswith("uploads/"):
            abort(404)
        full = os.path.normpath(os.path.join(FRONTEND_DIST, p))
        if full.startswith(FRONTEND_DIST) and os.path.isfile(full):
            return send_from_directory(FRONTEND_DIST, p)
        return send_index()

    # ---------- 日志自动清理线程 ----------
    def _log_cleaner():
        import time
        while True:
            try:
                if D.get_setting("log_auto_clear") == "1":
                    days = int(D.get_setting("log_retention_days", "30") or 30)
                    deadline = (datetime.now() - timedelta(days=days)).strftime(
                        "%Y-%m-%d %H:%M:%S")
                    D.execute("DELETE FROM sys_logs WHERE created_at < ?", (deadline,))
                # 清理过期会话
                D.execute("DELETE FROM sessions WHERE expires_at < ?", (D.now_str(),))
            except Exception:
                pass
            time.sleep(6 * 3600)

    threading.Thread(target=_log_cleaner, daemon=True).start()
    D.sys_log("INFO", "SYSTEM", f"DrawCode v{D.VERSION} 启动完成")
    return app
