---
theme: default
title: 訴願 AI 輔助草擬｜新北黑客松
author: C_莫捲莫認真
lang: zh-TW
colorSchema: light
aspectRatio: 16/9
canvasWidth: 1200
fonts:
  sans: Noto Sans TC
  provider: none
drawings:
  persist: false
transition: fade
class: hero
---

<div class="eyebrow">新北市 AI 黑客松 · 法制局</div>

# 訴願 AI<br>輔助草擬

<img class="photo" src="/images/mountain-cover.avif" alt="山景" />
<div class="lead">兩張照片進來，兩分鐘後<br>一份引用可回查的決定書草稿。</div>
<div style="margin-top:30px;font-size:24px;color:var(--forest);font-weight:500">C_莫捲莫認真</div>

<div class="foot"><span>單一案例 · 六階段 · 已端到端實測</span><span>01 / 11</span></div>

<!--
建議配時：15 秒。
一句話：承辦人上傳訴願書與原處分書照片，系統走完辨識、擷取、程序檢核、檢索、生成、檢核六個階段，約兩分鐘產出一份每個引用都能點回來源的草稿。
-->

---
class: side-photo
---

<div class="eyebrow">痛點</div>

# 承辦人需要的，<br>是有依據的草稿

<img class="photo" src="/images/mountain-ridge.avif" alt="山稜照片" />
<div class="body"><p class="lead">訴願案 110 年 1,238 件 → 114 年 1,566 件；<br>洗錢、廢清、空污佔大宗，論理高度重複。</p><div style="margin-top:34px"><h2>我們接手的是「起草」這一段</h2><p>讀文件、整理事實、查法條與相似案、<br>依 101 件決定書萃取的模板生成參考稿。</p></div><p class="note">結論由程序規則決定、引用只認檢索結果；判斷仍由承辦人作成。</p></div>

<div class="foot"><span>命題：案件擷取分類 · 法規推薦 · 相似案比對 · 草稿生成</span><span>02 / 11</span></div>

<!--
建議配時：30 秒。
命題文件列的四項標準化工具，這套系統各對應一個階段。我們刻意不讓模型決定結論——駁回、撤銷、不受理由規則引擎判，模型只負責寫。
-->

---

<div class="eyebrow">單案驗證 ＋ 兩個變化情境</div>

# 以洗錢告誡案，驗證完整流程

<div class="two"><div><div class="case-id">113-16</div><div class="case-kind">違反洗錢防制法事件 · 原決定：訴願駁回</div><p class="muted">模擬訴願書＋模擬書面告誡（人名帳號皆虛構）<br>實測 S5 檢核 29 / 31，引用 11 筆全部有據</p></div><div class="case-facts"><p><small>主線</small>受騙交付提款卡與密碼，主張無故意<br>→ 駁回版：逐一回應主張、引 114 簡上 13 與立法理由</p><p><small>變化一</small>送達日期改早 → 規則判逾 30 日<br>→ 不受理版，引訴願法 14、77 條第 2 款</p><p><small>變化二</small>告誡書事實欄空白 → 96 條瑕疵<br>→ 撤銷版，引行政程序法 96、114 條，不附教示</p></div></div>

<div class="foot"><span>三種主文版本都由 S2.5 規則決定，模型不得自創第四種結論</span><span>03 / 11</span></div>

<!--
建議配時：40 秒。
同一組文件，只改一個送達日期，結論從駁回變成不受理；把處分書事實欄清空，結論變成撤銷。三個情境都在 Bedrock 上實跑過，主文與教示由規則與模板決定。
-->

---

<div class="eyebrow">處理流程（已實作）</div>

# 兩份文件進來，一份參考稿產出

<div class="flow"><div class="step"><div class="n">S1</div><h2>OCR 辨識</h2><p>Claude 多模態讀圖<br>→ 個資取代後才往下</p></div><div class="step"><div class="n">S2 · S2.5</div><h2>擷取＋程序檢核</h2><p>模型擷取摘要 JSON<br>規則判 30 日／適格／處分／瑕疵</p></div><div class="step"><div class="n">S3</div><h2>法規與案例</h2><p>法條精確查表<br>KB 三類向量檢索</p></div><div class="step"><div class="n">S4</div><h2>依模板生成</h2><p>主文版本由規則給<br>引用只認檢索結果</p></div><div class="step"><div class="n">S5</div><h2>結果檢核</h2><p>與正本比對 31 項<br>格式／引用／防幻覺</p></div></div><div class="band">實測全鏈 100–120 秒（OCR 36 s、擷取 10 s、檢索 7 s、生成 60–70 s）；S2.5 與 S5 不呼叫模型。</div>

<div class="foot"><span>Docker Compose：Vue 前端（nginx）＋ FastAPI 後端；前端每 1.5 秒輪詢階段狀態</span><span>04 / 11</span></div>

<!--
建議配時：35 秒。
六個階段依序寫回同一個案件物件，前端輪詢逐格亮起。綠色的兩段——程序檢核與結果檢核——是純規則，不經模型。
-->

---
class: data-slide
---

<div class="eyebrow">資料應用（已匯入）</div>

# 每一類資料，都有明確用途

<div class="three"><div class="metric"><div class="huge">2,214<small>條</small></div><h2>法規（11 部）</h2><p>逐條 JSON，精確查表；<br>帶修正日期與來源檔。</p></div><div class="metric"><div class="huge">29<small>篇</small></div><h2>判解與函釋</h2><p>KB 向量檢索＋模型篩選；<br>判決內引用的立法理由逐點抽出。</p></div><div class="metric"><div class="huge">101<small>件</small></div><h2>歷史決定書</h2><p>結構化欄位＋KB 檢索相似案；<br>模板與 few-shot 由此萃取。</p></div></div><div class="band">141 篇 PDF 以 pdftotext 轉純文字＋metadata 上 S3，自建 Bedrock Knowledge Base（Titan v2 → S3 Vectors）；每個引用保留來源 ID 可回查。</div>

<div class="foot"><span>Bedrock 內建 parser 抽不出中文，改自行前處理後再匯入</span><span>05 / 11</span></div>

<!--
建議配時：30 秒。
一個踩坑：主辦方 PDF 直接餵 Knowledge Base，內建 parser 抽出來全是亂碼。我們改用 pdftotext 轉純文字並加類別 metadata 再匯入，141 篇全部成功。
-->

---

<div class="eyebrow">檢索策略（已實作）</div>

# 法條精確查，案例找相似

<div class="two retrieval"><div><h2>法規檢索</h2><p>處分依據 ∪ 相似案裁決條 ∪ 程序檢核未過的條文，<br>以法規名＋條號精確取回原文。</p><div class="logic">逐條 JSON → 精確查詢 → 法條依據（含修正日期）</div></div><div><h2>判解／函釋／相似案</h2><p>依類別各查一次 KB，同文件多段合併；<br>模型篩掉主題無關者，並為相似案寫一句相似原因。</p><div class="logic">metadata 過濾 → 向量排序 → 排除本案自己 → 3 件參考</div></div></div><p style="margin-top:32px">113-16 實測：命中臺北高等行政法院 114 簡上 13、立法理由第 2／3／5 點、相似案 113-18（撤銷）／113-15／114-15（駁回）。</p>

<div class="foot"><span>草稿引用帶 source ID（statutes[0]、precedents[0]…），前端可展開對應原文</span><span>06 / 11</span></div>

<!--
建議配時：35 秒。
法條走精確查表，不走向量，避免引錯條。判解與相似案走向量，但多一層模型篩選，把「政府資訊公開法」這種主題無關的判決剔除。
-->

---

<div class="eyebrow">輸出成果（實測）</div>

# 草稿像決定書，引用能展開

<div class="output-grid"><div class="output-copy"><h2>三種主文版本</h2><p>駁回／撤銷／不受理骨架與固定句<br>來自 101 件決定書；主文、教示由規則填。</p><h2>只引檢索到的東西</h2><p>citations 由後處理比對本文產生，<br>模型自寫的引用不採信；缺依據列入待補查。</p></div><div class="document"><div class="doc-title">113-16 生成結果</div><div class="doc-tag">S5 檢核 29 / 31 · 與正本比對</div><div class="doc-row"><b>主文</b><span>訴願駁回。（規則判定，與正本一致）</span></div><div class="doc-row"><b>事實</b><span>緣…茲摘敘訴辯意旨於次：一、訴願意旨…二、答辯意旨…</span></div><div class="doc-row"><b>理由</b><span>一按法條 → 二卷查涵攝 → 三逐一駁斥（引 114 簡上 13、立法理由 3／5 點、行政罰法 7 條）→ 四綜上論結<br><small style="color:#73978d">引用 11 筆，11 筆有據；gaps 0</small></span></div><div class="doc-row"><b>教示</b><span>臺北高等行政法院（依模板規則自動填入）</span></div></div></div>

<div class="foot"><span>未得分的 2 項是正本才有的 LINE 對話內容，輸入文件裡沒有——系統不編造</span><span>07 / 11</span></div>

<!--
建議配時：35 秒。
分數不是滿分，剩下兩項是正本引用了 LINE 對話截圖的內容，我們的輸入文件裡沒有，模型沒有編。這正是我們要的行為。
-->

---
class: arch-slide
---

<div class="eyebrow">技術架構（已部署 · AWS 官方架構圖示）</div>

# 一個協調器，串接各段服務

<img src="/images/aws-architecture.png" class="arch-img" alt="AWS 架構與資料流" />

<div class="foot"><span>CloudFront → 彈性 IP → EC2 Docker Compose（Vue＋FastAPI＋PostgreSQL）→ Bedrock Converse（Sonnet 5，降級 4.6）＋ Knowledge Base（Titan v2＋S3 Vectors）｜us-west-2</span><span>08 / 11</span></div>

<!--
建議配時：25 秒。
入口走 CloudFront 的 HTTPS 子網域，origin 指向 EC2 的彈性 IP；EC2 上 Docker Compose 一鍵起前端、後端、PostgreSQL 與簡報四個容器，右邊是 Bedrock。模型用環境變數設定，預設 Sonnet 5，帳戶拿不到會自動降級。全部呼叫共用 1 RPS 限流，符合主辦方規範。
-->

---

<div class="eyebrow">可信與合規</div>

# 模型從頭到尾沒看過真名

<div class="two" style="margin-top:30px"><div><h2>個資前處理（取代法）</h2><p>OCR 之後、任何文字送模型之前：姓名 → <span style="white-space:nowrap">甲○○</span>，身分證／電話／地址／生日 → ○ 遮罩；<br>純規則，不經模型。</p><p>對照表只存後端記憶體，不進 log、不上 AWS；<br>草稿輸出時還原姓名給承辦人。</p></div><div><h2>其他防線</h2><p><strong>結論不交給模型</strong>：主文版本由程序規則決定。</p><p><strong>引用只認檢索結果</strong>：後處理比對，缺依據列待補查。</p><p><strong>Bedrock ≤ 1 RPS、S3 不公開、us-west-2</strong>：對照規範逐條核過。</p><p><strong>帳密登入</strong>：環境變數設定，token 簽章。</p></div></div>

<div class="foot"><span>OCR 頁可見「已去識別化：姓名×3、身分證×1…」標籤；草稿頁顯示還原後真名</span><span>09 / 11</span></div>

<!--
建議配時：35 秒。
Demo 時請看 OCR 頁：訴願人顯示甲○○，身分證電話地址全是圈圈；翻到草稿頁，訴願人王小明回來了。對照表沒離開過這台機器。
-->

---
class: video-demo
---

<div class="eyebrow">Demo · 網站操作展示</div>

# 訴願 AI 輔助草擬｜操作影片

<video class="demo-video" controls playsinline preload="metadata" aria-label="訴願 AI 網站操作預錄影片">
  <source src="/videos/demo-walkthrough.mp4" type="video/mp4" />
  您的瀏覽器無法播放此影片，請開啟下方影片連結。
</video>

<div class="foot"><span>現場：登入 → 一鍵 Demo（載入模擬文件並分析）→ 六階段逐格亮起 → 草稿頁點引用回查來源</span><span>10 / 11</span></div>

<!--
建議配時：60 秒。
現場網路正常就直接操作：一鍵 Demo 約兩分鐘；不正常就播影片。
-->

---
class: closing
---

<div class="eyebrow">本次交付</div>

# 一件訴願案，<br>完成有依據的初稿

<img class="photo" src="/images/mountain-close.avif" alt="山景" /><div class="lead">文件讀得進來，引用查得到來源，<br>結論由規則把關，個資不出本機。</div><div class="promise">一案跑通 ✓ 三種結論 ✓<br>引用可查 ✓ 去識別化 ✓<br>Docker 一鍵部署 ✓</div>

<div class="foot"><span>github.com/guitimliu/mo-juan-mo-renzhen · 分支 backend</span><span>11 / 11</span></div>

<!--
建議配時：15 秒。
-->
