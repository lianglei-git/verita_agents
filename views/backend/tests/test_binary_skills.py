"""tts.speak / image.generate：预签 PUT、mode 枚举、信封元数据。不纳入 E9 五技能清单。"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.agents import get_agent, list_agents, run_agent
from backend.agents.loader import AGENTS_ROOT
from backend.config import SHARED_DIR

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from _lib.binary.put import BinaryError, parse_upload, put_bytes  # noqa: E402
from _lib.image.png import png_size  # noqa: E402

# 1x1 transparent PNG
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

FIXTURE_ROOT = Path(SHARED_DIR) / "ls-fixtures"
FORBIDDEN = ("object_id", "asset_id", "activity_id")


def _walk_keys(obj, found: set[str]) -> None:
    if isinstance(obj, dict):
        found.update(obj)
        for v in obj.values():
            _walk_keys(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk_keys(item, found)


class BinaryUploadTest(unittest.TestCase):
    def test_parse_upload(self):
        spec = parse_upload(
            {
                "url": "https://example.invalid/put",
                "method": "PUT",
                "headers": {"Content-Type": "audio/mpeg"},
                "expires_at": "2026-08-19T04:00:00.000Z",
                "max_bytes": 100,
            }
        )
        self.assertEqual(spec["method"], "PUT")
        self.assertEqual(spec["max_bytes"], 100)

    def test_missing_url(self):
        with self.assertRaises(BinaryError) as ctx:
            parse_upload({"method": "PUT"})
        self.assertEqual(ctx.exception.code, "missing_upload")

    def test_payload_too_large(self):
        with self.assertRaises(BinaryError) as ctx:
            put_bytes(
                {
                    "url": "https://example.invalid/put",
                    "method": "PUT",
                    "headers": {"Content-Type": "image/png"},
                    "max_bytes": 4,
                },
                b"12345",
                default_content_type="image/png",
            )
        self.assertEqual(ctx.exception.code, "payload_too_large")

    def test_expired(self):
        with self.assertRaises(BinaryError) as ctx:
            put_bytes(
                {
                    "url": "https://example.invalid/put",
                    "method": "PUT",
                    "expires_at": "2000-01-01T00:00:00.000Z",
                    "max_bytes": 1000,
                },
                b"ok",
                default_content_type="audio/mpeg",
            )
        self.assertEqual(ctx.exception.code, "upload_expired")


class ImagePromptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = get_agent("image.generate")
        cls.mod = spec["module"]

    def test_modes(self):
        self.assertEqual(
            self.mod.MODES,
            ("cover", "goal", "spot", "vocabulary", "sentence"),
        )

    def test_cover_prompt_locks_anchor(self):
        prompt, meta = self.mod.build_prompt(
            "cover",
            {"subject": "A hotel reception bell", "composition": "thirds"},
            "",
        )
        self.assertIn("#7A68EE", prompt)
        self.assertIn("rule of thirds", prompt)
        self.assertIn("no text", prompt)
        self.assertEqual(meta["composition"], "thirds")
        self.assertNotIn("http", prompt.lower())

    def test_goal_motif_fallback(self):
        prompt, meta = self.mod.build_prompt("goal", {"motif": "skyline"}, "")
        self.assertEqual(meta["track"], "a")
        self.assertIn("city skyline", prompt)

    def test_invalid_mode(self):
        result = run_agent("image.generate", "", mode="wallpaper")
        self.assertEqual(result["error"], "invalid_mode")

    def test_empty_cover(self):
        result = run_agent("image.generate", "", mode="cover", subject="  ")
        self.assertEqual(result["error"], "empty_subject")


class ImageGenerateRunTest(unittest.TestCase):
    def test_put_and_clean_output(self):
        spec = get_agent("image.generate")
        mod = spec["module"]
        upload = {
            "url": "https://example.invalid/put",
            "method": "PUT",
            "headers": {"Content-Type": "image/png"},
            "max_bytes": 10485760,
        }
        client = MagicMock()
        client.generate.return_value = {"b64_json": base64.b64encode(TINY_PNG).decode(), "url": None}
        client.cfg.model = "glm-image"
        with (
            patch.object(mod, "is_image_api_available", return_value=True),
            patch.object(mod, "get_image_client", return_value=client),
            patch.object(mod, "put_bytes") as pb,
        ):
            result = run_agent(
                "image.generate",
                "",
                mode="spot",
                kind="empty",
                upload=upload,
            )
        pb.assert_called_once()
        out = result["output"]
        self.assertTrue(out["uploaded"])
        self.assertEqual(out["mime"], "image/png")
        self.assertTrue(str(out["filename"]).endswith(".png"))
        self.assertEqual(png_size(TINY_PNG), (out["width"], out["height"]))
        self.assertNotIn("prompt", out)
        self.assertNotIn("url", out)
        blob = json.dumps(out)
        for banned in FORBIDDEN + ("http://", "https://", "base64"):
            self.assertNotIn(banned, blob)
        self.assertEqual(result["usage"]["tokens"], 1)

    def test_workbench_preview_outside_output(self):
        spec = get_agent("image.generate")
        mod = spec["module"]
        client = MagicMock()
        client.generate.return_value = {"b64_json": base64.b64encode(TINY_PNG).decode(), "url": None}
        client.cfg.model = "glm-image"
        with tempfile.TemporaryDirectory() as td:
            with (
                patch.object(mod, "is_image_api_available", return_value=True),
                patch.object(mod, "get_image_client", return_value=client),
                patch.dict(os.environ, {"IMAGE_MEDIA_DIR": td}),
            ):
                result = run_agent("image.generate", "", mode="spot", kind="empty")
        self.assertFalse(result["output"]["uploaded"])
        self.assertNotIn("url", result["output"])
        self.assertTrue(str(result["preview"]["url"]).startswith("/media/images/"))


class TtsSpeakTest(unittest.TestCase):
    def test_empty_input(self):
        result = run_agent("tts.speak", "", text="", language="en")
        self.assertEqual(result["error"], "empty_input")

    def test_stream_not_hijacked(self):
        result = run_agent("text-to-speech", "Hello there.", mode="stream")
        self.assertNotIsInstance(result.get("output"), dict)

    def test_speak_put(self):
        spec = get_agent("tts.speak")
        mod = spec["module"]
        upload = {
            "url": "https://example.invalid/put",
            "method": "PUT",
            "headers": {"Content-Type": "audio/mpeg"},
            "max_bytes": 104857600,
        }
        with (
            patch.object(mod, "is_tts_available", return_value=True),
            patch.object(
                mod,
                "_synthesize_wav",
                return_value={
                    "wav": b"RIFF....",
                    "duration_ms": 12400,
                    "sentence_count": 2,
                    "provider": "aliyun",
                },
            ),
            patch.object(mod, "wav_to_mp3", return_value=b"ID3fake-mp3"),
            patch.object(mod, "put_bytes") as pb,
        ):
            result = run_agent(
                "tts.speak",
                "",
                text="Hello. This is a test.",
                language="en",
                upload=upload,
            )
        pb.assert_called_once()
        out = result["output"]
        self.assertEqual(out["mime"], "audio/mpeg")
        self.assertEqual(out["filename"], "tts.mp3")
        self.assertTrue(out["uploaded"])
        self.assertEqual(out["duration_sec"], 12.4)
        self.assertEqual(result["usage"]["usage_sec"], 12.4)
        self.assertNotIn("url", out)
        self.assertIsNone(result.get("preview"))


class RegistryAndFixturesTest(unittest.TestCase):
    def test_aliases(self):
        self.assertIs(get_agent("tts.speak"), get_agent("text-to-speech"))
        self.assertIs(get_agent("image.generate"), get_agent("image-generate"))
        ids = [row["id"] for row in list_agents()]
        self.assertNotIn("tts.speak", ids)
        self.assertNotIn("image.generate", ids)
        tts = next(row for row in list_agents() if row["id"] == "text-to-speech")
        self.assertEqual(tts["skill"], "tts.speak")
        img = next(row for row in list_agents() if row["id"] == "image-generate")
        self.assertEqual(img["endpoint"], "/api/agents/image.generate/run")

    def test_discovery(self):
        from backend.app import create_app

        app = create_app()
        client = app.test_client()
        with patch.dict(os.environ, {"AGENT_AUTH_DISABLED": "1"}):
            for skill, agent_id in (
                ("tts.speak", "text-to-speech"),
                ("image.generate", "image-generate"),
            ):
                res = client.get(f"/api/agents/{skill}")
                self.assertEqual(res.status_code, 200, skill)
                data = res.get_json()
                self.assertEqual(data["id"], agent_id)
                self.assertEqual(data["skill"], skill)
                self.assertTrue(data.get("examples"), skill)

    def test_fixtures(self):
        files = [
            "tts.speak/200-en.json",
            "tts.speak/400-empty.json",
            "image.generate/200-spot.json",
            "image.generate/400-invalid-mode.json",
        ]
        for rel in files:
            path = FIXTURE_ROOT / rel
            self.assertTrue(path.is_file(), rel)
            data = json.loads(path.read_text(encoding="utf-8"))
            body = data["response"]
            if data["http"]["status"] == 200:
                out = body["output"]
                self.assertIsNone(body["usage"].get("cost_micros"))
                keys: set[str] = set()
                _walk_keys(out, keys)
                for banned in FORBIDDEN:
                    self.assertNotIn(banned, keys, rel)
                blob = json.dumps(out)
                self.assertNotIn("http://", blob)
                self.assertNotIn("https://", blob)
            else:
                self.assertIn("code", body["error"])


if __name__ == "__main__":
    unittest.main()
