# -*- coding: utf-8 -*-
"""微信通知：企业微信群机器人 / 企业微信自建应用（文字 & 图文）"""
import base64
import hashlib
import io
import json
import os
import random
import threading
import time
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont

from . import db as D

COVER_W, COVER_H = 1068, 455
# 机构 Logo（项目根目录 ceec.png，Dockerfile 会一并复制）
LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ceec.png")
_font_cache = {}
_token_cache = {"token": None, "expires": 0}

# 随机暖色渐变调色板（每次生成封面随机挑选一组：顶部色 -> 底部色）
GRADIENTS = [
    ((255, 146, 84), (250, 92, 52)),    # 橙 -> 橙红
    ((255, 160, 70), (255, 100, 60)),   # 亮橙 -> 珊瑚橙
    ((255, 120, 90), (240, 70, 90)),    # 珊瑚粉
    ((255, 180, 60), (255, 110, 40)),   # 金橙 -> 橘红
    ((250, 110, 100), (230, 60, 80)),   # 珊瑚红
    ((255, 140, 100), (245, 80, 100)),  # 蜜桃 -> 西柚
]


# ---------------- 字体 ----------------

def _find_font(size):
    # 优先使用设置中选定的自定义字体（data/uploads/fonts）
    custom = (D.get_setting("notify_font") or "").strip()
    if custom:
        p = os.path.join(D.UPLOAD_DIR, "fonts", custom)
        if os.path.isfile(p):
            key = f"c:{custom}:{int(os.path.getmtime(p))}:{size}"
            if key not in _font_cache:
                try:
                    _font_cache[key] = ImageFont.truetype(p, size)
                except OSError:
                    _font_cache[key] = None
            if _font_cache[key]:
                return _font_cache[key]
    # 系统字体回退
    key = f"n{size}"
    if key in _font_cache:
        return _font_cache[key]
    candidates = []
    env = os.environ.get("DRAWCODE_FONT")
    if env:
        candidates.append(env)
    candidates += [
        "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                f = ImageFont.truetype(path, size)
                _font_cache[key] = f
                return f
            except OSError:
                continue
    f = ImageFont.load_default()
    _font_cache[key] = f
    return f


# ---------------- 图文封面 1068x455 ----------------

def _cut(draw, text, font, max_w):
    """按像素宽度截断文本"""
    if not text:
        return ""
    text = str(text)
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def _paste_logo(img):
    """右上角贴机构 Logo（项目根目录 ceec.png），支持透明背景"""
    if not os.path.isfile(LOGO_PATH):
        return
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
    except Exception:
        return
    if logo.width < 10 or logo.height < 10:
        return
    # 等比缩放到高约 110px（过宽则限制宽度）
    h = 110
    w = int(logo.width * h / logo.height)
    if w > 300:
        w, h = 300, int(logo.height * w / logo.width)
    logo = logo.resize((w, h), Image.LANCZOS)
    img.paste(logo, (COVER_W - w - 56, 38), logo)


def make_cover(title, lines, footer_left):
    """生成 1068x455 通知封面：随机暖色渐变 + 双栏数据 + 右上角 Logo"""
    # 每次随机挑选一组鲜亮暖色渐变背景
    top, bottom = random.choice(GRADIENTS)
    grad = Image.new("RGB", (2, COVER_H))
    for y in range(COVER_H):
        t = y / COVER_H
        grad.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        grad.putpixel((1, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    img = grad.resize((COVER_W, COVER_H))
    draw = ImageDraw.Draw(img)

    f_small = _find_font(32)
    f_big = _find_font(64)
    f_line = _find_font(40)

    # 顶部小字 + 装饰线
    draw.text((56, 40), _cut(draw, footer_left, f_small, 620),
              font=f_small, fill=(255, 226, 192))
    draw.line((56, 96, 192, 96), fill=(255, 236, 200), width=4)

    # 大标题
    draw.text((56, 124), _cut(draw, title, f_big, 640), font=f_big, fill=(255, 255, 255))

    # 右上角 Logo
    _paste_logo(img)

    # 双栏键值：左列 名称 / 图号，右列 型号 / 申请人
    kv = {}
    for k, v in lines:
        kv[k] = "、".join(str(x) for x in v) if isinstance(v, list) else str(v or "")
    cols = [(58, ["名　称", "图　号"], 330), (568, ["型　号", "申请人"], 290)]
    for cx, keys, vw in cols:
        y = 252
        for k in keys:
            v = kv.get(k, "")
            draw.text((cx, y), k, font=f_line, fill=(255, 216, 168))
            draw.text((cx + 150, y), _cut(draw, v or "—", f_line, vw),
                      font=f_line, fill=(255, 250, 244))
            y += 78

    # 右下角时间（右对齐）
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    draw.text((COVER_W - 56 - int(draw.textlength(ts, font=f_small)), COVER_H - 58),
              ts, font=f_small, fill=(255, 208, 176))
    return img


def cover_png_bytes(img):
    bio = io.BytesIO()
    img.convert("RGB").save(bio, format="PNG")
    return bio.getvalue()


def _cover_media(title, lines, footer):
    """封面图来源：优先使用自定义文件 data/uploads/cover.png / cover.jpg，
    不存在时按内容动态生成 1068x455。返回 (bytes, 文件名, mime)"""
    for fn, mime in (("cover.png", "image/png"),
                     ("cover.jpg", "image/jpeg"),
                     ("cover.jpeg", "image/jpeg")):
        p = os.path.join(D.UPLOAD_DIR, fn)
        if os.path.isfile(p):
            with open(p, "rb") as f:
                data = f.read()
            if data:
                return data, fn, mime
    return cover_png_bytes(make_cover(title, lines, footer)), "cover.png", "image/png"


# ---------------- 消息构建 ----------------

def build_content(event, table, data, user):
    s = D.get_settings()
    names = D.site_names(s["site_org"])
    titles = {"add": "新增图号通知", "delete": "图号删除通知", "test": "测试通知"}
    title = titles.get(event, "图号通知")
    lines = [("表　名", table["name"] if table else "—")]
    for key in ("drawing_no", "name", "model", "project", "applicant"):
        label = {"drawing_no": "图　号", "name": "名　称", "model": "型　号",
                 "project": "工程项目", "applicant": "申请人"}.get(key)
        if data and data.get(key):
            lines.append((label, data[key]))
    if data and data.get("apply_time"):
        lines.append(("时　间", data["apply_time"]))
    lines.append(("操 作 人", user))
    footer = f"{names['full']} · DrawCode"
    return title, lines, footer


def _robot_send_md(webhook, title, lines, footer):
    parts = [f"**【{title}】**", ""]
    for k, v in lines:
        parts.append(f"> **{k}**：{v}")
    parts.append(f"> \n> ——— \n> {footer}")
    r = requests.post(webhook, json={"msgtype": "markdown",
                                     "markdown": {"content": "\n".join(parts)}}, timeout=8)
    return _wecom_check(r, "群机器人")


def _wecom_check(resp, tag):
    try:
        j = resp.json()
    except ValueError:
        return f"{tag}响应解析失败: HTTP {resp.status_code}"
    if j.get("errcode") not in (0, None) and j.get("errcode") != 0:
        return f"{tag}错误({j.get('errcode')}): {j.get('errmsg')}"
    return None


def _robot_send(webhook, style, title, lines, footer):
    if style == "image_text":
        png, _, _ = _cover_media(title, lines, footer)
        if len(png) > 2 * 1024 * 1024:
            return "封面图超过机器人 2MB 限制"
        r = requests.post(webhook, json={
            "msgtype": "image",
            "image": {"base64": base64.b64encode(png).decode(),
                      "md5": hashlib.md5(png).hexdigest()}}, timeout=10)
        err = _wecom_check(r, "群机器人图片")
        if err:
            return err
        time.sleep(0.3)
        return _robot_send_md(webhook, title, lines, footer)
    return _robot_send_md(webhook, title, lines, footer)


def _wecom_token(corpid, secret):
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires"]:
        return _token_cache["token"]
    r = requests.get("https://qyapi.weixin.qq.com/cgi-bin/gettoken",
                     params={"corpid": corpid, "corpsecret": secret}, timeout=8)
    j = r.json()
    if j.get("errcode") != 0:
        raise RuntimeError(f"获取access_token失败({j.get('errcode')}): {j.get('errmsg')}")
    _token_cache.update(token=j["access_token"], expires=now + j.get("expires_in", 7200) - 300)
    return j["access_token"]


def _wecom_app_send(s, style, title, lines, footer):
    token = _wecom_token(s["notify_corpid"], s["notify_secret"])
    touser = (s.get("notify_touser") or "").strip() or "@all"
    agentid = s["notify_agentid"].strip()
    base = "https://qyapi.weixin.qq.com/cgi-bin"
    if style == "text":
        content = f"【{title}】\n" + "\n".join(f"{k}：{v}" for k, v in lines) + f"\n———\n{footer}"
        r = requests.post(f"{base}/message/send?access_token={token}", json={
            "touser": touser, "msgtype": "text", "agentid": int(agentid) if agentid.isdigit() else agentid,
            "text": {"content": content}}, timeout=10)
        return _wecom_check(r, "企业微信应用")
    # 图文：上传封面 → news
    png, cover_name, cover_mime = _cover_media(title, lines, footer)
    files = {"media": (cover_name, png, cover_mime)}
    r = requests.post(f"{base}/media/uploadimg?access_token={token}", files=files, timeout=15)
    j = r.json()
    if j.get("errcode") not in (0, None) and "url" not in j:
        return f"封面上传失败({j.get('errcode')}): {j.get('errmsg')}"
    desc = "\n".join(f"{k}：{v}" for k, v in lines)
    r = requests.post(f"{base}/message/send?access_token={token}", json={
        "touser": touser, "msgtype": "news", "agentid": int(agentid) if agentid.isdigit() else agentid,
        "news": {"articles": [{
            "title": title, "description": desc[:255],
            "url": D.GITHUB_URL, "picurl": j.get("url", "")}]}}, timeout=10)
    return _wecom_check(r, "企业微信应用")


def send_notification(event, table=None, data=None, user=""):
    """发送通知，成功返回 None，失败返回错误描述"""
    s = D.get_settings()
    if s["notify_enabled"] != "1":
        return "通知未启用"
    title, lines, footer = build_content(event, table, data, user)
    try:
        if s["notify_type"] == "robot":
            webhook = (s.get("notify_webhook") or "").strip()
            if not webhook:
                return "未配置群机器人 Webhook 地址"
            return _robot_send(webhook, s["notify_style"], title, lines, footer)
        corpid = (s.get("notify_corpid") or "").strip()
        secret = (s.get("notify_secret") or "").strip()
        agentid = (s.get("notify_agentid") or "").strip()
        if not (corpid and secret and agentid):
            return "企业微信应用参数不完整（需要企业ID / 密钥 / 应用AgentId）"
        return _wecom_app_send(s, s["notify_style"], title, lines, footer)
    except Exception as e:
        return f"发送异常: {e}"


def send_notification_async(event, table=None, data=None, user=""):
    def run():
        err = send_notification(event, table, data, user)
        if err:
            D.sys_log("WARN", "NOTIFY", f"通知发送失败: {err}")
        else:
            D.sys_log("INFO", "NOTIFY",
                      f"通知已发送: {event} " +
                      (f"图号 {data.get('drawing_no')}" if data else ""))
    threading.Thread(target=run, daemon=True).start()
