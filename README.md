# mo-juan-mo-renzhen

訴願 POC 專案，儲存庫根目錄供前後端專案並列。

## 專案結構

```text
f2e/        Vue 3 + Vite + TypeScript 前端
slides/     Slidev 簡報（含 Demo 影片）
```

後端由負責成員新增同層資料夾，目前尚未建立。

## 啟動前端

```powershell
cd f2e
npm install
npm run dev
```

目前前端使用本機假資料，API 待補。送出後可展示六階段處理進度。

建置：在 `f2e/` 執行 `npm run build`。

詳細操作與假資料說明見 [前端 README](f2e/README.md)。

## 啟動簡報

在 `slides/` 執行 `npm ci`，再執行 `npm run dev`。
內容編輯、建置與影片說明見 [簡報 README](slides/README.md)。
