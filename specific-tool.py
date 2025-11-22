import customtkinter as ctk
import threading
import time
import json
import os
import sys
import struct
import ctypes
import hid
import winreg
import shutil
import tempfile
import psutil       # Modern Process Yönetimi
import win32gui     # Modern Pencere Yönetimi
import win32process # Modern PID Yönetimi
import atexit       # ADDED: For safe sensitivity reset
from typing import Dict # ADDED: For type hinting
from PIL import Image, ImageDraw

# =============================================================================
# DESIGN SYSTEM (High-End Minimalist)
# =============================================================================
COLOR_BG = "#121212"          # Deep Matte Black
COLOR_SURFACE = "#1E1E1E"     # Dark Grey Cards
COLOR_ACCENT = "#E0E0E0"      # Soft White (Active)
COLOR_TEXT_PRI = "#FFFFFF"    # Primary Text
COLOR_TEXT_SEC = "#757575"    # Secondary Text
COLOR_CRITICAL = "#FF3B30"    # Subtle Red
COLOR_SUCCESS = "#34C759"     # Subtle Green (Status)

FONT_HEADER = ("Roboto", 24, "bold")
FONT_SUBHEAD = ("Roboto", 18, "bold")
FONT_BODY = ("Roboto", 14)
FONT_SMALL = ("Roboto", 12)

# =============================================================================
# ICON GENERATOR
# =============================================================================
def setup_custom_icon(window_instance):
    try:
        size = 64
        img = Image.new('RGB', (size, size), color=(18, 18, 18)) # Match BG
        draw = ImageDraw.Draw(img)
        white = (224, 224, 224) # Match Accent
        # Kaomoji Face (Restored)
        draw.rectangle([10, 28, 25, 32], fill=white) # Left Eye
        draw.rectangle([39, 28, 54, 32], fill=white) # Right Eye
        draw.rectangle([18, 48, 46, 52], fill=white) # Mouth
        
        temp_dir = tempfile.gettempdir()
        icon_path = os.path.join(temp_dir, "specific_kaomoji.ico")
        img.save(icon_path, format='ICO', sizes=[(64, 64)])
        window_instance.iconbitmap(icon_path)
    except: pass

# =============================================================================
# BACKEND CLASSES
# =============================================================================
class ProcessMonitor:
    def __init__(self): pass
    def get_active_exe(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd: return ""
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid <= 0: return ""
            process = psutil.Process(pid)
            return process.name().lower()
        except: return ""

class WindowsMouse:
    """
    Manages Windows mouse sensitivity settings via the win32 API.
    Implements 'Murqin Mode' logic: High Hardware DPI + Low Windows Sensitivity
    to achieve lower input latency and jitter while maintaining effective cursor speed.
    """

    SENSITIVITY_MAP: Dict[int, float] = {
        1: 0.03125, 2: 0.0625, 3: 0.125, 4: 0.25, 5: 0.375,
        6: 0.5,     7: 0.625,  8: 0.75,  9: 0.875, 10: 1.0,
        11: 1.25,   12: 1.5,   13: 1.75, 14: 2.0,  15: 2.25,
        16: 2.5,    17: 2.75,  18: 3.0,  19: 3.25, 20: 3.5
    }

    def __init__(self):
        self._user32 = ctypes.windll.user32
        self.SPI_GETMOUSESPEED = 0x0070
        self.SPI_SETMOUSESPEED = 0x0071
        self.SPIF_UPDATEINIFILE = 0x01
        self.SPIF_SENDCHANGE = 0x02
        
        self._default_speed: int = self.get_current_speed()
        atexit.register(self.reset_to_default)

    def get_current_speed(self) -> int:
        speed = ctypes.c_int()
        self._user32.SystemParametersInfoW(self.SPI_GETMOUSESPEED, 0, ctypes.byref(speed), 0)
        return speed.value

    def set_speed(self, speed_index: int):
        valid_index = max(1, min(20, int(speed_index)))
        try:
            self._user32.SystemParametersInfoW(
                self.SPI_SETMOUSESPEED, 
                0, 
                ctypes.c_void_p(valid_index), 
                self.SPIF_UPDATEINIFILE | self.SPIF_SENDCHANGE
            )
        except: pass

    def reset_to_default(self):
        self.set_speed(self._default_speed)

    def calculate_ideal_index(self, base_dpi: int, target_dpi: int, base_index: int = 10) -> int:
        if base_index not in self.SENSITIVITY_MAP: base_index = 10
        base_multiplier = self.SENSITIVITY_MAP[base_index]
        required_multiplier = (base_dpi * base_multiplier) / target_dpi
        closest_index = min(
            self.SENSITIVITY_MAP.keys(), 
            key=lambda k: abs(self.SENSITIVITY_MAP[k] - required_multiplier)
        )
        return closest_index

    def apply_murqin_optimization(self, base_dpi: int, current_hardware_dpi: int):
        ideal_index = self.calculate_ideal_index(base_dpi, current_hardware_dpi)
        self.set_speed(ideal_index)

class AppManager:
    def __init__(self):
        self.app_name = "SpecificHub"
        self.folder_name = "SpecificHub"
        self.appdata_dir = os.path.join(os.getenv('APPDATA'), self.folder_name)
        if getattr(sys, 'frozen', False):
            self.exe_name = os.path.basename(sys.executable)
            self.current_path = sys.executable
        else:
            self.exe_name = "SpecificHub.exe"
            self.current_path = os.path.abspath(sys.argv[0])
        self.target_path = os.path.join(self.appdata_dir, self.exe_name)
        self.reg_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    def ensure_installed(self):
        if getattr(sys, 'frozen', False):
            try:
                if not os.path.exists(self.appdata_dir): os.makedirs(self.appdata_dir)
                if self.current_path.lower() != self.target_path.lower(): shutil.copy2(self.current_path, self.target_path)
            except: pass
    def is_startup_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, self.app_name)
            winreg.CloseKey(key)
            return val.lower() == f'"{self.target_path}"'.lower()
        except: return False
    def set_startup(self, enable=True):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_key, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                cmd = f'"{self.target_path}"'
                winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, cmd)
            else: winreg.DeleteValue(key, self.app_name)
            winreg.CloseKey(key)
            return True
        except: return False

class NvidiaBackend:
    def __init__(self):
        self._nvapi = None
        self._handles = []
        self.available = False
        try:
            sys_root = os.environ.get('SystemRoot', 'C:\\Windows')
            bits = struct.calcsize("P") * 8
            if bits == 32:
                dll_path = os.path.join(sys_root, 'System32', 'nvapi.dll')
                self._functype = ctypes.WINFUNCTYPE 
            else:
                dll_path = os.path.join(sys_root, 'System32', 'nvapi64.dll')
                self._functype = ctypes.CFUNCTYPE
            if os.path.exists(dll_path):
                self._nvapi = ctypes.windll.LoadLibrary(dll_path)
                self._nvapi_query_interface = self._nvapi.nvapi_QueryInterface
                self._nvapi_query_interface.restype = ctypes.c_void_p
                self._nvapi_query_interface.argtypes = [ctypes.c_int]
                init_func = self._get_func(0x0150E828, [])
                self._enum_display = self._get_func(0x9ABDD40D, [ctypes.c_int, ctypes.POINTER(ctypes.c_int)])
                self._set_dvc = self._get_func(0x172409B4, [ctypes.c_int, ctypes.c_int, ctypes.c_int])
                if init_func and init_func() == 0:
                    self._find_displays()
                    self.available = True
        except: pass
    def _get_func(self, id, arg_types):
        if not self._nvapi: return None
        addr = self._nvapi_query_interface(id)
        if not addr: return None
        proto = self._functype(ctypes.c_int, *arg_types)
        return proto(addr)
    def _find_displays(self):
        self._handles = []
        for i in range(10):
            handle = ctypes.c_int(0)
            if self._enum_display and self._enum_display(i, ctypes.byref(handle)) == 0: self._handles.append(handle)
            else: break
    def set_vibrance(self, level):
        if not self.available: return
        try:
            centered = level - 50
            val = int(centered * 1.26)
            val = max(-63, min(63, val))
            for h in self._handles: self._set_dvc(h, 0, val)
        except: pass

class MouseBackend:
    def __init__(self):
        self.VENDOR_ID = 0x373B
        self.PRODUCT_ID = 0x1040
        self.device = None
    def connect(self):
        try:
            for d in hid.enumerate(self.VENDOR_ID, self.PRODUCT_ID):
                path = d['path'].decode('utf-8','ignore').lower()
                if "mi_01" in path and "col05" in path:
                    self.device = hid.device()
                    self.device.open_path(d['path'])
                    self.device.set_nonblocking(1)
                    return True
            return False
        except: return False
    def send_cmd(self, data):
        if self.device:
            try: self.device.write(data)
            except: pass
    def send_seq(self, seq):
        if self.device:
            for p in seq:
                # Bus Safety: 0.02s buffer between packets
                try: self.device.write(p); time.sleep(0.02)
                except: pass

CMD_HZ_8000 = [0x08, 0x07, 0x00, 0x00, 0x00, 0x06, 0x40, 0x15, 0x04, 0x51, 0x01, 0x54, 0x00, 0x00, 0x00, 0x00, 0x41]
CMD_HZ_1000 = [0x08, 0x07, 0x00, 0x00, 0x00, 0x06, 0x01, 0x54, 0x04, 0x51, 0x01, 0x54, 0x00, 0x00, 0x00, 0x00, 0x41]
SEQ_DPI_1600 = [[0x08, 0x07, 0x00, 0x00, 0x0c, 0x08, 0x07, 0x07, 0x00, 0x47, 0x1f, 0x1f, 0x00, 0x17, 0x00, 0x00, 0x88],[0x08, 0x07, 0x00, 0x00, 0x14, 0x08, 0x1f, 0x1f, 0x00, 0x17, 0x3f, 0x3f, 0x00, 0xd7, 0x00, 0x00, 0x80],[0x08, 0x07, 0x00, 0x00, 0x1c, 0x08, 0x3f, 0x3f, 0x00, 0xd7, 0x3f, 0x3f, 0x00, 0xd7, 0x00, 0x00, 0x78],[0x08, 0x07, 0x00, 0x00, 0x24, 0x08, 0x3f, 0x3f, 0x00, 0xd7, 0x3f, 0x3f, 0x00, 0xd7, 0x00, 0x00, 0x70]]
SEQ_DPI_800 = [[0x08, 0x07, 0x00, 0x00, 0x0c, 0x08, 0x07, 0x07, 0x00, 0x47, 0x0f, 0x0f, 0x00, 0x37, 0x00, 0x00, 0x88],[0x08, 0x07, 0x00, 0x00, 0x14, 0x08, 0x1f, 0x1f, 0x00, 0x17, 0x3f, 0x3f, 0x00, 0xd7, 0x00, 0x00, 0x80],[0x08, 0x07, 0x00, 0x00, 0x1c, 0x08, 0x3f, 0x3f, 0x00, 0xd7, 0x3f, 0x3f, 0x00, 0xd7, 0x00, 0x00, 0x78],[0x08, 0x07, 0x00, 0x00, 0x24, 0x08, 0x3f, 0x3f, 0x00, 0xd7, 0x3f, 0x3f, 0x00, 0xd7, 0x00, 0x00, 0x70]]

# =============================================================================
# FRONTEND
# =============================================================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.mgr = AppManager()
        self.mgr.ensure_installed()
        self.pm = ProcessMonitor()
        self.win_mouse = WindowsMouse()
        self.config_file = os.path.join(self.mgr.appdata_dir, "settings.json")
        self.games_list = []
        self.running = False
        self.murqin_mode = False
        self.current_state = "unknown"
        self.load_config()
        
        self.nv = NvidiaBackend()
        self.mouse = MouseBackend()
        self.mouse_connected = self.mouse.connect()

        # Global Safety Net
        atexit.register(self.perform_safe_exit)

        self.title("Specific Hub")
        self.geometry("800x600")
        self.resizable(False, False)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue")
        
        try: self.after(200, lambda: setup_custom_icon(self))
        except: pass

        self.setup_ui()
        
        # Automation Thread
        self.thread = threading.Thread(target=self.automation_loop, daemon=True)
        self.thread.start()

    def perform_safe_exit(self):
        """Emergency Exit Protocol."""
        print("\n[System] Safe Exit Triggered: Restoring Defaults...")
        try: self.win_mouse.reset_to_default()
        except: pass

        try:
            if self.mouse_connected:
                self.mouse.send_seq(SEQ_DPI_800)
                time.sleep(0.05)
                self.mouse.send_cmd(CMD_HZ_1000)
                print("[System] Mouse Hardware reset complete.")
        except: pass

        try:
            if self.nv.available:
                try: target = int(self.slider_vib_desk.get())
                except: target = 50 
                self.nv.set_vibrance(target)
        except: pass

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.create_sidebar()
        self.create_main_view()
        self.show_view("Dashboard")

    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=COLOR_BG)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        self.lbl_logo = ctk.CTkLabel(self.sidebar, text="SPECIFIC HUB", font=FONT_HEADER, text_color=COLOR_ACCENT)
        self.lbl_logo.grid(row=0, column=0, padx=20, pady=(30, 40))

        self.btn_dash = self.create_nav_btn("Dashboard", 1)
        self.btn_prof = self.create_nav_btn("Profiles", 2)
        self.btn_sett = self.create_nav_btn("Settings", 3)

        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.status_frame.grid(row=5, column=0, padx=20, pady=20, sticky="ew")
        
        self.create_status_dot("NVIDIA", self.nv.available)
        self.create_status_dot("MOUSE", self.mouse_connected)

    def create_nav_btn(self, text, row):
        btn = ctk.CTkButton(
            self.sidebar, 
            text=text, 
            font=FONT_BODY,
            fg_color="transparent", 
            text_color=COLOR_TEXT_SEC,
            hover_color=COLOR_SURFACE,
            anchor="w",
            height=40,
            command=lambda: self.show_view(text)
        )
        btn.grid(row=row, column=0, padx=10, pady=5, sticky="ew")
        return btn

    def create_status_dot(self, label, active):
        color = COLOR_SUCCESS if active else COLOR_TEXT_SEC
        frame = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        frame.pack(fill="x", pady=2)
        canvas = ctk.CTkCanvas(frame, width=10, height=10, bg=COLOR_BG, highlightthickness=0)
        canvas.pack(side="left", padx=(0, 10))
        canvas.create_oval(2, 2, 8, 8, fill=color, outline="")
        lbl = ctk.CTkLabel(frame, text=label, font=FONT_SMALL, text_color=COLOR_TEXT_SEC)
        lbl.pack(side="left")

    def create_main_view(self):
        self.main_container = ctk.CTkFrame(self, fg_color=COLOR_BG)
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        self.frames = {}
        for ViewName in ["Dashboard", "Profiles", "Settings"]:
            frame = ctk.CTkFrame(self.main_container, fg_color=COLOR_BG)
            frame.grid(row=0, column=0, sticky="nsew")
            self.frames[ViewName] = frame
            
            if ViewName == "Dashboard": self.create_dashboard_content(frame)
            elif ViewName == "Profiles": self.create_profiles_content(frame)
            elif ViewName == "Settings": self.create_settings_content(frame)

    def show_view(self, view_name):
        frame = self.frames[view_name]
        frame.tkraise()
        for btn, name in [(self.btn_dash, "Dashboard"), (self.btn_prof, "Profiles"), (self.btn_sett, "Settings")]:
            if name == view_name:
                btn.configure(text_color=COLOR_ACCENT, fg_color=COLOR_SURFACE)
            else:
                btn.configure(text_color=COLOR_TEXT_SEC, fg_color="transparent")

    def create_dashboard_content(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        container = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, corner_radius=16)
        container.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8, relheight=0.6)

        self.lbl_status = ctk.CTkLabel(container, text="SYSTEM IDLE", font=("Roboto", 32, "bold"), text_color=COLOR_TEXT_SEC)
        self.lbl_status.pack(pady=(60, 20))

        self.btn_toggle = ctk.CTkButton(
            container, 
            text="START AUTOMATION", 
            font=FONT_SUBHEAD,
            width=240, 
            height=50,
            corner_radius=25,
            fg_color=COLOR_ACCENT, 
            text_color=COLOR_BG,
            hover_color="#FFFFFF",
            command=self.toggle_automation
        )
        self.btn_toggle.pack(pady=20)

        self.chk_murqin = ctk.CTkSwitch(
            container, 
            text="Murqin Mode (Input Norm)", 
            font=FONT_BODY,
            progress_color=COLOR_ACCENT, 
            fg_color="#333333",
            button_color="#555555",
            button_hover_color="#777777",
            text_color=COLOR_TEXT_SEC,
            command=self.toggle_murqin
        )
        self.chk_murqin.pack(pady=30)

        self.lbl_debug = ctk.CTkLabel(parent, text="Ready...", font=FONT_SMALL, text_color=COLOR_TEXT_SEC)
        self.lbl_debug.place(relx=0.05, rely=0.95)

    def create_profiles_content(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(parent, text="Game Profiles", font=FONT_HEADER, text_color=COLOR_ACCENT).pack(pady=(40, 20), padx=40, anchor="w")

        card_add = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, corner_radius=16)
        card_add.pack(fill="x", padx=40, pady=10)
        
        self.entry_game = ctk.CTkEntry(card_add, placeholder_text="executable_name.exe", border_width=0, fg_color="#2B2B2B", text_color=COLOR_TEXT_PRI, height=40)
        self.entry_game.pack(side="left", fill="x", expand=True, padx=15, pady=15)
        
        btn_add = ctk.CTkButton(card_add, text="+", width=40, height=40, fg_color=COLOR_ACCENT, text_color=COLOR_BG, hover_color="#FFFFFF", command=self.add_game)
        btn_add.pack(side="left", padx=(0, 10))
        
        btn_run = ctk.CTkButton(card_add, text="Scan Running", height=40, fg_color="#2B2B2B", hover_color="#333333", text_color=COLOR_ACCENT, command=self.open_process_selector)
        btn_run.pack(side="left", padx=(0, 15))

        self.scroll_list = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.scroll_list.pack(fill="both", expand=True, padx=30, pady=10)
        self.update_game_list_ui()

        card_hw = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, corner_radius=16)
        card_hw.pack(fill="x", padx=40, pady=(10, 40))
        
        ctk.CTkLabel(card_hw, text="Active Profile Settings", font=FONT_SUBHEAD, text_color=COLOR_ACCENT).pack(pady=15)
        
        self.lbl_vib_game = ctk.CTkLabel(card_hw, text="Digital Vibrance: 100%", font=FONT_BODY, text_color=COLOR_TEXT_SEC)
        self.lbl_vib_game.pack()
        self.slider_vib_game = ctk.CTkSlider(card_hw, from_=0, to=100, number_of_steps=100, command=self.update_slider_game_live, button_color=COLOR_ACCENT, button_hover_color="#FFFFFF", progress_color=COLOR_ACCENT)
        self.slider_vib_game.set(100)
        self.slider_vib_game.pack(fill="x", padx=40, pady=(5, 20))

    def create_settings_content(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(parent, text="System Settings", font=FONT_HEADER, text_color=COLOR_ACCENT).pack(pady=(40, 20), padx=40, anchor="w")

        card = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, corner_radius=16)
        card.pack(fill="x", padx=40, pady=10)

        self.chk_startup = ctk.CTkSwitch(card, text="Run on Windows Startup", font=FONT_BODY, progress_color=COLOR_ACCENT, fg_color="#333333", command=self.toggle_startup)
        if self.mgr.is_startup_enabled(): self.chk_startup.select()
        self.chk_startup.pack(pady=20, padx=20, anchor="w")

        ctk.CTkLabel(card, text="Desktop Vibrance Level", font=FONT_BODY, text_color=COLOR_TEXT_SEC).pack(padx=20, anchor="w")
        self.lbl_vib_desk = ctk.CTkLabel(card, text="50%", font=FONT_SMALL, text_color=COLOR_TEXT_SEC)
        self.lbl_vib_desk.pack(anchor="e", padx=40)
        
        self.slider_vib_desk = ctk.CTkSlider(card, from_=0, to=100, number_of_steps=100, command=self.update_slider_desk_live, button_color=COLOR_ACCENT, progress_color=COLOR_ACCENT)
        self.slider_vib_desk.set(50)
        self.slider_vib_desk.pack(fill="x", padx=40, pady=(0, 30))

        ctk.CTkButton(parent, text="Open Config Folder", fg_color="transparent", border_width=1, border_color=COLOR_TEXT_SEC, text_color=COLOR_TEXT_SEC, hover_color=COLOR_SURFACE, command=lambda: os.startfile(self.mgr.appdata_dir)).pack(pady=20)

    def update_slider_game_live(self, value):
        val_int = int(value)
        self.lbl_vib_game.configure(text=f"Digital Vibrance: {val_int}%")
        if self.running and self.current_state == "game": self.nv.set_vibrance(val_int)

    def update_slider_desk_live(self, value):
        val_int = int(value)
        self.lbl_vib_desk.configure(text=f"{val_int}%")
        if self.running and self.current_state == "desktop": self.nv.set_vibrance(val_int)

    def toggle_murqin(self): self.murqin_mode = bool(self.chk_murqin.get())
    def toggle_startup(self): self.mgr.set_startup(bool(self.chk_startup.get()))
    
    def add_game(self):
        game = self.entry_game.get().lower().strip()
        if game and game not in self.games_list:
            self.games_list.append(game)
            self.save_config()
            self.update_game_list_ui()
            self.entry_game.delete(0, "end")

    def remove_game(self, game_name):
        if game_name in self.games_list:
            self.games_list.remove(game_name)
            self.save_config()
            self.update_game_list_ui()

    def update_game_list_ui(self):
        for widget in self.scroll_list.winfo_children(): widget.destroy()
        for game in self.games_list:
            row = ctk.CTkFrame(self.scroll_list, fg_color=COLOR_SURFACE, corner_radius=8)
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=game, font=FONT_BODY, text_color=COLOR_TEXT_PRI).pack(side="left", padx=15, pady=10)
            btn_del = ctk.CTkButton(row, text="×", width=30, height=30, fg_color="transparent", hover_color=COLOR_CRITICAL, text_color=COLOR_TEXT_SEC, command=lambda g=game: self.remove_game(g))
            btn_del.pack(side="right", padx=10)

    def open_process_selector(self):
        top = ctk.CTkToplevel(self)
        top.title("Select Process")
        top.geometry("400x500")
        top.attributes("-topmost", True)
        top.configure(fg_color=COLOR_BG)
        try: self.after(200, lambda: setup_custom_icon(top))
        except: pass

        search_frame = ctk.CTkFrame(top, fg_color=COLOR_SURFACE)
        search_frame.pack(fill="x", padx=10, pady=10)
        
        entry = ctk.CTkEntry(search_frame, placeholder_text="Search process...", border_width=0, fg_color="#2B2B2B", text_color=COLOR_TEXT_PRI)
        entry.pack(fill="x", padx=10, pady=10)
        
        scroll = ctk.CTkScrollableFrame(top, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        def load_procs(filter_text=""):
            for w in scroll.winfo_children(): w.destroy()
            procs = sorted(list(set([p.info['name'].lower() for p in psutil.process_iter(['name']) if p.info['name']])))
            for p in procs:
                if filter_text.lower() in p:
                    btn = ctk.CTkButton(scroll, text=p, anchor="w", fg_color="transparent", hover_color=COLOR_SURFACE, text_color=COLOR_TEXT_SEC, height=30, command=lambda n=p: select_proc(n))
                    btn.pack(fill="x")
        
        def select_proc(name):
            self.entry_game.delete(0, "end")
            self.entry_game.insert(0, name)
            self.add_game()
            top.destroy()

        entry.bind("<KeyRelease>", lambda e: load_procs(entry.get()))
        load_procs()

    def load_config(self):
        try:
            with open(self.config_file, "r") as f: self.games_list = json.load(f)
        except: self.games_list = []

    def save_config(self):
        if not os.path.exists(os.path.dirname(self.config_file)): os.makedirs(os.path.dirname(self.config_file))
        with open(self.config_file, "w") as f: json.dump(self.games_list, f)

    def toggle_automation(self):
        self.running = not self.running
        if self.running:
            self.btn_toggle.configure(text="STOP AUTOMATION", fg_color=COLOR_CRITICAL, hover_color="#FF5555")
            self.lbl_status.configure(text="MONITORING...", text_color=COLOR_ACCENT)
        else:
            self.btn_toggle.configure(text="START AUTOMATION", fg_color=COLOR_ACCENT, hover_color="#FFFFFF")
            self.force_desktop_mode()

    def force_desktop_mode(self):
        target_desk = int(self.slider_vib_desk.get())
        self.nv.set_vibrance(target_desk)
        
        # Buffer fix to prevent bus contention
        self.mouse.send_seq(SEQ_DPI_800)
        time.sleep(0.25)
        self.mouse.send_cmd(CMD_HZ_1000)
        
        self.win_mouse.reset_to_default()
        self.lbl_status.configure(text="SYSTEM IDLE", text_color=COLOR_TEXT_SEC)
        self.lbl_debug.configure(text="Automation stopped.")
        self.current_state = "unknown"

    def automation_loop(self):
        # Debounce State
        stable_counter = 0
        REQUIRED_STABLE_FRAMES = 2
        last_exe = ""

        while True:
            if not self.running:
                time.sleep(1)
                continue
            
            try:
                current_exe = self.pm.get_active_exe()
                
                # --- Debounce Logic ---
                # Check if the window focus has changed since last check
                if current_exe != last_exe:
                    stable_counter = 0
                    last_exe = current_exe
                else:
                    stable_counter += 1
                
                # If window hasn't been stable for 2 cycles (approx 1 sec), skip logic
                # This prevents "spamming" commands during rapid Alt-Tab
                if stable_counter < REQUIRED_STABLE_FRAMES:
                    time.sleep(0.5)
                    continue
                # ----------------------

                is_game = any(game in current_exe for game in self.games_list)
                
                if is_game:
                    if self.current_state != "game":
                        val = int(self.slider_vib_game.get())
                        self.nv.set_vibrance(val)
                        
                        self.mouse.send_seq(SEQ_DPI_1600)
                        time.sleep(0.25) # WAIT FOR DPI WRITE
                        self.mouse.send_cmd(CMD_HZ_8000)
                        
                        mode_text = "GAME MODE ACTIVE"
                        if self.murqin_mode:
                            self.win_mouse.apply_murqin_optimization(base_dpi=800, current_hardware_dpi=1600)
                            mode_text += " (MURQIN)"
                        
                        self.lbl_status.configure(text=mode_text, text_color=COLOR_SUCCESS)
                        self.current_state = "game"
                else:
                    if self.current_state != "desktop":
                        val = int(self.slider_vib_desk.get())
                        self.nv.set_vibrance(val)
                        
                        self.mouse.send_seq(SEQ_DPI_800)
                        time.sleep(0.25) # WAIT FOR DPI WRITE
                        self.mouse.send_cmd(CMD_HZ_1000)
                        
                        self.win_mouse.reset_to_default()
                        
                        self.lbl_status.configure(text="DESKTOP MODE", text_color=COLOR_ACCENT)
                        self.current_state = "desktop"
            except: pass
            
            # Faster polling rate for smoother UI update, relied on stable_counter for logic
            time.sleep(0.5)

if __name__ == "__main__":
    app = App()
    app.mainloop()