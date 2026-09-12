# 訴願審查助手前端

使用 Vue 3、Vite 與 TypeScript 建置的案件審查介面。

## 本機開發

在 `f2e/` 目錄執行：

```powershell
npm ci
Copy-Item .env.example .env
npm run dev
```

`VITE_API_BASE_URL` 指向後端（預設 `http://localhost:8000`）。後端啟動方式見 `../backend/README.md`。若後端啟用帳密驗證，使用者需先登入。

## 操作流程

1. 上傳訴願書與原處分書各一份 JPG、PNG 或 WebP 圖片，單檔上限 10 MB。
2. 選填送達日期，按「開始分析」送交後端；日期會一起送出供程序檢核使用。
3. 依序核對 OCR、程序檢核、法源與草稿。可用上一步／下一步導覽。
4. 核對草稿內容與引用後，匯出 PDF 或 Word。

「載入 Demo 文件」只填入測試圖片；「一鍵 Demo（載入並分析）」會填入圖片並送交後端。有現有內容時，會先確認是否取代，載入失敗則保留原內容。

缺檔時禁止開始；格式、空檔與大小錯誤會顯示在文件旁。更換或移除文件會清除舊結果。新建案件前會確認是否清除內容，離開頁面時由瀏覽器提醒未保存內容。停止更新進度不會取消伺服器端案件；重新開始會建立另一個案件。

結果來自 `POST /api/cases` 與 `GET /api/cases/{id}`。後端支援 stub 與 bedrock 模式；stub 使用示範資料，bedrock 由後端執行辨識與生成。連線失敗會顯示錯誤，不會自動改用本機假資料。

## 建置與部署

```powershell
npm run build
npm run preview
```

部署根目錄設為 `f2e`，建置指令 `npm run build`，輸出目錄 `dist`。Docker 部署使用根目錄 `docker compose up --build`，nginx 將 `/api/` 代理至後端。

介面基礎字級為 14px，使用 Noto Sans TC 與 Noto Serif TC；PDF 內嵌 Noto Serif TC，授權位於 `public/fonts/`。
