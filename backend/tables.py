# -*- coding: utf-8 -*-
"""图号数据：表、字段、记录、导入导出"""
import json
import sqlite3
import re
from datetime import datetime
from flask import Blueprint, request, jsonify, g

from . import db as D

tables_bp = Blueprint("tables", __name__)

SELECT_TYPES = ("select", "multi_select", "radio", "checkbox")
FIELD_TYPES = ("text", "textarea", "number", "select", "multi_select",
               "radio", "checkbox", "switch", "date", "datetime")


# ---------------- 工具 ----------------

def get_table(tid):
    t = D.query("SELECT * FROM tables WHERE id=?", (tid,), one=True)
    if not t:
        return None
    t["fields"] = D.query(
        "SELECT * FROM fields WHERE table_id=? ORDER BY sort, id", (tid,))
    for f in t["fields"]:
        try:
            f["options"] = json.loads(f["options"] or "[]")
        except Exception:
            f["options"] = []
        f["required"] = bool(f["required"])
        f["is_system"] = bool(f["is_system"])
    return t


def field_map(table):
    return {f["key"]: f for f in table["fields"]}


def sort_key(v):
    """混合类型安全排序：数值类在前，空值在后"""
    if v is None or v == "":
        return (2, 0.0, "")
    s = str(v).strip()
    try:
        return (0, float(s), "")
    except ValueError:
        return (1, 0.0, s.lower())


def load_records(tid):
    rows = D.query(
        "SELECT id, table_id, data, created_at, updated_at, created_by "
        "FROM records WHERE table_id=? ORDER BY id DESC", (tid,))
    out = []
    for r in rows:
        try:
            r["data"] = json.loads(r["data"])
        except Exception:
            r["data"] = {}
        out.append(r)
    return out


def apply_query(records, table, args):
    """搜索 / 筛选 / 排序（内存中完成）"""
    fmap = field_map(table)
    kw = (args.get("search") or "").strip().lower()

    filters = {}
    try:
        filters = json.loads(args.get("filters") or "{}")
    except Exception:
        filters = {}

    result = []
    for r in records:
        data = r["data"]
        # 全局搜索
        if kw:
            hay = " ".join(
                str(data.get(k, "")) for k in fmap) + " " + r.get("created_at", "")
            if kw not in hay.lower():
                continue
        # 字段筛选
        ok = True
        for key, cond in (filters or {}).items():
            if not isinstance(cond, dict):
                continue
            op = cond.get("op")
            val = cond.get("value")
            target = data.get(key, "")
            tstr = str(target if target is not None else "")
            if op == "in":
                vals = [str(x) for x in (val or [])]
                if vals and tstr not in vals:
                    ok = False
                    break
            elif op == "like":
                if (val or "") and (val or "").lower() not in tstr.lower():
                    ok = False
                    break
            elif op == "eq":
                if val is not None and val != "" and tstr != str(val):
                    ok = False
                    break
            elif op == "range":
                lo, hi = (val or [None, None])
                lo, hi = str(lo or ""), str(hi or "")
                try:  # 数值范围
                    tv, lv, hv = float(tstr or 0), (float(lo) if lo else None), (float(hi) if hi else None)
                    if lv is not None and tv < lv:
                        ok = False
                        break
                    if hv is not None and tv > hv:
                        ok = False
                        break
                except ValueError:  # 字符串范围（日期/时间）
                    if lo and tstr < lo:
                        ok = False
                        break
                    if hi and tstr > hi + " 23:59:59":
                        ok = False
                        break
            elif op == "empty":
                # val 为 true：仅看空值；为 false：仅看非空值
                if val is True and tstr != "":
                    ok = False
                    break
                if val is False and tstr == "":
                    ok = False
                    break
        if ok:
            result.append(r)

    # 排序
    sort = args.get("sort", "sn")
    order = args.get("order", "desc")
    if sort == "id":
        result.sort(key=lambda r: r["id"], reverse=(order == "desc"))
    elif sort in fmap:
        result.sort(key=lambda r: sort_key(r["data"].get(sort)),
                    reverse=(order == "desc"))
    else:
        result.sort(key=lambda r: sort_key(r["data"].get("sn")))
    return result


def record_row(r, table=None):
    return {"id": r["id"], "table_id": r["table_id"], "data": r["data"],
            "created_at": r["created_at"], "updated_at": r["updated_at"],
            "created_by": r["created_by"]}


def merge_options(table, data, user=""):
    """下拉类字段新值自动加入可选值"""
    changed = False
    for f in table["fields"]:
        if f["type"] in SELECT_TYPES and f["key"] in data:
            vals = data[f["key"]]
            if f["type"] in ("multi_select", "checkbox"):
                vals = vals if isinstance(vals, list) else [vals]
            else:
                vals = [vals]
            opts = f["options"]
            new_opts = list(opts)
            for v in vals:
                v = str(v or "").strip()
                if v and v not in new_opts:
                    new_opts.append(v)
            if new_opts != opts:
                D.execute("UPDATE fields SET options=? WHERE id=?",
                          (json.dumps(new_opts, ensure_ascii=False), f["id"]))
                changed = True
    return changed


def build_create_data(table, raw, existing_records=None):
    """规范化新记录数据：自动序号、自动申请时间"""
    fmap = field_map(table)
    data = {}
    for k, v in (raw or {}).items():
        if k in fmap:
            data[k] = v
    # 自动序号
    if "sn" in fmap:
        sn = raw.get("sn")
        try:
            data["sn"] = int(sn) if sn not in (None, "",) else None
        except (TypeError, ValueError):
            data["sn"] = None
        if data["sn"] is None:
            mx = 0
            for r in (existing_records or load_records(table["id"])):
                try:
                    mx = max(mx, int(r["data"].get("sn") or 0))
                except (TypeError, ValueError):
                    pass
            data["sn"] = mx + 1
    # 申请时间：不填则自动
    if "apply_time" in fmap and not str(data.get("apply_time") or "").strip():
        data["apply_time"] = D.now_str()
    # 必填校验
    missing = [f["label"] for f in table["fields"]
               if f["required"] and not str(data.get(f["key"], "") or "").strip()
               and f["key"] != "sn"]
    if missing:
        return None, f"必填项未填写：{ '、'.join(missing) }"
    return data, None


def do_create_record(table, raw, user):
    """创建记录（含唯一图号约束处理），返回 (record|None, error_message)"""
    existing = load_records(table["id"])
    data, err = build_create_data(table, raw, existing)
    if err:
        return None, err
    now = D.now_str()
    try:
        rid = D.execute(
            "INSERT INTO records(table_id, data, created_at, updated_at, created_by) "
            "VALUES(?,?,?,?,?)",
            (table["id"], json.dumps(data, ensure_ascii=False), now, now, user))
    except sqlite3.IntegrityError:
        return None, f"图号「{data.get('drawing_no')}」已被申请使用，请更换图号或查看已有记录"
    merge_options(table, data, user)
    return {"id": rid, "table_id": table["id"], "data": data,
            "created_at": now, "updated_at": now, "created_by": user}, None


# ---------------- 表与字段 ----------------

@tables_bp.get("/tables")
def list_tables():
    if not g.can_read():
        return jsonify(ok=False, message="请先登录"), 401
    tables = D.query("SELECT * FROM tables ORDER BY id")
    counts = {r["table_id"]: r["c"] for r in D.query(
        "SELECT table_id, COUNT(*) c FROM records GROUP BY table_id")}
    for t in tables:
        t["count"] = counts.get(t["id"], 0)
        t["fields"] = D.query(
            "SELECT * FROM fields WHERE table_id=? ORDER BY sort, id", (t["id"],))
        for f in t["fields"]:
            try:
                f["options"] = json.loads(f["options"] or "[]")
            except Exception:
                f["options"] = []
            f["required"] = bool(f["required"])
            f["is_system"] = bool(f["is_system"])
    return jsonify(ok=True, tables=tables)


@tables_bp.post("/tables")
def create_table():
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    body = request.get_json(force=True, silent=True) or {}
    name = (body.get("name") or "").strip()
    template = body.get("template", "blank")
    if not name:
        return jsonify(ok=False, message="请填写表名"), 400
    if D.query("SELECT id FROM tables WHERE name=?", (name,), one=True):
        return jsonify(ok=False, message="表名已存在，请更换"), 400
    src = None
    if template in ("t1", "t2", "t3"):
        sys_tables = D.query(
            "SELECT id FROM tables WHERE is_system=1 ORDER BY id")
        idx = int(template[1]) - 1
        if idx < len(sys_tables):
            src = sys_tables[idx]["id"]
    tid = D.execute(
        "INSERT INTO tables(name, is_system, template, created_at) VALUES(?,0,?,?)",
        (name, template, D.now_str()))
    if src:
        for f in D.query("SELECT * FROM fields WHERE table_id=? ORDER BY sort, id", (src,)):
            D.execute(
                "INSERT INTO fields(table_id, key, label, type, required, default_value,"
                " options, is_system, sort) VALUES(?,?,?,?,?,?,?,?,?)",
                (tid, f["key"], f["label"], f["type"], f["required"],
                 f["default_value"], f["options"], 0, f["sort"]))
    D.log_op(g.req_user_name(), "table_create", tid, name,
             detail={"name": name, "template": template})
    D.sys_log("INFO", "TABLES", f"新建数据表: {name} (模板: {template})")
    return jsonify(ok=True, id=tid)


@tables_bp.route("/tables/<int:tid>", methods=["PUT", "DELETE"])
def manage_table(tid):
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    if request.method == "PUT":
        body = request.get_json(force=True, silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify(ok=False, message="请填写表名"), 400
        dup = D.query("SELECT id FROM tables WHERE name=? AND id<>?",
                      (name, tid), one=True)
        if dup:
            return jsonify(ok=False, message="表名已存在，请更换"), 400
        D.execute("UPDATE tables SET name=? WHERE id=?", (name, tid))
        D.log_op(g.req_user_name(), "table_rename", tid, name,
                 detail={"old": table["name"], "new": name})
        return jsonify(ok=True)
    # DELETE
    if table["is_system"]:
        return jsonify(ok=False, message="内置表不允许删除，仅可重命名"), 400
    D.execute("DELETE FROM records WHERE table_id=?", (tid,))
    D.execute("DELETE FROM fields WHERE table_id=?", (tid,))
    D.execute("DELETE FROM tables WHERE id=?", (tid,))
    D.log_op(g.req_user_name(), "table_delete", tid, table["name"],
             detail={"name": table["name"]})
    D.sys_log("WARN", "TABLES", f"删除数据表: {table['name']}（含全部数据）")
    return jsonify(ok=True)


@tables_bp.post("/tables/<int:tid>/fields")
def add_field(tid):
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    body = request.get_json(force=True, silent=True) or {}
    label = (body.get("label") or "").strip()
    ftype = body.get("type", "text")
    if not label:
        return jsonify(ok=False, message="请填写字段名称"), 400
    if ftype not in FIELD_TYPES:
        return jsonify(ok=False, message="字段类型不合法"), 400
    if any(f["label"] == label for f in table["fields"]):
        return jsonify(ok=False, message="字段名称重复"), 400
    n = 1
    keys = {f["key"] for f in table["fields"]}
    while f"f_{n}" in keys:
        n += 1
    sort = max([f["sort"] for f in table["fields"]], default=0) + 1
    opts = [str(o).strip() for o in (body.get("options") or [])
            if str(o).strip()]
    fid = D.execute(
        "INSERT INTO fields(table_id, key, label, type, required, default_value,"
        " options, is_system, sort) VALUES(?,?,?,?,?,?,?,0,?)",
        (tid, f"f_{n}", label, ftype, 1 if body.get("required") else 0,
         str(body.get("default_value") or ""), json.dumps(opts, ensure_ascii=False),
         sort))
    D.log_op(g.req_user_name(), "field_add", tid, table["name"],
             detail={"label": label, "type": ftype})
    return jsonify(ok=True, id=fid)


@tables_bp.route("/fields/<int:fid>", methods=["PUT", "DELETE"])
def manage_field(fid):
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    f = D.query("SELECT * FROM fields WHERE id=?", (fid,), one=True)
    if not f:
        return jsonify(ok=False, message="字段不存在"), 404
    table = get_table(f["table_id"])
    body = request.get_json(force=True, silent=True) or {}
    if request.method == "PUT":
        # 内置字段仅允许修改必填/默认值/可选值；自定义字段可改名称与类型
        required = 1 if body.get("required") else 0
        default_value = str(body.get("default_value") or "")
        options = json.dumps(
            [str(o).strip() for o in (body.get("options") or []) if str(o).strip()],
            ensure_ascii=False)
        if f["is_system"]:
            D.execute(
                "UPDATE fields SET required=?, default_value=?, options=? WHERE id=?",
                (required, default_value, options, fid))
        else:
            label = (body.get("label") or f["label"]).strip()
            ftype = body.get("type") or f["type"]
            if ftype not in FIELD_TYPES:
                return jsonify(ok=False, message="字段类型不合法"), 400
            D.execute(
                "UPDATE fields SET label=?, type=?, required=?, default_value=?,"
                " options=? WHERE id=?",
                (label, ftype, required, default_value, options, fid))
        D.log_op(g.req_user_name(), "field_update", f["table_id"],
                 table["name"], detail={"label": f["label"]})
        return jsonify(ok=True)
    # DELETE
    if f["is_system"]:
        return jsonify(ok=False, message="内置字段不允许删除"), 400
    D.execute("DELETE FROM fields WHERE id=?", (fid,))
    # 清理记录中的该字段数据
    for r in load_records(f["table_id"]):
        if f["key"] in r["data"]:
            r["data"].pop(f["key"])
            D.execute("UPDATE records SET data=?, updated_at=? WHERE id=?",
                      (json.dumps(r["data"], ensure_ascii=False), D.now_str(), r["id"]))
    D.log_op(g.req_user_name(), "field_delete", f["table_id"],
             table["name"], detail={"label": f["label"]})
    return jsonify(ok=True)


# ---------------- 可选值 ----------------

@tables_bp.get("/tables/<int:tid>/options")
def table_options(tid):
    if not g.can_read():
        return jsonify(ok=False, message="请先登录"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    records = load_records(tid)
    out = {}
    for f in table["fields"]:
        if f["type"] in ("select", "multi_select", "radio", "checkbox"):
            vals = list(f["options"])
            for r in records:
                v = r["data"].get(f["key"])
                items = v if isinstance(v, list) else [v]
                for it in items:
                    it = str(it or "").strip()
                    if it and it not in vals:
                        vals.append(it)
            out[f["key"]] = vals
        else:
            out[f["key"]] = None
    return jsonify(ok=True, options=out)


# ---------------- 记录 ----------------

@tables_bp.get("/tables/<int:tid>/records")
def list_records(tid):
    if not g.can_read():
        return jsonify(ok=False, message="请先登录"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    records = apply_query(load_records(tid), table, request.args)
    total = len(records)
    mode = request.args.get("mode", "lazy")
    page = max(1, int(request.args.get("page", 1)))
    size = min(500, max(1, int(request.args.get("page_size", 100 if mode == "page" else 50))))
    start = (page - 1) * size
    items = records[start:start + size]
    return jsonify(ok=True, total=total, page=page, page_size=size,
                   has_more=start + size < total,
                   items=[record_row(r) for r in items],
                   fields=table["fields"])


@tables_bp.post("/tables/<int:tid>/records")
def create_record(tid):
    if not g.can_add():
        return jsonify(ok=False, message="当前未开放申请权限，请先登录"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    body = request.get_json(force=True, silent=True) or {}
    user = g.req_user_name()
    data = body.get("data") or {}
    # 登录用户：申请人锁定为当前用户名；访客：保留下拉选择/自行输入的值
    u = g.current_user()
    if u and any(f["key"] == "applicant" for f in table["fields"]):
        data["applicant"] = u["username"]
    record, err = do_create_record(table, data, user)
    if err:
        return jsonify(ok=False, message=err), 409 if "已被申请使用" in err else 400
    D.log_op(user, "record_add", tid, table["name"],
             target=str(record["data"].get("drawing_no") or record["data"].get("name") or ""),
             detail={"data": record["data"]})
    # 通知（后台线程，不阻塞响应）
    if D.get_setting("notify_enabled") == "1" and D.get_setting("notify_on_add") == "1":
        from .notify import send_notification_async
        send_notification_async("add", table, record["data"], user)
    return jsonify(ok=True, record=record_row(record))


def _check_owner(rid):
    """登录用户可操作自己的记录，管理员可操作全部；返回 (user, record) 或错误响应"""
    u = g.current_user()
    if not u:
        return None, None, (jsonify(ok=False, message="请先登录"), 401)
    r = D.query("SELECT * FROM records WHERE id=?", (rid,), one=True)
    if not r:
        return None, None, (jsonify(ok=False, message="记录不存在"), 404)
    if u["role"] != "admin" and r["created_by"] != u["username"]:
        return None, None, (jsonify(ok=False, message="只能操作自己创建的数据"), 403)
    return u, r, None


@tables_bp.put("/records/<int:rid>")
def update_record(rid):
    u, r, err = _check_owner(rid)
    if err:
        return err
    table = get_table(r["table_id"])
    old = json.loads(r["data"])
    body = request.get_json(force=True, silent=True) or {}
    raw = body.get("data") or {}
    fmap = field_map(table)
    data = {k: v for k, v in raw.items() if k in fmap}
    if "sn" in fmap:
        data["sn"] = old.get("sn")  # 序号不可改
    if "apply_time" in fmap and not str(data.get("apply_time") or "").strip():
        data["apply_time"] = D.now_str()
    missing = [f["label"] for f in table["fields"]
               if f["required"] and not str(data.get(f["key"], "") or "").strip()
               and f["key"] != "sn"]
    if missing:
        return jsonify(ok=False, message=f"必填项未填写：{'、'.join(missing)}"), 400
    try:
        D.execute("UPDATE records SET data=?, updated_at=? WHERE id=?",
                  (json.dumps(data, ensure_ascii=False), D.now_str(), rid))
    except sqlite3.IntegrityError:
        return jsonify(ok=False, message=f"图号「{data.get('drawing_no')}」已被申请使用"), 409
    merge_options(table, data)
    changes = {}
    for k, v in data.items():
        if str(old.get(k, "")) != str(v):
            changes[fmap[k]["label"] if k in fmap else k] = [old.get(k), v]
    D.log_op(g.req_user_name(), "record_update", table["id"], table["name"],
             target=str(data.get("drawing_no") or data.get("name") or ""),
             detail={"changes": changes})
    return jsonify(ok=True)


@tables_bp.delete("/records/<int:rid>")
def delete_record(rid):
    u, r, err = _check_owner(rid)
    if err:
        return err
    table = get_table(r["table_id"])
    data = json.loads(r["data"])
    D.execute("DELETE FROM records WHERE id=?", (rid,))
    D.log_op(g.req_user_name(), "record_delete", table["id"], table["name"],
             target=str(data.get("drawing_no") or data.get("name") or ""),
             detail={"data": data})
    if D.get_setting("notify_enabled") == "1" and D.get_setting("notify_on_delete") == "1":
        from .notify import send_notification_async
        send_notification_async("delete", table, data, g.req_user_name())
    return jsonify(ok=True)


# ---------------- 导入 / 导出 ----------------

@tables_bp.post("/tables/<int:tid>/import")
def import_records(tid):
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(ok=False, message="未选择文件"), 400
    from . import excelio
    result = excelio.import_xlsx(table, f)
    if result["added"] > 0:
        D.log_op(g.req_user_name(), "import", tid, table["name"],
                 detail={"added": result["added"],
                         "failed": len(result["failed"]),
                         "file": f.filename})
    D.sys_log("INFO", "IMPORT",
             f"导入 {table['name']}: 成功 {result['added']} 条，失败 {len(result['failed'])} 条")
    return jsonify(ok=True, **result)


@tables_bp.get("/tables/<int:tid>/export")
def export_records(tid):
    if not g.can_read():
        return jsonify(ok=False, message="请先登录"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    records = apply_query(load_records(tid), table, request.args)
    from . import excelio
    resp = excelio.export_xlsx(table, records)
    D.log_op(g.req_user_name(), "export", tid, table["name"],
             detail={"count": len(records)})
    return resp


@tables_bp.get("/tables/<int:tid>/template")
def import_template(tid):
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    from . import excelio
    return excelio.export_xlsx(table, [], template=True)
