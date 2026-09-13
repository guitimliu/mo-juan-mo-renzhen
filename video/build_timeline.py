"""narration.json ＋ assets/generated/tts/<id>.json（duration）→ remotion/src/timeline.json。
narration[id] = {text（口白，中文數字）, subtitle（字幕，阿拉伯數字）, duration}；demoMarks 沿用既有值。"""
import json, pathlib
HERE = pathlib.Path(__file__).resolve().parent
spec = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))
out = HERE / "remotion/src/timeline.json"
old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
nar = {}
for s in spec["segments"]:
    meta = json.loads((HERE / "assets/generated/tts" / f"{s['id']}.json").read_text(encoding="utf-8"))
    nar[s["id"]] = {"text": s["text"], "subtitle": s.get("subtitle", s["text"]), "duration": meta["duration"]}
out.write_text(json.dumps({"narration": nar, "demoMarks": old.get("demoMarks", {})}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(nar)} segments, total {sum(v['duration'] for v in nar.values()):.1f}s → {out}")
