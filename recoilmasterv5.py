import os
import sys
import asyncio
import threading
import ctypes
import time
import random
import tkinter as tk
from tkinter import filedialog

from pynput import mouse, keyboard
from PyQt5 import QtWidgets, QtGui, QtCore
from screeninfo import get_monitors
import websockets
import webview
import base64
import tempfile

import winreg

# ---------------- Config ----------------
the_url = 'https://kindpump.github.io/RecoilMaster/adplayer.html'

# ---------------- File Save Function and COLOR setter ----------------
def save_text_file(data):
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        initialfile="my_V5config.txt",
        filetypes=[("Text files", "*.txt")]
    )
    if file_path:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(data)
        print(f"Message saved to {file_path}")
    else:
        print("Save cancelled")

def hex_to_bgr(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 8:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        # Alpha is hex_color[6:8], ignored for accent color
    elif len(hex_color) == 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    else:
        raise ValueError("Hex color must be 6 or 8 characters, like '#RRGGBB' or '#RRGGBBAA'")
    return b, g, r

def show_overlay(msg, duration=500):
    root = tk.Tk()
    root.overrideredirect(True)        # no title bar
    root.attributes("-topmost", True)  # always on top
    root.attributes("-alpha", 0.85)    # slightly transparent

    label = tk.Label(
        root,
        text=msg,
        font=("Calibri", 12),  # font family, size, style
        bg="black",
        fg="white"
        
    )
    label.pack(ipadx=10, ipady=5)

    # place near the top-center
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    # 50 pixels down from top
    root.geometry(f"{w}x{h}+{(sw - w)//2}+50")

    # close after `duration` ms
    root.after(duration, root.destroy)
    root.mainloop()



def set_windows_accent_color_hex(hex_color):
    b, g, r = hex_to_bgr(hex_color)
    color_dword = (b << 16) | (g << 8) | r

    key_path = r"Software\Microsoft\Windows\DWM"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "AccentColor", 0, winreg.REG_DWORD, color_dword)

    key_path2 = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path2, 0, winreg.KEY_SET_VALUE) as key2:
            winreg.SetValueEx(key2, "AccentColorMenu", 0, winreg.REG_DWORD, color_dword)
    except FileNotFoundError:
        pass

    # Force Windows to refresh accent color
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "ImmersiveColorSet", 0x2, 500)
# ---------------- PyQt Overlay ----------------
class TransparentOverlay(QtWidgets.QWidget):
    def __init__(self, image_path, opacity, grayscale, size_percent):
        super().__init__()
        self.anim = None

        original_image = None
        temp_file_path = None

        if len(image_path) > 100 and not os.path.exists(image_path):
            try:
                clean_b64 = ''.join(image_path.strip().splitlines()).replace('\r', '').replace('\n', '')
                padded_b64 = clean_b64 + '=' * ((4 - len(clean_b64) % 4) % 4)
                img_bytes = base64.b64decode(padded_b64)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                temp_file.write(img_bytes)
                temp_file.close()
                temp_file_path = temp_file.name
                image_path = temp_file_path
            except Exception as e:
                print("[ERROR] Failed to decode and write base64 image:", e)

        original_image = QtGui.QPixmap(image_path)
        if original_image.isNull():
            raise ValueError("Failed to load image from input (base64 or file path).")

        if grayscale:
            image = original_image.toImage().convertToFormat(QtGui.QImage.Format_ARGB32)
            original_image = QtGui.QPixmap.fromImage(image)

        self.opacity = max(0.0, min(opacity, 1.0))

        monitor = next((m for m in get_monitors() if m.is_primary), get_monitors()[0])
        screen_x = monitor.x
        screen_y = monitor.y
        screen_w = monitor.width
        screen_h = monitor.height

        if grayscale:
            new_width = int(original_image.width() * (size_percent / 100))
            new_height = int(original_image.height() * (size_percent / 100))
            self.image = original_image.scaled(new_width, new_height, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            x = screen_w // 2 - self.image.width() // 2
            y = screen_h // 2 - self.image.height() // 2
            self.setGeometry(screen_x + x, screen_y + y, self.image.width(), self.image.height())
            self.setFixedSize(self.image.width(), self.image.height())
        else:
            self.image = original_image
            self.setGeometry(screen_x, screen_y, self.image.width(), self.image.height())
            self.setFixedSize(self.image.width(), self.image.height())

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool |
            QtCore.Qt.WindowTransparentForInput
        )

        self.setWindowOpacity(0.0)
        self.show()
        self.fade_in()

        if temp_file_path:
            QtCore.QTimer.singleShot(5000, lambda: os.remove(temp_file_path))

    def fade_in(self):
        self.anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(500)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(self.opacity)
        self.anim.start()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setOpacity(1.0)
        painter.drawPixmap(0, 0, self.image)

# ---------------- Main Logic ----------------
def run():
    
    #for the crouch spammer:
    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    VK_C = 0x43  # virtual key for 'C'
    SC_C = 0x2E  # hardware scan code for 'C' key
    KEYEVENTF_SCANCODE = 0x0008  # just in case engine expects scancode flag
    VK_K = 0x4B  # virtual key for 'K'
    
    #for rapid fire:
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP   = 0x0004
    rapid_fire_enabled = 0

    variable1 = 0
    variable2 = 0
    variable3 = 0
    variable4 = 0
    variable5 = 0
    variable6 = 0

    color = 1.0
    grayscale = False
    size_percent = 100
    png = "crosshair007.png"

    primaryHotkey = '1'
    secondaryHotkey = '2'
    pause_key = 'p'
    crouch_key = 'k'

    holding = False
    left_held = False
    right_held = False

    paused = False
    pause_lock = threading.Lock()
    ws_client = None
    ws_lock = threading.Lock()
    loop = asyncio.new_event_loop()
    weapon = 1

    qt_app = None
    overlay_widget = None
    overlay_thread = None


    def hotkeys_set(data):
        nonlocal primaryHotkey, secondaryHotkey, pause_key, crouch_key
        pause_key = str(data[4])
        primaryHotkey = str(data[5])
        secondaryHotkey = str(data[6])
        crouch_key = str(data[7])

    def move_mouse(dx, dy):
        ctypes.windll.user32.mouse_event(0x0001, int(dx), int(dy), 0, 0)
    
    def recoil_control():
        nonlocal paused
        nonlocal weapon
        while True:
            if weapon == 1:
                with pause_lock:
                    if holding and not paused:
                        dx = variable2 if random.random() < 0.5 else 0
                        move_mouse(dx, variable3)
                time.sleep(variable1)
            else:
                with pause_lock:
                    if holding and not paused:
                        dx = variable5 if random.random() < 0.5 else 0
                        move_mouse(dx, variable6)
                time.sleep(variable4)

    def on_click(x, y, button, pressed):
        nonlocal left_held, right_held, holding
        if button == mouse.Button.left:
            left_held = pressed
        elif button == mouse.Button.right:
            right_held = pressed
            time.sleep(0.02)
        holding = left_held and right_held

    def send_ws_message_threadsafe(message):
        asyncio.run_coroutine_threadsafe(_send_ws_message(message), loop)

    async def _send_ws_message(message):
        nonlocal ws_client
        try:
            if ws_client:
                await ws_client.send(message)
                print(f"Sent message: {message}")
        except Exception as e:
            print(f"WebSocket send error: {e}")

    def on_release(key):
        nonlocal paused
        nonlocal weapon
        try:
            if key.char == primaryHotkey:
                print("Primary hotkey pressed")
                weapon = 1
                #show_overlay(msg=f"Switched to Primary, Rapid Fire:{rapid_fire==weapon}")
            elif key.char == secondaryHotkey:
                print("Secondary hotkey pressed")
                weapon = 2
                #show_overlay(msg=f"Switched to Secondary, Rapid Fire:{rapid_fire==weapon}")
            elif key.char == pause_key:
                with pause_lock:
                    paused = not paused
                    print("Paused" if paused else "Resumed")
                    send_ws_message_threadsafe("Paused" if paused else "Resumed")
        except AttributeError:
            pass

    def show_crosshair(new_color, new_grayscale, new_size_percent, new_png):
        nonlocal qt_app, overlay_widget

        def start_overlay():
            nonlocal qt_app, overlay_widget
            qt_app = QtWidgets.QApplication([])
            overlay_widget = TransparentOverlay(new_png, new_color, new_grayscale, new_size_percent)
            qt_app.exec_()

        nonlocal overlay_thread
        if overlay_thread and overlay_thread.is_alive():
            if overlay_widget:
                overlay_widget.close()
                overlay_widget = None
            QtWidgets.QApplication.quit()
            overlay_thread.join()
            qt_app = None

        overlay_thread = threading.Thread(target=start_overlay, daemon=True)
        overlay_thread.start()

    async def handler(websocket):
        nonlocal variable1, variable2, variable3, variable4, variable5, variable6, paused, ws_client
        nonlocal color, grayscale, size_percent, png
        nonlocal overlay_widget
        nonlocal weapon
        nonlocal rapid_fire_enabled

        print("Client connected to WebSocket")
        with ws_lock:
            ws_client = websocket
        try:
            async for message in websocket:
                print(f"Received: {message}")
                if message.startswith("^^^"):
                    try:
                        save_text_file(message)
                        await websocket.send("Message saved successfully.")
                    except Exception as e:
                        print(f"Failed to save message: {e}")
                        await websocket.send("Error saving message.")
                    
                if message.startswith("&WEP&1"):
                    try:
                        weapon = 1
                        #show_overlay(msg=f"Switched to Primary, Rapid Fire:{rapid_fire==weapon}")
                    except Exception as e:
                        print(f"Failed to update weapon#: {e}")
                
                elif message.startswith("&WEP&2"):
                    try:
                        weapon = 2
                        #show_overlay(msg=f"Switched to Secondary, Rapid Fire:{rapid_fire==weapon}")
                    except Exception as e:
                        print(f"Failed to update weapon#: {e}")
                elif message.startswith(">"):
                    try:
                        parts = message[1:].split(',')
                        color = float(parts[0])
                        grayscale = bool(int(float(parts[1])))
                        size_percent = float(parts[2])
                        png = parts[3]
                        show_crosshair(color, grayscale, size_percent, png)
                    except Exception as e:
                        print(f"Failed to update crosshair: {e}")

                elif message.startswith("<"):
                    if overlay_widget:
                        overlay_widget.close()
                        overlay_widget = None
                        await websocket.send("Crosshair deactivated")
                    else:
                        await websocket.send("No crosshair active")


                elif message.startswith("HKEY"):
                    try:
                        hotkeys_set(message)
                        await websocket.send("Hotkey changes saved successfully.")
                    except Exception as e:
                        print(f"Failed to change hotkeys: {e}")
                        await websocket.send("Error editing hotkeys.")
                elif message.startswith("#"):
                    try:
                        set_windows_accent_color_hex(message)
                        print("Accent color changed.")
                    except Exception as e:
                        print(f"Failed to change win color: {e}")
                elif message == "sudoku":
                    try:
                        sys.exit()
                    except Exception as e:
                        print("bro I've been coding for 6...7... hours im boutta crash out")
                else:
                    try:
                        new_var1, new_var2, new_var3, new_var4, new_var5, new_var6, temprapidfileenabled = map(float, message.split(','))
                        with pause_lock:
                            variable1 = new_var1
                            variable2 = new_var2
                            variable3 = new_var3
                            variable4 = new_var4
                            variable5 = new_var5
                            variable6 = new_var6
                            rapid_fire_enabled = temprapidfileenabled
                            paused = False
                        print(f"Updated Variables -> WEP1: Speed: {variable1}, X: {variable2}, Y: {variable3}, WEP2: Speed: {variable4}, X: {variable5}, Y: {variable6}")
                        await websocket.send(f"Settings updated to: {message}")
                    except ValueError:
                        print("Invalid message format")
                        await websocket.send("Error: Invalid format. Use format like '5,7,13'.")
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket client disconnected")
        finally:
            with ws_lock:
                ws_client = None

    async def websocket_server():
        async with websockets.serve(handler, "localhost", 6741):
            print("WebSocket server listening on ws://localhost:6741")
            await asyncio.Future()

    def start_websocket_server():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(websocket_server())

    def crouch_listener():
            #for def(crouchspammer) or whatever its called:
        while True:
            VK_K = ord(crouch_key.upper())
            if key_down(VK_K):
                press_c()
                time.sleep(random.uniform(0.01, 0.03))
    
    def key_down(vk):
        nonlocal user32
        return (user32.GetAsyncKeyState(vk) & 0x8000) != 0
        
        
    def press_c():
        nonlocal user32, VK_C, SC_C, KEYEVENTF_KEYUP
        # Press
        user32.keybd_event(VK_C, SC_C, 0, 0)
        # Release
        time.sleep(0.02)
        user32.keybd_event(VK_C, SC_C, KEYEVENTF_KEYUP, 0)

    def rapid_fire():
        nonlocal weapon
        nonlocal holding
        #basically if rapidfireenabled = 1 its on for primary, if its 2 its on for secondary, if it's 0 its off
        print("Hold K to spam left mouse clicks every 0.08s. Ctrl+C to quit.")
        while True:
            if rapid_fire_enabled == weapon and holding:
                time.sleep(0.001)
                while key_down(MOUSEEVENTF_LEFTDOWN):
                    click_mouse()
                    time.sleep(random.uniform(0.011, 0.023))   # interval between clicks
            else:
                time.sleep(0.1)
    
    def click_mouse():
        nonlocal user32, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTDOWN
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.015)
        user32.mouse_event(MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)



    def start_all_threads():
        threading.Thread(target=recoil_control, daemon=True).start()
        threading.Thread(target=start_websocket_server, daemon=True).start()
        threading.Thread(target=crouch_listener, daemon=True).start()
        threading.Thread(target=rapid_fire, daemon=True).start()
        mouse.Listener(on_click=on_click).start()

        def keyboard_thread():
            with keyboard.Listener(on_release=on_release) as listener:
                listener.join()
        threading.Thread(target=keyboard_thread, daemon=True).start()

    return start_all_threads

# ---------------- Start Everything ----------------
if __name__ == "__main__":
    logic_thread = threading.Thread(target=run(), daemon=True)
    logic_thread.start()

    webview.create_window(
        '𝐑𝐞𝐜𝐨𝐢𝐥 𝐌𝐚𝐬𝐭𝐞𝐫 𝐕𝟓 – 𝐂𝐥𝐢𝐞𝐧𝐭',
        the_url,
        width=960,
        height=570
    )
    webview.start()