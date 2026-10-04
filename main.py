from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.properties import NumericProperty, ListProperty, StringProperty
from kivy.animation import Animation
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp
from kivy.graphics import (
    Color, Triangle, Line, Ellipse, Rectangle,
    PushMatrix, PopMatrix, Rotate,
)
from kivy.utils import get_color_from_hex

import random
import json
import os
import math

# ---------- Константы ----------
DATA_FILE = "wheely_options.json"

# Тёмная мистическая палитра
SECTOR_COLORS = [
    "#FF8C42", "#FFB26B", "#E85D75", "#C44B8A",
    "#8B5FBF", "#FF6B6B", "#FFA45B", "#D65DB1",
    "#FF8C42", "#FFB26B", "#E85D75", "#C44B8A",
    "#8B5FBF", "#FF6B6B", "#FFA45B", "#D65DB1",
]

DEFAULT_OPTIONS = [
    "Однозначно да",
    "Да",
    "Скорее да",
    "Спроси позже",
    "Не могу решить",
    "Скорее нет",
    "Нет",
    "Даже не думай",
    "Определённо нет",
    "Наберись смелости",
    "Доверься интуиции",
    "Всё в твоих руках",
    "Рискни",
    "Подожди",
    "Забудь",
    "А сам как думаешь?",
]


# ---------- Экран колеса ----------
class WheelScreen(Screen):
    angle = NumericProperty(0)
    result_text = StringProperty("Задай вопрос и крути")
    is_spinning = False

    def on_pre_enter(self):
        self.load_options()
        self.update_wheel()

    def load_options(self):
        app = App.get_running_app()
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, encoding="utf-8") as f:
                    app.options = json.load(f)
            except Exception:
                app.options = list(DEFAULT_OPTIONS)
        else:
            app.options = list(DEFAULT_OPTIONS)
            app.save_options()

    def update_wheel(self):
        app = App.get_running_app()
        self.ids.wheel.options = app.options
        self.result_text = "Задай вопрос и крути"

    def spin(self):
        if self.is_spinning:
            return
        app = App.get_running_app()
        n = len(app.options)
        if n < 2:
            self.result_text = "Нужно хотя бы 2 ответа"
            return

        self.is_spinning = True
        self.result_text = "..."

        turns = random.randint(5, 9)
        target = self.angle + turns * 360 + random.randint(0, 360)

        anim = Animation(angle=target, duration=4.0, t="out_quint")
        anim.bind(on_complete=self.show_result)
        anim.start(self)

    def show_result(self, *args):
        app = App.get_running_app()
        n = len(app.options)
        sector = 360 / n
        # Указатель сверху = угол 0.
        # Сектор i занимает углы [angle + i*sector, angle + (i+1)*sector].
        # Хотим найти i, для которого этот диапазон накрывает 0 (или 360).
        # Эквивалентно: найти сектор, в который попадает точка 360° (== 0°).
        normalized = (-self.angle) % 360
        index = int(normalized // sector) % n
        self.result_text = f"🔮 {app.options[index]}"
        self.is_spinning = False

        try:
            from plyer import vibrator
            vibrator.vibrate(0.2)
        except Exception:
            pass


# ---------- Экран списка ----------
class ListScreen(Screen):
    def on_pre_enter(self):
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        self.ids.options_list.clear_widgets()
        for i, opt in enumerate(app.options):
            row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(5))

            lbl = Label(text=f"{i+1}. {opt}", font_size="18sp")
            row.add_widget(lbl)

            del_btn = Button(
                text="✕",
                font_size="20sp",
                size_hint_x=None,
                width=dp(50),
                background_color=(0.9, 0.3, 0.3, 1),
            )
            del_btn.bind(on_press=lambda inst, idx=i: self.remove_option(idx))
            row.add_widget(del_btn)

            self.ids.options_list.add_widget(row)

    def add_option(self):
        text = self.ids.new_option.text.strip()
        if text:
            app = App.get_running_app()
            app.options.append(text)
            app.save_options()
            self.ids.new_option.text = ""
            self.refresh()

    def remove_option(self, index):
        app = App.get_running_app()
        if 0 <= index < len(app.options):
            app.options.pop(index)
            app.save_options()
            self.refresh()

    def reset_options(self):
        app = App.get_running_app()
        app.options = list(DEFAULT_OPTIONS)
        app.save_options()
        self.refresh()


# ---------- Виджет колеса ----------
class WheelWidget(BoxLayout):
    options = ListProperty([])
    angle = NumericProperty(0)

    def on_options(self, *args):
        self.redraw()

    def on_angle(self, *args):
        self.redraw()

    def on_size(self, *args):
        self.redraw()

    def on_pos(self, *args):
        self.redraw()

    def redraw(self):
        self.canvas.clear()
        if not self.options:
            return

        cx, cy = self.center_x, self.center_y
        radius = min(self.width, self.height) / 2 - dp(30)
        n = len(self.options)
        sector_deg = 360 / n

        def polar(angle_deg, r):
            a = math.radians(angle_deg - 90)
            return cx + r * math.cos(a), cy + r * math.sin(a)

        with self.canvas:
            # --- Сектора ---
            for i, opt in enumerate(self.options):
                color_hex = SECTOR_COLORS[i % len(SECTOR_COLORS)]
                Color(*get_color_from_hex(color_hex))

                a1 = self.angle + i * sector_deg
                a2 = self.angle + (i + 1) * sector_deg
                p1 = polar(a1, radius)
                p2 = polar(a2, radius)
                Triangle(points=[cx, cy, p1[0], p1[1], p2[0], p2[1]])

            # --- Текст (вращается вместе с колесом) ---
            for i, opt in enumerate(self.options):
                mid_angle = self.angle + (i + 0.5) * sector_deg

                # Позиция текста — на радиусе 0.7R от центра
                tx, ty = polar(mid_angle, radius * 0.65)

                label = CoreLabel(
                    text=opt[:16],
                    font_size=dp(13),
                    color=(0.05, 0.05, 0.1, 1),
                )
                label.refresh()
                texture = label.texture

                # Поворачиваем текст так, чтобы он "лежал" вдоль сектора.
                # В Kivy Rotate вращает вокруг origin (по умолчанию 0,0).
                # Мы смещаем origin в точку текста и вращаем на mid_angle.
                PushMatrix()
                Rotate(
                    angle=-(mid_angle - 90),  # компенсируем сдвиг -90 в polar()
                    origin=(tx, ty),
                )
                Color(1, 1, 1, 1)
                Rectangle(
                    texture=texture,
                    pos=(tx - texture.width / 2, ty - texture.height / 2),
                    size=texture.size,
                )
                PopMatrix()

            # --- Контур ---
            Color(0.9, 0.9, 1, 1)
            Line(circle=(cx, cy, radius), width=dp(3))

            # --- Ступица ---
            Color(0.1, 0.1, 0.2, 1)
            Ellipse(pos=(cx - dp(22), cy - dp(22)), size=(dp(44), dp(44)))

            # --- Указатель ---
            Color(1, 1, 1, 1)
            Triangle(points=[
                cx - dp(18), cy + radius + dp(5),
                cx + dp(18), cy + radius + dp(5),
                cx, cy + radius - dp(25),
            ])

# ---------- Приложение ----------
class WheelyApp(App):
    options = ListProperty(list(DEFAULT_OPTIONS))

    def build(self):
        self.title = "Wheely"
        self.load_options()

        sm = ScreenManager()
        sm.add_widget(WheelScreen(name="wheel"))
        sm.add_widget(ListScreen(name="list"))
        return sm

    def load_options(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, encoding="utf-8") as f:
                    self.options = json.load(f)
            except Exception:
                self.options = list(DEFAULT_OPTIONS)
        else:
            self.options = list(DEFAULT_OPTIONS)
            self.save_options()

    def save_options(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.options, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    WheelyApp().run()
