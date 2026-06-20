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

LOGO_B64 = (
    "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"
)

user32  = ctypes.windll.user32
shell32 = ctypes.windll.shell32
gdi32   = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

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
SCAN_V = 0x2F
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


def type_string(s, delay=0.006):
    for ch in s:
        _uni(ch, False)
        _uni(ch, True)
        time.sleep(delay)


def key_ctrl_a():
    _key(SCAN_LCTRL, False)
    _key(SCAN_A, False)
    _key(SCAN_A, True)
    _key(SCAN_LCTRL, True)


def tap(scan, hold=0.02):
    _key(scan, False)
    time.sleep(hold)
    _key(scan, True)


CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]


def set_clipboard(text):
    data = text.encode("utf-16-le") + b"\x00\x00"
    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not h:
        return
    p = kernel32.GlobalLock(h)
    if not p:
        return
    ctypes.memmove(p, data, len(data))
    kernel32.GlobalUnlock(h)
    if user32.OpenClipboard(0):
        user32.EmptyClipboard()
        user32.SetClipboardData(CF_UNICODETEXT, h)
        user32.CloseClipboard()


def paste():
    _key(SCAN_LCTRL, False)
    _key(SCAN_V, False)
    time.sleep(0.02)
    _key(SCAN_V, True)
    _key(SCAN_LCTRL, True)


def focus_roblox():
    # bring the Roblox window to the front so chat keys land in the game,
    # not in our own textbox.
    try:
        hwnd = user32.FindWindowW(None, ROBLOX_TITLE)
        if not hwnd:
            return False
        fg = user32.GetForegroundWindow()
        t1 = user32.GetWindowThreadProcessId(fg, None)
        t2 = user32.GetWindowThreadProcessId(hwnd, None)
        if t1 != t2:
            user32.AttachThreadInput(t1, t2, True)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
            user32.AttachThreadInput(t1, t2, False)
        else:
            user32.SetForegroundWindow(hwnd)
        time.sleep(0.05)
        return True
    except Exception:
        return False


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


def is_ore_cursor(h, baseline):
    # if the user calibrated the exact mine cursor, match it precisely;
    # otherwise fall back to "cursor changed from the neutral one".
    oc = state.get("ore_cursor")
    if oc:
        return bool(h) and h == oc
    return bool(h) and bool(baseline) and h != baseline


def lighten(hexc, f=1.18):
    try:
        hexc = hexc.lstrip("#")
        r = min(255, int(int(hexc[0:2], 16) * f))
        g = min(255, int(int(hexc[2:4], 16) * f))
        b = min(255, int(int(hexc[4:6], 16) * f))
        return "#%02x%02x%02x" % (r, g, b)
    except Exception:
        return "#" + hexc


def add_glow(w):
    # cheap hover "glow": brighten the button while the pointer is over it.
    def on_enter(_):
        if not state.get("glow", True):
            return
        try:
            w._g = w.cget("bg")
            w.config(bg=lighten(w._g, 1.18))
        except Exception:
            pass

    def on_leave(_):
        try:
            if getattr(w, "_g", None):
                w.config(bg=w._g)
        except Exception:
            pass

    w.bind("<Enter>", on_enter, add="+")
    w.bind("<Leave>", on_leave, add="+")
    return w


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
VERSION = "v1.3"

state = {
    "running": False, "quit": False, "go_busy": False, "rejoining": False,
    "hold": LEVELS[DEFAULT_LEVEL][1], "center": None,
    "deeplink": "",
    "auto_vote": False, "vote_interval": 60.0,
    "vote_admin": None, "vote_button": None, "vote_w": None, "vote_h": None,
    "auto_walk": False, "disc_detect": True,
    "auto_pay": False, "pay_host": "", "mine_count": 0,
    "ore_cursor": None, "kb_mine": "f2", "glow": True,
    "show": {}, "compact": False,
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
        state["glow"] = bool(c.get("glow", True))
        state["kb_mine"] = c.get("kb_mine", "f2") or "f2"
        state["show"] = c.get("show", {}) or {}
        state["compact"] = bool(c.get("compact", False))
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
             "pay_host": state["pay_host"],
             "glow": state["glow"], "kb_mine": state["kb_mine"],
             "show": state["show"], "compact": state["compact"]}
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(c, f)
    except Exception:
        pass


# ---- chat / pay ----
def send_chat(msg):
    focus_roblox()                      # so it types into the game, not our UI
    tap(SCAN_SEMI)                      # press ; to open the chat box
    time.sleep(0.25)
    for _ in range(CHAT_BACKSPACES):    # clear the box
        tap(SCAN_BACK, 0.004)
        time.sleep(0.003)
    time.sleep(0.04)
    set_clipboard(msg)                  # paste instead of typing (fast)
    paste()
    time.sleep(0.08)
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
                    if is_ore_cursor(h, baseline):
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
                if is_ore_cursor(hc, baseline):
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
    root.overrideredirect(True)
    root.configure(bg=BG)
    status = tk.StringVar(value="ready - press Start")
    ui["root"] = root
    ui["status"] = status

    def L(parent, text, fg=FG, size=8, bold=False, bgc=CARD):
        return tk.Label(parent, text=text, fg=fg, bg=bgc,
                        font=("Segoe UI", size, "bold" if bold else "normal"))

    def B(parent, text, cmd, bg=ACCENT, fg="#1a1320"):
        return add_glow(tk.Button(parent, text=text, command=cmd, bg=ACCENT, fg=fg,
                        activebackground=ACCENT, activeforeground=fg, relief="flat",
                        bd=0, font=("Segoe UI", 8, "bold"), cursor="hand2",
                        padx=6, pady=3))

    def E(parent, var, show=None, width=22):
        return tk.Entry(parent, textvariable=var, width=width, show=show,
                        bg=ENTRY, fg=FG, insertbackground=FG, relief="flat",
                        font=("Segoe UI", 8))

    def C(parent, text, var, cmd):
        return tk.Checkbutton(parent, text=text, variable=var, command=cmd,
                              bg=CARD, fg=FG, selectcolor=ENTRY, relief="flat",
                              activebackground=CARD, activeforeground=FG,
                              font=("Segoe UI", 8))

    # ---------- custom title bar ----------
    def _start_move(e):
        root._dx, root._dy = e.x, e.y

    def _do_move(e):
        root.geometry("+%d+%d" % (root.winfo_pointerx() - root._dx,
                                  root.winfo_pointery() - root._dy))

    def _minimize():
        root.overrideredirect(False)
        root.iconify()

    def _restore(_=None):
        root.overrideredirect(True)
        root.attributes("-topmost", True)
    root.bind("<Map>", _restore)

    topbar = tk.Frame(root, bg=CARD)
    topbar.pack(fill="x", side="top")
    tbtitle = tk.Label(topbar, text="Ink's Racro", bg=CARD, fg=ACCENT,
                       font=("Segoe UI", 8, "bold"))
    tbtitle.pack(side="left", padx=(8, 4), pady=2)
    tk.Label(topbar, text=VERSION, bg=CARD, fg=MUTED,
             font=("Segoe UI", 7)).pack(side="left")

    def _ctrl(txt, cmd):
        return add_glow(tk.Button(topbar, text=txt, command=cmd, bg=CARD, fg=MUTED,
                        activebackground=ACCENT, activeforeground="#1a1320",
                        relief="flat", bd=0, font=("Segoe UI", 9), cursor="hand2",
                        padx=8))
    _ctrl("\u2715", lambda: on_close()).pack(side="right")
    _ctrl("\u2013", _minimize).pack(side="right")
    _ctrl("\u2699", lambda: open_settings()).pack(side="right")
    for _w in (topbar, tbtitle):
        _w.bind("<Button-1>", _start_move)
        _w.bind("<B1-Motion>", _do_move)

    # ---------- header ----------
    head = tk.Frame(root, bg=BG)
    head.pack(fill="x", padx=12, pady=(8, 4))
    try:
        logo_full = tk.PhotoImage(data=LOGO_B64)
        try:
            root.iconphoto(True, logo_full)
        except Exception:
            pass
        fct = max(1, logo_full.width() // 64)
        img = logo_full.subsample(fct) if fct > 1 else logo_full
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
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(padx=10, pady=9)
        return outer, inner

    # --- column 1: MINE ---
    c1o, c1 = column()
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

    def calib_cursor():
        def cap():
            state["ore_cursor"] = cursor_handle()
            status.set("ore-cursor locked in!" if state["ore_cursor"]
                       else "couldn't read cursor")

        def cd(n):
            if n > 0:
                status.set("hover the ORE (pickaxe cursor)... %d" % n)
                root.after(1000, lambda: cd(n - 1))
            else:
                cap()
        cd(3)

    B(c1, "Calibrate ore-cursor", calib_cursor).pack(fill="x", pady=(4, 0))
    L(c1, "Lock the exact pickaxe\ncursor for reliable finds.\nF2 = start / stop.",
      MUTED, 7).pack(anchor="w", pady=(6, 0))

    # --- column 2: REJOIN ---
    c2o, c2 = column()
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
    c3o, c3 = column()
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

    # ---------- layout / compact ----------
    def relayout():
        for o in (c1o, c2o, c3o):
            o.pack_forget()
        c1o.pack(side="left", padx=5, anchor="n")
        if state["show"].get("rejoin", True):
            c2o.pack(side="left", padx=5, anchor="n")
        if state["show"].get("votepay", True):
            c3o.pack(side="left", padx=5, anchor="n")

    # ---------- hotkey ----------
    def f2_toggle():
        if state["running"]:
            state["running"] = False
            try:
                _send(MOUSEEVENTF_LEFTUP)
            except Exception:
                pass
            set_status("stopped (hotkey)")
        else:
            state["center"] = cursor_pos()
            state["running"] = True
            set_status("mining - tap hotkey again to STOP")

    hk = {"h": None}

    def register_hotkey():
        if not HAVE_KEYBOARD:
            return
        try:
            if hk["h"] is not None:
                keyboard.remove_hotkey(hk["h"])
        except Exception:
            pass
        try:
            hk["h"] = keyboard.add_hotkey(state["kb_mine"], f2_toggle)
        except Exception:
            hk["h"] = None

    # ---------- settings window ----------
    def open_settings():
        win = tk.Toplevel(root)
        win.title("Racro Settings")
        win.configure(bg=CARD)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        pad = tk.Frame(win, bg=CARD)
        pad.pack(padx=16, pady=14)
        L(pad, "SETTINGS", ACCENT, 11, True).pack(anchor="w", pady=(0, 8))

        L(pad, "Start / stop hotkey", FG, 8, True).pack(anchor="w")
        kb_var = tk.StringVar(value=state["kb_mine"])
        krow = tk.Frame(pad, bg=CARD)
        krow.pack(anchor="w", pady=(2, 0))
        E(krow, kb_var, width=12).pack(side="left")

        def apply_kb():
            k = kb_var.get().strip().lower() or "f2"
            state["kb_mine"] = k
            save_config()
            register_hotkey()
            status.set("hotkey set to " + k)
        B(krow, "Apply", apply_kb).pack(side="left", padx=6)
        L(pad, "e.g. f2 - f4 - ctrl+m - num 0", MUTED, 7).pack(anchor="w")
        if not HAVE_KEYBOARD:
            L(pad, "install 'keyboard' for hotkeys", RED, 7).pack(anchor="w")

        glow_var = tk.BooleanVar(value=state["glow"])

        def on_glow():
            state["glow"] = glow_var.get()
            save_config()
        C(pad, "Glow effect on hover", glow_var, on_glow).pack(anchor="w", pady=(10, 2))

        L(pad, "Show sections (compact)", FG, 8, True).pack(anchor="w", pady=(8, 0))
        rj_var = tk.BooleanVar(value=state["show"].get("rejoin", True))
        vp_var = tk.BooleanVar(value=state["show"].get("votepay", True))

        def on_show():
            state["show"]["rejoin"] = rj_var.get()
            state["show"]["votepay"] = vp_var.get()
            save_config()
            relayout()
        C(pad, "Auto-Rejoin", rj_var, on_show).pack(anchor="w")
        C(pad, "Vote & Pay", vp_var, on_show).pack(anchor="w")

        B(pad, "Close", win.destroy).pack(anchor="e", pady=(12, 0))

    relayout()
    update_warn()
    register_hotkey()

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
