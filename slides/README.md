# C_莫捲莫認真｜訴願 AI 輔助草擬簡報

Slidev簡報，共11頁，總配時約6分鐘。第10頁為58秒預錄Demo影片；第8頁為 `docs/aws-architecture.png` 架構圖（改圖後 `cp docs/aws-architecture.png slides/public/images/`）。

## 啟動

需要Node.js 22.12以上（建議24）。從repo根目錄執行：

```sh
cd slides
npm ci
npm run dev
```

開啟終端顯示的網址，以方向鍵切換。第9頁可播放或全螢幕觀看影片。

## 編輯與建置

- `slides.md`：投影片內容。
- `style.css`：簡報樣式。
- `public/images/`：簡報圖片。
- `public/videos/demo-walkthrough.mp4`：預錄Demo。

```sh
npm run build
```

靜態網站輸出至`slides/dist/`。圖片與影片隨建置打包；`node_modules/`與`dist/`不提交。

配時：15、30、40、35、30、35、35、25、35、60、15秒，合計355秒。

## Docker

`docker compose up --build` 會一併建置簡報（`slides/Dockerfile`：Slidev build → nginx），前端 nginx 把 `/slides/` 反向代理過去：http://localhost:8080/slides/ ；前端側欄也有「簡報」連結。
