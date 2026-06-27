"""视差滚动 HTML 模板渲染。"""

from __future__ import annotations

from string import Template
from typing import Any


def _reveal_timing(reveal: str) -> tuple[float, float]:
    if reveal == "early":
        return 0.12, 0.88
    if reveal == "mid":
        return 0.32, 0.68
    return 0.55, 0.45


_ZOOM_IN_HTML = Template(
    """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>$scene_title</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .scroll-container { height: 300vh; position: relative; }
    .sticky-stage {
      position: sticky; top: 0; height: 100vh; width: 100vw;
      overflow: hidden; display: flex; align-items: center; justify-content: center;
      background: #000;
    }
    .layer { position: absolute; will-change: transform, opacity; pointer-events: none; }
    #background-layer {
      z-index: 1; width: 120%; height: 120%; object-fit: cover;
      left: 50%; top: 50%; transform: translate(-50%, -50%);
    }
    #subject-layer {
      z-index: 2; max-height: 78vh; max-width: 88vw; width: auto; height: auto;
      left: 50%; top: 52%; transform: translate(-50%, -50%);
    }
    #text-layer {
      z-index: 3; max-height: 32vh; max-width: 92vw; width: auto; height: auto;
      left: 50%; top: 28%; transform: translate(-50%, -50%);
    }
    #text-layer.hidden-text { opacity: 0 !important; visibility: hidden; }
    .vignette {
      position: absolute; z-index: 4; inset: 0; pointer-events: none;
      box-shadow: inset 0 0 200px 50px rgba(0,0,0,0.72);
    }
    .scene-caption {
      position: fixed; bottom: 16px; left: 16px; right: 16px; z-index: 5;
      font-size: 12px; opacity: 0.45; text-align: center; pointer-events: none;
    }
    @media (prefers-reduced-motion: reduce) {
      .scroll-container { height: 100vh; }
      #subject-layer, #text-layer { opacity: 1 !important; transform: translate(-50%, -50%) !important; }
      #background-layer { transform: translate(-50%, -50%) scale(1.1) !important; }
    }
  </style>
</head>
<body>
  <div class="scroll-container">
    <div class="sticky-stage">
      <img id="background-layer" class="layer" alt="background" src="data:$bg_mime;base64,$bg_b64" />
      <img id="subject-layer" class="layer" alt="subject" src="data:$subject_mime;base64,$subject_b64" />
      <img id="text-layer" class="layer$text_cls pos-$text_pos" alt="text" data-reveal="$text_reveal" data-role="$text_role" src="data:$text_mime;base64,$text_b64" />
      <div class="vignette"></div>
    </div>
  </div>
  <p class="scene-caption">$scene_description · 向上滑动体验推镜头</p>
  <script>
    (function () {
      const container = document.querySelector('.scroll-container');
      const bg = document.getElementById('background-layer');
      const subject = document.getElementById('subject-layer');
      const text = document.getElementById('text-layer');
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reduced) return;

      function clamp(v, min, max) { return Math.min(max, Math.max(min, v)); }

      function onScroll() {
        const rect = container.getBoundingClientRect();
        const scrollable = rect.height - window.innerHeight;
        const progress = scrollable > 0 ? clamp(-rect.top / scrollable, 0, 1) : 0;

        const bgScale = 1 + progress * 0.3;
        bg.style.transform = 'translate(-50%, -50%) scale(' + bgScale + ')';

        const subScale = 0.8 + progress * 0.2;
        const subOpacity = Math.min(1, progress * 1.5);
        subject.style.transform = 'translate(-50%, -50%) scale(' + subScale + ')';
        subject.style.opacity = subOpacity;

        const textProgress = Math.max(0, (progress - 0.7) / 0.3);
        if (!text.classList.contains('hidden-text')) {
          text.style.opacity = textProgress;
          text.style.transform = 'translate(-50%, -50%) translateY(' + (40 - textProgress * 40) + 'px)';
        }
      }

      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    })();
  </script>
</body>
</html>
"""
)

_SCROLL_FOLLOW_HTML = Template(
    """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>$scene_title</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .scroll-container { height: 320vh; position: relative; }
    .sticky-stage {
      position: sticky; top: 0; height: 100vh; width: 100vw;
      overflow: hidden; display: flex; align-items: center; justify-content: center;
      background: #000;
    }
    .layer { position: absolute; will-change: transform, opacity; pointer-events: none; }
    #background-layer {
      z-index: 1; width: 100%; height: 100%; object-fit: cover;
      left: 50%; top: 50%; transform: translate(-50%, -50%);
    }
    #subject-layer {
      z-index: 2; max-height: 72vh; max-width: 90vw; width: auto; height: auto;
      left: 50%; top: 58%; transform: translate(-50%, -50%);
      filter: drop-shadow(0 12px 28px rgba(0,0,0,0.35));
    }
    #text-layer {
      z-index: 3; max-height: 28vh; max-width: 92vw; width: auto; height: auto;
      left: 50%; top: 22%; transform: translate(-50%, -50%);
    }
    #text-layer.hidden-text { opacity: 0 !important; visibility: hidden; }
    .vignette {
      position: absolute; z-index: 4; inset: 0; pointer-events: none;
      box-shadow: inset 0 0 160px 40px rgba(0,0,0,0.45);
    }
    .scene-caption {
      position: fixed; bottom: 16px; left: 16px; right: 16px; z-index: 5;
      font-size: 12px; opacity: 0.45; text-align: center; pointer-events: none;
    }
    @media (prefers-reduced-motion: reduce) {
      .scroll-container { height: 100vh; }
      #subject-layer, #text-layer { opacity: 1 !important; transform: translate(-50%, -50%) !important; }
    }
  </style>
</head>
<body>
  <div class="scroll-container">
    <div class="sticky-stage">
      <img id="background-layer" class="layer" alt="background" src="data:$bg_mime;base64,$bg_b64" />
      <img id="subject-layer" class="layer" alt="subject" src="data:$subject_mime;base64,$subject_b64" />
      <img id="text-layer" class="layer$text_cls pos-$text_pos" alt="text" data-reveal="$text_reveal" data-role="$text_role" src="data:$text_mime;base64,$text_b64" />
      <div class="vignette"></div>
    </div>
  </div>
  <p class="scene-caption">$scene_description · 背景固定，主体随滚动移动</p>
  <script>
    (function () {
      const container = document.querySelector('.scroll-container');
      const bg = document.getElementById('background-layer');
      const subject = document.getElementById('subject-layer');
      const text = document.getElementById('text-layer');
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reduced) return;

      function clamp(v, min, max) { return Math.min(max, Math.max(min, v)); }

      function onScroll() {
        const rect = container.getBoundingClientRect();
        const scrollable = rect.height - window.innerHeight;
        const progress = scrollable > 0 ? clamp(-rect.top / scrollable, 0, 1) : 0;

        // 背景层：完全固定，营造「场景不动」的纵深感
        bg.style.transform = 'translate(-50%, -50%)';

        // 主体层：随滚动向上位移（像微信长图里前景跟着走）
        const followY = 80 - progress * 160;
        const followX = -progress * 24;
        const subOpacity = Math.min(1, progress * 1.8);
        subject.style.opacity = subOpacity;
        subject.style.transform =
          'translate(calc(-50% + ' + followX + 'px), calc(-50% + ' + followY + 'px))';

        // 文字层
        if (!text.classList.contains('hidden-text')) {
          const textProgress = Math.max(0, (progress - $text_reveal_start) / $text_reveal_span);
          text.style.opacity = textProgress;
          text.style.transform = 'translate(-50%, calc(-50% + ' + (40 - textProgress * 40) + 'px))';
        }
      }

      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    })();
  </script>
</body>
</html>
"""
)

_PARALLAX_HTML = Template(
    """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>$scene_title</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .scroll-container { height: 300vh; position: relative; }
    .sticky-stage {
      position: sticky; top: 0; height: 100vh; width: 100vw;
      overflow: hidden; display: flex; align-items: center; justify-content: center;
      background: #000;
    }
    .layer { position: absolute; will-change: transform, opacity; pointer-events: none; }
    #background-layer {
      z-index: 1; width: 115%; height: 115%; object-fit: cover;
      left: 50%; top: 50%; transform: translate(-50%, -50%);
    }
    #subject-layer {
      z-index: 2; max-height: 78vh; max-width: 88vw;
      left: 50%; top: 52%; transform: translate(-50%, -50%);
    }
    #text-layer {
      z-index: 3; max-height: 32vh; max-width: 92vw;
      left: 50%; top: 30%; transform: translate(-50%, -50%);
    }
    #text-layer.hidden-text { opacity: 0 !important; visibility: hidden; }
    .vignette {
      position: absolute; z-index: 4; inset: 0; pointer-events: none;
      box-shadow: inset 0 0 180px 40px rgba(0,0,0,0.65);
    }
    .scene-caption {
      position: fixed; bottom: 16px; left: 16px; right: 16px; z-index: 5;
      font-size: 12px; opacity: 0.45; text-align: center; pointer-events: none;
    }
    @media (prefers-reduced-motion: reduce) {
      .scroll-container { height: 100vh; }
      #subject-layer, #text-layer { opacity: 1 !important; }
    }
  </style>
</head>
<body>
  <div class="scroll-container">
    <div class="sticky-stage">
      <img id="background-layer" class="layer" alt="background" src="data:$bg_mime;base64,$bg_b64" />
      <img id="subject-layer" class="layer" alt="subject" src="data:$subject_mime;base64,$subject_b64" />
      <img id="text-layer" class="layer$text_cls pos-$text_pos" alt="text" data-reveal="$text_reveal" data-role="$text_role" src="data:$text_mime;base64,$text_b64" />
      <div class="vignette"></div>
    </div>
  </div>
  <p class="scene-caption">$scene_description · 向上滑动体验横向视差</p>
  <script>
    (function () {
      const container = document.querySelector('.scroll-container');
      const bg = document.getElementById('background-layer');
      const subject = document.getElementById('subject-layer');
      const text = document.getElementById('text-layer');
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reduced) return;

      function clamp(v, min, max) { return Math.min(max, Math.max(min, v)); }

      function onScroll() {
        const rect = container.getBoundingClientRect();
        const scrollable = rect.height - window.innerHeight;
        const progress = scrollable > 0 ? clamp(-rect.top / scrollable, 0, 1) : 0;

        // 背景固定
        bg.style.transform = 'translate(-50%, -50%)';

        const subX = -progress * 48;
        const subOpacity = Math.min(1, progress * 1.4);
        subject.style.transform = 'translate(calc(-50% + ' + subX + 'px), -50%)';
        subject.style.opacity = subOpacity;

        const textX = 50 - progress * 50;
        if (!text.classList.contains('hidden-text')) {
          const textOpacity = Math.max(0, (progress - $text_reveal_start) / $text_reveal_span);
          text.style.transform = 'translate(calc(-50% + ' + textX + 'px), -50%)';
          text.style.opacity = textOpacity;
        }
      }

      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    })();
  </script>
</body>
</html>
"""
)


def render_parallax_html(plan: dict[str, Any], assets: dict[str, Any]) -> str:
    template_key = plan.get("cinematic_template", "scroll_follow")
    if template_key == "zoom_in":
        tpl = _ZOOM_IN_HTML
    elif template_key == "parallax_horizontal":
        tpl = _PARALLAX_HTML
    else:
        tpl = _SCROLL_FOLLOW_HTML
    title = plan.get("scene_description") or plan.get("text_content") or "电影感分层图文"
    has_text = assets.get("has_text", bool(plan.get("show_text")))
    text_cls = "" if has_text else " hidden-text"
    text_pos = plan.get("text_position") or assets.get("text_position") or "top"
    text_reveal = plan.get("text_reveal") or assets.get("text_reveal") or "late"
    text_role = plan.get("text_role") or assets.get("text_role") or ""
    start, span = _reveal_timing(text_reveal)
    return tpl.substitute(
        scene_title=title[:24],
        scene_description=plan.get("scene_description", ""),
        bg_b64=assets["background_b64"],
        bg_mime=assets["background_mime"],
        subject_b64=assets["subject_b64"],
        subject_mime=assets["subject_mime"],
        text_b64=assets["text_b64"],
        text_mime=assets["text_mime"],
        text_cls=text_cls,
        text_pos=text_pos,
        text_reveal=text_reveal,
        text_role=text_role,
        text_reveal_start=start,
        text_reveal_span=span,
    )


def _render_scene_section(beat: dict[str, Any], assets: dict[str, Any], index: int) -> str:
    beat_id = beat["id"]
    has_text = assets.get("has_text", beat.get("show_text", False))
    text_cls = "" if has_text else " hidden-text"
    text_pos = beat.get("text_position") or assets.get("text_position") or "top"
    text_reveal = beat.get("text_reveal") or assets.get("text_reveal") or "late"
    text_role = beat.get("text_role") or assets.get("text_role") or ""
    narration = beat.get("narration") or beat.get("scene_description") or f"第{beat_id}幕"
    text_label = f" · {beat['text_content']}" if has_text and beat.get("text_content") else ""
    return f"""
  <section class="scene" data-beat="{beat_id}" id="scene-{beat_id}" aria-label="第{beat_id}幕">
    <div class="scene-label">第 {beat_id} 幕 · {narration}{text_label}</div>
    <div class="scroll-container">
      <div class="sticky-stage">
        <img class="layer bg-layer" alt="background" src="data:{assets['background_mime']};base64,{assets['background_b64']}" />
        <img class="layer subject-layer" alt="subject" src="data:{assets['subject_mime']};base64,{assets['subject_b64']}" />
        <img class="layer text-layer{text_cls} pos-{text_pos}" alt="text" data-reveal="{text_reveal}" data-role="{text_role}" src="data:{assets['text_mime']};base64,{assets['text_b64']}" />
        <div class="vignette"></div>
      </div>
    </div>
  </section>"""


_SERIES_SCROLL_JS = """
      function clamp(v, min, max) { return Math.min(max, Math.max(min, v)); }

      function bindScene(scene) {
        const container = scene.querySelector('.scroll-container');
        const bg = scene.querySelector('.bg-layer');
        const subject = scene.querySelector('.subject-layer');
        const text = scene.querySelector('.text-layer');
        const hasText = !text.classList.contains('hidden-text');

        function onScroll() {
          const rect = container.getBoundingClientRect();
          const scrollable = rect.height - window.innerHeight;
          const progress = scrollable > 0 ? clamp(-rect.top / scrollable, 0, 1) : 0;

          bg.style.transform = 'translate(-50%, -50%)';

          const followY = 80 - progress * 160;
          const followX = -progress * 24;
          const subOpacity = Math.min(1, progress * 1.8);
          subject.style.opacity = subOpacity;
          subject.style.transform =
            'translate(calc(-50% + ' + followX + 'px), calc(-50% + ' + followY + 'px))';

          if (hasText) {
            const reveal = text.dataset.reveal || 'late';
            let start = 0.55;
            if (reveal === 'early') start = 0.12;
            if (reveal === 'mid') start = 0.32;
            const textProgress = Math.max(0, (progress - start) / Math.max(0.01, 1 - start));
            const textY = 30 - textProgress * 30;
            text.style.opacity = textProgress;
            text.style.transform = 'translate(-50%, calc(-50% + ' + textY + 'px))';
          }
        }

        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
      }

      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (!reduced) {
        document.querySelectorAll('.scene').forEach(bindScene);
      }
"""


def render_series_html(storyboard: dict[str, Any], beats_assets: list[dict[str, Any]]) -> str:
    title = storyboard.get("title") or "连续故事"
    style_note = storyboard.get("visual_style") or ""
    beats = storyboard["beats"]

    sections = []
    for i, beat in enumerate(beats):
        assets = beats_assets[i]
        sections.append(_render_scene_section(beat, assets, i))

    sections_html = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #0a0a0a; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .story-scroll {{ width: 100%; }}
    .scene {{ position: relative; border-bottom: 1px solid rgba(255,255,255,0.06); }}
    .scene-label {{
      position: absolute; top: 12px; left: 16px; z-index: 10;
      font-size: 11px; opacity: 0.5; letter-spacing: 0.06em;
      pointer-events: none; text-shadow: 0 1px 4px #000;
    }}
    .scroll-container {{ height: 300vh; position: relative; }}
    .sticky-stage {{
      position: sticky; top: 0; height: 100vh; width: 100vw;
      overflow: hidden; background: #000;
    }}
    .layer {{ position: absolute; will-change: transform, opacity; pointer-events: none; }}
    .bg-layer {{
      z-index: 1; width: 100%; height: 100%; object-fit: cover;
      left: 50%; top: 50%; transform: translate(-50%, -50%);
    }}
    .subject-layer {{
      z-index: 2; max-height: 72vh; max-width: 90vw;
      left: 50%; top: 58%; transform: translate(-50%, -50%);
      filter: drop-shadow(0 10px 24px rgba(0,0,0,0.4));
    }}
    .text-layer {{
      z-index: 3; max-height: 28vh; max-width: 92vw;
      left: 50%; top: 22%; transform: translate(-50%, -50%);
    }}
    .text-layer.hidden-text {{ opacity: 0 !important; visibility: hidden; }}
    .vignette {{
      position: absolute; z-index: 4; inset: 0; pointer-events: none;
      box-shadow: inset 0 0 140px 36px rgba(0,0,0,0.42);
    }}
    .story-footer {{
      padding: 24px; text-align: center; font-size: 12px; opacity: 0.4;
    }}
    @media (prefers-reduced-motion: reduce) {{
      .scroll-container {{ height: 100vh; }}
    }}
  </style>
</head>
<body>
  <div class="story-scroll">
{sections_html}
  </div>
  <p class="story-footer">{title} · {style_note} · 共 {len(beats)} 幕，向上连续滑动阅读</p>
  <script>
    (function () {{
{_SERIES_SCROLL_JS}
    }})();
  </script>
</body>
</html>"""


def _sprite_layer_markup(sprite: dict[str, Any]) -> str:
    sid = sprite["id"]
    text_cls = "" if sprite.get("has_text") else " hidden-text"
    text_pos = sprite.get("text_position") or "top"
    text_reveal = sprite.get("text_reveal") or "late"
    text_role = sprite.get("text_role") or "none"
    text_html = ""
    if sprite.get("has_text"):
        text_html = f"""
      <img
        class="sprite-text{text_cls} pos-{text_pos}"
        id="sprite-text-{sid}"
        alt="text"
        data-sprite-id="{sid}"
        data-reveal="{text_reveal}"
        data-role="{text_role}"
        src="data:{sprite['text_mime']};base64,{sprite['text_b64']}"
      />"""

    return f"""
      <img
        class="sprite-layer"
        id="sprite-{sid}"
        alt="{sprite.get('label', 'sprite')}"
        data-anchor-y="{sprite['anchor_y_norm']}"
        data-anchor-x="{sprite.get('anchor_x', 0.5)}"
        data-scale="{sprite.get('scale', 0.32)}"
        data-parallax="{sprite.get('parallax', 'scroll_follow')}"
        data-scroll-start="{sprite.get('scroll_start', 0)}"
        data-scroll-end="{sprite.get('scroll_end', 1)}"
        style="z-index: {sprite.get('z_index', 10)}"
        src="data:{sprite['mime']};base64,{sprite['b64']}"
      />{text_html}"""


def render_strip_scroll_html(plan: dict[str, Any], assets: dict[str, Any]) -> str:
    """连续底图长卷 + 漫画精灵视差层。"""
    title = plan.get("title") or "连续长卷"
    style_note = plan.get("visual_style") or ""
    scroll_vh = int(plan.get("estimated_scroll_screens") or assets.get("tile_count", 3)) * 100
    scroll_vh = max(300, min(1400, scroll_vh))
    tile_count = assets.get("tile_count", len(plan.get("background_tiles", [])))
    sprite_count = assets.get("sprite_count", len(assets.get("sprites", [])))
    sprites = assets.get("sprites") or []
    sprite_layers_html = "".join(_sprite_layer_markup(s) for s in sprites)
    hud_sprites = f" · {sprite_count} 个漫画精灵" if sprite_count else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #0a0a0a; color: #e8e8e8; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .scroll-root {{
      position: relative;
      height: {scroll_vh}vh;
    }}
    .viewport {{
      position: sticky;
      top: 0;
      height: 100vh;
      width: 100vw;
      overflow: hidden;
      background: #0a0a0a;
    }}
    .bg-strip {{
      position: absolute;
      left: 0;
      top: 0;
      width: 100%;
      height: auto;
      min-height: 100vh;
      will-change: transform;
      display: block;
      z-index: 1;
    }}
    .sprite-layer {{
      position: absolute;
      width: auto;
      height: auto;
      max-width: 48vw;
      will-change: transform, opacity;
      pointer-events: none;
      filter: drop-shadow(0 8px 20px rgba(0,0,0,0.38));
      opacity: 0;
    }}
    .sprite-text {{
      position: absolute;
      width: auto;
      height: auto;
      max-width: 72vw;
      max-height: 18vh;
      will-change: transform, opacity;
      pointer-events: none;
      z-index: 40;
      opacity: 0;
    }}
    .sprite-text.hidden-text {{ display: none; }}
    .vignette {{
      position: absolute;
      inset: 0;
      pointer-events: none;
      box-shadow: inset 0 0 120px 30px rgba(0,0,0,0.35);
      z-index: 50;
    }}
    .hud {{
      position: fixed;
      bottom: 14px;
      left: 0;
      right: 0;
      text-align: center;
      font-size: 11px;
      opacity: 0.45;
      z-index: 60;
      pointer-events: none;
      text-shadow: 0 1px 3px #000;
    }}
    .progress-bar {{
      position: fixed;
      top: 0;
      left: 0;
      height: 2px;
      width: 0%;
      background: linear-gradient(90deg, #5ec4d4, #c67f07);
      z-index: 70;
      transition: width 0.08s linear;
    }}
    @media (prefers-reduced-motion: reduce) {{
      .scroll-root {{ height: 100vh; }}
      .bg-strip {{ transform: none !important; }}
      .sprite-layer, .sprite-text {{ opacity: 1 !important; }}
    }}
  </style>
</head>
<body>
  <div class="progress-bar" id="progress-bar"></div>
  <div class="scroll-root" id="scroll-root">
    <div class="viewport" id="viewport">
      <img
        id="bg-strip"
        class="bg-strip"
        alt="连续底图长卷"
        src="data:{assets['strip_mime']};base64,{assets['strip_b64']}"
        width="{assets.get('strip_width', '')}"
        height="{assets.get('strip_height', '')}"
      />
{sprite_layers_html}
      <div class="vignette"></div>
    </div>
  </div>
  <p class="hud">{title} · {style_note} · {tile_count} 段无缝底图{hud_sprites} · 上滑穿越长卷</p>
  <script>
    (function () {{
      const root = document.getElementById('scroll-root');
      const bg = document.getElementById('bg-strip');
      const bar = document.getElementById('progress-bar');
      const sprites = Array.from(document.querySelectorAll('.sprite-layer'));
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      function clamp(v, min, max) {{ return Math.min(max, Math.max(min, v)); }}

      function fadeWindow(progress, start, end) {{
        if (progress < start || progress > end) return 0;
        const span = Math.max(0.04, end - start);
        const edge = Math.min(0.12, span * 0.25);
        if (progress < start + edge) return (progress - start) / edge;
        if (progress > end - edge) return (end - progress) / edge;
        return 1;
      }}

      function revealStart(reveal) {{
        if (reveal === 'early') return 0.12;
        if (reveal === 'mid') return 0.32;
        return 0.55;
      }}

      function maxPan() {{
        const imgH = bg.offsetHeight || bg.naturalHeight || window.innerHeight;
        return Math.max(0, imgH - window.innerHeight);
      }}

      function panFactor(mode) {{
        if (mode === 'slow') return 0.82;
        if (mode === 'fast') return 1.14;
        return 1;
      }}

      function placeSprites(progress, pan) {{
        const imgH = bg.offsetHeight || bg.naturalHeight || window.innerHeight;
        sprites.forEach((el) => {{
          const start = parseFloat(el.dataset.scrollStart || '0');
          const end = parseFloat(el.dataset.scrollEnd || '1');
          const local = end > start ? clamp((progress - start) / (end - start), 0, 1) : progress;
          const opacity = fadeWindow(progress, start, end);
          const parallax = el.dataset.parallax || 'scroll_follow';
          const anchorX = parseFloat(el.dataset.anchorX || '0.5');
          const scale = parseFloat(el.dataset.scale || '0.32');
          const maxH = scale * window.innerHeight;

          let topPx;
          let extraX = 0;
          let extraY = 0;

          if (parallax === 'fixed') {{
            topPx = parseFloat(el.dataset.anchorY || '0.6') * window.innerHeight;
          }} else {{
            const anchorY = parseFloat(el.dataset.anchorY || '0.5');
            const anchorPx = anchorY * imgH;
            topPx = anchorPx - pan * panFactor(parallax);
            if (parallax === 'scroll_follow') {{
              extraY = 36 - local * 72;
              extraX = -local * 18;
            }}
          }}

          el.style.maxHeight = maxH + 'px';
          el.style.left = (anchorX * 100) + '%';
          el.style.top = topPx + 'px';
          el.style.opacity = opacity;
          el.style.transform = 'translate(-50%, -50%) translate(' + extraX + 'px, ' + extraY + 'px)';

          const text = document.getElementById('sprite-text-' + el.id.replace('sprite-', ''));
          if (text && !text.classList.contains('hidden-text')) {{
            const reveal = text.dataset.reveal || 'late';
            const rs = revealStart(reveal);
            const textProgress = clamp((local - rs) / Math.max(0.08, 1 - rs), 0, 1);
            const textOpacity = opacity * textProgress;
            const textLift = 28 - textProgress * 28;
            text.style.maxHeight = (maxH * 0.55) + 'px';
            text.style.left = el.style.left;
            text.style.top = (topPx - maxH * 0.42) + 'px';
            text.style.opacity = textOpacity;
            text.style.transform = 'translate(-50%, -50%) translateY(' + textLift + 'px)';
          }}
        }});
      }}

      function onScroll() {{
        const rect = root.getBoundingClientRect();
        const scrollable = root.offsetHeight - window.innerHeight;
        const progress = scrollable > 0 ? clamp(-rect.top / scrollable, 0, 1) : 0;
        const pan = progress * maxPan();
        bg.style.transform = 'translateY(' + (-pan) + 'px)';
        bar.style.width = (progress * 100) + '%';
        if (!reduced) placeSprites(progress, pan);
      }}

      if (reduced) {{
        sprites.forEach((el) => {{ el.style.opacity = '1'; }});
        return;
      }}

      if (bg.complete) onScroll();
      else bg.addEventListener('load', onScroll);
      window.addEventListener('scroll', onScroll, {{ passive: true }});
      window.addEventListener('resize', onScroll);
    }})();
  </script>
</body>
</html>"""
