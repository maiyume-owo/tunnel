import subprocess
import sys
import ctypes
import json
import time
import atexit
import os
import threading
import requests
from plyer import notification
import pystray
from PIL import Image, ImageDraw

PRIMARY_DNS = "8.8.8.8"

running = True
current_proc = None
last_ip = None
notified = False

CREATE_NO_WINDOW = 0x08000000

# ---------------------------
# Auto elevate
# ---------------------------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 0
    )
    sys.exit()

# ---------------------------
# Paths
# ---------------------------
BASE_DIR = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)

CONFIG_PATH = os.path.join(BASE_DIR, "config.conf")
LOG_FILE = os.path.join(BASE_DIR, "singbox.log")
SINGBOX_PATH = os.path.join(BASE_DIR, "sing-box.exe")

CMD = [SINGBOX_PATH, "-c", CONFIG_PATH, "run"]

# ---------------------------
# Logging
# ---------------------------
def reset_log():
    with open(LOG_FILE, "w") as f:
        f.write("=== sing-box log ===\n")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")

# ---------------------------
# Cleanup
# ---------------------------
def kill_orphan():
    subprocess.run(
        ["taskkill", "/f", "/im", "sing-box.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW
    )

def cleanup():
    global current_proc
    if current_proc and current_proc.poll() is None:
        current_proc.kill()

    kill_orphan()
    flush_dns()

atexit.register(cleanup)

# ---------------------------
# DNS
# ---------------------------
def flush_dns():
    subprocess.run(
        ["ipconfig", "/flushdns"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW
    )

def set_dns(interface):
    subprocess.run([
        "netsh", "interface", "ipv4", "set", "dnsservers",
        f"name={interface}",
        "static", PRIMARY_DNS
    ], creationflags=CREATE_NO_WINDOW)

# ---------------------------
# Interface
# ---------------------------
def interface_exists(name):
    result = subprocess.run(
        ["netsh", "interface", "show", "interface"],
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW
    )
    return name.lower() in result.stdout.lower()

def wait_for_interface(name):
    for _ in range(30):
        if interface_exists(name):
            return True
        time.sleep(1)
    return False

# ---------------------------
# Config
# ---------------------------
def get_interface_name():
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)

        def find(obj):
            if isinstance(obj, dict):
                if "interface_name" in obj:
                    return obj["interface_name"]
                for v in obj.values():
                    r = find(v)
                    if r:
                        return r
            elif isinstance(obj, list):
                for i in obj:
                    r = find(i)
                    if r:
                        return r
            return None

        return find(data)
    except:
        return None

# ---------------------------
# Notification
# ---------------------------
def notify(title, msg):
    notification.notify(
        title=title,
        message=msg,
        timeout=3
    )

# ---------------------------
# Connection monitor
# ---------------------------
def get_ip():
    try:
        return requests.get("https://api.ipify.org", timeout=3).text
    except:
        return None

def monitor(icon):
    global last_ip, notified

    while running:
        ip = get_ip()

        if ip != last_ip:
            if ip:
                icon.title = f"Connected: {ip}"
                log(f"CONNECTED {ip}")

                if not notified:
                    notify("Sing-box", f"Connected\nIP: {ip}")
                    notified = True
            else:
                icon.title = "No Internet"
                log("NO INTERNET")
                notified = False

            last_ip = ip

        time.sleep(5)

# ---------------------------
# Tray icon
# ---------------------------
def create_icon():
    img = Image.new("RGB", (64, 64), "#111")
    d = ImageDraw.Draw(img)
    d.ellipse((16, 16, 48, 48), fill="#00ff88")
    return img

def on_exit(icon, item):
    global running
    running = False
    cleanup()
    icon.stop()

# ---------------------------
# Main
# ---------------------------
def main():
    global running, current_proc

    reset_log()
    kill_orphan()
    flush_dns()

    interface = get_interface_name()
    if not interface:
        return

    icon = pystray.Icon(
        "singbox",
        create_icon(),
        "Starting...",
        menu=pystray.Menu(
            pystray.MenuItem("Exit", on_exit)
        )
    )

    def run():
        icon.run()

    threading.Thread(target=run, daemon=True).start()

    while running:
        with open(LOG_FILE, "a") as log_file:
            current_proc = subprocess.Popen(
                CMD,
                stdout=log_file,
                stderr=log_file,
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
            )

        if wait_for_interface(interface):
            set_dns(interface)

        threading.Thread(target=monitor, args=(icon,), daemon=True).start()

        while running:
            if current_proc.poll() is not None:
                break
            time.sleep(1)

        # sing-box died → exit tray too
        running = False
        icon.stop()

# ---------------------------
if __name__ == "__main__":
    main()