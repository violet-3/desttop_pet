"""Small Windows desktop pet runner for the GPT and DeepSeek sprite atlases."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk


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
        self.canvas.bind("<Button-3>", self.menu)
        self.root.bind("<Escape>", lambda _event: self.root.destroy())

        self.pet_index = 0
        self.state_name = "休息"
        self.frame = 0
        self.drag_origin = (0, 0)
        self.images: dict[str, Image.Image] = {}
        self.photo: ImageTk.PhotoImage | None = None
        self.load_pet()
        self.place_bottom_right()
        self.tick()

    def place_bottom_right(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{CELL_W}x{CELL_H}+{screen_w - CELL_W - 28}+{screen_h - CELL_H - 60}")

    @staticmethod
    def strip_green_edges(image: Image.Image) -> None:
        """二值化 alpha，彻底消除绿边：alpha>=128 置 255，alpha<128 置 0。
        窗口内不再存在半透明像素，不会与 #00ff01 透明色背景混合。"""
        pixels = image.load()
        width, height = image.size
        for y in range(height):
            for x in range(width):
                a = pixels[x, y][3]
                if a >= 128:
                    r, g, b = pixels[x, y][0], pixels[x, y][1], pixels[x, y][2]
                    pixels[x, y] = (r, g, b, 255)
                elif a > 0:
                    pixels[x, y] = (0, 0, 0, 0)

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
            self.strip_green_edges(atlas)
            atlas.save(clean, "WEBP", lossless=True)
            self.images["atlas"] = atlas
        self.frame = 0

    def current_cell(self) -> Image.Image:
        row, count = STATES[self.state_name]
        column = self.frame % count
        return self.images["atlas"].crop((column * CELL_W, row * CELL_H, (column + 1) * CELL_W, (row + 1) * CELL_H))

    def tick(self) -> None:
        self.photo = ImageTk.PhotoImage(self.current_cell())
        self.canvas.delete("pet")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw", tags="pet")
        self.frame += 1
        self.root.after(260, self.tick)

    def start_drag(self, event: tk.Event) -> None:
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def drag(self, event: tk.Event) -> None:
        x = event.x_root - self.drag_origin[0]
        y = event.y_root - self.drag_origin[1]
        self.root.geometry(f"+{x}+{y}")

    def menu(self, event: tk.Event) -> None:
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label=f"当前：{list(PETS)[self.pet_index]}", state="disabled")
        menu.add_separator()
        for index, name in enumerate(PETS):
            menu.add_command(label=f"切换到 {name}", command=lambda i=index: self.switch_pet(i))
        state_menu = tk.Menu(menu, tearoff=False)
        for name in STATES:
            state_menu.add_command(label=name, command=lambda n=name: self.switch_state(n))
        menu.add_cascade(label="状态", menu=state_menu)
        menu.add_separator()
        menu.add_command(label="退出桌面宠物", command=self.root.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def switch_pet(self, index: int) -> None:
        self.pet_index = index
        self.load_pet()

    def switch_state(self, name: str) -> None:
        self.state_name = name
        self.frame = 0

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    DesktopPet().run()
