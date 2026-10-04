from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.properties import NumericProperty, ListProperty, StringProperty
from kivy.animation import Animation
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp
from kivy.graphics import Color, Line, Ellipse, Rectangle, Triangle, PushMatrix, PopMatrix, Rotate
from kivy.utils import get_color_from_hex

import random
import json
import os
import math

# ---------- Константы ----------
DATA_FILE = "wheely_options.json"

SECTOR_COLORS = [
    "#6C5CE7", "#A29BFE", "#FD79A8", "#E84393",
    "#00CEC9", "#55EFC4", "#FAB1A0", "#FFEAA7",
    "#74B9FF", "#81ECEC", "#DFE6E9", "#B2BEC3",
    "#FF7675", "#FDCB6E", "#E17055", "#00B894",
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

PROMPT_TEXT = "Задай вопрос и крути"


# ---------- Экран колеса ----------
class WheelScreen(Screen):
    angle = NumericProperty(0)
    result_text = StringProperty(PROMPT_TEXT)
    is_spinning = False

    def on_pre_enter(self, *args):
        self.update_wheel()

    def update_wheel(self):
        app = App.get_running_app()
        self.ids.wheel.options = list(app.options)
        if not self.is_spinning:
            self.result_text = PROMPT_TEXT

    def spin(self):
        if self.is_spinning:
            return
        app = App.get_running_app()
        if len(app.options) < 2:
            self.result_text = "Нужно хотя бы 2 ответа"
            return

        self.is_spinning = True
        self.result_text = "..."

        # не даём углу расти бесконечно
        self.angle = self.angle % 360
        target = self.angle + random.randint(5, 9) * 360 + random.uniform(0, 360)

        anim = Animation(angle=target, duration=4.0, t="out_quint")
        anim.bind(on_complete=self.show_result)
        anim.start(self)

    def show_result(self, *args):
        app = App.get_running_app()
        n = len(app.options)
        sector = 360 / n
        # Углы отсчитываются по часовой стрелке от верха (как в WheelWidget).
        # Сектор i занимает [angle + i*sector, angle + (i+1)*sector].
        # Указатель смотрит в точку 0°, ищем сектор, накрывающий её.
        normalized = (-self.angle) % 360
        index = min(int(normalized // sector), n - 1)
        self.result_text = app.options[index]
        self.is_spinning = False

        try:
            from plyer import vibrator
            vibrator.vibrate(0.2)
        except Exception:
            pass


# ---------- Экран списка ----------
class ListScreen(Screen):
    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        self.ids.options_list.clear_widgets()
        for i, opt in enumerate(app.options):
            row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(5))

            lbl = Label(
                text=f"{i + 1}. {opt}",
                font_size="18sp",
                halign="left",
                valign="middle",
                shorten=True,
                shorten_from="right",
            )
            lbl.bind(size=lambda inst, size: setattr(inst, "text_size", size))
            row.add_widget(lbl)

            del_btn = Button(
                text="X",
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
class WheelWidget(Widget):
    options = ListProperty([])
    angle = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._textures = {}
        self._redraw_trigger = Clock.create_trigger(self.redraw, -1)
        self.bind(
            options=self._redraw_trigger,
            angle=self._redraw_trigger,
            size=self._redraw_trigger,
            pos=self._redraw_trigger,
        )
        self._redraw_trigger()

    def _get_texture(self, text, font_size):
        key = (text, round(font_size, 1))
        tex = self._textures.get(key)
        if tex is None:
            label = CoreLabel(text=text, font_size=font_size, color=(0.05, 0.05, 0.1, 1))
            label.refresh()
            tex = label.texture
            if len(self._textures) > 200:
                self._textures.clear()
            self._textures[key] = tex
        return tex

    def redraw(self, *args):
        self.canvas.clear()
        if not self.options:
            return

        cx, cy = self.center_x, self.center_y
        radius = min(self.width, self.height) / 2 - dp(30)
        if radius <= 0:
            return
        n = len(self.options)
        sector_deg = 360 / n

        def polar(angle_deg, r):
            # 0° = верх, угол растёт по часовой стрелке
            a = math.radians(90 - angle_deg)
            return cx + r * math.cos(a), cy + r * math.sin(a)

        font_size = max(dp(9), min(dp(14), radius / 11))
        segments = max(3, int(sector_deg / 3) + 1)

        with self.canvas:
            # --- Сектора (настоящие дуги, а не треугольники) ---
            for i in range(n):
                Color(*get_color_from_hex(SECTOR_COLORS[i % len(SECTOR_COLORS)]))
                start = (self.angle + i * sector_deg) % 360
                Ellipse(
                    pos=(cx - radius, cy - radius),
                    size=(radius * 2, radius * 2),
                    angle_start=start,
                    angle_end=start + sector_deg,
                    segments=segments,
                )

            # --- Текст вдоль сектора ---
            for i, opt in enumerate(self.options):
                mid_angle = self.angle + (i + 0.5) * sector_deg
                tx, ty = polar(mid_angle, radius * 0.62)

                short = opt if len(opt) <= 16 else opt[:15] + "…"
                tex = self._get_texture(short, font_size)

                # Kivy Rotate крутит против часовой; направление текста = 90 - mid_angle
                rot = 90 - mid_angle
                if math.cos(math.radians(rot)) < 0:
                    rot += 180  # не переворачиваем текст вверх ногами

                PushMatrix()
                Rotate(angle=rot, origin=(tx, ty))
                Color(1, 1, 1, 1)
                Rectangle(
                    texture=tex,
                    pos=(tx - tex.width / 2, ty - tex.height / 2),
                    size=tex.size,
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

    @property
    def data_path(self):
        # user_data_dir доступен для записи и на Android, и на десктопе
        os.makedirs(self.user_data_dir, exist_ok=True)
        return os.path.join(self.user_data_dir, DATA_FILE)

    def build(self):
        self.title = "Wheely"
        self.load_options()

        sm = ScreenManager()
        sm.add_widget(WheelScreen(name="wheel"))
        sm.add_widget(ListScreen(name="list"))
        return sm

    def load_options(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and all(isinstance(x, str) for x in data):
                    self.options = data
                    return
            except Exception:
                pass
        self.options = list(DEFAULT_OPTIONS)
        self.save_options()

    def save_options(self):
        try:
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(list(self.options), f, ensure_ascii=False, indent=2)
        except Exception:
            pass


if __name__ == "__main__":
    WheelyApp().run()
