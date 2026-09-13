"""從 timeline.json 產出影片側檔：
  out/mjmr_demo_video.srt   — 字幕（時間碼與 Remotion 字幕元件同一套算法：每句依口白字數比例分配）
  out/mjmr_demo_video.md    — 影片資訊：標題、描述、章節時間軸、逐字稿（含時間碼）、製作資訊
  out/mjmr_demo_video.json  — 同上結構化版本（title / description / chapters / transcript / credits）
場景順序與長度照 remotion/src/Main.tsx（sceneLen = 旁白 + 1.2 s；close 多 1.5 s；demo 固定 100.6 s），
Demo 內旁白起點照 remotion/src/scenes.tsx。用法：python build_video_meta.py
"""
from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
TL = json.loads((HERE / "remotion/src/timeline.json").read_text(encoding="utf-8"))["narration"]
OUT = HERE / "out"
FPS = 30
PAD = 1.2
sec = lambda s: round(s * FPS)  # noqa: E731
dur = lambda i: TL[i]["duration"]  # noqa: E731

# ---- 場景（同 Main.tsx）----
DEMO_SEG = [(0.5, 14.0, 1.0), (14.0, 61.5, 8.0), (61.5, 72.5, 1.5), (72.5, 133.5, 2.5), (133.5, 137.5, 1.0), (137.5, 163.0, 0.72)]
demo_seg_frames = [sec((b - a) / r) for a, b, r in DEMO_SEG]
demo_len = sum(demo_seg_frames) + sec(10)
SCENES = [
    ("intro", "開場：莫捲莫認真 × 訴願決定書草稿助理", sec(dur("01_intro") + PAD), ["01_intro"]),
    ("pain", "痛點：案量成長、論理重複，承辦人需要有依據的草稿", sec(dur("02_pain") + PAD), ["02_pain"]),
    ("case", "驗證案例：113 年第 16 號洗錢防制法告誡案，三種主文由規則決定", sec(dur("03_case") + PAD), ["03_case"]),
    ("pipeline", "六階段管線：OCR → 擷取 → 程序檢核 → 檢索 → 生成 → 檢核", sec(dur("04_pipeline") + PAD), ["04_pipeline"]),
    ("arch", "AWS 架構：CloudFront → 彈性 IP → EC2 Docker Compose；Bedrock Converse＋Knowledge Base", sec(dur("05_arch") + PAD), ["05_arch"]),
    ("demo", "實際操作：登入、上傳、即時進度、個資遮罩、法源檢索、草稿串流與引用溯源", demo_len, None),
    ("result", "成果：與正本比對 31 項檢核得 29 分，11 筆引用全部有據", sec(dur("09_result") + PAD), ["09_result"]),
    ("trust", "可信與合規：結論由規則決定、引用只認檢索、個資不出本機", sec(dur("10_trust") + PAD), ["10_trust"]),
    ("close", "結語：一件訴願案，完成有依據的初稿", sec(dur("11_close") + PAD + 1.5), ["11_close"]),
]
# Demo 內旁白起點（scenes.tsx）
s07 = sum(demo_seg_frames[:5]) + sec(1.0)
s08 = s07 + sec(dur("07_demo_b")) + sec(0.6)
DEMO_NARR = [("06_demo_a", 0), ("06b_demo_wait", sec(15)), ("06c_demo_stream", sec(15) + sec(dur("06b_demo_wait")) + sec(0.8)), ("07_demo_b", s07), ("08_demo_c", s08)]


def split(t: str) -> list[str]:
    return [s for s in re.split(r"(?<=[。！？])", t) if s.strip()]


def tc(frames: int, srt: bool = False) -> str:
    ms = round(frames * 1000 / FPS)
    h, rem = divmod(ms, 3600_000); m, rem = divmod(rem, 60_000); s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}" if srt else (f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    chapters, cues, transcript = [], [], []
    f0 = 0
    for name, title, length, ids in SCENES:
        chapters.append({"start": f0, "title": title})
        narr = DEMO_NARR if ids is None else [(i, 0) for i in ids]
        for nid, off in narr:
            n = TL[nid]; total = sec(n["duration"]); start = f0 + off
            spoken, shown = split(n["text"]), split(n["subtitle"])
            weights = [len(p) for p in (spoken if len(spoken) == len(shown) else shown)]; wsum = sum(weights)
            acc = 0.0
            for w, line in zip(weights, shown):
                a = start + round(acc); acc += w / wsum * total; b = start + round(acc)
                cues.append((a, b, line.strip()))
            transcript.append({"id": nid, "start": start, "end": start + total, "subtitle": n["subtitle"], "spoken": n["text"]})
        f0 += length
    total_frames = f0

    srt = "\n".join(f"{i}\n{tc(a, True)} --> {tc(b, True)}\n{line}\n" for i, (a, b, line) in enumerate(cues, 1))
    (OUT / "mjmr_demo_video.srt").write_text(srt, encoding="utf-8")

    title = "莫捲莫認真｜訴願決定書草稿助理（新北市 AI 黑客松・法制局）"
    short = "承辦人上傳訴願書與原處分書照片，兩分鐘內取得每一個引用都能點回來源的決定書草稿；結論由程序規則決定、引用只認檢索結果、個資不出本機。"
    description = "\n".join([
        short, "",
        "本片為新北市 AI 黑客松「法制局：訴願決定書草稿」題目的作品展示，長度約 5 分鐘。",
        "系統以六階段管線處理一件真實的洗錢防制法告誡案（113 年第 16 號）：OCR 辨識、案件擷取、程序檢核、法規與案例檢索、依模板生成草稿、與正本比對檢核。",
        "程序檢核與結果檢核為純規則，不經過模型；主文（駁回／撤銷／不受理）由規則決定，模型只負責撰寫理由。",
        "檢索走自建 Bedrock Knowledge Base（主辦方 141 篇＋新北市法制局歷年訴願決定書 26,607 篇），引用只認檢索結果，缺依據列為待補查。",
        "個資在 OCR 後立即以代號取代，對照表只存在後端記憶體，AWS 帳戶內不放個資。",
        "實測全鏈約 100–120 秒；與正本比對 31 項檢核得 29 分，11 筆引用全部有據。", "",
        "技術：Vue 3＋FastAPI（Docker Compose on EC2，CloudFront＋彈性 IP 對外）、Amazon Bedrock Converse API（Claude Sonnet 5，降級 4.6）、Bedrock Knowledge Base（Titan Text Embeddings v2＋S3 Vectors）、PostgreSQL（案件／草稿版本）。",
    ])
    chapter_lines = [f"{tc(c['start'])} {c['title']}" for c in chapters]
    md = [f"# {title}", "", f"**一句話**：{short}", "", "## 影片描述", "", description, "",
          "## 章節時間軸", ""] + [f"- {l}" for l in chapter_lines] + [
          "", f"總長 {tc(total_frames)}（{total_frames / FPS:.1f} s，{total_frames} 幀 @30fps，1920×1080）", "",
          "## 逐字稿（字幕版；口白數字為中文讀法）", ""]
    for t in transcript:
        md.append(f"**{tc(t['start'])}–{tc(t['end'])}**　{t['subtitle']}\n")
    md += ["## 製作資訊", "",
           "- 影像：Remotion（React）合成，9 個場景；Demo 段為 Playwright 實錄網站操作（分段變速 8×／1.5×／2.5×／0.72×）",
           "- 旁白：Gemini TTS（聲音 Leda，台灣國語），每句經 Gemini 聽寫回驗（拼音 CER ≤ 4.4%）；字幕以阿拉伯數字顯示、口白以中文數字發音",
           "- 配樂：ElevenLabs Music（講解段／Demo 段兩軌，−16／−15 dB 於旁白之下）",
           "- 架構圖：draw.io（AWS 官方圖示），自架容器匯出",
           "- 字幕側檔：`mjmr_demo_video.srt`（與畫面字幕同時間碼）",
           "- 團隊：莫捲莫認真｜專案：https://github.com/guitimliu/mo-juan-mo-renzhen",
           ]
    (OUT / "mjmr_demo_video.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (OUT / "mjmr_demo_video.json").write_text(json.dumps({
        "title": title, "short_description": short, "description": description,
        "duration_seconds": round(total_frames / FPS, 2), "resolution": "1920x1080", "fps": FPS,
        "chapters": [{"time": tc(c["start"]), "seconds": round(c["start"] / FPS, 2), "title": c["title"]} for c in chapters],
        "transcript": [{"id": t["id"], "start": round(t["start"] / FPS, 2), "end": round(t["end"] / FPS, 2), "subtitle": t["subtitle"], "spoken": t["spoken"]} for t in transcript],
        "credits": {"visuals": "Remotion + Playwright screen recording", "narration": "Gemini TTS (Leda)", "music": "ElevenLabs Music", "diagram": "draw.io (AWS icons)"},
        "files": {"video": "mjmr_demo_video.mp4", "preview": "mjmr_demo_video_preview.mp4", "subtitles": "mjmr_demo_video.srt"},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(cues)} cues, {len(chapters)} chapters, total {tc(total_frames)} → {OUT}")
    print("\n".join(chapter_lines))


if __name__ == "__main__":
    main()
