"""
Ink's Racro -- mining macro with a dark control panel.

Features
  * Speed dropdown (Level 1 / 2 / 12), Start (auto-finds the ore), Stop, F2.
  * Auto-find ore: probes the screen until the cursor turns into the pickaxe.
  * Auto-rejoin: paste a server link; resolves to a deep link (grabs your
    Roblox login automatically for /share links) and rejoins on crash.
  * Auto-reconnect on freeze: if the screen stops changing it rejoins.
  * Walk-to-ore after a rejoin (holds W, watches the cursor).
  * Auto-vote: clicks the admin slot + Vote button on a timer (calibrated).
  * Auto-pay: every N mines, types  ;pay <host> <amount>  in chat.

Only Python is required. 'keyboard' is optional (just the F2 hotkey).
Settings save to racro_config.json next to this file. The cookie is NEVER saved.
"""

import os
import re
import sys
import json
import time
import random
import threading
import ctypes
from ctypes import wintypes
import urllib.request
import urllib.error
import urllib.parse
import tkinter as tk

try:
    import winreg
except Exception:
    winreg = None
try:
    import keyboard
    HAVE_KEYBOARD = True
except Exception:
    HAVE_KEYBOARD = False

# ---- speed levels ----
LEVELS = [
    ("Level 1  -  slow  (3.5s)", 3.5),
    ("Level 2  -  medium (2.8s)", 2.8),
    ("Level 12 -  fast  (2.2s)", 2.2),
]
DEFAULT_LEVEL = 1
RELEASE_GAP   = 0.05

WATCHDOG          = True
ROBLOX_TITLE      = "Roblox"
WATCH_POLL        = 15
WATCH_RELOAD_WAIT = 45

# walk-to-ore / auto-find tunables
WALK_TIMEOUT = 4.0
CAM_DX       = 220
MAX_SWEEPS   = 12
SPAWN_DELAY  = 9
MAX_PROBES   = 60          # random spots to try when auto-finding the ore

# disconnect-popup detection (dim overlay + static centered modal)
POPUP_POLL    = 1.2
POPUP_CONFIRM = 2.5      # the popup look must persist this long before we act
POPUP_DARK    = 95       # avg edge brightness (0-255) below this = "dimmed"
POPUP_UNIFORM = 45       # edge brightness spread below this = flat overlay
EDGE_POINTS = [(0.03, 0.05), (0.50, 0.04), (0.97, 0.05),
               (0.03, 0.50), (0.97, 0.50),
               (0.03, 0.95), (0.50, 0.96), (0.97, 0.95)]
CENTER_POINTS = [(0.50, 0.50), (0.42, 0.50), (0.58, 0.50),
                 (0.50, 0.42), (0.50, 0.58)]

# auto-pay
PAY_EVERY  = 10000
PAY_AMOUNT = 10000

IMAGE_FILE  = "racro.png"
IMAGE_WIDTH = 92
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "racro_config.json")

user32  = ctypes.windll.user32
shell32 = ctypes.windll.shell32
gdi32   = ctypes.windll.gdi32

# ---- input structs ----
PUL = ctypes.POINTER(ctypes.c_ulong)

class _MI(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]

class _KI(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class _IU(ctypes.Union):
    _fields_ = [("mi", _MI), ("ki", _KI)]

class _INP(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _IU)]

class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("flags", ctypes.c_uint),
                ("hCursor", ctypes.c_void_p), ("ptScreenPos", wintypes.POINT)]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008
SCAN_W = 0x11
SCAN_SLASH = 0x35
SCAN_SEMI = 0x27
SCAN_ENTER = 0x1C
SCAN_BACK = 0x0E
SCAN_A = 0x1E
SCAN_LCTRL = 0x1D
CHAT_BACKSPACES = 40
SM_CXSCREEN = 0
SM_CYSCREEN = 1

input_lock = threading.Lock()


def _send(flags, dx=0, dy=0):
    extra = ctypes.c_ulong(0)
    mi = _MI(dx, dy, 0, flags, 0, ctypes.pointer(extra))
    inp = _INP(INPUT_MOUSE, _IU(mi=mi))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INP))


def _key(scan, up=False):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
    extra = ctypes.c_ulong(0)
    ki = _KI(0, scan, flags, 0, ctypes.pointer(extra))
    inp = _INP(INPUT_KEYBOARD, _IU(ki=ki))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INP))


def _uni(ch, up=False):
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
    extra = ctypes.c_ulong(0)
    ki = _KI(0, ord(ch), flags, 0, ctypes.pointer(extra))
    inp = _INP(INPUT_KEYBOARD, _IU(ki=ki))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INP))


def type_string(s):
    for ch in s:
        _uni(ch, False)
        _uni(ch, True)
        time.sleep(0.012)


def key_ctrl_a():
    _key(SCAN_LCTRL, False)
    _key(SCAN_A, False)
    _key(SCAN_A, True)
    _key(SCAN_LCTRL, True)


def tap(scan):
    _key(scan, False)
    time.sleep(0.03)
    _key(scan, True)


def _move_abs(x, y):
    sw = user32.GetSystemMetrics(SM_CXSCREEN) or 1920
    sh = user32.GetSystemMetrics(SM_CYSCREEN) or 1080
    _send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
          int(x * 65535 / max(1, sw - 1)),
          int(y * 65535 / max(1, sh - 1)))


def screen_size():
    return (user32.GetSystemMetrics(SM_CXSCREEN) or 1920,
            user32.GetSystemMetrics(SM_CYSCREEN) or 1080)


def screen_center():
    w, h = screen_size()
    return (w // 2, h // 2)


def cursor_pos():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return (p.x, p.y)


def cursor_handle():
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if user32.GetCursorInfo(ctypes.byref(ci)):
        return ci.hCursor
    return None


def get_pixel(x, y):
    hdc = user32.GetDC(0)
    try:
        return gdi32.GetPixel(hdc, int(x), int(y))
    finally:
        user32.ReleaseDC(0, hdc)


def _bri(c):
    return ((c & 0xff) + ((c >> 8) & 0xff) + ((c >> 16) & 0xff)) // 3


def popup_signature():
    """Return (looks_dimmed, center_pixels). A disconnect popup dims the whole
    screen to a flat dark overlay and drops a static modal in the middle."""
    w, h = screen_size()
    edge = [_bri(get_pixel(int(w * fx), int(h * fy))) for fx, fy in EDGE_POINTS]
    cen = tuple(get_pixel(int(w * fx), int(h * fy)) for fx, fy in CENTER_POINTS)
    dimmed = (sum(edge) / len(edge) < POPUP_DARK
              and (max(edge) - min(edge)) < POPUP_UNIFORM)
    return dimmed, cen


def roblox_open():
    return bool(user32.FindWindowW(None, ROBLOX_TITLE))


def click_at(x, y):
    user32.SetCursorPos(int(x), int(y))
    _move_abs(x, y)
    time.sleep(0.03)
    _send(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.05)
    _send(MOUSEEVENTF_LEFTUP)


def rotate_camera(dx):
    _send(MOUSEEVENTF_RIGHTDOWN)
    time.sleep(0.05)
    for _ in range(10):
        _send(MOUSEEVENTF_MOVE, int(dx / 10), 0)
        time.sleep(0.012)
    time.sleep(0.05)
    _send(MOUSEEVENTF_RIGHTUP)


def read_roblox_cookie():
    """Read this machine's own .ROBLOSECURITY from the local Roblox registry.
    Used ONLY to call Roblox's resolve-link API for /share links; never stored,
    never sent anywhere but roblox.com."""
    if winreg is None:
        return None
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Roblox\RobloxStudioBrowser\roblox.com")
        val, _ = winreg.QueryValueEx(k, ".ROBLOSECURITY")
        winreg.CloseKey(k)
    except Exception:
        return None
    if not val:
        return None
    m = re.search(r"(_\|WARNING.*)", val, re.S)
    if m:
        return m.group(1).strip()
    if "::" in val:
        return val.split("::")[-1].strip()
    return val.strip()


# ---- link resolving ----
def _api_call(share, cookie, csrf=None):
    body = json.dumps({"linkId": share, "linkType": "Server"}).encode()
    req = urllib.request.Request(
        "https://apis.roblox.com/sharelinks/v1/resolve-link",
        data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Cookie", ".ROBLOSECURITY=" + cookie)
    if csrf:
        req.add_header("X-CSRF-TOKEN", csrf)
    return urllib.request.urlopen(req, timeout=15)


def resolve_share(share, cookie):
    try:
        resp = _api_call(share, cookie)
    except urllib.error.HTTPError as e:
        token = e.headers.get("x-csrf-token")
        if e.code == 403 and token:
            resp = _api_call(share, cookie, token)
        else:
            raise ValueError("Roblox API error %s" % e.code)
    data = json.loads(resp.read())
    inv = data.get("privateServerInviteData") or {}
    place = inv.get("placeId") or data.get("placeId")
    code = inv.get("linkCode") or inv.get("accessCode")
    if place and code:
        return "roblox://experiences/start?placeId=%s&linkCode=%s" % (place, code)
    raise ValueError("couldn't read server info")


def resolve_link(text, cookie=""):
    text = (text or "").strip()
    if not text:
        raise ValueError("paste a link first")
    if text.startswith("roblox://"):
        return text
    parts = urllib.parse.urlsplit(text)
    q = dict(urllib.parse.parse_qsl(parts.query))
    place = q.get("placeId") or q.get("placeid")
    code = q.get("linkCode") or q.get("privateServerLinkCode") or q.get("accessCode")
    if not place:
        m = re.search(r"/games/(\d+)", parts.path)
        if m:
            place = m.group(1)
    if place and code:
        return "roblox://experiences/start?placeId=%s&linkCode=%s" % (place, code)
    share = q.get("code")
    if share and ("share" in parts.path or q.get("type", "").lower() == "server"):
        if not cookie:
            cookie = read_roblox_cookie() or ""
        if not cookie:
            raise ValueError("/share link: no Roblox login found - paste cookie")
        return resolve_share(share, cookie)
    raise ValueError("link not recognized")


# ---- shared state ----
state = {
    "running": False, "quit": False, "go_busy": False, "rejoining": False,
    "hold": LEVELS[DEFAULT_LEVEL][1], "center": None,
    "deeplink": "",
    "auto_vote": False, "vote_interval": 60.0,
    "vote_admin": None, "vote_button": None, "vote_w": None, "vote_h": None,
    "auto_walk": False, "disc_detect": True,
    "auto_pay": False, "pay_host": "", "mine_count": 0,
}

ui = {"root": None, "status": None}


def set_status(msg):
    r, s = ui["root"], ui["status"]
    if r is not None and s is not None:
        try:
            r.after(0, lambda: s.set(msg))
        except Exception:
            pass


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("deeplink"):
            state["deeplink"] = c["deeplink"]
        v = c.get("vote") or {}
        if v.get("admin"):
            state["vote_admin"] = tuple(v["admin"])
        if v.get("vote"):
            state["vote_button"] = tuple(v["vote"])
        state["vote_w"] = v.get("w")
        state["vote_h"] = v.get("h")
        if c.get("interval"):
            state["vote_interval"] = float(c["interval"])
        state["auto_walk"] = bool(c.get("auto_walk", False))
        state["disc_detect"] = bool(c.get("disc_detect", True))
        state["pay_host"] = c.get("pay_host", "") or ""
    except Exception:
        pass


def save_config():
    try:
        c = {"deeplink": state["deeplink"],
             "vote": {"admin": state["vote_admin"], "vote": state["vote_button"],
                      "w": state["vote_w"], "h": state["vote_h"]},
             "interval": state["vote_interval"],
             "auto_walk": state["auto_walk"],
             "disc_detect": state["disc_detect"],
             "pay_host": state["pay_host"]}
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(c, f)
    except Exception:
        pass


# ---- chat / pay ----
def send_chat(msg):
    tap(SCAN_SEMI)                      # press ; to open the chat box
    time.sleep(0.3)
    for _ in range(CHAT_BACKSPACES):    # spam backspace to clear everything
        tap(SCAN_BACK)
        time.sleep(0.006)
    time.sleep(0.05)
    type_string(msg)                    # type the full ;pay command
    time.sleep(0.12)
    tap(SCAN_ENTER)
    time.sleep(0.1)


def do_pay():
    host = state["pay_host"].strip()
    if not host:
        return
    msg = ";pay %s %d" % (host, PAY_AMOUNT)
    with input_lock:
        send_chat(msg)
    set_status("paid %s (%d mines)" % (host, state["mine_count"]))


# ---- worker loops ----
def mine_loop():
    while not state["quit"]:
        if state["running"] and state["center"]:
            try:
                with input_lock:
                    x, y = int(state["center"][0]), int(state["center"][1])
                    user32.SetCursorPos(x, y)
                    _move_abs(x, y)
                    time.sleep(0.02)
                    _send(MOUSEEVENTF_LEFTDOWN)
                    end = time.time() + state["hold"]
                    while time.time() < end and state["running"] and not state["quit"]:
                        time.sleep(0.02)
                    _send(MOUSEEVENTF_LEFTUP)
                state["mine_count"] += 1
                if (state["auto_pay"] and state["pay_host"].strip()
                        and PAY_EVERY > 0 and state["mine_count"] % PAY_EVERY == 0):
                    do_pay()
                time.sleep(RELEASE_GAP)
            except Exception:
                try:
                    _send(MOUSEEVENTF_LEFTUP)
                except Exception:
                    pass
                time.sleep(0.4)
        else:
            time.sleep(0.05)


def vote_loop():
    last = 0.0
    while not state["quit"]:
        time.sleep(0.5)
        if not state["auto_vote"]:
            continue
        if not (state["vote_admin"] and state["vote_button"]):
            continue
        if time.time() - last < state["vote_interval"]:
            continue
        last = time.time()
        try:
            with input_lock:
                click_at(*state["vote_admin"])
                time.sleep(0.4)
                click_at(*state["vote_button"])
        except Exception:
            pass


def rejoin(reason=""):
    if state["rejoining"] or not state["deeplink"]:
        return
    state["rejoining"] = True
    state["running"] = False
    try:
        set_status("rejoining (%s)..." % reason)
        try:
            shell32.ShellExecuteW(None, "open", state["deeplink"], None, None, 1)
        except Exception:
            pass
        waited = 0
        while waited < WATCH_RELOAD_WAIT and not state["quit"]:
            time.sleep(3)
            waited += 3
            if roblox_open():
                break
        if state["auto_walk"] and not state["quit"]:
            time.sleep(SPAWN_DELAY)
            go_to_ore()
    finally:
        state["rejoining"] = False


def watchdog_loop():
    seen = False
    while not state["quit"]:
        time.sleep(WATCH_POLL)
        if not state["deeplink"]:
            continue
        if roblox_open():
            seen = True
            continue
        if seen:
            rejoin("closed")


def popup_loop():
    since = None
    last_cen = None
    while not state["quit"]:
        time.sleep(POPUP_POLL)
        if not (state["disc_detect"] and state["deeplink"]):
            since = None
            continue
        if not roblox_open() or state["rejoining"] or state["go_busy"]:
            since = None
            continue
        try:
            dimmed, cen = popup_signature()
        except Exception:
            continue
        # popup = dim overlay AND a static modal in the center
        if dimmed and cen == last_cen:
            if since is None:
                since = time.time()
            elif time.time() - since >= POPUP_CONFIRM:
                since = None
                last_cen = None
                rejoin("disconnected")
                continue
        else:
            since = None
        last_cen = cen


def go_to_ore():
    if state["go_busy"]:
        return
    state["go_busy"] = True
    state["running"] = False
    found = False
    try:
        cx, cy = state["center"] if state["center"] else screen_center()
        with input_lock:
            user32.SetCursorPos(cx, cy)
            time.sleep(0.25)
            baseline = cursor_handle()
            sweeps = 0
            while sweeps < MAX_SWEEPS and not state["quit"]:
                _key(SCAN_W, False)
                t_end = time.time() + WALK_TIMEOUT
                while time.time() < t_end and not state["quit"]:
                    user32.SetCursorPos(cx, cy)
                    h = cursor_handle()
                    if h and baseline and h != baseline:
                        found = True
                        break
                    time.sleep(0.1)
                _key(SCAN_W, True)
                if found:
                    break
                rotate_camera(CAM_DX)
                time.sleep(0.3)
                sweeps += 1
        if found:
            state["center"] = (cx, cy)
            state["running"] = True
            set_status("found ore - mining")
        else:
            set_status("no ore found - hover + F2")
    finally:
        try:
            _key(SCAN_W, True)
        except Exception:
            pass
        state["go_busy"] = False


def auto_find_ore():
    """Probe random spots until the cursor becomes the pickaxe, then mine."""
    if state["go_busy"]:
        return
    state["go_busy"] = True
    state["running"] = False
    found = False
    try:
        w, h = screen_size()
        with input_lock:
            user32.SetCursorPos(w // 2, int(h * 0.10))
            time.sleep(0.15)
            baseline = cursor_handle()
            for _ in range(MAX_PROBES):
                if state["quit"]:
                    break
                x = random.randint(int(w * 0.28), int(w * 0.72))
                y = random.randint(int(h * 0.34), int(h * 0.74))
                user32.SetCursorPos(x, y)
                time.sleep(0.06)
                hc = cursor_handle()
                if hc and baseline and hc != baseline:
                    time.sleep(0.05)
                    if cursor_handle() == hc:
                        state["center"] = (x, y)
                        found = True
                        break
        if found:
            state["running"] = True
            set_status("ore found - mining @ %ss" % state["hold"])
        else:
            set_status("no ore found - hover + F2 to set it")
    finally:
        state["go_busy"] = False


# ============================ UI ============================
BG = "#16161e"
CARD = "#20202e"
ENTRY = "#2b2b3d"
FG = "#ece9f5"
MUTED = "#8d89a6"
ACCENT = "#b07ee0"
GREEN = "#79e0a3"
RED = "#ff8a9b"
AMBER = "#f3c969"


def main():
    load_config()
    if len(sys.argv) > 1:
        try:
            state["hold"] = float(sys.argv[1])
        except ValueError:
            pass
    if len(sys.argv) > 2 and sys.argv[2].strip():
        state["deeplink"] = sys.argv[2].strip()
        save_config()

    threading.Thread(target=mine_loop, daemon=True).start()
    threading.Thread(target=vote_loop, daemon=True).start()
    if WATCHDOG:
        threading.Thread(target=watchdog_loop, daemon=True).start()
        threading.Thread(target=popup_loop, daemon=True).start()

    root = tk.Tk()
    root.title("Ink's Racro")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.geometry("+20+20")
    root.configure(bg=BG)
    status = tk.StringVar(value="ready - press Start")
    ui["root"] = root
    ui["status"] = status

    def L(parent, text, fg=FG, size=8, bold=False, bgc=CARD):
        return tk.Label(parent, text=text, fg=fg, bg=bgc,
                        font=("Segoe UI", size, "bold" if bold else "normal"))

    def B(parent, text, cmd, bg=ACCENT, fg="#1a1320"):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                         activebackground=bg, activeforeground=fg, relief="flat",
                         bd=0, font=("Segoe UI", 8, "bold"), cursor="hand2",
                         padx=6, pady=3)

    def E(parent, var, show=None, width=22):
        return tk.Entry(parent, textvariable=var, width=width, show=show,
                        bg=ENTRY, fg=FG, insertbackground=FG, relief="flat",
                        font=("Segoe UI", 8))

    def C(parent, text, var, cmd):
        return tk.Checkbutton(parent, text=text, variable=var, command=cmd,
                              bg=CARD, fg=FG, selectcolor=ENTRY, relief="flat",
                              activebackground=CARD, activeforeground=FG,
                              font=("Segoe UI", 8))

    # ---------- header ----------
    head = tk.Frame(root, bg=BG)
    head.pack(fill="x", padx=12, pady=(10, 4))
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        img = tk.PhotoImage(file=os.path.join(here, IMAGE_FILE))
        fct = max(1, img.width() // 64)
        if fct > 1:
            img = img.subsample(fct)
        il = tk.Label(head, image=img, bg=BG)
        il.image = img
        il.pack(side="left", padx=(0, 10))
    except Exception:
        pass
    htext = tk.Frame(head, bg=BG)
    htext.pack(side="left")
    L(htext, "Ink's Racro", ACCENT, 14, True, BG).pack(anchor="w")
    L(htext, "mining, but lazy", MUTED, 8, False, BG).pack(anchor="w")
    tk.Label(head, textvariable=status, fg=MUTED, bg=BG,
             font=("Segoe UI", 8), anchor="e").pack(side="right")

    # ---------- columns ----------
    body = tk.Frame(root, bg=BG)
    body.pack(padx=10, pady=(0, 10))

    def column():
        outer = tk.Frame(body, bg=CARD)
        outer.pack(side="left", padx=5, anchor="n")
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(padx=10, pady=9)
        return inner

    # --- column 1: MINE ---
    c1 = column()
    L(c1, "MINE", ACCENT, 8, True).pack(anchor="w")
    labels = [l for l, _ in LEVELS]
    sel = tk.StringVar(value=labels[DEFAULT_LEVEL])

    def on_level(choice):
        for l, v in LEVELS:
            if l == choice:
                state["hold"] = v
        status.set("speed: %ss" % state["hold"])

    drop = tk.OptionMenu(c1, sel, *labels, command=on_level)
    drop.config(bg=ENTRY, fg=FG, activebackground=ACCENT, activeforeground="#1a1320",
                relief="flat", bd=0, highlightthickness=0, font=("Segoe UI", 8),
                width=20)
    drop["menu"].config(bg=CARD, fg=FG, activebackground=ACCENT,
                        activeforeground="#1a1320")
    drop.pack(fill="x", pady=(3, 7))

    def do_start():
        status.set("looking for the ore...")
        threading.Thread(target=auto_find_ore, daemon=True).start()

    def do_stop():
        state["running"] = False
        status.set("stopped")

    B(c1, "\u25B6  Start", do_start, GREEN).pack(fill="x", pady=2)
    B(c1, "\u25A0  Stop", do_stop, RED).pack(fill="x", pady=2)
    L(c1, "Start auto-finds the ore.\nF2 sets it by hand.", MUTED, 7).pack(
        anchor="w", pady=(6, 0))

    # --- column 2: REJOIN ---
    c2 = column()
    L(c2, "AUTO-REJOIN", ACCENT, 8, True).pack(anchor="w")
    link_var = tk.StringVar(value=state["deeplink"])
    E(c2, link_var, width=26).pack(fill="x", pady=(3, 0))
    L(c2, "server link (login grabbed for you)", MUTED, 7).pack(anchor="w")
    cookie_var = tk.StringVar()
    E(c2, cookie_var, show="*", width=26).pack(fill="x", pady=(3, 0))
    L(c2, "cookie - only if auto-grab fails", MUTED, 7).pack(anchor="w")

    def save_link():
        raw, ck = link_var.get().strip(), cookie_var.get().strip()
        status.set("resolving...")

        def work():
            try:
                dl = resolve_link(raw, ck)
                state["deeplink"] = dl
                save_config()
                root.after(0, lambda: (link_var.set(dl), status.set("rejoin saved!")))
            except Exception as e:
                msg = str(e)
                root.after(0, lambda: status.set("link: " + msg))

        threading.Thread(target=work, daemon=True).start()

    B(c2, "Save & enable rejoin", save_link).pack(fill="x", pady=(5, 5))
    disc_var = tk.BooleanVar(value=state["disc_detect"])

    def on_disc():
        state["disc_detect"] = disc_var.get()
        save_config()

    C(c2, "Reconnect on disconnect popup", disc_var, on_disc).pack(anchor="w")
    walk_var = tk.BooleanVar(value=state["auto_walk"])

    def on_walk():
        state["auto_walk"] = walk_var.get()
        save_config()

    wrow = tk.Frame(c2, bg=CARD)
    wrow.pack(fill="x")
    C(wrow, "Walk to ore after rejoin", walk_var, on_walk).pack(side="left")
    B(wrow, "Go", lambda: threading.Thread(target=go_to_ore, daemon=True).start(),
      AMBER).pack(side="right")

    # --- column 3: VOTE + PAY ---
    c3 = column()
    L(c3, "AUTO-VOTE", ACCENT, 8, True).pack(anchor="w")
    auto_vote_var = tk.BooleanVar(value=False)
    warn = tk.StringVar(value="")

    def update_warn():
        if state["vote_w"]:
            cw, ch = screen_size()
            if (cw, ch) != (state["vote_w"], state["vote_h"]):
                warn.set("screen %dx%d != calib %dx%d" %
                         (cw, ch, state["vote_w"], state["vote_h"]))
                return
        warn.set("")

    iv_var = tk.StringVar(value=str(int(state["vote_interval"])))

    def on_vote():
        if auto_vote_var.get():
            if not (state["vote_admin"] and state["vote_button"]):
                auto_vote_var.set(False)
                status.set("calibrate vote buttons first")
                return
            try:
                state["vote_interval"] = max(5.0, float(iv_var.get()))
            except ValueError:
                state["vote_interval"] = 60.0
            save_config()
            state["auto_vote"] = True
            update_warn()
            status.set("auto-vote ON")
        else:
            state["auto_vote"] = False
            status.set("auto-vote off")

    C(c3, "Auto-Vote last admin?", auto_vote_var, on_vote).pack(anchor="w")
    vrow = tk.Frame(c3, bg=CARD)
    vrow.pack(anchor="w", pady=(1, 0))
    L(vrow, "every", MUTED, 8).pack(side="left")
    E(vrow, iv_var, width=4).pack(side="left", padx=2)
    L(vrow, "sec", MUTED, 8).pack(side="left")

    def calibrate():
        cal_btn.config(state="disabled")
        auto_vote_var.set(False)
        state["auto_vote"] = False

        def finish():
            state["vote_button"] = cursor_pos()
            state["vote_w"], state["vote_h"] = screen_size()
            save_config()
            update_warn()
            status.set("vote calibrated!")
            cal_btn.config(state="normal")

        def s2(n):
            if n > 0:
                status.set("hover the VOTE button... %d" % n)
                root.after(1000, lambda: s2(n - 1))
            else:
                finish()

        def mid():
            state["vote_admin"] = cursor_pos()
            root.after(800, lambda: s2(3))

        def s1(n):
            if n > 0:
                status.set("hover the ADMIN slot... %d" % n)
                root.after(1000, lambda: s1(n - 1))
            else:
                mid()

        s1(3)

    cal_btn = B(c3, "Calibrate buttons", calibrate, AMBER)
    cal_btn.pack(fill="x", pady=(4, 1))
    tk.Label(c3, textvariable=warn, fg=RED, bg=CARD, font=("Segoe UI", 7),
             wraplength=150).pack(anchor="w")

    tk.Frame(c3, bg=ENTRY, height=1).pack(fill="x", pady=7)

    L(c3, "AUTO-PAY", ACCENT, 8, True).pack(anchor="w")
    pay_var = tk.BooleanVar(value=False)
    host_var = tk.StringVar(value=state["pay_host"])

    def on_pay():
        state["pay_host"] = host_var.get().strip()
        save_config()
        if pay_var.get():
            if not state["pay_host"]:
                pay_var.set(False)
                status.set("enter the host name first")
                return
            state["auto_pay"] = True
            status.set("auto-pay ON")
        else:
            state["auto_pay"] = False
            status.set("auto-pay off")

    C(c3, "Pay host every %dk mines" % (PAY_EVERY // 1000), pay_var, on_pay).pack(
        anchor="w")
    prow = tk.Frame(c3, bg=CARD)
    prow.pack(fill="x", pady=(1, 0))
    L(prow, "host:", MUTED, 8).pack(side="left", padx=(0, 3))
    he = E(prow, host_var, width=14)
    he.pack(side="left", fill="x", expand=True)
    he.bind("<FocusOut>", lambda e: on_pay() if pay_var.get()
            else state.update(pay_host=host_var.get().strip()))

    if HAVE_KEYBOARD:
        def pin():
            state["center"] = cursor_pos()
            state["running"] = True
            set_status("mining @ %ss" % state["hold"])
        try:
            keyboard.add_hotkey("f2", pin)
        except Exception:
            pass

    update_warn()

    def on_close():
        state["quit"] = True
        try:
            _send(MOUSEEVENTF_LEFTUP)
            _key(SCAN_W, True)
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
