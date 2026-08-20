"""LS 图片 Prompt 生产线 · 风格锚 v1.0（手册一字不改）。"""

from __future__ import annotations

import json
from typing import Any

STYLE_VERSION = "v1.0"

NEGATIVE = (
    "no text, no letters, no numbers, no watermark, no logo, no signature, "
    "no realistic human face close-up, no photo collage, no neon glow, "
    "no rainbow gradients, no clutter, no extra unrelated objects"
)

ANCHORS = {
    "cover": (
        "Flat vector illustration, modern editorial style, soft matte texture, "
        "dominant deep violet and lavender palette (#7A68EE, #BDB0F7, #EBE7FD) "
        "with warm off-white background (#F8F8FC), one small accent of muted gold, "
        "calm and composed mood, generous negative space, clean geometric shapes, "
        "subtle grain, flat lighting"
    ),
    "goal": (
        "Minimal geometric landscape illustration, layered flat shapes with soft depth, "
        "monochromatic violet scale from deep indigo (#312878) to pale lavender (#F4F2FE), "
        "distant layers lighter and lower contrast, crisp clean edges, no texture noise, "
        "airy negative space occupying upper half, serene and determined mood, "
        "flat design, no outlines"
    ),
    "spot": (
        "Simple geometric spot illustration, one single object or one tiny scene, "
        "flat violet and lavender palette (#7A68EE, #BDB0F7, #EBE7FD) on transparent background, "
        "thick-and-thin balance of shapes, 1.5px line details, soft rounded corners everywhere, "
        "friendly but restrained, no facial expressions beyond two dots and one curve at most"
    ),
    "vocabulary": (
        "flat vector icon illustration, centered composition, "
        "one object only filling 70% of the frame, soft violet-tinted neutral palette "
        "with the object's natural colors slightly desaturated, clean simple shapes, "
        "rounded corners, no outline heavier than 2px, plain background removed, "
        "educational flashcard style, instantly recognizable at small size"
    ),
    "sentence": (
        "Flat vector illustration, modern editorial style, soft matte texture, "
        "dominant deep violet and lavender palette (#7A68EE, #BDB0F7, #EBE7FD) "
        "with warm off-white background (#F8F8FC), calm mood, clean geometric shapes, "
        "subtle grain, flat lighting"
    ),
}

COMPOSITIONS = {
    "centered": "centered composition, single focal object",
    "thirds": "rule of thirds, subject on the right, space for title on the left",
    "panorama": "horizontal panorama with layered depth",
}

MOTIFS = {
    "mountain_path": (
        "a quiet winding mountain path in the lower left, a pale peak in the upper right, "
        "a single trail connecting them"
    ),
    "skyline": (
        "a small desk with a monitor and a coffee cup on quiet ground in the lower left, "
        "a distant city skyline across calm water in the upper right, "
        "a single narrow bridge path connecting the desk to the city"
    ),
    "book_steps": (
        "a stack of books forming steps in the lower left, an open archway of light in the upper right, "
        "a path of pages connecting them"
    ),
    "bridge": (
        "two river banks, a simple geometric bridge spanning from lower left to upper right"
    ),
    "harbor": (
        "a small boat at a quiet pier in the lower left, a lighthouse across water in the upper right, "
        "a calm channel connecting them"
    ),
    "doorway": (
        "a closed geometric door in the lower left, a corridor of light in the upper right, "
        "a straight path connecting them"
    ),
    "runway": (
        "a short runway strip in the lower left, a distant hangar of light in the upper right, "
        "a painted center line connecting them"
    ),
    "compass": (
        "a simple compass on quiet ground in the lower left, an open horizon in the upper right, "
        "a dotted bearing line connecting them"
    ),
}

SPOT_KIND_SUBJECT = {
    "empty": "An open empty book with a small violet bookmark ribbon, floating 2-3 tiny stars around",
    "onboarding": "A small violet flag planted on a round hilltop, a dotted path line leading to it",
    "badge": (
        "A geometric flame icon inside a circular medal, circular medal composition, "
        "muted gold accent (#C9A227) on violet base, subtle radial depth, centered"
    ),
    "error": (
        "A small geometric cloud with a single rain drop paused mid-air, "
        "a tiny violet arrow circling back (retry metaphor)"
    ),
}

POS_TEMPLATES = {
    "noun": "a single {visual}",
    "verb": "{visual}",
    "adjective": "{visual}",
    "abstract": "{visual}",
    "phrase": "{visual}",
}

# glm-image 推荐枚举值：1280x1280 (默认), 1568×1056, 1056×1568, 1472×1088, 1088×1472, 1728×960, 960×1728。自定义参数:长宽推荐设置在1024px-2048px范围内,并保证最大像素数不超过2^22px;长宽均需为32的整数倍。
# 其它模型推荐枚举值：1024x1024 (默认), 768x1344, 864x1152, 1344x768, 1152x864, 1440x720, 720x1440。自定义参数：长宽均需满足512px-2048px之间，需被16整除，并保证最大像素数不超过2^21px。
MODE_SPEC = {
    "cover": {"size": "1024x1024", "transparent": False, "filename": "cover.png"},
    "goal": {"size": "1024x1024", "transparent": False, "filename": "goal.png"},
    "spot": {"size": "1024x1024", "transparent": True, "filename": "spot.png"},
    "vocabulary": {"size": "1024x1024", "transparent": True, "filename": "vocab.png"},
    "sentence": {"size": "1024x1024", "transparent": False, "filename": "sentence.png"},
}

MODES = tuple(MODE_SPEC.keys())


def _join(*parts: str) -> str:
    return ", ".join(p.strip().rstrip(",") for p in parts if p and p.strip())


def cover_prompt(subject: str, composition: str = "centered") -> str:
    comp = COMPOSITIONS.get(composition, COMPOSITIONS["centered"])
    return _join(subject, comp, ANCHORS["cover"], NEGATIVE, "16:9, 2K")


def goal_prompt_from_motif(motif: str) -> str:
    scene = MOTIFS.get(motif) or MOTIFS["mountain_path"]
    return _join(scene, ANCHORS["goal"], NEGATIVE, "16:9, 2K")


def goal_prompt_from_scenes(current_scene: str, goal_scene: str, connector: str) -> str:
    body = (
        f"{current_scene}, in the lower left foreground, {goal_scene}, "
        f"in the upper right distance, {connector} connecting the foreground to the distance"
    )
    return _join(body, ANCHORS["goal"], NEGATIVE, "16:9, 2K")


def spot_prompt(subject: str, kind: str = "empty") -> str:
    text = subject.strip() or SPOT_KIND_SUBJECT.get(kind, SPOT_KIND_SUBJECT["empty"])
    extra = ""
    if kind == "badge" and "circular medal" not in text:
        extra = (
            "circular medal composition, muted gold accent (#C9A227) on violet base, "
            "subtle radial depth, centered"
        )
    return _join(text, extra, ANCHORS["spot"], NEGATIVE, "1:1, transparent, 1K")


def vocabulary_prompt(visual: str) -> str:
    scene = visual.strip()
    if not scene.lower().startswith("a single") and "," not in scene[:24]:
        scene = f"a single {scene}"
    return _join(
        scene,
        ANCHORS["vocabulary"],
        NEGATIVE,
        "no printed text on object, no background scenery",
        "1:1, transparent, 1K",
    )


def sentence_prompt(text: str) -> str:
    return _join(
        f"a quiet scene that illustrates: {text.strip()}",
        "single focal group, no people with faces",
        ANCHORS["sentence"],
        NEGATIVE,
        "3:2, 1K",
    )


def visual_from_lemma(lemma: str, pos: str, sense: str = "") -> str:
    word = (lemma or "").strip()
    gloss = (sense or "").strip()
    bucket = (pos or "noun").strip().lower()
    if gloss:
        return gloss if bucket != "noun" else f"a single {gloss}"
    if bucket == "verb":
        return f"a {word} action shown with three motion lines, no people"
    if bucket == "adjective":
        return f"two of the same object, one {word} and one opposite"
    if bucket == "abstract":
        return f"a simple metaphor object for {word}"
    if bucket == "phrase":
        return f"a tiny two-element scene for {word}"
    return f"a single {word}"


def translate_goal_scenes(profile: dict[str, Any]) -> dict[str, str] | None:
    try:
        from _lib.llm import get_client, is_llm_available
    except ImportError:
        return None
    if not is_llm_available():
        return None
    client = get_client()
    if client is None:
        return None
    system = (
        "You are an art director for a language-learning product. Convert a learner's "
        "profile into a minimal geometric illustration scene description.\n\n"
        'Input: { "identity": "...", "current": "...", "goal": "...", "language": "..." }\n\n'
        "Output strict JSON only:\n"
        "{\n"
        '  "current_scene": "2-4 concrete physical objects describing the learner\'s PRESENT situation, lower-left foreground",\n'
        '  "goal_scene": "1 concrete physical subject describing the learner\'s GOAL, upper-right distance",\n'
        '  "connector": "one connecting element: a path, river, road, bridge, or flight trail"\n'
        "}\n\n"
        "Rules:\n"
        '- Only concrete, drawable, physical objects. No abstract concepts (no "success", no "dream").\n'
        "- No people, no faces, no text, no letters, no logos, no flags with symbols.\n"
        "- No sun, moon, stars, or clock — nothing that indicates a specific time.\n"
        "- Each element describable in under 8 English words.\n"
        "- Objects must be culturally neutral unless the goal explicitly names a culture.\n"
        '- If the goal is too vague, output { "fallback": true }.'
    )
    payload = {
        "identity": profile.get("identity"),
        "current": profile.get("current"),
        "goal": profile.get("goal"),
        "language": profile.get("language"),
    }
    try:
        raw = client.chat_json(
            json.dumps(payload, ensure_ascii=False),
            system=system,
        )
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(raw, dict) or raw.get("fallback"):
        return None
    current = str(raw.get("current_scene") or "").strip()
    goal = str(raw.get("goal_scene") or "").strip()
    connector = str(raw.get("connector") or "").strip()
    if not (current and goal and connector):
        return None
    return {"current_scene": current, "goal_scene": goal, "connector": connector}
