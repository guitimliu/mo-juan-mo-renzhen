# -*- coding: utf-8 -*-
"""Gemini TTS 配音 + 雙重驗證：每句生成後再送 Gemini 轉回文字，與原稿比對字錯率（CER）；超過門檻自動重生（最多 3 次）。
用法：python tts.py [--voice Leda] [--only 05_arch]   （金鑰讀 video/.env 的 GEMINI_API_KEY）
輸出：assets/generated/tts/<id>.wav、<id>.json（時長、轉錄、CER）、tts_report.md
"""
import argparse, base64, difflib, json, os, pathlib, re, subprocess, sys, time, urllib.request

HERE = pathlib.Path(__file__).parent
ENV = dict(l.split("=", 1) for l in (HERE / ".env").read_text().splitlines() if "=" in l)
KEY = ENV["GEMINI_API_KEY"].strip()
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
STT_MODEL = os.environ.get("STT_MODEL", "gemini-2.5-flash")
OUT = HERE / "assets/generated/tts"; OUT.mkdir(parents=True, exist_ok=True)
CER_MAX = float(os.environ.get("CER_MAX", "0.06"))


def gemini(model: str, body: dict) -> dict:
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={KEY}",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=180))
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:200]
            if e.code in (429, 500, 503) and attempt < 3:
                time.sleep(5 * (attempt + 1)); continue
            raise RuntimeError(f"{model} HTTP {e.code}: {msg}")


def synth(text: str, voice: str, style: str, wav: pathlib.Path) -> float:
    d = gemini(TTS_MODEL, {"contents": [{"parts": [{"text": style + text}]}],
                           "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}})
    try:
        part = d["candidates"][0]["content"]["parts"][0]["inlineData"]
    except (KeyError, IndexError):
        reason = (d.get("candidates") or [{}])[0].get("finishReason") or d.get("promptFeedback")
        raise RuntimeError(f"TTS 沒回音訊（{reason}）")
    pcm = wav.with_suffix(".pcm"); pcm.write_bytes(base64.b64decode(part["data"]))
    rate = re.search(r"rate=(\d+)", part["mimeType"]); rate = rate[1] if rate else "24000"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", rate, "-ac", "1", "-i", str(pcm),
                    "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,apad=pad_dur=0.35", str(wav)], check=True)
    pcm.unlink()
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)], capture_output=True, text=True).stdout.strip())


def transcribe(wav: pathlib.Path) -> str:
    audio = base64.b64encode(wav.read_bytes()).decode()
    d = gemini(STT_MODEL, {"contents": [{"parts": [{"text": "請逐字聽寫這段台灣國語音檔，輸出繁體中文全文。數字一律照讀音寫成中文數字（例如「一百一十年」「一千二百三十八件」「第二十二條」，不要寫成 110、1238、22）；英文名稱（AI、Docker、EC2、S3、Bedrock、Claude Sonnet、WebSocket、LINE、GitHub、OCR、PDF、Titan、Knowledge Base）照原文寫。不要加任何說明。"},
                                                     {"inlineData": {"mimeType": "audio/wav", "data": audio}}]}],
                           "generationConfig": {"temperature": 0}})
    return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]).strip()


NUM = {"0": "零", "1": "一", "2": "二", "3": "三", "4": "四", "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"}
def _cn_num(n: int) -> str:
    if n < 10: return NUM[str(n)]
    units = ["", "十", "百", "千"]; digits = str(n); out = ""
    if n >= 10000: return "".join(NUM[c] for c in digits)
    for i, c in enumerate(digits):
        pos = len(digits) - i - 1
        if c == "0":
            if out and not out.endswith("零") and pos > 0 and any(ch != "0" for ch in digits[i+1:]): out += "零"
            continue
        out += (NUM[c] if not (c == "1" and pos == 1 and i == 0) else "") + units[pos]
    return out


def norm(s: str) -> str:
    s = re.sub(r"\d+", lambda m: _cn_num(int(m.group())), s)
    s = re.sub(r"[\s，。、；：「」『』（）()！？!?,.\-—·：:／/…]+", "", s)
    s = s.replace("臺", "台").replace("裏", "裡").replace("Sonnet5", "Sonnet 5")
    return s.lower()


def phon(s: str) -> list[str]:
    """字串 → 每字拼音（不含聲調；非中文字原樣）。同音字（制／治）視為相同。"""
    from pypinyin import lazy_pinyin
    return lazy_pinyin(norm(s))


def cer(ref: str, hyp: str) -> float:
    """語音字錯率：以拼音序列比對，同音字不算錯。"""
    a, b = phon(ref), phon(hyp)
    if not a:
        return 0.0
    sm = difflib.SequenceMatcher(None, a, b)
    edits = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
    return edits / len(a)


def cer_text(ref: str, hyp: str) -> float:
    a, b = norm(ref), norm(hyp)
    if not a:
        return 0.0
    sm = difflib.SequenceMatcher(None, a, b)
    edits = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
    return edits / len(a)


def diff_marks(ref: str, hyp: str) -> str:
    a, b = norm(ref), norm(hyp); out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal": out.append(a[i1:i2])
        elif tag == "replace": out.append(f"[{a[i1:i2]}→{b[j1:j2]}]")
        elif tag == "delete": out.append(f"[漏:{a[i1:i2]}]")
        else: out.append(f"[多:{b[j1:j2]}]")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--voice"); ap.add_argument("--only"); ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    spec = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))
    voice = args.voice or spec["voice"]; style = spec["style"]
    report = ["# 配音雙重驗證報告", f"voice: {voice} · TTS: {TTS_MODEL} · STT: {STT_MODEL} · CER 門檻 {CER_MAX}", "", "| id | 秒 | 拼音CER | 文字CER | 嘗試 | 差異（同音字僅列示，不計錯） |", "|---|---|---|---|---|---|"]
    total = 0.0
    for seg in spec["segments"]:
        if args.only and seg["id"] != args.only:
            continue
        wav = OUT / f"{seg['id']}.wav"; meta = wav.with_suffix(".json")
        if meta.exists() and not args.force and json.loads(meta.read_text())["voice"] == voice and json.loads(meta.read_text())["text"] == seg["text"]:
            m = json.loads(meta.read_text()); print(f"skip {seg['id']} (cached, CER {m['cer']:.3f})"); total += m["duration"]
            report.append(f"| {seg['id']} | {m['duration']:.1f} | {m['cer']:.3f} | {m.get('cer_text', 0):.3f} | cached | {m['diff']} |"); continue
        best = None
        for attempt in range(1, 4):
            try:
                dur = synth(seg["text"], voice, style, wav)
            except RuntimeError as e:
                print(f"{seg['id']} try{attempt}: {e}，重試"); continue
            hyp = transcribe(wav); c = cer(seg["text"], hyp); ct = cer_text(seg["text"], hyp)
            print(f"{seg['id']} try{attempt}: {dur:.1f}s 拼音CER={c:.3f} 文字CER={ct:.3f}")
            if best is None or c < best["cer"]:
                best = {"id": seg["id"], "voice": voice, "text": seg["text"], "duration": dur, "transcript": hyp, "cer": c, "cer_text": ct, "attempt": attempt, "diff": diff_marks(seg["text"], hyp)}
                wav.with_suffix(".best.wav").write_bytes(wav.read_bytes())
            if c <= CER_MAX:
                break
        wav.write_bytes(wav.with_suffix(".best.wav").read_bytes()); wav.with_suffix(".best.wav").unlink()
        meta.write_text(json.dumps(best, ensure_ascii=False, indent=1), encoding="utf-8")
        total += best["duration"]
        flag = "" if best["cer"] <= CER_MAX else " ⚠️"
        report.append(f"| {seg['id']} | {best['duration']:.1f} | {best['cer']:.3f}{flag} | {best.get('cer_text', 0):.3f} | {best['attempt']} | {best['diff'] if best.get('cer_text', 0) > 0 else '完全一致'} |")
    report += ["", f"總配音長度：{total:.1f} s"]
    (OUT / "tts_report.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report[-3:]))


if __name__ == "__main__":
    main()
