# -*- coding: utf-8 -*-
"""Flask 应用：认证、设置、仪表盘、操作记录、系统日志"""
import os
import re
import json
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote

import requests
from flask import Flask, request, jsonify, redirect, send_from_directory, abort, g
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
            "SELECT u.id, u.username, u.avatar, u.role, u.wecom_userid "
            "FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token = ? AND s.expires_at > ?", (token, D.now_str()), one=True)
        return row

    def is_admin():
        u = current_user()
        return bool(u) and u["role"] == "admin"

    def guest_mode():
        """访客模式三档：off / readonly / add"""
        v = D.get_setting("guest_mode")
        return v if v in ("readonly", "add") else "off"

    def can_read():
        return bool(current_user()) or guest_mode() != "off"

    def can_add():
        return bool(current_user()) or guest_mode() == "add"

    def req_user_name():
        u = current_user()
        return u["username"] if u else "访客"

    def login_required(f):
        @wraps(f)
        def w(*a, **kw):
            if not current_user():
                return jsonify(ok=False, message="请先登录"), 401
            return f(*a, **kw)
        return w

    def admin_required(f):
        @wraps(f)
        def w(*a, **kw):
            if not is_admin():
                return jsonify(ok=False, message="需要管理员权限"), 401
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
        g.current_user = current_user
        g.is_admin = is_admin
        g.can_read = can_read
        g.can_add = can_add
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
            "role": user["role"] or "user"})

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
        gm = settings["guest_mode"]
        if gm not in ("readonly", "add"):
            gm = "off"
        # 企微 OAuth 是否已配置齐全（corpid + secret + agentid）
        wecom = bool((settings.get("notify_corpid") or "").strip()
                     and (settings.get("notify_secret") or "").strip()
                     and (settings.get("notify_agentid") or "").strip())
        return jsonify(
            ok=True,
            authed=bool(u),
            guest_mode=gm,
            wecom_login=wecom,
            user={"id": u["id"], "username": u["username"],
                  "avatar": u["avatar"], "role": u["role"] or "user",
                  "wecom": bool(u["wecom_userid"])} if u else None,
            site={
                "name": names["full"],
                "subtitle": names["subtitle"],
                "org": names["org"],
                "version": D.VERSION,
                "changelog": D.CHANGELOG,
                "github": D.GITHUB_URL,
                "author": D.AUTHOR,
            })

    # ---------- 企业微信 OAuth 登录 ----------
    # state 短期缓存（单进程 waitress，进程内存即可）
    _oauth_states = {}

    @app.get("/api/auth/wecom/login")
    def wecom_login():
        s = D.get_settings()
        corpid = (s.get("notify_corpid") or "").strip()
        secret = (s.get("notify_secret") or "").strip()
        agentid = (s.get("notify_agentid") or "").strip()
        if not (corpid and secret and agentid):
            return redirect("/login?wecom_err=" + quote("未配置企业微信应用，请先在系统设置-微信通知中填写"))
        redirect_uri = request.host_url.rstrip("/") + "/api/auth/wecom/callback"
        state = secrets.token_hex(8)
        _oauth_states[state] = time.time()
        ua = (request.headers.get("User-Agent") or "").lower()
        if "wxwork" in ua:
            # 企微客户端内：网页授权免密登录
            url = ("https://open.weixin.qq.com/connect/oauth2/authorize"
                   f"?appid={corpid}&redirect_uri={quote(redirect_uri, safe='')}"
                   f"&response_type=code&scope=snsapi_base&agentid={agentid}"
                   f"&state={state}#wechat_redirect")
        else:
            # PC 浏览器：企业微信扫码登录
            url = ("https://login.work.weixin.qq.com/wwlogin/sso/login"
                   f"?login_type=CorpApp&appid={corpid}&agentid={agentid}"
                   f"&redirect_uri={quote(redirect_uri, safe='')}&state={state}")
        return redirect(url)

    @app.get("/api/auth/wecom/callback")
    def wecom_callback():
        code = request.args.get("code") or ""
        state = request.args.get("state") or ""
        ts = _oauth_states.pop(state, None)
        if not code or ts is None or time.time() - ts > 600:
            return redirect("/login?wecom_err=" + quote("登录会话已过期，请重新发起企业微信登录"))
        s = D.get_settings()
        corpid = (s.get("notify_corpid") or "").strip()
        secret = (s.get("notify_secret") or "").strip()
        try:
            from .notify import _wecom_token
            token = _wecom_token(corpid, secret)
            r = requests.get("https://qyapi.weixin.qq.com/cgi-bin/auth/getuserinfo",
                             params={"access_token": token, "code": code}, timeout=8)
            j = r.json()
            userid = str(j.get("userid") or j.get("UserID") or "").strip()
            if j.get("errcode") not in (0, None) or not userid:
                raise RuntimeError(f"{j.get('errcode')}: {j.get('errmsg')}")
        except Exception as e:
            D.sys_log("ERROR", "AUTH", f"企业微信登录失败: {e}")
            return redirect("/login?wecom_err=" + quote("企业微信登录失败，请稍后重试"))
        # 查找用户：先按企微 ID，再按同名非管理员账号绑定，否则自动创建普通用户
        user = D.query("SELECT * FROM users WHERE wecom_userid=?", (userid,), one=True)
        if not user:
            user = D.query(
                "SELECT * FROM users WHERE username=? AND role<>'admin'", (userid,), one=True)
            if user:
                D.execute("UPDATE users SET wecom_userid=? WHERE id=?", (userid, user["id"]))
            else:
                uid = D.execute(
                    "INSERT INTO users(username, password_hash, avatar, role, wecom_userid, created_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (userid, generate_password_hash(secrets.token_hex(16)), "",
                     "user", userid, D.now_str()))
                user = D.query("SELECT * FROM users WHERE id=?", (uid,), one=True)
                D.sys_log("INFO", "AUTH", f"企业微信登录自动创建用户: {userid}")
        token = D.create_session(user["id"])
        D.log_op(user["username"], "login", detail={"方式": "企业微信"})
        return redirect("/?wecom_token=" + token)

    # ---------- 用户管理 ----------
    def _admin_count():
        return D.query("SELECT COUNT(*) c FROM users WHERE role='admin'",
                       one=True)["c"]

    @app.get("/api/users")
    @admin_required
    def list_users():
        rows = D.query(
            "SELECT id, username, avatar, role, wecom_userid, created_at "
            "FROM users ORDER BY id")
        return jsonify(ok=True, users=rows)

    @app.post("/api/users")
    @admin_required
    def create_user():
        body = request.get_json(force=True, silent=True) or {}
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        role = body.get("role") if body.get("role") in ("admin", "user") else "user"
        if not username or len(username) > 40:
            return jsonify(ok=False, message="请输入合法用户名（40 字以内）"), 400
        if len(password) < 4:
            return jsonify(ok=False, message="初始密码至少 4 位"), 400
        if D.query("SELECT id FROM users WHERE username=?", (username,), one=True):
            return jsonify(ok=False, message="用户名已存在"), 400
        D.execute(
            "INSERT INTO users(username, password_hash, avatar, role, created_at) VALUES(?,?,?,?,?)",
            (username, generate_password_hash(password), "", role, D.now_str()))
        D.log_op(current_user()["username"], "user_create", target=username,
                 detail={"角色": role})
        return jsonify(ok=True, message="用户已创建")

    @app.put("/api/users/<int:uid>")
    @admin_required
    def update_user(uid):
        me = current_user()
        target = D.query("SELECT * FROM users WHERE id=?", (uid,), one=True)
        if not target:
            return jsonify(ok=False, message="用户不存在"), 404
        body = request.get_json(force=True, silent=True) or {}
        detail = {}
        role = body.get("role")
        if role is not None:
            if role not in ("admin", "user"):
                return jsonify(ok=False, message="角色不合法"), 400
            if uid == me["id"] and role != "admin":
                return jsonify(ok=False, message="不能取消自己的管理员角色"), 400
            if target["role"] == "admin" and role == "user" and _admin_count() <= 1:
                return jsonify(ok=False, message="系统至少保留一名管理员"), 400
            D.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
            detail["角色"] = "管理员" if role == "admin" else "普通用户"
        password = body.get("password")
        if password:
            if len(password) < 4:
                return jsonify(ok=False, message="密码至少 4 位"), 400
            D.execute("UPDATE users SET password_hash=? WHERE id=?",
                      (generate_password_hash(password), uid))
            detail["重置密码"] = "是"
        if not detail:
            return jsonify(ok=False, message="无变更"), 400
        D.log_op(me["username"], "user_update", target=target["username"],
                 detail=detail)
        return jsonify(ok=True, message="已保存")

    @app.delete("/api/users/<int:uid>")
    @admin_required
    def delete_user(uid):
        me = current_user()
        if uid == me["id"]:
            return jsonify(ok=False, message="不能删除当前登录账号"), 400
        target = D.query("SELECT * FROM users WHERE id=?", (uid,), one=True)
        if not target:
            return jsonify(ok=False, message="用户不存在"), 404
        if target["role"] == "admin" and _admin_count() <= 1:
            return jsonify(ok=False, message="系统至少保留一名管理员"), 400
        D.execute("DELETE FROM users WHERE id=?", (uid,))
        D.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
        D.log_op(me["username"], "user_delete", target=target["username"])
        return jsonify(ok=True, message="用户已删除")

    @app.post("/api/auth/password")
    @login_required
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
        D.sys_log("INFO", "AUTH", f"用户 {u['username']} 修改了登录密码")
        return jsonify(ok=True, message="密码修改成功，请重新登录")

    @app.post("/api/auth/avatar")
    @login_required
    def upload_avatar():
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify(ok=False, message="未选择文件"), 400
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            return jsonify(ok=False, message="仅支持图片格式"), 400
        u = current_user()
        name = f"u{u['id']}_{int(datetime.now().timestamp())}{ext}"
        os.makedirs(D.AVATAR_DIR, exist_ok=True)
        f.save(os.path.join(D.AVATAR_DIR, name))
        # 清理该用户旧头像
        prefix = f"u{u['id']}_"
        for old in os.listdir(D.AVATAR_DIR):
            if old.startswith(prefix) and old != name:
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

    # ---------- 外观（公开接口：访客也需读取表格边框开关） ----------
    @app.get("/api/appearance")
    def appearance():
        return jsonify(ok=True, vborder=D.get_setting("table_vborder") == "1")

    # ---------- 仪表盘 ----------
    @app.get("/api/dashboard")
    @read_required
    def dashboard():
        tables = D.query("SELECT id, name, is_system FROM tables ORDER BY id")
        counts = {r["table_id"]: r["c"] for r in D.query(
            "SELECT table_id, COUNT(*) c FROM records GROUP BY table_id")}
        total = sum(counts.values())

        def day_count(days):
            start = (D.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
            row = D.query("SELECT COUNT(*) c FROM records WHERE created_at >= ?",
                          (start,), one=True)
            return row["c"]

        growth = []
        today = D.now().replace(hour=0, minute=0, second=0, microsecond=0)
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

        # 申请人 / 工程项目排行
        counter = {}
        proj_counter = {}
        for r in D.query("SELECT data FROM records"):
            data = json.loads(r["data"])
            name = str(data.get("applicant") or "").strip()
            if name:
                counter[name] = counter.get(name, 0) + 1
            proj = str(data.get("project") or "").strip()
            if proj:
                proj_counter[proj] = proj_counter.get(proj, 0) + 1
        ranking = sorted(counter.items(), key=lambda x: -x[1])[:10]
        project_ranking = sorted(proj_counter.items(), key=lambda x: -x[1])[:10]

        ops_total = D.query("SELECT COUNT(*) c FROM ops", one=True)["c"]
        return jsonify(ok=True, total=total, today=day_count(0), week=day_count(6),
                       ops_total=ops_total,
                       by_table=[{"id": t["id"], "name": t["name"],
                                  "count": counts.get(t["id"], 0)} for t in tables],
                       growth=growth,
                       recent=[dict(r, data=json.loads(r["data"])) for r in recent],
                       ranking=[{"name": k, "count": v} for k, v in ranking],
                       project_ranking=[{"name": k, "count": v} for k, v in project_ranking])

    @app.get("/api/dashboard/calendar")
    @read_required
    def dash_calendar():
        """按月返回每日新增数据量（热力图日历用）"""
        month = (request.args.get("month") or
                 D.now().strftime("%Y-%m")).strip()
        if not re.match(r"^\d{4}-\d{2}$", month):
            return jsonify(ok=False, message="月份格式应为 YYYY-MM"), 400
        rows = D.query(
            "SELECT substr(created_at, 1, 10) d, COUNT(*) c FROM records "
            "WHERE created_at LIKE ? GROUP BY substr(created_at, 1, 10)",
            (month + "%",))
        return jsonify(ok=True, month=month,
                       days={r["d"]: r["c"] for r in rows})

    @app.get("/api/dashboard/day")
    @read_required
    def dash_day():
        """某天新增 / 修改的记录列表（日历点击弹窗用）"""
        date = (request.args.get("date") or
                D.now().strftime("%Y-%m-%d")).strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            return jsonify(ok=False, message="日期格式应为 YYYY-MM-DD"), 400
        rows = D.query(
            "SELECT r.id, r.table_id, r.data, r.created_at, r.updated_at, t.name table_name "
            "FROM records r JOIN tables t ON t.id = r.table_id "
            "WHERE r.created_at LIKE ? OR r.updated_at LIKE ? "
            "ORDER BY r.id DESC LIMIT 500",
            (date + "%", date + "%"))
        items = []
        for r in rows:
            try:
                data = json.loads(r["data"])
            except Exception:
                data = {}
            items.append(dict(r, data=data,
                              kind="add" if (r["created_at"] or "").startswith(date)
                              else "update"))
        return jsonify(ok=True, date=date, items=items)

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

    # ---------- 通知字体（图文封面自定义字体） ----------
    FONT_DIR = os.path.join(D.UPLOAD_DIR, "fonts")
    FONT_EXTS = (".ttf", ".otf", ".ttc")

    def _list_fonts():
        os.makedirs(FONT_DIR, exist_ok=True)
        items = []
        for fn in os.listdir(FONT_DIR):
            if os.path.splitext(fn)[1].lower() in FONT_EXTS:
                items.append({"name": fn,
                              "size": os.stat(os.path.join(FONT_DIR, fn)).st_size})
        items.sort(key=lambda x: x["name"])
        return items

    @app.get("/api/notify/fonts")
    @admin_required
    def list_fonts():
        return jsonify(ok=True, fonts=_list_fonts(),
                       current=D.get_setting("notify_font"))

    @app.post("/api/notify/fonts")
    @admin_required
    def upload_font():
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify(ok=False, message="未选择文件"), 400
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in FONT_EXTS:
            return jsonify(ok=False, message="仅支持 TTF / OTF / TTC 字体文件"), 400
        # 仅取文件名防路径穿越（保留中文名，不用 secure_filename）
        name = os.path.basename(f.filename)
        os.makedirs(FONT_DIR, exist_ok=True)
        f.save(os.path.join(FONT_DIR, name))
        D.log_op(current_user()["username"], "font_upload", target=name)
        D.sys_log("INFO", "NOTIFY", f"上传通知字体: {name}")
        return jsonify(ok=True, name=name)

    @app.delete("/api/notify/fonts/<name>")
    @admin_required
    def delete_font(name):
        fn = os.path.basename(name)
        p = os.path.join(FONT_DIR, fn)
        if os.path.splitext(fn)[1].lower() not in FONT_EXTS or not os.path.isfile(p):
            return jsonify(ok=False, message="字体不存在"), 404
        os.remove(p)
        if D.get_setting("notify_font") == fn:
            D.set_setting("notify_font", "")
        D.log_op(current_user()["username"], "font_delete", target=fn)
        D.sys_log("INFO", "NOTIFY", f"删除通知字体: {fn}")
        return jsonify(ok=True)

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

    # ---------- 数据备份 ----------
    BACKUP_DIR = os.path.join(D.DATA_DIR, "backups")
    BACKUP_KEEP = 10

    def _list_backups():
        os.makedirs(BACKUP_DIR, exist_ok=True)
        items = []
        for fn in os.listdir(BACKUP_DIR):
            if not (fn.startswith("drawcode-backup-") and fn.endswith(".db")):
                continue
            st = os.stat(os.path.join(BACKUP_DIR, fn))
            items.append({
                "name": fn, "size": st.st_size, "_ts": st.st_mtime,
                "created_at": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")})
        items.sort(key=lambda x: x["_ts"], reverse=True)
        return items

    def _safe_backup_name(name):
        fn = os.path.basename(str(name or ""))
        if fn.startswith("drawcode-backup-") and fn.endswith(".db") \
                and os.path.isfile(os.path.join(BACKUP_DIR, fn)):
            return fn
        return None

    def _create_backup(reason="manual", user="系统"):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        fname = "drawcode-backup-%s.db" % D.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(BACKUP_DIR, fname)
        src = sqlite3.connect(D.DB_PATH)
        dst = sqlite3.connect(dest)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        # 最多保留 10 个，超出删除最旧
        for old in _list_backups()[BACKUP_KEEP:]:
            try:
                os.remove(os.path.join(BACKUP_DIR, old["name"]))
            except OSError:
                pass
        D.log_op(user, "backup", target=fname, detail={"原因": reason})
        D.sys_log("INFO", "BACKUP", "数据备份完成：%s（%s）" % (fname, reason))
        return fname

    @app.get("/api/backups")
    @admin_required
    def list_backups():
        items = [{k: v for k, v in it.items() if k != "_ts"} for it in _list_backups()]
        return jsonify(ok=True, items=items, enabled=D.get_setting("backup_enabled") == "1")

    @app.post("/api/backups")
    @admin_required
    def create_backup():
        fname = _create_backup("manual", g.req_user_name())
        return jsonify(ok=True, message="备份完成", name=fname)

    @app.delete("/api/backups/<name>")
    @admin_required
    def delete_backup(name):
        fn = _safe_backup_name(name)
        if not fn:
            return jsonify(ok=False, message="备份不存在"), 404
        os.remove(os.path.join(BACKUP_DIR, fn))
        D.log_op(g.req_user_name(), "backup_delete", target=fn)
        D.sys_log("INFO", "BACKUP", "备份已删除：" + fn)
        return jsonify(ok=True, message="已删除")

    @app.get("/api/backups/<name>/download")
    @admin_required
    def download_backup(name):
        fn = _safe_backup_name(name)
        if not fn:
            return jsonify(ok=False, message="备份不存在"), 404
        return send_from_directory(BACKUP_DIR, fn, as_attachment=True, download_name=fn)

    @app.post("/api/backups/restore")
    @admin_required
    def restore_backup():
        body = request.get_json(force=True, silent=True) or {}
        fn = _safe_backup_name(body.get("name"))
        if not fn:
            return jsonify(ok=False, message="备份不存在"), 404
        # 记录当前有效会话，恢复后回填（若用户仍存在），避免操作者被立即登出
        live = D.query("SELECT * FROM sessions WHERE expires_at > ?", (D.now_str(),))
        src = sqlite3.connect(os.path.join(BACKUP_DIR, fn))
        dst = sqlite3.connect(D.DB_PATH)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        try:
            for s in live:
                if D.query("SELECT id FROM users WHERE id=?", (s["user_id"],), one=True):
                    D.execute(
                        "INSERT OR IGNORE INTO sessions(token,user_id,created_at,expires_at) "
                        "VALUES(?,?,?,?)",
                        (s["token"], s["user_id"], s["created_at"], s["expires_at"]))
        except Exception:
            pass
        D.log_op(g.req_user_name(), "backup_restore", target=fn)
        D.sys_log("WARN", "BACKUP", "已从备份恢复数据：" + fn)
        return jsonify(ok=True, message="恢复完成")

    # 自动备份线程：每半小时检查一次，最新备份超过 24 小时且开关开启时自动备份
    def _backup_worker():
        import time
        time.sleep(120)
        while True:
            try:
                if D.get_setting("backup_enabled") == "1":
                    items = _list_backups()
                    if not items or (time.time() - items[0]["_ts"]) >= 24 * 3600:
                        _create_backup("auto")
            except Exception as e:
                D.sys_log("ERROR", "BACKUP", "自动备份失败: %s" % e)
            time.sleep(1800)

    threading.Thread(target=_backup_worker, daemon=True).start()

    # ---------- 日志自动清理线程 ----------
    def _log_cleaner():
        import time
        while True:
            try:
                if D.get_setting("log_auto_clear") == "1":
                    days = int(D.get_setting("log_retention_days", "30") or 30)
                    deadline = (D.now() - timedelta(days=days)).strftime(
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
