"""GPT × DeepSeek 桌宠增强版：自主行为状态机 + 散步移动 + 状态气泡 + 互动情绪。"""

from __future__ import annotations

import ctypes
import random
import time
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk


ROOT = Path(__file__).resolve().parent
CELL_W, CELL_H = 192, 208
TRANSPARENT = "#00ff01"

PETS = {
    "Luma · GPT": ROOT / "assets" / "luma-gpt.webp",
    "Mira · DeepSeek": ROOT / "assets" / "mira-deepseek.webp",
}
STATES = {
    "休息": (0, 6),
    "散步": (1, 8),
    "招呼": (3, 4),
    "开心": (4, 5),
    "偷吃": (5, 8),
    "喝水": (6, 6),
    "工作": (7, 6),
    "完成": (8, 6),
}

# 行为状态机：当前状态 -> {可转移状态: 权重}，权重越高越容易被选中
TRANSITIONS: dict[str, dict[str, int]] = {
    "休息": {"休息": 4, "散步": 5, "招呼": 2, "开心": 1, "喝水": 1, "工作": 1},
    "散步": {"散步": 4, "休息": 3, "招呼": 1, "偷吃": 1, "喝水": 1},
    "招呼": {"休息": 2, "散步": 2, "开心": 3, "偷吃": 1},
    "开心": {"休息": 3, "散步": 2, "招呼": 2, "喝水": 1},
    "偷吃": {"休息": 3, "开心": 3, "散步": 1},
    "喝水": {"休息": 4, "散步": 2, "工作": 1},
    "工作": {"工作": 4, "完成": 2, "休息": 2},
    "完成": {"休息": 3, "开心": 3, "散步": 1},
}
# 每个状态最少/最多持续帧数
STATE_DURATION = {
    "休息": (10, 28),
    "散步": (12, 30),
    "招呼": (4, 7),
    "开心": (5, 10),
    "偷吃": (6, 10),
    "喝水": (5, 9),
    "工作": (10, 20),
    "完成": (5, 8),
}
# 散步时的移动速度（像素/帧），散步会从一侧横穿到另一侧
WALK_SPEED = 8
# 状态气泡显示时长（帧）
BUBBLE_FRAMES = 30
# 气泡文案池（按状态触发）
BUBBLES = {
    "招呼": ["嗨，来玩呀～", "今天也要加油！"],
    "开心": ["嘿嘿，好开心！", "你回来啦！", "你戳到我啦～", "摸摸头～"],
    "偷吃": ["唔……好吃！", "就吃一口！"],
    "喝水": ["咕嘟咕嘟～", "补充能量中"],
    "工作": ["写代码中……", "思路清晰！", "好好干活！"],
    "完成": ["搞定啦！", "任务完成！"],
    "休息": ["zzz……", "眯一会儿"],
}


def weighted_choice(options: dict[str, int]) -> str:
    total = sum(options.values())
    pick = random.randint(1, total)
    acc = 0
    for name, weight in options.items():
        acc += weight
        if pick <= acc:
            return name
    return list(options)[0]


class DesktopPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(self.root, width=CELL_W, height=CELL_H, bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.toggle_pet)
        self.canvas.bind("<Button-3>", self.menu)
        self.canvas.bind("<MouseWheel>", self.zoom)
        self.root.bind("<Escape>", lambda _event: self.root.destroy())

        self.pet_index = 0
        self.state_name = "休息"
        self.frame = 0
        self.frames_in_state = 0
        self.state_target = STATE_DURATION[self.state_name][1]
        self.drag_origin = (0, 0)
        self.press_root = (0, 0)
        self.walking = False
        self.walk_dir = 1
        self.check_counter = 0
        self.interact_until = 0.0  # 互动冷却截止时间，期间不被前台检测打扰
        self.zoom_target = 1.0  # 滚轮缩放目标（防抖合并用）
        self.zoom_timer: str | None = None
        self.scale = 1.0
        self.win_size = [CELL_W, CELL_H]
        self.images: dict[str, Image.Image] = {}
        self.photo: ImageTk.PhotoImage | None = None
        self.pet_item: int | None = None
        self.bubble_text: str | None = None
        self.bubble_image: ImageTk.PhotoImage | None = None
        self.bubble_left = 0
        self.load_pet()
        self.place_bottom_right()
        self.tick()

    def place_bottom_right(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        w, h = self.win_size
        self.root.geometry(f"{w}x{h}+{screen_w - w - 28}+{screen_h - h - 60}")

    # ---- 滚轮缩放 ----
    def zoom(self, event: tk.Event) -> None:
        """滚轮缩放：向上滚放大，向下滚缩小。范围 0.4x-3.0x。
        防抖合并：快速滚动时 60ms 内只应用一次窗口变化，避免 DWM 连续 resize 闪黑框。"""
        step = 0.1 if event.delta > 0 else -0.1
        self.zoom_target = round(min(3.0, max(0.4, self.zoom_target + step)), 1)
        if self.zoom_timer is not None:
            self.root.after_cancel(self.zoom_timer)
        self.zoom_timer = self.root.after(60, self.apply_zoom)

    def apply_zoom(self) -> None:
        """真正应用缩放：先渲染新帧 → 改 canvas/窗口尺寸 → 强制同步绘制。"""
        self.zoom_timer = None
        if self.zoom_target == self.scale:
            return
        cx = self.root.winfo_x() + self.win_size[0] / 2
        cy = self.root.winfo_y() + self.win_size[1] / 2
        self.scale = self.zoom_target
        self.win_size = [int(CELL_W * self.scale), int(CELL_H * self.scale)]
        if self.bubble_text:
            self.bubble_image = self.render_bubble(self.bubble_text, self.scale)
        self.draw()  # 先渲染新尺寸帧
        self.canvas.configure(width=self.win_size[0], height=self.win_size[1])
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        nx = max(0, min(int(cx - self.win_size[0] / 2), sw - self.win_size[0]))
        ny = max(0, min(int(cy - self.win_size[1] / 2), sh - self.win_size[1]))
        self.root.geometry(f"{self.win_size[0]}x{self.win_size[1]}+{nx}+{ny}")
        # 强制同步绘制，确保 DWM 合成时窗口已有完整内容（消除黑框窗口期）
        self.root.update_idletasks()
        self.root.update()

    @staticmethod
    def strip_green_edges(image: Image.Image) -> Image.Image:
        """二值化 alpha，彻底消除绿边（返回新图像）：
        - alpha >= 128 的像素置为 255（完全不透明）
        - alpha < 128 的像素置为 0（全透明）
        窗口内不再存在任何半透明像素，因此不会与 #00ff01 透明色背景混合。
        用 LUT 查表实现，比逐像素 Python 循环快数百倍。"""
        r, g, b, a = image.split()
        a = a.point([0] * 128 + [255] * 128)
        return Image.merge("RGBA", (r, g, b, a))

    def render_bubble(self, text: str, scale: float = 1.0) -> ImageTk.PhotoImage:
        """用 PIL 渲染状态气泡（深色圆角底 + 白字），2x 超采样抗锯齿后二值化，
        避免 tkinter 文字与绿色背景混合产生绿边。scale 为桌宠当前缩放比例。"""
        ss = 2  # 超采样倍数（用于抗锯齿）
        font = None
        for font_path in (
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        ):
            try:
                font = ImageFont.truetype(font_path, int(12 * scale * ss))
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()
        bbox = font.getbbox(text)
        pad_x, pad_y = int(6 * scale * ss), int(4 * scale * ss)
        width = bbox[2] - bbox[0] + pad_x * 2
        height = bbox[3] - bbox[1] + pad_y * 2
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            (0, 0, width - 1, height - 1),
            radius=int(6 * scale * ss),
            fill=(40, 46, 66, 255),
            outline=(130, 140, 175, 255),
            width=int(scale * ss),
        )
        draw.text((pad_x - bbox[0], pad_y - bbox[1]), text, font=font, fill=(255, 255, 255, 255))
        img = img.resize((width // ss, height // ss), Image.LANCZOS)
        return ImageTk.PhotoImage(self.strip_green_edges(img))

    def load_pet(self) -> None:
        path = list(PETS.values())[self.pet_index]
        clean = ROOT / "assets" / f"{path.stem}_clean.webp"
        if clean.exists():
            with Image.open(clean) as source:
                self.images["atlas"] = source.convert("RGBA")
        else:
            with Image.open(path) as source:
                atlas = source.convert("RGBA")
            print("首次运行：正在清除精灵边缘，请稍候……", flush=True)
            atlas = self.strip_green_edges(atlas)
            atlas.save(clean, "WEBP", lossless=True)
            self.images["atlas"] = atlas
        self.frame = 0

    def current_cell(self) -> Image.Image:
        row, count = STATES[self.state_name]
        column = self.frame % count
        return self.images["atlas"].crop((column * CELL_W, row * CELL_H, (column + 1) * CELL_W, (row + 1) * CELL_H))

    # ---- 行为状态机 ----
    def next_state(self) -> None:
        options = TRANSITIONS[self.state_name]
        if len(options) == 1 and self.state_name in options:
            return
        new_state = weighted_choice(options)
        self.state_name = new_state
        self.frame = 0
        self.frames_in_state = 0
        self.state_target = random.randint(*STATE_DURATION[new_state])
        self.walking = new_state == "散步"
        if self.walking:
            self.set_walk_direction()
        if new_state in BUBBLES and random.random() < 0.6:
            self.bubble_text = random.choice(BUBBLES[new_state])
            self.bubble_image = self.render_bubble(self.bubble_text, self.scale)
            self.bubble_left = BUBBLE_FRAMES

    # ---- 绘制与主循环 ----
    def set_walk_direction(self) -> None:
        """设置散步方向：走向离自己较远的那一侧，实现屏幕左右横穿。"""
        sw = self.root.winfo_screenwidth()
        self.walk_dir = 1 if self.root.winfo_x() < sw / 2 else -1

    def walk(self) -> None:
        """散步：横向走向屏幕另一侧，到达屏幕边缘后结束散步。"""
        win_x = self.root.winfo_x()
        speed = WALK_SPEED * self.scale
        edge_right = self.root.winfo_screenwidth() - self.win_size[0]
        new_x = win_x + self.walk_dir * speed
        if new_x <= 0 or new_x >= edge_right:
            new_x = max(0, min(edge_right, new_x))
            self.root.geometry(f"+{int(new_x)}+{self.root.winfo_y()}")
            self.switch_state("休息")  # 走完全程，歇一会
            if random.random() < 0.5:
                self.bubble_text = random.choice(["走累了，歇会～", "逛了一圈！"])
                self.bubble_image = self.render_bubble(self.bubble_text, self.scale)
                self.bubble_left = BUBBLE_FRAMES
        else:
            self.root.geometry(f"+{int(new_x)}+{self.root.winfo_y()}")

    def draw(self) -> None:
        """绘制当前帧到画布（不推进动画状态，可被缩放等事件立即调用）。"""
        cell = self.current_cell()
        if self.walking and self.walk_dir < 0:
            # 向左散步时镜像动画，让头朝向移动方向
            cell = cell.transpose(Image.FLIP_LEFT_RIGHT)
        if self.scale != 1.0:
            cell = self.strip_green_edges(cell.resize(tuple(self.win_size), Image.LANCZOS))
        self.photo = ImageTk.PhotoImage(cell)
        if self.pet_item is None:
            self.pet_item = self.canvas.create_image(0, 0, image=self.photo, anchor="nw", tags="pet")
        else:
            self.canvas.itemconfig(self.pet_item, image=self.photo)

        self.canvas.delete("bubble")
        if self.bubble_text and self.bubble_left > 0:
            if self.bubble_image is not None:
                self.canvas.create_image(
                    self.win_size[0] // 2, int(2 * self.scale),
                    image=self.bubble_image, anchor="n", tags="bubble",
                )
            self.bubble_left -= 1
            if self.bubble_left <= 0:
                self.bubble_text = None
                self.bubble_image = None

    def tick(self) -> None:
        # 散步：横向走向屏幕另一侧
        if self.walking:
            self.walk()

        self.frame += 1
        self.frames_in_state += 1
        if not self.walking and self.frames_in_state >= self.state_target:
            self.next_state()
        self.check_counter += 1
        if self.check_counter >= 6:  # 约 1.5 秒检测一次前台窗口
            self.check_counter = 0
            self.check_foreground()
        self.draw()
        self.root.after(260, self.tick)

    # ---- 互动情绪 ----
    def on_release(self, event: tk.Event) -> None:
        """鼠标释放（点击或拖拽结束）→ 开心状态 + 气泡。"""
        self.switch_state("开心")
        self.interact_until = time.time() + 4.0  # 4 秒内不被前台检测切走
        if random.random() < 0.8:
            self.bubble_text = random.choice(BUBBLES["开心"])
            self.bubble_image = self.render_bubble(self.bubble_text, self.scale)
            self.bubble_left = BUBBLE_FRAMES

    def check_foreground(self) -> None:
        """检测前台窗口：真实应用被打开/操作 → 工作状态；回到桌面 → 恢复自由活动。"""
        if time.time() < self.interact_until:
            return  # 互动冷却期（刚点击/拖拽过），不打断开心状态
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return
            if hwnd == self.root.winfo_id():
                return  # 正在和桌宠互动（点击/拖拽由 on_release 处理）
            length = user32.GetWindowTextLengthW(hwnd)
            title_buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buf, length + 1)
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            title = title_buf.value
            cls = cls_buf.value
            # 系统级窗口（桌面/任务栏/壁纸/开始菜单等）不算"软件被打开"
            system_classes = {"Progman", "Shell_TrayWnd", "WorkerW", "Windows.UI.Core.CoreWindow", ""}
            if title and cls not in system_classes:
                if self.state_name != "工作":
                    self.switch_state("工作")
            elif self.state_name == "工作":
                self.switch_state("休息")
        except Exception:
            pass

    # ---- 交互 ----
    def start_drag(self, event: tk.Event) -> None:
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())
        self.press_root = (event.x_root, event.y_root)

    def drag(self, event: tk.Event) -> None:
        x = event.x_root - self.drag_origin[0]
        y = event.y_root - self.drag_origin[1]
        self.root.geometry(f"+{x}+{y}")

    def toggle_pet(self, _event: tk.Event) -> None:
        self.pet_index = (self.pet_index + 1) % len(PETS)
        self.load_pet()

    def menu(self, event: tk.Event) -> None:
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label=f"当前：{list(PETS)[self.pet_index]}（{self.state_name}） {self.scale:.1f}x", state="disabled")
        menu.add_separator()
        for index, name in enumerate(PETS):
            menu.add_command(label=f"切换到 {name}", command=lambda i=index: self.switch_pet(i))
        state_menu = tk.Menu(menu, tearoff=False)
        for name in STATES:
            state_menu.add_command(label=name, command=lambda n=name: self.switch_state(n))
        menu.add_cascade(label="手动状态", menu=state_menu)
        menu.add_separator()
        menu.add_command(label="退出桌面宠物", command=self.root.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def switch_pet(self, index: int) -> None:
        self.pet_index = index
        self.load_pet()

    def switch_state(self, name: str) -> None:
        self.state_name = name
        self.frame = 0
        self.frames_in_state = 0
        self.state_target = random.randint(*STATE_DURATION[name])
        self.walking = name == "散步"
        if self.walking:
            self.set_walk_direction()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    DesktopPet().run()
