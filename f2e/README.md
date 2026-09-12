# 訴願審查助手前端

使用 Vue 3、Vite 與 TypeScript 建置的案件審查介面。

## 本機開發

在 `f2e/` 目錄執行：

```powershell
npm ci
Copy-Item .env.example .env
npm run dev
```

## 建置與部署

```powershell
npm run build
npm run preview
```

部署專案根目錄設為 `f2e`，建置指令為 `npm run build`，輸出目錄為 `dist`。

## 功能

前端展示功能：

- 上傳訴願書與原處分書圖片，支援 JPG、PNG、WebP，單檔上限 10 MB。
- 填寫送達日期，供承辦人核對。
- 檢視文件、OCR 對照、程序檢核及法源檢索結果。
- 審閱決定書草稿與段落引用。
- 匯出 PDF 或可編輯的 Word（DOCX）。
- 使用「載入示範案件」測試操作流程。

## 目前串接狀態

目前仍使用內建示範資料與本機處理進度，尚未串接後端 API。上傳圖片僅供預覽，分析結果不會隨所選圖片改變；送達日期與選檔狀態在重新整理後重置。

## 字型

介面使用 Noto Sans TC 與 Noto Serif TC；PDF 內嵌 Noto Serif TC。字型授權文件位於 `public/fonts/`。
