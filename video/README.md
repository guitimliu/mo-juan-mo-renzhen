# 六分鐘繳交影片產線（Playwright ＋ Gemini TTS ＋ Remotion ＋ ffmpeg）

```
video/
  narration.json       11 段旁白稿（scene 對應）＋聲線（Leda）
  tts.py               Gemini TTS 配音 ＋ 雙重驗證：每句生成後再送 Gemini 聽寫，拼音 CER > 6% 自動重生（最多 3 次），輸出 tts_report.md
  record_demo.py       Playwright 錄 Demo 實錄（登入 → 一鍵 Demo → 六階段 → 逐頁瀏覽 → 點引用），1920×1080
  remotion/            Remotion 專案：src/scenes.tsx 九個場景、src/timeline.ts（場景長度由配音長度驅動、Demo 分段變速表）
  assets/generated/    產物（gitignore）：tts/*.wav、demo_cfr.mp4、tts_report.md
  .env                 GEMINI_API_KEY（gitignore）
```

## 產生流程

1. 錄 Demo（需 docker compose 的 bedrock stack 在跑，登入帳密同 .env）
   `python record_demo.py` → `assets/generated/_rec/*.webm`
   轉 CFR：`ffmpeg -i assets/generated/_rec/*.webm -fps_mode cfr -r 30 -c:v libx264 -crf 18 -pix_fmt yuv420p -an assets/generated/demo_cfr.mp4`
2. 配音＋驗證：`python tts.py`（改 narration.json 後只重生變動的句子；`--force` 全重生；`--only <id>` 單句）
3. Remotion：`cd remotion && npm install`，把 `../assets/generated/tts/*.wav` 複製到 `public/tts/`、`demo_cfr.mp4` 到 `public/video/`、`../../docs/aws-architecture.png` 到 `public/img/`；用 `tts/*.json` 的 duration 重建 `src/timeline.json`（欄位 `narration[id] = {text, duration}`）
4. 輸出：`npm run render` → `out/main.mp4`（1080p30，約 4:45；concurrency 4 約 45 分鐘）；預覽用 `npm run studio`

## 注意
- Playwright 錄下的 webm 時間軸會拉伸（164 s vs 實際 154 s），`src/timeline.ts` 的 `DEMO_SEGMENTS` 是用影片畫面差異定位的秒數；重錄後要重新定位（`ffmpeg -vf "select='gt(scene,0.08)',showinfo"` 或每 0.5 s 抽幀算差異）。
- 字幕依句號切段、按字數比例排時間。
- 聲線：Leda（選定）；試聽過 Zephyr、Aoede、Puck。改 `narration.json` 的 `voice` 後 `python tts.py --force`。
