import tkinter as tk
from tkinter import filedialog, ttk
import ctypes
from pathlib import Path
import sys
from config import RESOURCE_DIR

class DarkTheme:
    BG_BASE = "#0f172a"
    BG_SURFACE = "#1e293b"
    TEXT_PRIMARY = "#f1f5f9"
    TEXT_SECONDARY = "#94a3b8"
    PRIMARY = "#22c55e"
    PRIMARY_HOVER = "#16a34a"
    BORDER = "#334155"

class SetupWindow:
    def __init__(self):
        # DPI Awareness
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

        self.root = tk.Tk()
        
        # 设置窗口图标
        try:
            icon_path = RESOURCE_DIR / "logo.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

        self.root.withdraw()  # 先隐藏
        self.root.overrideredirect(True)  # 无标题栏
        self.root.configure(bg=DarkTheme.BG_BASE)
        
        # 窗口大小和位置 (增加高度)
        width = 500
        height = 420  # 增加高度从 380 -> 420
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        self.selected_path = None
        self.confirmed = False
        
        self._setup_ui()
        self.root.deiconify()  # 显示窗口

    def _setup_ui(self):
        # 标题栏区域（用于拖拽）
        title_bar = tk.Frame(self.root, bg=DarkTheme.BG_BASE)
        title_bar.pack(fill="x", pady=(0, 10))
        
        # 绑定拖拽事件到标题栏区域
        title_bar.bind("<ButtonPress-1>", self.start_move)
        title_bar.bind("<ButtonRelease-1>", self.stop_move)
        title_bar.bind("<B1-Motion>", self.do_move)
        
        # 主容器
        main_frame = tk.Frame(self.root, bg=DarkTheme.BG_BASE, padx=30, pady=30)
        main_frame.pack(fill="both", expand=True)
        
        # 整个 main_frame 也绑定，但要注意不覆盖子控件
        main_frame.bind("<ButtonPress-1>", self.start_move)
        main_frame.bind("<ButtonRelease-1>", self.stop_move)
        main_frame.bind("<B1-Motion>", self.do_move)
        
        # 关闭按钮 (右上角) - 放在 title_bar 内
        close_btn = tk.Label(
            title_bar, 
            text="✕", 
            bg=DarkTheme.BG_BASE, 
            fg=DarkTheme.TEXT_SECONDARY,
            font=("Segoe UI", 14),
            cursor="hand2"
        )
        close_btn.pack(side="right", padx=10, pady=5)
        close_btn.bind("<Button-1>", lambda e: sys.exit(0))
        close_btn.bind("<Enter>", lambda e: e.widget.config(fg="#ef4444"))
        close_btn.bind("<Leave>", lambda e: e.widget.config(fg=DarkTheme.TEXT_SECONDARY))

        # Logo / Icon - 绑定拖拽
        try:
            from PIL import Image, ImageTk
            logo_path = RESOURCE_DIR / "logo.png"
            if logo_path.exists():
                pil_image = Image.open(str(logo_path))
                # 调整大小
                pil_image = pil_image.resize((100, 100), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_image)
                
                icon_label = tk.Label(
                    main_frame,
                    image=self.logo_img,
                    bg=DarkTheme.BG_BASE
                )
            else:
                # 回退到 Emoji
                icon_label = tk.Label(
                    main_frame,
                    text="🌸",
                    font=("Segoe UI Emoji", 48),
                    bg=DarkTheme.BG_BASE,
                    fg=DarkTheme.TEXT_PRIMARY
                )
        except Exception as e:
            print(f"加载 Logo 失败: {e}")
             # 如果没有 PIL 或出错，回退到 Emoji
            icon_label = tk.Label(
                main_frame,
                text="🌸",
                font=("Segoe UI Emoji", 48),
                bg=DarkTheme.BG_BASE,
                fg=DarkTheme.TEXT_PRIMARY
            )
            
        icon_label.pack(pady=(0, 10))
        icon_label.bind("<ButtonPress-1>", self.start_move)
        icon_label.bind("<ButtonRelease-1>", self.stop_move)
        icon_label.bind("<B1-Motion>", self.do_move)
        
        # 标题 - 绑定拖拽
        title_label = tk.Label(
            main_frame,
            text="欢迎使用 FlowerGame",
            font=("Microsoft YaHei UI", 18, "bold"),
            bg=DarkTheme.BG_BASE,
            fg=DarkTheme.TEXT_PRIMARY
        )
        title_label.pack(pady=(0, 5))
        title_label.bind("<ButtonPress-1>", self.start_move)
        title_label.bind("<ButtonRelease-1>", self.stop_move)
        title_label.bind("<B1-Motion>", self.do_move)
        
        # 副标题 - 绑定拖拽
        subtitle = tk.Label(
            main_frame,
            text="首次启动，请选择游戏数据存储位置",
            font=("Microsoft YaHei UI", 10),
            bg=DarkTheme.BG_BASE,
            fg=DarkTheme.TEXT_SECONDARY
        )
        subtitle.pack(pady=(0, 30))
        subtitle.bind("<ButtonPress-1>", self.start_move)
        subtitle.bind("<ButtonRelease-1>", self.stop_move)
        subtitle.bind("<B1-Motion>", self.do_move)
        
        # 路径显示框
        self.path_var = tk.StringVar()
        self.path_var.set("未选择目录...")
        
        path_frame = tk.Frame(
            main_frame, 
            bg=DarkTheme.BG_SURFACE,
            highlightbackground=DarkTheme.BORDER,
            highlightthickness=1
        )
        path_frame.pack(fill="x", pady=(0, 20), ipady=5)
        
        path_label = tk.Label(
            path_frame,
            textvariable=self.path_var,
            font=("Consolas", 9),
            bg=DarkTheme.BG_SURFACE,
            fg=DarkTheme.TEXT_SECONDARY,
            width=40,
            anchor="w"
        )
        path_label.pack(side="left", padx=10, fill="x", expand=True)
        
        browse_btn = tk.Button(
            path_frame,
            text="浏览...",
            font=("Microsoft YaHei UI", 9),
            bg=DarkTheme.BG_SURFACE,
            fg=DarkTheme.PRIMARY,
            bd=0,
            relief="flat",
            activebackground=DarkTheme.BG_SURFACE,
            activeforeground=DarkTheme.PRIMARY_HOVER,
            cursor="hand2",
            command=self.browse_dir
        )
        browse_btn.pack(side="right", padx=10)
        
        # 确认按钮
        self.confirm_btn = tk.Button(
            main_frame,
            text="开始使用",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=DarkTheme.PRIMARY,
            fg="white",
            bd=0,
            relief="flat",
            activebackground=DarkTheme.PRIMARY_HOVER,
            activeforeground="white",
            cursor="hand2",
            state="disabled",
            command=self.confirm
        )
        self.confirm_btn.pack(fill="x", pady=(10, 0), ipady=5)
        
        # 默认禁用确认按钮样式
        self.confirm_btn.config(bg=DarkTheme.BG_SURFACE, fg=DarkTheme.TEXT_SECONDARY, cursor="arrow")

    def browse_dir(self):
        path = filedialog.askdirectory(
            title="选择 FlowerGame 数据目录",
            initialdir=str(Path.home() / "Desktop")
        )
        if path:
            self.selected_path = Path(path) / "FlowerGame"
            self.path_var.set(str(self.selected_path))
            # 启用确认按钮
            self.confirm_btn.config(
                state="normal",
                bg=DarkTheme.PRIMARY,
                fg="white",
                cursor="hand2"
            )

    def confirm(self):
        if self.selected_path:
            try:
                self.selected_path.mkdir(parents=True, exist_ok=True)
                self.confirmed = True
                self.root.destroy()
            except Exception as e:
                tk.messagebox.showerror("错误", f"无法创建目录: {e}")

    def start_move(self, event):
        self.root.x = event.x
        self.root.y = event.y

    def stop_move(self, event):
        self.root.x = None
        self.root.y = None

    def do_move(self, event):
        # 确保已记录起始位置
        if getattr(self.root, 'x', None) is None or getattr(self.root, 'y', None) is None:
            return
            
        deltax = event.x - self.root.x
        deltay = event.y - self.root.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def run(self):
        self.root.mainloop()
        return self.selected_path if self.confirmed else None

def show_success_dialog(path):
    # 简单的成功提示，也使用深色主题
    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.configure(bg=DarkTheme.BG_BASE)
    
    width, height = 400, 200
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    frame = tk.Frame(root, bg=DarkTheme.BG_BASE, padx=20, pady=20)
    frame.pack(fill="both", expand=True)
    
    tk.Label(
        frame, text="🎉 配置成功！", 
        font=("Microsoft YaHei UI", 16, "bold"),
        bg=DarkTheme.BG_BASE, fg=DarkTheme.PRIMARY
    ).pack(pady=(10, 5))
    
    tk.Label(
        frame, text=f"数据目录已设置为:\n{path}", 
        font=("Microsoft YaHei UI", 9),
        bg=DarkTheme.BG_BASE, fg=DarkTheme.TEXT_SECONDARY,
        wraplength=360
    ).pack(pady=10)
    
    # 2秒后自动关闭
    root.after(2000, root.destroy)
    root.mainloop()
