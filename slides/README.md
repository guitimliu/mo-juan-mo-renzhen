# C_莫捲莫認真｜訴願 AI 輔助草擬簡報

以 Slidev 製作，10 頁主簡報＋2 頁備用頁，總配時 6 分鐘。第9頁內嵌58秒預錄Demo。

## 本機使用

需要 Node.js 22.12 以上（建議24）。從repo根目錄執行：

```sh
cd slides
npm ci
npm run dev
```

開啟終端顯示的本機網址。方向鍵切換投影片；第9頁使用影片控制列播放／全螢幕。講者模式為 `/presenter/`。

## 修改與建置

- `slides.md`：簡報內容、逐頁講稿、配時及來源。
- `style.css`：森林綠、灰綠、白底與斜切照片樣式。
- `public/images/`：模板圖片與來源說明。
- `public/videos/demo-walkthrough.mp4`：使用者提供的58秒操作影片。
- `package-lock.json`：固定套件版本。

```sh
npm run build
```

靜態網站輸出至 `slides/dist/`。影片會隨建置打包，播放不依賴原始電腦的D槽路徑。字型優先載入Google Fonts的Noto Sans TC，無網路時使用系統中文字型。

`node_modules/`、`dist/` 不提交。此資料夾的 `.gitignore` 特別允許Demo影片，以覆寫repo根目錄忽略MP4的規則。

## 簡報配時與內容依據

主講配時：15、35、25、40、55、55、35、25、60、15秒，合計360秒。第9頁60秒含58秒影片及切換時間。

內容以團隊會議、更新版POC計畫及提供的工作包為依據；命題文件僅作背景參考。原始工作包、歷次草稿與本機測試暫存未包含於此資料夾。

- [POC計畫](https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296)
- [使用者指定的Gamma視覺模板](https://gamma.app/docs/Strategic-Priorities-Framework-rwelbh5m7687av6)

資料總量與端到端生成成效仍待驗證；檢核器30/30與9/30為構造樣本自測，非AI生成正確率。部分來源的教示法院、生成分支與範例標籤存在差異，需另行核對。網站部署完成後再補實機連結。
