from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.label import Label
from kivy.properties import NumericProperty, ListProperty, StringProperty
from kivy.animation import Animation
from kivy.core.text import Label as CoreLabel
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.graphics import (
    Color, Line, Ellipse, Rectangle, RoundedRectangle, Triangle,
    PushMatrix, PopMatrix, Rotate,
)
from kivy.utils import get_color_from_hex

import random
import os
import math
import time
import wave
import struct

# ---------- Константы ----------
SECTOR_COLORS = [
    "#FF8A3D", "#F0509B", "#7B5CF0", "#FF5E6C", "#2DA8E0",
    "#D6336C", "#F59E0B", "#9B5DE5", "#FF7043", "#5E60CE",
]
SECTOR_RGBA = [get_color_from_hex(c) for c in SECTOR_COLORS]

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
CAPTION_IDLE = "ОРАКУЛ ЖДЁТ"
CREAM = (1, 0.97, 0.93, 1)


# ---------- Звуки: синтезируются кодом, внешние файлы не нужны ----------
SAMPLE_RATE = 22050


def _write_wav(path, samples):
    peak = max(1e-9, max(abs(s) for s in samples))
    k = 0.85 / peak
    ints = [int(max(-1.0, min(1.0, s * k)) * 32767) for s in samples]
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(struct.pack("<%dh" % len(ints), *ints))


def _synth_click():
    """Мягкий «поп» при нажатии кнопки."""
    n = int(SAMPLE_RATE * 0.12)
    out, phase = [], 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        phase += 2 * math.pi * (380 + 700 * math.exp(-t * 40)) / SAMPLE_RATE
        env = min(1.0, t / 0.002) * math.exp(-t * 38)
        out.append(math.sin(phase) * env)
    return out


def _synth_tick():
    """Короткий деревянный щелчок при прохождении сектора."""
    n = int(SAMPLE_RATE * 0.05)
    rnd = random.Random(1)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = min(1.0, t / 0.0008) * math.exp(-t * 110)
        s = (0.7 * math.sin(2 * math.pi * 1650 * t)
             + 0.4 * math.sin(2 * math.pi * 2480 * t)
             + 0.25 * (rnd.random() * 2 - 1))
        out.append(s * env)
    return out


def _bell(freq, dur):
    partials = [(1.0, 1.0, 3.5), (2.0, 0.45, 5.0), (2.76, 0.25, 7.0), (4.07, 0.12, 10.0)]
    out = []
    for i in range(int(SAMPLE_RATE * dur)):
        t = i / SAMPLE_RATE
        s = sum(a * math.sin(2 * math.pi * freq * r * t) * math.exp(-t * d)
                for r, a, d in partials)
        out.append(s * min(1.0, t / 0.003))
    return out


def _synth_win():
    """Колокольчики-арпеджио для финального ответа."""
    notes = [(1046.5, 0.00), (1318.5, 0.10), (1568.0, 0.20), (2093.0, 0.32)]
    total = int(SAMPLE_RATE * 1.9)
    out = [0.0] * total
    for freq, start in notes:
        off = int(start * SAMPLE_RATE)
        for i, s in enumerate(_bell(freq, 1.5)):
            if off + i < total:
                out[off + i] += s
    return out


def ensure_sounds(folder):
    os.makedirs(folder, exist_ok=True)
    makers = {"click": _synth_click, "tick": _synth_tick, "win": _synth_win}
    paths = {}
    for name, make in makers.items():
        path = os.path.join(folder, name + "_v1.wav")
        if not os.path.exists(path):
            _write_wav(path, make())
        paths[name] = path
    return paths


class Sfx:
    TICK_MIN_GAP = 0.04  # быстрее щелчки сливаются в гул

    def __init__(self, folder):
        self.click_snd = None
        self.win_snd = None
        self.ticks = []
        self._ti = 0
        self._last_tick = 0.0
        try:
            from kivy.core.audio import SoundLoader
            paths = ensure_sounds(folder)
            self.click_snd = SoundLoader.load(paths["click"])
            self.win_snd = SoundLoader.load(paths["win"])
            # несколько копий, чтобы быстрые щелчки могли перекрываться
            self.ticks = [s for s in (SoundLoader.load(paths["tick"]) for _ in range(4)) if s]
            if self.click_snd:
                self.click_snd.volume = 0.7
            if self.win_snd:
                self.win_snd.volume = 0.9
            for s in self.ticks:
                s.volume = 0.55
        except Exception as e:
            print("Звук отключён:", e)

    @staticmethod
    def _play(snd):
        if snd:
            try:
                snd.play()
            except Exception:
                pass

    def click(self):
        self._play(self.click_snd)

    def tick(self):
        if not self.ticks:
            return
        now = time.monotonic()
        if now - self._last_tick < self.TICK_MIN_GAP:
            return
        self._last_tick = now
        self._play(self.ticks[self._ti])
        self._ti = (self._ti + 1) % len(self.ticks)

    def win(self):
        self._play(self.win_snd)


# ---------- Текстуры: градиенты и свечение ----------
_TEX = {}


def tex_gradient(key, stops, horizontal=False, size=128):
    """Линейный градиент. Для вертикального stops идут сверху вниз."""
    tex = _TEX.get(key)
    if tex is not None:
        return tex
    rgba = [get_color_from_hex(s) if isinstance(s, str) else tuple(s) for s in stops]
    n = len(rgba)
    buf = bytearray()
    for i in range(size):
        v = i / (size - 1)
        t = v if horizontal else 1 - v
        pos = t * (n - 1)
        k = min(int(pos), n - 2)
        f = pos - k
        for j in range(4):
            val = rgba[k][j] * (1 - f) + rgba[k + 1][j] * f
            buf.append(max(0, min(255, int(val * 255))))
    tex = Texture.create(size=(size, 1) if horizontal else (1, size), colorfmt="rgba")
    tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    tex.mag_filter = "linear"
    tex.min_filter = "linear"
    _TEX[key] = tex
    return tex


def tex_radial(kind, size=128):
    """'glow' — яркий центр, плавно гаснет к краю; 'vignette' — наоборот."""
    key = "radial_" + kind
    tex = _TEX.get(key)
    if tex is not None:
        return tex
    c = (size - 1) / 2
    buf = bytearray()
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - c, y - c) / c
            if d >= 1:
                a = 0.0
            elif kind == "glow":
                a = (1 - d) ** 2
            else:
                a = d ** 2.2
            buf += bytes((255, 255, 255, int(a * 255)))
    tex = Texture.create(size=(size, size), colorfmt="rgba")
    tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    tex.mag_filter = "linear"
    tex.min_filter = "linear"
    _TEX[key] = tex
    return tex


# ---------- Фон: градиент, туманности и мерцающие звёзды ----------
class Backdrop(Widget):
    ORBS = [  # (x, y, размер от max(w,h), цвет, прозрачность)
        (0.10, 0.92, 1.10, (0.48, 0.18, 0.97), 0.38),
        (0.95, 0.55, 0.95, (1.00, 0.30, 0.55), 0.26),
        (0.20, 0.05, 1.00, (1.00, 0.55, 0.26), 0.22),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        rnd = random.Random(7)
        # x, y, размер(dp), фаза, скорость, базовая яркость
        self._stars = [
            (rnd.random(), rnd.random(), rnd.uniform(1.0, 2.6),
             rnd.uniform(0, 6.28), rnd.uniform(0.6, 1.8), rnd.uniform(0.35, 0.95))
            for _ in range(38)
        ]
        self._star_colors = []
        self._t = 0.0
        self.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_interval(self._twinkle, 1 / 15)

    def _redraw(self, *args):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        bg = tex_gradient("bg", ["#0A0614", "#170A28", "#2A0F3B"])
        glow = tex_radial("glow")
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(pos=self.pos, size=self.size, texture=bg)
            for ox, oy, os_, col, a in self.ORBS:
                s = os_ * max(w, h)
                Color(col[0], col[1], col[2], a)
                Rectangle(texture=glow, pos=(x + ox * w - s / 2, y + oy * h - s / 2), size=(s, s))
            self._star_colors = []
            for sx, sy, sz, ph, spd, base in self._stars:
                c = Color(1, 0.95, 0.9, base)
                self._star_colors.append(c)
                d = dp(sz)
                Ellipse(pos=(x + sx * w - d / 2, y + sy * h - d / 2), size=(d, d))

    def _twinkle(self, dt):
        self._t += dt
        for c, (_, _, _, ph, spd, base) in zip(self._star_colors, self._stars):
            c.a = base * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(self._t * spd + ph)))


# ---------- Стеклянная карточка ----------
class GlassCard(BoxLayout):
    radius = NumericProperty(dp(22))
    tint = ListProperty([1, 1, 1, 0.07])
    edge = ListProperty([1, 1, 1, 0.16])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._draw, size=self._draw, radius=self._draw,
                  tint=self._draw, edge=self._draw)
        self._draw()

    def _draw(self, *args):
        self.canvas.before.clear()
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        r = min(self.radius, h / 2, w / 2)
        sheen = tex_gradient("sheen", [(1, 1, 1, 0.14), (1, 1, 1, 0.0)])
        with self.canvas.before:
            for k in range(1, 5):
                s = dp(2 * k)
                Color(0, 0, 0, 0.07)
                RoundedRectangle(pos=(x - s, y - s - dp(3)), size=(w + 2 * s, h + 2 * s), radius=[r + s])
            Color(*self.tint)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=(x, y + h * 0.5), size=(w, h * 0.5),
                             radius=[r, r, 0, 0], texture=sheen)
            Color(*self.edge)
            Line(rounded_rectangle=(x, y, w, h, r), width=dp(1))


# ---------- Кнопка-«пилюля» без прямоугольного бокса ----------
BUTTON_STYLES = {
    "primary": dict(grad=["#FFB347", "#FF6B6B", "#E4408E"], text=(1, 1, 1, 1),
                    glow=(1, 0.42, 0.45)),
    "ghost": dict(grad=None, tint=(1, 1, 1, 0.08), edge=(1, 1, 1, 0.22),
                  text=CREAM, glow=None),
}


class PillButton(ButtonBehavior, Label):
    style = StringProperty("ghost")
    press_amt = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._draw, size=self._draw, style=self._draw, press_amt=self._draw)
        self.bind(state=self._on_state)
        self._draw()

    def _on_state(self, inst, st):
        Animation.cancel_all(self, "press_amt")
        down = st == "down"
        Animation(press_amt=1 if down else 0, d=0.08 if down else 0.22, t="out_quad").start(self)
        if down:
            sfx = getattr(App.get_running_app(), "sfx", None)
            if sfx:
                sfx.click()

    def _draw(self, *args):
        spec = BUTTON_STYLES.get(self.style, BUTTON_STYLES["ghost"])
        self.color = spec["text"]
        self.canvas.before.clear()
        if self.width <= 0 or self.height <= 0:
            return
        p = self.press_amt
        inset = dp(2) * p
        x, y = self.x + inset, self.y + inset
        w, h = self.width - 2 * inset, self.height - 2 * inset
        r = h / 2
        with self.canvas.before:
            if spec["glow"]:
                for k in range(1, 7):
                    s = dp(2.2 * k)
                    Color(*spec["glow"], 0.07 * (1 - 0.6 * p))
                    RoundedRectangle(pos=(x - s, y - s - dp(5)), size=(w + 2 * s, h + 2 * s),
                                     radius=[r + s])
            if spec["grad"]:
                tex = tex_gradient("btn_" + self.style, spec["grad"], horizontal=True)
                b = 1 - 0.15 * p
                Color(b, b, b, 1)
                RoundedRectangle(pos=(x, y), size=(w, h), radius=[r], texture=tex)
                Color(1, 1, 1, 0.20)
                RoundedRectangle(pos=(x + dp(3), y + h * 0.52), size=(w - dp(6), h * 0.44),
                                 radius=[h * 0.22, h * 0.22, h * 0.12, h * 0.12])
                Color(1, 1, 1, 0.35)
                Line(rounded_rectangle=(x, y, w, h, r), width=dp(0.8))
            else:
                Color(*spec["tint"])
                RoundedRectangle(pos=(x, y), size=(w, h), radius=[r])
                Color(1, 1, 1, 0.10 * p)
                RoundedRectangle(pos=(x, y), size=(w, h), radius=[r])
                Color(*spec["edge"])
                Line(rounded_rectangle=(x, y, w, h, r), width=dp(1))


# ---------- Экран колеса ----------
class WheelScreen(FloatLayout):
    angle = NumericProperty(0)
    result_text = StringProperty(PROMPT_TEXT)
    caption_text = StringProperty(CAPTION_IDLE)
    spin_label = StringProperty("Крутить")
    result_fs = NumericProperty(sp(20))
    result_opacity = NumericProperty(0.75)
    is_spinning = False
    _last_idx = 0

    def on_kv_post(self, base_widget):
        self.ids.wheel.options = list(App.get_running_app().answers)

    def _sector_index(self, angle, n):
        # Углы идут по часовой стрелке от верха (как в WheelWidget).
        # Указатель смотрит в точку 0°, ищем сектор, который её накрывает.
        return min(int(((-angle) % 360) // (360 / n)), n - 1)

    def on_angle(self, inst, value):
        """Щелчок каждый раз, когда под указателем оказывается новый сектор."""
        if not self.is_spinning:
            return
        app = App.get_running_app()
        idx = self._sector_index(value, len(app.answers))
        if idx != self._last_idx:
            self._last_idx = idx
            if app.sfx:
                app.sfx.tick()

    def spin(self):
        if self.is_spinning:
            return
        app = App.get_running_app()
        n = len(app.answers)

        # не даём углу расти бесконечно (до включения is_spinning, чтобы не щёлкнуло)
        self.angle = self.angle % 360
        self._last_idx = self._sector_index(self.angle, n)

        self.is_spinning = True
        Animation.cancel_all(self, "result_opacity", "result_fs")
        self.result_text = "· · ·"
        self.caption_text = "ВСЕЛЕННАЯ ДУМАЕТ"
        self.result_fs = sp(28)
        self.result_opacity = 1
        self.spin_label = "Крутим..."

        target = self.angle + random.randint(5, 9) * 360 + random.uniform(0, 360)
        anim = Animation(angle=target, duration=4.2, t="out_quint")
        anim.bind(on_complete=self.show_result)
        anim.start(self)

    def show_result(self, *args):
        app = App.get_running_app()
        index = self._sector_index(self.angle, len(app.answers))

        self.result_text = app.answers[index]
        self.caption_text = "ТВОЙ ОТВЕТ"
        self.spin_label = "Крутить"
        self.is_spinning = False

        self.result_opacity = 0
        self.result_fs = sp(20)
        Animation(result_opacity=1, result_fs=sp(28), d=0.5, t="out_back").start(self)

        if app.sfx:
            app.sfx.win()
        try:
            from plyer import vibrator
            vibrator.vibrate(0.2)
        except Exception:
            pass


# ---------- Виджет колеса ----------
N_LIGHTS = 28


class WheelWidget(Widget):
    options = ListProperty([])
    angle = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._textures = {}
        self._last_angle = 0.0
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
            label = CoreLabel(text=text, font_size=font_size, bold=True, color=(1, 1, 1, 1))
            label.refresh()
            tex = label.texture
            if len(self._textures) > 200:
                self._textures.clear()
            self._textures[key] = tex
        return tex

    def redraw(self, *args):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        radius = min(self.width / 2 - dp(28), self.height / 2 - dp(42))
        speed = abs(self.angle - self._last_angle)
        self._last_angle = self.angle
        if radius <= dp(30):
            return

        opts = self.options
        n = len(opts)
        sector_deg = 360 / n if n else 360

        glow = tex_radial("glow")
        vig = tex_radial("vignette")

        def polar(angle_deg, r):
            # 0° = верх, угол растёт по часовой стрелке
            a = math.radians(90 - angle_deg)
            return cx + r * math.cos(a), cy + r * math.sin(a)

        font_size = max(dp(10), min(dp(15), radius / 10))
        segments = max(3, int(sector_deg / 3) + 1)
        energy = min(1.0, speed / 6.0)

        with self.canvas:
            # --- Свечение позади колеса ---
            g = (radius + dp(80)) * 2
            Color(1.0, 0.42, 0.5, 0.40 + 0.25 * energy)
            Rectangle(texture=glow, pos=(cx - g / 2, cy - g / 2), size=(g, g))
            g2 = g * 1.25
            Color(0.55, 0.35, 1.0, 0.28)
            Rectangle(texture=glow, pos=(cx - g2 / 2, cy - g2 / 2), size=(g2, g2))

            # --- Ободок ---
            rim = radius + dp(17)
            Color(0.09, 0.04, 0.17, 1)
            Ellipse(pos=(cx - rim, cy - rim), size=(2 * rim, 2 * rim))
            Color(1, 1, 1, 0.22)
            Line(circle=(cx, cy, rim), width=dp(1.2))

            # --- Огоньки на ободке (бегут при вращении) ---
            for k in range(N_LIGHTS):
                ang = k * 360 / N_LIGHTS
                lx, ly = polar(ang, radius + dp(9))
                ph = math.radians(ang - self.angle * 2.5)
                a = 0.30 + 0.70 * (0.5 + 0.5 * math.cos(ph)) ** 3
                Color(1, 0.78, 0.45, 0.25 * a)
                d = dp(12)
                Ellipse(pos=(lx - d / 2, ly - d / 2), size=(d, d))
                Color(1, 0.88, 0.6, a)
                d = dp(5)
                Ellipse(pos=(lx - d / 2, ly - d / 2), size=(d, d))

            if n:
                # --- Сектора ---
                for i in range(n):
                    ci = i % len(SECTOR_RGBA)
                    if i == n - 1 and n > 1 and ci == 0:
                        ci = len(SECTOR_RGBA) // 2  # последний не должен совпасть с первым
                    Color(*SECTOR_RGBA[ci])
                    start = (self.angle + i * sector_deg) % 360
                    Ellipse(
                        pos=(cx - radius, cy - radius),
                        size=(radius * 2, radius * 2),
                        angle_start=start,
                        angle_end=start + sector_deg,
                        segments=segments,
                    )

                # --- Объём: виньетка и блик ---
                Color(0, 0, 0, 0.5)
                Rectangle(texture=vig, pos=(cx - radius, cy - radius), size=(2 * radius, 2 * radius))
                gs = radius * 1.1
                Color(1, 1, 1, 0.22)
                Rectangle(texture=glow,
                          pos=(cx - radius * 0.28 - gs / 2, cy + radius * 0.38 - gs / 2),
                          size=(gs, gs))

                # --- Разделители ---
                Color(1, 1, 1, 0.28)
                for i in range(n):
                    x2, y2 = polar(self.angle + i * sector_deg, radius)
                    Line(points=[cx, cy, x2, y2], width=dp(1))

                # --- Подписи вдоль секторов ---
                # Текст всегда читается от центра к ободу и плавно вращается
                # вместе с колесом, без переворотов у указателя.
                outer = radius * 0.93
                avail = outer - dp(36)
                for i, opt in enumerate(opts):
                    mid_angle = self.angle + (i + 0.5) * sector_deg
                    short = opt if len(opt) <= 18 else opt[:17] + "…"
                    tex = self._get_texture(short, font_size)
                    tw, th = tex.size
                    scale = min(1.0, avail / tw)
                    we, he = tw * scale, th * scale
                    tx, ty = polar(mid_angle, outer - we / 2)

                    PushMatrix()
                    Rotate(angle=90 - mid_angle, origin=(tx, ty))
                    Color(0, 0, 0, 0.35)
                    Rectangle(texture=tex, pos=(tx - we / 2 + dp(1), ty - he / 2 - dp(1)), size=(we, he))
                    Color(1, 1, 1, 1)
                    Rectangle(texture=tex, pos=(tx - we / 2, ty - he / 2), size=(we, he))
                    PopMatrix()
            else:
                Color(1, 1, 1, 0.06)
                Ellipse(pos=(cx - radius, cy - radius), size=(radius * 2, radius * 2))

            # --- Золотая окантовка ---
            Color(1, 0.86, 0.6, 0.95)
            Line(circle=(cx, cy, radius), width=dp(1.6))

            # --- Ступица ---
            Color(1, 0.5, 0.35, 0.25)
            d = dp(68)
            Rectangle(texture=glow, pos=(cx - d / 2, cy - d / 2), size=(d, d))
            Color(0.09, 0.04, 0.16, 1)
            d = dp(56)
            Ellipse(pos=(cx - d / 2, cy - d / 2), size=(d, d))
            Color(1, 0.55, 0.38, 1)
            d = dp(48)
            Rectangle(texture=glow, pos=(cx - d / 2, cy - d / 2), size=(d, d))
            Color(1, 1, 1, 0.55)
            d = dp(6)
            Ellipse(pos=(cx - dp(9), cy + dp(5)), size=(d, d))
            Color(1, 1, 1, 0.45)
            Line(circle=(cx, cy, dp(28)), width=dp(1))

            # --- Указатель-«капля» с покачиванием на разделителях ---
            px, py = cx, cy + radius + dp(15)
            tip_y = cy + radius - dp(18)
            if n and speed > 0:
                t = (self.angle % sector_deg) / sector_deg
                defl = 16 * max(0.0, 1 - t * 6) ** 1.5 * min(1.0, speed / 2)
            else:
                defl = 0

            Color(1, 0.5, 0.3, 0.6)
            d = dp(64)
            Rectangle(texture=glow, pos=(px - d / 2, py - d / 2), size=(d, d))

            PushMatrix()
            Rotate(angle=defl, origin=(px, py))
            Color(1, 1, 1, 1)
            Triangle(points=[px - dp(11), py - dp(4), px + dp(11), py - dp(4), px, tip_y])
            d = dp(24)
            Ellipse(pos=(px - d / 2, py - d / 2), size=(d, d))
            Color(1, 0.45, 0.3, 1)
            d = dp(11)
            Ellipse(pos=(px - d / 2, py - d / 2), size=(d, d))
            PopMatrix()


# ---------- Приложение ----------
class WheelyApp(App):
    answers = ListProperty(list(DEFAULT_OPTIONS))
    sfx = None

    def build(self):
        self.title = "Wheely"
        Window.clearcolor = (0.04, 0.025, 0.08, 1)

        self.sfx = Sfx(os.path.join(self.user_data_dir, "sounds"))

        root = FloatLayout()
        root.add_widget(Backdrop())
        root.add_widget(WheelScreen())
        return root


if __name__ == "__main__":
    WheelyApp().run()
