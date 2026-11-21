from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from datetime import datetime

def _font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()

def create_forecast_graphic(location, headline, details, output_path):
    w, h = 1600, 900
    im = Image.new("RGB", (w, h), "#081321")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w, 18), fill="#1688e8")
    d.rectangle((0, 18, w, 900), outline="#183c5c", width=3)
    d.text((78, 66), "STORMCORE", font=_font(38, True), fill="#55b7ff")
    d.text((78, 135), "WEATHER CENTER  /  FORECAST", font=_font(22, True), fill="#91a9bf")
    d.line((78, 190, 1520, 190), fill="#23415c", width=3)
    d.text((78, 240), location.upper(), font=_font(58, True), fill="white")
    d.text((78, 355), headline, font=_font(44, True), fill="#ff555d")
    # Wrap details to fit the graphic.
    words, lines, line = details.split(), [], ""
    for word in words:
        test = (line + " " + word).strip()
        if d.textbbox((0, 0), test, font=_font(29))[2] > 1370:
            lines.append(line); line = word
        else:
            line = test
    if line:
        lines.append(line)
    y = 455
    for ln in lines[:5]:
        d.text((82, y), ln, font=_font(29), fill="#d9e7f3")
        y += 52
    d.rounded_rectangle((78, 755, 1520, 835), radius=18, fill="#102a43", outline="#28577c", width=2)
    stamp = datetime.now().strftime("%A, %B %d, %Y  •  %I:%M %p")
    d.text((105, 780), f"STORMCORE BROADCAST GRAPHIC     |     {stamp}", font=_font(20, True), fill="#8db6d6")
    im.save(output_path)
    return str(output_path)
