"""Create a free, local Arabic overview video for the Mujib project."""

from __future__ import annotations

import math
from pathlib import Path
import sys
import wave

import arabic_reshaper
from bidi.algorithm import get_display
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.local_tts import synthesize_arabic


OUT_DIR = ROOT / "artifacts"
VIDEO_PATH = OUT_DIR / "mujib-project-overview.mp4"
AUDIO_PATH = OUT_DIR / "mujib-project-narration.wav"
POSTER_PATH = OUT_DIR / "mujib-project-video-poster.png"

WIDTH, HEIGHT = 1280, 720
FPS = 24

BG = "#101A17"
PANEL = "#1C2B25"
PANEL_ALT = "#143D30"
BORDER = "#34483D"
TEXT = "#F2F4EF"
MUTED = "#B5C3B9"
GREEN = "#21704E"
GOLD = "#D4AD32"

WINDOWS_FONTS = Path(r"C:\Windows\Fonts")
FONT_REGULAR = WINDOWS_FONTS / "arial.ttf"
FONT_BOLD = WINDOWS_FONTS / "arialbd.ttf"
LOGO_PATH = ROOT / "frontend" / "images" / "logo-icon.png"
AVATAR_DIR = ROOT / "frontend" / "images" / "ai-effendi" / "fallback"

NARRATION = (
    "هذا هو مُجيب، المساعد القانوني العراقي المحلي. "
    "يبحث في الوثائق القانونية المفهرسة، ويتحقق من المراجع، ثم يقدم إجابة عربية واضحة ومدعومة بالمصادر. "
    "يعمل النموذج والبحث والصوت محلياً للمساعدة في حماية البيانات. "
    "ويوفر واجهة عربية، محادثات، إدارة وثائق، وإعدادات تختار النموذج المناسب حسب كرت الشاشة. "
    "المرحلة القادمة هي توحيد مصدر البيانات، إكمال اختبارات الأمان، ثم إطلاق نسخة تجريبية منظّمة. "
    "مُجيب، معرفة قانونية عراقية أقرب إليك."
)


def rtl(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def load_sprite_sheet(name: str) -> list[Image.Image]:
    sheet = Image.open(AVATAR_DIR / name).convert("RGBA")
    cell_w, cell_h = sheet.width // 4, sheet.height // 2
    return [
        sheet.crop((column * cell_w, row * cell_h, (column + 1) * cell_w, (row + 1) * cell_h))
        for row in range(2)
        for column in range(4)
    ]


def contain(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    result = image.copy()
    result.thumbnail(size, Image.Resampling.LANCZOS)
    return result


def rounded_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str = PANEL,
    outline: str = BORDER,
    radius: int = 28,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def center_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    size: int,
    color: str = TEXT,
    bold: bool = False,
    center_x: int = 780,
) -> None:
    rendered = rtl(text)
    active_font = font(size, bold)
    box = draw.textbbox((0, 0), rendered, font=active_font)
    draw.text((center_x - (box[2] - box[0]) / 2, y), rendered, font=active_font, fill=color)


def right_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    size: int,
    color: str = TEXT,
    bold: bool = False,
) -> None:
    rendered = rtl(text)
    active_font = font(size, bold)
    box = draw.textbbox((0, 0), rendered, font=active_font)
    draw.text((x - (box[2] - box[0]), y), rendered, font=active_font, fill=color)


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def draw_background(frame_index: int) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    drift = math.sin(frame_index / FPS * 0.35)
    glow_draw.ellipse((760 + drift * 35, -190, 1340 + drift * 35, 390), fill=(33, 112, 78, 38))
    glow_draw.ellipse((-220 - drift * 20, 430, 380 - drift * 20, 1030), fill=(212, 173, 50, 24))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    canvas.alpha_composite(glow)
    return canvas


def draw_brand(draw: ImageDraw.ImageDraw, logo: Image.Image) -> None:
    logo_small = contain(logo, (62, 62))
    draw.rounded_rectangle((1118, 34, 1198, 114), radius=18, fill="#F2F4EF")
    # Pillow draw cannot alpha-composite, so the caller pastes the logo.
    right_text(draw, "مجلس الوزراء - إدارة القرارات", 1090, 42, 23, TEXT, True)
    right_text(draw, "تقرير تعريفي بالمشروع", 1090, 78, 18, MUTED)
    return logo_small


def draw_avatar(canvas: Image.Image, frames: list[Image.Image], frame_index: int, mode: str) -> None:
    sprite = frames[(frame_index // 3) % len(frames)]
    sprite = contain(sprite, (360, 590))
    bob = 0 if mode == "thinking" else int(math.sin(frame_index / FPS * 2.4) * 2)
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((75, 625, 390, 682), fill=(0, 0, 0, 75))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(sprite, (55 + (360 - sprite.width) // 2, 104 + bob))


def draw_title(draw: ImageDraw.ImageDraw, progress: float) -> None:
    offset = int((1 - ease(progress)) * 35)
    center_text(draw, "مُجيب", 198 + offset, 86, GOLD, True)
    center_text(draw, "المساعد القانوني العراقي المحلي", 304 + offset, 42, TEXT, True)
    center_text(draw, "بحث موثّق • خصوصية محلية • واجهة عربية", 380 + offset, 26, MUTED)
    rounded_panel(draw, (565, 468, 995, 540), PANEL_ALT, GREEN, 24, 2)
    center_text(draw, "معرفة قانونية أقرب إليك", 482, 29, TEXT, True)


def draw_retrieval(draw: ImageDraw.ImageDraw, progress: float) -> None:
    center_text(draw, "من الوثيقة إلى الإجابة الموثّقة", 146, 48, TEXT, True)
    labels = ["وثائق قانونية", "بحث وتحليل", "تحقق من المصادر", "إجابة عربية"]
    xs = [540, 720, 900, 1080]
    reveal = int(progress * len(labels) + 0.8)
    for index, (label, x) in enumerate(zip(labels, xs)):
        active = index < reveal
        fill = GREEN if active else PANEL
        border = GOLD if active else BORDER
        draw.rounded_rectangle((x - 72, 270, x + 72, 410), radius=25, fill=fill, outline=border, width=3)
        symbol = ["§", "⌕", "✓", "؟"][index]
        symbol_font = font(54, True)
        symbol_box = draw.textbbox((0, 0), symbol, font=symbol_font)
        draw.text((x - (symbol_box[2] - symbol_box[0]) / 2, 292), symbol, font=symbol_font, fill=TEXT)
        center_text(draw, label, 430, 23, TEXT if active else MUTED, index in (0, 3), x)
        if index < len(labels) - 1:
            draw.line((x + 82, 340, xs[index + 1] - 82, 340), fill=BORDER, width=5)
            draw.polygon(
                [(xs[index + 1] - 90, 332), (xs[index + 1] - 78, 340), (xs[index + 1] - 90, 348)],
                fill=GOLD if index + 1 < reveal else BORDER,
            )
    center_text(draw, "لا تُستخدم النتيجة قبل مطابقتها مع سجل المراجع", 540, 25, MUTED)


def draw_local(draw: ImageDraw.ImageDraw, progress: float) -> None:
    center_text(draw, "يعمل محلياً للمساعدة في حماية البيانات", 145, 46, TEXT, True)
    cards = [
        ("النموذج المحلي", "Qwen 2.5", "AI"),
        ("فهرسة المعرفة", "ChromaDB + bge-m3", "⌕"),
        ("الصوت العربي", "Piper + Whisper", "◖"),
    ]
    for index, (title, detail, icon) in enumerate(cards):
        x1 = 480 + index * 220
        lift = int((1 - ease(progress * 1.5 - index * 0.18)) * 35)
        rounded_panel(draw, (x1, 278 + lift, x1 + 196, 487 + lift), PANEL, BORDER, 24, 2)
        draw.ellipse((x1 + 64, 302 + lift, x1 + 132, 370 + lift), fill=GREEN, outline=GOLD, width=2)
        icon_font = font(33, True)
        ib = draw.textbbox((0, 0), icon, font=icon_font)
        draw.text((x1 + 98 - (ib[2] - ib[0]) / 2, 316 + lift), icon, font=icon_font, fill=TEXT)
        center_text(draw, title, 387 + lift, 25, TEXT, True, x1 + 98)
        detail_font = font(17)
        db = draw.textbbox((0, 0), detail, font=detail_font)
        draw.text((x1 + 98 - (db[2] - db[0]) / 2, 435 + lift), detail, font=detail_font, fill=MUTED)
    center_text(draw, "لا حاجة لإرسال الأسئلة القانونية إلى خدمة خارجية في المسار الأساسي", 555, 24, MUTED)


def draw_features(draw: ImageDraw.ImageDraw, progress: float) -> None:
    center_text(draw, "تجربة عربية متكاملة", 145, 48, TEXT, True)
    features = [
        "واجهة عربية من اليمين إلى اليسار",
        "محادثات وإدارة وثائق وقرارات",
        "وضع نهاري وليلي متجاوب",
        "اختيار الموديل حسب ذاكرة GPU",
    ]
    for index, item in enumerate(features):
        y = 260 + index * 76
        alpha_progress = ease(progress * 1.4 - index * 0.13)
        x_shift = int((1 - alpha_progress) * 45)
        rounded_panel(draw, (560 + x_shift, y, 1100 + x_shift, y + 56), PANEL, BORDER, 18, 2)
        draw.ellipse((1055 + x_shift, y + 13, 1085 + x_shift, y + 43), fill=GREEN)
        tick_font = font(20, True)
        draw.text((1062 + x_shift, y + 12), "✓", font=tick_font, fill=TEXT)
        right_text(draw, item, 1038 + x_shift, y + 13, 24, TEXT)


def draw_next_steps(draw: ImageDraw.ImageDraw, progress: float) -> None:
    center_text(draw, "المرحلة القادمة", 150, 50, GOLD, True)
    steps = [
        ("١", "توحيد مصدر البيانات القانوني"),
        ("٢", "إكمال اختبارات الأمان والأداء"),
        ("٣", "إطلاق نسخة تجريبية منظّمة"),
    ]
    for index, (number, label) in enumerate(steps):
        y = 274 + index * 96
        rounded_panel(draw, (560, y, 1075, y + 68), PANEL_ALT if index < int(progress * 4) else PANEL, BORDER, 20, 2)
        draw.ellipse((995, y + 9, 1045, y + 59), fill=GOLD if index < int(progress * 4) else GREEN)
        nfont = font(26, True)
        nb = draw.textbbox((0, 0), rtl(number), font=nfont)
        draw.text((1020 - (nb[2] - nb[0]) / 2, y + 18), rtl(number), font=nfont, fill=BG)
        right_text(draw, label, 970, y + 18, 27, TEXT, True)
    center_text(draw, "مُجيب — معرفة قانونية عراقية أقرب إليك", 610, 29, TEXT, True)


def section_for_time(time_seconds: float, duration: float) -> tuple[int, float]:
    boundaries = [0.0, 0.18, 0.40, 0.62, 0.82, 1.0]
    fraction = min(0.9999, time_seconds / duration)
    for index in range(len(boundaries) - 1):
        if boundaries[index] <= fraction < boundaries[index + 1]:
            local = (fraction - boundaries[index]) / (boundaries[index + 1] - boundaries[index])
            return index, local
    return 4, 1.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_PATH.write_bytes(synthesize_arabic(NARRATION, speed=1.08))
    with wave.open(str(AUDIO_PATH), "rb") as wav_file:
        audio_duration = wav_file.getnframes() / wav_file.getframerate()
    duration = max(28.0, audio_duration + 1.2)
    total_frames = math.ceil(duration * FPS)

    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo_small = contain(logo, (62, 62))
    idle = load_sprite_sheet("effendi-idle-8-aligned-transparent-v1.png")
    talking = load_sprite_sheet("effendi-talking-8-aligned-transparent-v1.png")
    thinking = load_sprite_sheet("effendi-thinking-chair-day-8-aligned-transparent-v1.png")

    writer = imageio_ffmpeg.write_frames(
        str(VIDEO_PATH),
        (WIDTH, HEIGHT),
        fps=FPS,
        codec="libx264",
        quality=7,
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
        audio_path=str(AUDIO_PATH),
        audio_codec="aac",
        output_params=["-movflags", "+faststart", "-shortest"],
        ffmpeg_log_level="warning",
    )
    writer.send(None)

    poster_saved = False
    try:
        for frame_index in range(total_frames):
            time_seconds = frame_index / FPS
            section, progress = section_for_time(time_seconds, duration)
            canvas = draw_background(frame_index)
            draw = ImageDraw.Draw(canvas)
            brand_logo = draw_brand(draw, logo)
            canvas.alpha_composite(brand_logo, (1127, 43))

            avatar_mode = "idle" if section in (0, 4) else "talking"
            if section == 1:
                avatar_mode = "thinking"
            frames = {"idle": idle, "talking": talking, "thinking": thinking}[avatar_mode]
            draw_avatar(canvas, frames, frame_index, avatar_mode)

            [draw_title, draw_retrieval, draw_local, draw_features, draw_next_steps][section](draw, progress)

            # Thin progress line at the bottom doubles as a restrained motion cue.
            draw.rounded_rectangle((460, 680, 1135, 687), radius=4, fill=BORDER)
            draw.rounded_rectangle(
                (460, 680, 460 + int(675 * min(1.0, time_seconds / duration)), 687),
                radius=4,
                fill=GOLD,
            )

            if not poster_saved and frame_index >= FPS:
                canvas.convert("RGB").save(POSTER_PATH, quality=95)
                poster_saved = True
            writer.send(np.asarray(canvas.convert("RGB")))
    finally:
        writer.close()

    print(f"VIDEO={VIDEO_PATH}")
    print(f"AUDIO={AUDIO_PATH}")
    print(f"POSTER={POSTER_PATH}")
    print(f"DURATION={duration:.2f}")
    print(f"FRAMES={total_frames}")


if __name__ == "__main__":
    main()
