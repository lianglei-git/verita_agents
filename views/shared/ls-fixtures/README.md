# LS fixtures

给 LS E4 对字段用。说明与交接顺序见 [`../../docs/给LS.md`](../../docs/给LS.md)。

- 200 + 至少一条 400
- `output` 无 URL / base64 / `asset_id`
- `cost_micros` 为 null
- `tts.speak` 产物为 `audio/wav` / `tts.wav`

五个 JSON skill 的 live 录制若缺失，见 `views/backend/scripts/record_ls_fixtures.py`。**不要**把 TTS/出图并进 E9 五技能清单。
