# LS fixtures（二进制 skill）

`tts.speak/` 与 `image.generate/` 是契约样本（mock 字节量），给 LS E4 对字段用。

- 200 + 至少一条 400
- `output` 无 URL / base64 / `asset_id`
- `cost_micros` 为 null

五个 JSON skill 的 live 录制样本若缺失，见历史 `record_ls_fixtures.py`；**不要**把 TTS/出图并进 E9 五技能清单。
