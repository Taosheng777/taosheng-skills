"""Prepare readable caption layers before expensive video rendering.

Quiet/plate layout adapted from sweety-handdraw-video caption_assets.py at
5206ec0d17f9b353e400b64b9c51ad69e721e02a (MIT; see ../LICENSE).
The footer mode preserves existing timed jobs.
"""
import math
from pathlib import Path
from PIL import Image, ImageColor, ImageDraw, ImageFont
from media_checks import validate_captions


class CaptionLayer:
    def __init__(self, spec, root, duration):
        self.captions = spec.get("captions", [])
        validate_captions(self.captions, duration)
        self.layers = []
        if not self.captions:
            return
        options = spec.get("caption_style", {})
        mode = options.get("mode", "footer")
        if mode not in {"footer", "quiet", "plate"}:
            raise ValueError("字幕 mode 只能为 footer、quiet 或 plate")
        width, height = spec["canvas"]["width"], spec["canvas"]["height"]
        configured = options.get("font")
        if configured is None and mode == "footer":
            configured = spec["font"]
        if configured is None:
            for candidate in ("/System/Library/Fonts/Hiragino Sans GB.ttc",
                              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
                if Path(candidate).is_file():
                    configured = {"path": candidate, "index": 0}
                    break
        if configured is None:
            raise ValueError("请指定独立的常规字幕字体 caption_style.font")
        self.font_path = (Path(root) / configured["path"]).expanduser().resolve()
        size = int(options.get("size", 42 if mode == "footer" else max(18, round(height * 38 / 1080))))
        bottom = int(options.get("bottom", 110 if mode == "footer" else round(height * .05)))
        ratio = float(options.get("max_width_ratio", .88))
        stroke = int(options.get("stroke_width", 0 if mode == "footer" else 2))
        if size <= 0 or bottom < 0 or not math.isfinite(ratio) or not 0 < ratio <= .95 or not 0 <= stroke <= 4:
            raise ValueError("字幕字号、边距、最大宽度或描边无效")
        font = ImageFont.truetype(str(self.font_path), size, index=int(configured.get("index", 0)))
        max_lines = options.get("max_lines", None if mode == "footer" else 2)
        if max_lines is not None:
            max_lines = int(max_lines)
        if max_lines is not None and max_lines < 1:
            raise ValueError("字幕至少允许一行")
        for caption in self.captions:
            lines = caption["text"].split("\n")
            if (max_lines is not None and len(lines) > max_lines) or any(not line.strip() for line in lines):
                raise ValueError("字幕含空行或过多行；先按意思和声音拆句")
            boxes = [font.getbbox(line, stroke_width=stroke) for line in lines]
            if any(max(font.getlength(line), box[2] - box[0]) > width * ratio
                   for line, box in zip(lines, boxes)):
                raise ValueError("字幕过宽；在 build 前按意思和声音拆句")
            if mode == "footer":
                line_h = round(size * 1.45)
                y = height - bottom - line_h * len(lines)
                if y - 14 < 0 or any(y + i * line_h + box[3] > height for i, box in enumerate(boxes)):
                    raise ValueError("字幕超出画布上下边界")
                layer = Image.new("RGBA", (width, height - y + 14), options.get("background", "#FFFFFF"))
                draw = ImageDraw.Draw(layer)
                for i, line in enumerate(lines):
                    draw.text(((width - font.getlength(line)) / 2, 14 + i * line_h), line,
                              font=font, fill=options.get("color", "#243340"),
                              stroke_width=stroke, stroke_fill=options.get("stroke_color", "#000000"))
                x, y = 0, y - 14
            else:
                margin = 6 + stroke
                line_h = max(box[3] - box[1] for box in boxes)
                gap = round(size * .18)
                lw = max(box[2] - box[0] for box in boxes) + 2 * margin
                lh = line_h * len(lines) + gap * (len(lines) - 1) + 2 * margin
                x, y = (width - lw) // 2, height - bottom - lh
                if x < 0 or y < 0:
                    raise ValueError("字幕图层超出画布")
                layer = Image.new("RGBA", (lw, lh))
                draw = ImageDraw.Draw(layer)
                if mode == "plate":
                    background = options.get("background", {"color": "#243039", "opacity": .76})
                    opacity = float(background.get("opacity", .76))
                    if not math.isfinite(opacity) or not 0 < opacity <= 1:
                        raise ValueError("字幕底板透明度必须在 0..1")
                    color = ImageColor.getrgb(background.get("color", "#243039"))[:3] + (round(255 * opacity),)
                    draw.rounded_rectangle((0, 0, lw - 1, lh - 1), radius=round(size * .2), fill=color)
                for i, (line, box) in enumerate(zip(lines, boxes)):
                    tx = (lw - (box[2] - box[0])) / 2 - box[0]
                    ty = margin + i * (line_h + gap) - box[1]
                    draw.text((tx, ty), line, font=font, fill=options.get("color", "#FFFFFF"),
                              stroke_width=stroke, stroke_fill=options.get("stroke_color", "#000000"))
            self.layers.append((float(caption["start"]), float(caption["end"]), layer, (x, y)))

    def draw(self, frame, time):
        for start, end, layer, position in self.layers:
            if start <= time < end:
                frame.alpha_composite(layer, position)
                break
        return frame
