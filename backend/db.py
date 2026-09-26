# -*- coding: utf-8 -*-
"""数据库初始化与通用工具"""
import os
import json
import sqlite3
import threading
import secrets
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash

DATA_DIR = os.environ.get("DRAWCODE_DATA_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "drawcode.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
AVATAR_DIR = os.path.join(UPLOAD_DIR, "avatars")

_write_lock = threading.Lock()

# 时区：Docker 容器默认 UTC（比北京时间少 8 小时），显式按东八区取时间，
# 可用环境变量 DRAWCODE_TZ 覆盖；时区库不可用时回退系统本地时间
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(os.environ.get("DRAWCODE_TZ") or "Asia/Shanghai")
except Exception:
    _TZ = None


def now():
    """当前时间（默认东八区）"""
    return datetime.now(_TZ)

VERSION = "1.3.2"
GITHUB_URL = "https://github.com/xushier/DrawCode"
AUTHOR = "段松博"

CHANGELOG = [
    {
        "version": "1.3.2",
        "date": "2026-09-26",
        "items": [
            "微信通知：操作人字段标签与其它字段对齐",
        ],
    },
    {
        "version": "1.3.1",
        "date": "2026-09-26",
        "items": [
            "修复 Docker 内时区为 UTC 导致封面时间、日志时间比北京时间少 8 小时的问题",
        ],
    },
    {
        "version": "1.3.0",
        "date": "2026-09-26",
        "items": [
            "通知封面：背景渐变色调全随机，文字颜色随背景亮度自适应",
        ],
    },
    {
        "version": "1.2.0",
        "date": "2026-09-26",
        "items": [
            "通知封面：背景渐变每次随机，文字增大，版面更饱满",
            "优化后端日志：客户端断连噪音改为单行提示，不再刷堆栈",
        ],
    },
    {
        "version": "1.1.0",
        "date": "2026-09-26",
        "items": [
            "新增数据备份与恢复：每日自动备份、手动备份、下载、恢复，最多保留 10 份",
            "仪表盘新增数据日历（农历 / 节假日 / 当日动态）与工程项目排行榜",
            "操作记录与系统日志增加明细列展示，支持懒加载 / 分页切换",
            "微信通知：可上传自定义字体与封面图，封面改为暖色双栏布局并显示机构 Logo",
            "Docker 镜像支持 amd64 / arm64 双架构原生构建，标签含 latest 与版本号",
            "移动端适配与界面细节全面优化",
        ],
    },
    {
        "version": "1.0.0",
        "date": "2026-09-24",
        "items": [
            "图号申请与数据管理，支持三张内置申请表",
            "仪表盘：汇总统计、增长曲线、数据分布、申请人排行、最近数据",
            "图号数据：无限懒加载 / 分页、搜索、筛选、排序、自定义列",
            "操作记录时间线与系统日志，支持筛选、搜索与清理",
            "微信通知：群机器人 / 企业微信应用，文字与图文消息",
            "Excel 导入（附加式）与导出",
            "自定义扩展字段、字段类型、默认值、必填项与可选值",
            "以内置表为模板新建数据表，表名可修改",
            "六种诗意主题与暗色模式，移动端自适应",
        ],
    }
]

DEFAULT_SETTINGS = {
    "site_org": "智能装备研究院",
    "guest_mode": "0",
    "notify_enabled": "0",
    "notify_type": "robot",          # robot | wecom_app
    "notify_webhook": "",
    "notify_corpid": "",
    "notify_secret": "",
    "notify_agentid": "",
    "notify_touser": "@all",
    "notify_style": "text",          # text | image_text
    "notify_font": "",               # 自定义字体文件名（空 = 系统默认）
    "notify_on_add": "1",
    "notify_on_delete": "1",
    "log_auto_clear": "1",
    "log_retention_days": "30",
    "table_vborder": "0",
    "backup_enabled": "1",
}

SYSTEM_TABLES = [
    {
        "name": "融冰装置零件申请表",
        "fields": [
            ("sn", "序号", "number", 1),
            ("name", "名称", "select", 2),
            ("model", "型号", "select", 3),
            ("drawing_no", "图号", "select", 4),
            ("project", "工程/项目", "select", 5),
            ("applicant", "申请人", "select", 6),
            ("apply_time", "申请时间", "datetime", 7),
            ("remark", "备注", "text", 8),
            ("std_drawing", "标准图样", "text", 9),
        ],
    },
    {
        "name": "新设计产品图号申请表",
        "fields": [
            ("sn", "序号", "number", 1),
            ("name", "名称", "select", 2),
            ("model", "型号", "select", 3),
            ("drawing_no", "图号", "select", 4),
            ("project", "工程/项目", "select", 5),
            ("applicant", "申请人", "select", 6),
            ("apply_time", "申请时间", "datetime", 7),
            ("remark", "备注", "text", 8),
            ("std_drawing", "标准图样", "text", 9),
        ],
    },
    {
        "name": "装置图号申请表",
        "fields": [
            ("sn", "序号", "number", 1),
            ("name", "名称", "select", 2),
            ("model", "型号", "select", 3),
            ("drawing_no", "图号", "select", 4),
            ("project", "工程/项目", "select", 5),
            ("tower_no", "塔号", "select", 6),
            ("cross_arm", "横担", "select", 7),
            ("rod_length", "导电杆长度", "select", 8),
            ("applicant", "申请人", "select", 9),
            ("apply_time", "申请时间", "datetime", 10),
            ("remark", "备注", "text", 11),
        ],
    },
]


def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")


def site_names(org):
    """根据机构名生成系统名称：智能XXX图号系统（机构名以'智能'开头时自动去重）"""
    org = (org or "").strip() or "智能装备研究院"
    full = org + "图号系统" if org.startswith("智能") else "智能" + org + "图号系统"
    return {"full": full, "subtitle": org + "图号系统", "org": org}


def get_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def query(sql, args=(), one=False):
    conn = get_db()
    try:
        rows = conn.execute(sql, args).fetchall()
        if one:
            return dict(rows[0]) if rows else None
        return [dict(r) for r in rows]
    finally:
        conn.close()


def execute(sql, args=()):
    """带写锁的写入，返回 lastrowid"""
    with _write_lock:
        conn = get_db()
        try:
            cur = conn.execute(sql, args)
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def get_setting(key, default=None):
    row = query("SELECT value FROM settings WHERE key=?", (key,), one=True)
    if row is None:
        return DEFAULT_SETTINGS.get(key, default) if default is None else default
    return row["value"]


def get_settings():
    stored = {r["key"]: r["value"] for r in query("SELECT key, value FROM settings")}
    merged = dict(DEFAULT_SETTINGS)
    merged.update(stored)
    return merged


def set_setting(key, value):
    execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)))


def log_op(user, action, table_id=None, table_name="", target="", detail=None):
    execute(
        "INSERT INTO ops(user, action, table_id, table_name, target, detail, created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (user, action, table_id, table_name, target,
         json.dumps(detail, ensure_ascii=False) if detail else "", now_str()))


def sys_log(level, module, message, detail=""):
    try:
        execute(
            "INSERT INTO sys_logs(level, module, message, detail, created_at) VALUES(?,?,?,?,?)",
            (level, module, message, detail, now_str()))
    except Exception:
        pass


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(AVATAR_DIR, exist_ok=True)
    conn = get_db()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            avatar TEXT DEFAULT '',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions(
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            created_at TEXT,
            expires_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tables(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            is_system INTEGER DEFAULT 0,
            template TEXT DEFAULT '',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS fields(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            key TEXT,
            label TEXT,
            type TEXT,
            required INTEGER DEFAULT 0,
            default_value TEXT DEFAULT '',
            options TEXT DEFAULT '[]',
            is_system INTEGER DEFAULT 0,
            sort INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS records(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            data TEXT,
            created_at TEXT,
            updated_at TEXT,
            created_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_records_table ON records(table_id);
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_records_drawing
            ON records(table_id, json_extract(data, '$.drawing_no'))
            WHERE json_extract(data, '$.drawing_no') IS NOT NULL
              AND TRIM(json_extract(data, '$.drawing_no')) != '';
        CREATE TABLE IF NOT EXISTS ops(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT, action TEXT,
            table_id INTEGER, table_name TEXT, target TEXT, detail TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sys_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT, module TEXT, message TEXT, detail TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY, value TEXT
        );
        """)
        conn.commit()

        # 种子：管理员
        if not query("SELECT id FROM users LIMIT 1", one=True):
            conn.execute(
                "INSERT INTO users(username, password_hash, avatar, created_at) VALUES(?,?,?,?)",
                ("admin", generate_password_hash("admin"), "", now_str()))
            conn.commit()

        # 种子：三张内置表与字段
        if not query("SELECT id FROM tables LIMIT 1", one=True):
            for t in SYSTEM_TABLES:
                cur = conn.execute(
                    "INSERT INTO tables(name, is_system, template, created_at) VALUES(?,1,?,?)",
                    (t["name"], "", now_str()))
                tid = cur.lastrowid
                for key, label, ftype, sort in t["fields"]:
                    conn.execute(
                        "INSERT INTO fields(table_id, key, label, type, required, default_value,"
                        " options, is_system, sort) VALUES(?,?,?,?,0,'','[]',1,?)",
                        (tid, key, label, ftype, sort))
                conn.commit()
        conn.commit()
    finally:
        conn.close()


def create_session(user_id):
    token = secrets.token_hex(32)
    expires = (now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    execute(
        "INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES(?,?,?,?)",
        (token, user_id, now_str(), expires))
    return token


def check_password(username, password):
    row = query("SELECT * FROM users WHERE username=?", (username,), one=True)
    if row and check_password_hash(row["password_hash"], password):
        return row
    return None
