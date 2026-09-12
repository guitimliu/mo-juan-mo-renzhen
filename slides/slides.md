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

<img class="photo" src="/images/mountain-cover.avif" alt="模板山景" />
<div class="lead">以一件訴願案，走完<br>文件辨識到決定書參考稿。</div>
<div style="margin-top:30px;font-size:24px;color:var(--forest);font-weight:500">C_莫捲莫認真</div>

<div class="foot"><span>單一案例 · 完整流程 · 可展示結果</span><span>01 / 10</span></div>

<!--
建議配時：15 秒。
我們聚焦訴願案件審理中的文書準備，以一個案型設計 Demo，讓訴願書与原處分書經 AI 處理後，產出可檢視引用的決定書參考稿。
來源：會議摘要（內容主軸）及最新提供的《訴願POC作戰計畫.pdf》（5頁），以PDF為更新依據。先前網頁參考：https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296 。補充來源：sources/poc/的00至09工作包。案例已對照提供原文、模板與範例已讀取，檢核器自測已執行；全量11／29／101資料與系統部署仍未驗證。
圖片及視覺參考：使用者指定模板 https://gamma.app/docs/Strategic-Priorities-Framework-rwelbh5m7687av6 。山景為模板視覺，不代表新北實際地景。
-->

---
class: side-photo
---

<div class="eyebrow">訴願流程自動化</div>

# 承辦人需要的，<br>是有依據的草稿

<img class="photo" src="/images/mountain-ridge.avif" alt="模板山稜照片" />
<div class="body"><p class="lead">案件事實在兩份文件裡；<br>草擬理由，還要對照法規與過往案例。</p><div style="margin-top:34px"><h2>我們支援這一段工作</h2><p>讀取文件、整理事實、找出依據，<br>依既有決定書格式形成參考稿。</p></div><p class="note">交由承辦人檢視與修正，輸出定位為參考稿。</p></div>

<div class="foot"><span>以團隊討論的草擬流程為範圍</span><span>02 / 10</span></div>

<!--
建議配時：35 秒。
訴願書和原處分書各自提供資訊，草擬時需要把事實與主張放在一起，對照法規和既有案例。我們把 AI 放在資料整理與初稿生成的位置，最後讓承辦人檢視與修正。命題文件僅作背景參考，不擴入其他需求。
來源：會議摘要（內容主軸）及最新提供的《訴願POC作戰計畫.pdf》（5頁），以PDF為更新依據。先前網頁參考：https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296 。補充來源：sources/poc/的00至09工作包。案例已對照提供原文、模板與範例已讀取，檢核器自測已執行；全量11／29／101資料與系統部署仍未驗證。
圖片及視覺參考：使用者指定模板 https://gamma.app/docs/Strategic-Priorities-Framework-rwelbh5m7687av6 。山景為模板視覺，不代表新北實際地景。
-->

---

<div class="eyebrow">單案驗證</div>

# 以洗錢告誡案，驗證完整流程

<div class="two"><div><div class="case-id">113-16</div><div class="case-kind">違反洗錢防制法事件</div><p class="muted">POC 計畫選定案例<br>原決定結果：訴願駁回</p></div><div class="case-facts"><p><small>原處分</small>新店分局作成書面告誡</p><p><small>訴願主張</small>遭中獎詐騙，交付提款卡與密碼，<br>主張沒有故意</p><p><small>本次展示</small>模擬訴願書＋模擬原處分書<br>生成可對照理由與引用的草稿</p></div></div>

<div class="foot"><span>已核對提供的 113-16 原決定書文字；輸入文件為依案情逆推的模擬版本</span><span>03 / 10</span></div>

<!--
建議配時：25 秒。
新的 POC 計畫選定113-16，屬洗錢告誡案。民眾主張被中獎訊息誘騙，交出提款卡和密碼，對書面告誡提出訴願。我們用它做一條完整管線，驗證文件、檢索和草稿是否能接起來。案號、案情與原結果已對照此次提供的00_標準答案_113-16_原決定書.md；未另驗證官方PDF。結果為原文記載，不是系統生成實測結果。01與02為模擬輸入，姓名等資料為虛構。
來源：會議摘要（內容主軸）及最新提供的《訴願POC作戰計畫.pdf》（5頁），以PDF為更新依據。先前網頁參考：https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296 。補充來源：sources/poc/的00至09工作包。案例已對照提供原文、模板與範例已讀取，檢核器自測已執行；全量11／29／101資料與系統部署仍未驗證。
-->

---

<div class="eyebrow">預定處理流程</div>

# 兩份文件進來，一份參考稿產出

<div class="flow"><div class="step"><div class="n">01</div><h2>OCR 辨識</h2><p>多模態模型讀圖<br>輸出兩份純文字</p></div><div class="step"><div class="n">02</div><h2>擷取與檢核</h2><p>模型擷取案件摘要<br>規則引擎檢核程序</p></div><div class="step"><div class="n">03</div><h2>法規與案例</h2><p>精確查法條<br>比對相似案件</p></div><div class="step"><div class="n">04</div><h2>依模板生成</h2><p>填入事實與理由<br>保留來源識別碼</p></div><div class="step"><div class="n">05</div><h2>結果檢核</h2><p>查核段落與引用<br>對照原決定結果</p></div></div><div class="band">OCR、案件擷取與生成呼叫模型；程序檢核依規則，法條依條號查詢。</div>

<div class="foot"><span>五階段依更新版 POC 計畫第 4 頁；屬規劃功能</span><span>04 / 10</span></div>

<!--
建議配時：40 秒。
兩份文件先做辨識與資訊擷取，再依規則標出程序上需要確認的事項。檢索分別取回法規與相似案例，生成端依模板形成草稿，最後檢查段落和引用。程序與引用檢核是新POC計畫補充的規劃，未宣稱已實作。依更新PDF第4頁：OCR為第1階段；案件擷取與程序檢核合為第2階段；檢索、生成、檢核依序為第3至5階段。模型用於OCR、案件擷取和生成；程序檢核採規則引擎。
來源：會議摘要（內容主軸）及最新提供的《訴願POC作戰計畫.pdf》（5頁），以PDF為更新依據。先前網頁參考：https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296 。補充來源：sources/poc/的00至09工作包。案例已對照提供原文、模板與範例已讀取，檢核器自測已執行；全量11／29／101資料與系統部署仍未驗證。
-->

---
class: data-slide
---

<div class="eyebrow">資料應用</div>

# 每一類資料，都有明確用途

<div class="three"><div class="metric"><div class="huge">11<small>部</small></div><h2>法規</h2><p>切成逐條資料，支援<br>條號查詢與法規引用。</p></div><div class="metric"><div class="huge">29<small>篇</small></div><h2>判解與函釋</h2><p>提供相關實務論述，<br>作為理由草擬的參考。</p></div><div class="metric"><div class="huge">101<small>件</small></div><h2>歷史決定書</h2><p>萃取格式與相似案例，<br>支援結構化草稿生成。</p></div></div><div class="band">資料支援事實對照、法規引用與論述結構；引用需能回查來源。</div>

<div class="foot"><span>筆數依 POC 計畫盤點；尚未核對資料檔案及實際匯入量</span><span>05 / 10</span></div>

<!--
建議配時：55 秒。
資料應用是最高比重的評分項目。法規適合按條號查，判解和函釋提供論述，歷史決定書提供案例比較和輸出模板。每項資料保留來源，讓承辦人回查。依POC計畫，盤點數量為11部、29篇和101件；仍需對照實際檔案及索引結果。本工作區未提供data/INVENTORY.md。建議隔離測試案原決定書，避免直接檢索到標準答案。
來源：會議摘要（內容主軸）及最新提供的《訴願POC作戰計畫.pdf》（5頁），以PDF為更新依據。先前網頁參考：https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296 。補充來源：sources/poc/的00至09工作包。案例已對照提供原文、模板與範例已讀取，檢核器自測已執行；全量11／29／101資料與系統部署仍未驗證。
-->

---

<div class="eyebrow">檢索策略</div>

# 法條精確查，案例找相似

<div class="two retrieval"><div><h2>法規檢索</h2><p>以法規名稱與條號取回原文，<br>保留明確的引用來源。</p><div class="logic">逐條 JSON → 精確查詢 → 法條依據</div></div><div><h2>相似案例檢索</h2><p>先篩選同類型案件，<br>再依語意相關性排序。</p><div class="logic">類型篩選 → 向量排序 → 3–5 件參考</div></div></div><p style="margin-top:32px">草稿引用帶來源 ID，前端可展開查看對應依據。</p>

<div class="foot"><span>依 POC 計畫規劃；檢索命中與引用一致性仍需實測</span><span>06 / 10</span></div>

<!--
建議配時：55 秒。
找指定條文，用名稱與條號精確查詢；找類似情境，先依案件類型篩選，再排序案例。每個引用保留來源ID，讓前端展開原文。案例提供參考，不是直接套用結論。驗證時檢查结果與爭點是否有關，以及生成內容是否忠於來源。第二案例114-18不納入主線承諾，3–5件推薦是規劃目標。更新PDF第4頁列三個索引：法條JSON、判解函釋、petitions.jsonl；案例帶標籤，Bedrock KB規劃採Titan向量與OpenSearch。
來源：會議摘要（內容主軸）及最新提供的《訴願POC作戰計畫.pdf》（5頁），以PDF為更新依據。先前網頁參考：https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296 。補充來源：sources/poc/的00至09工作包。案例已對照提供原文、模板與範例已讀取，檢核器自測已執行；全量11／29／101資料與系統部署仍未驗證。
-->

---

<div class="eyebrow">輸出成果</div>

# 草稿像決定書，引用能展開

<div class="output-grid"><div class="output-copy"><h2>三版模板已提供</h2><p>駁回、撤銷與不受理骨架；<br>本次主線使用駁回案格式。</p><h2>理由與來源一起交付</h2><p>將案件摘要、法規和相似案例<br>對應到草稿；缺少依據列為待補查。</p></div><div class="document"><div class="doc-title">訴願決定書參考稿</div><div class="doc-tag">結構示意 · 非實際生成結果</div><div class="doc-row"><b>主文</b><span>建議處理結論，待人工確認</span></div><div class="doc-row"><b>事實</b><span>處分經過與訴願主張</span></div><div class="doc-row"><b>理由</b><span>法規依據、事實對照、主張回應<br><small style="color:#73978d">引用來源可回查</small></span></div><div class="doc-row"><b>教示</b><span>依模板提供，須檢視正確性</span></div></div></div>

<div class="foot"><span>已提供模板、範例與生成提示詞；教示內容有來源差異，待確認</span><span>07 / 10</span></div>

<!--
建議配時：35 秒。
成果依決定書格式呈現，讓承辦人可以順著熟悉的欄位閱讀。右側只是結構示意，正式Demo要換成生成結果。重點不只是段落完整，而是每段理由能對照引用依據。已讀取04_決定書模板.json的駁回、撤銷、不受理三版及05_few_shot.json的113-15、114-15範例。09提示詞要求citations帶source、缺少資料寫入gaps；這是生成規則，不是模型必然遵守的保證。00原文與03範例的教示法院和04、06、07、09不一致，尚待核對。
來源：會議摘要（內容主軸）及最新提供的《訴願POC作戰計畫.pdf》（5頁），以PDF為更新依據。先前網頁參考：https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296 。補充來源：sources/poc/的00至09工作包。案例已對照提供原文、模板與範例已讀取，檢核器自測已執行；全量11／29／101資料與系統部署仍未驗證。
-->

---

<div class="eyebrow">技術可行性</div>

# 一個協調器，串接各段服務（已實作）

<img src="/images/aws-architecture.png" style="width:92%;margin:0 auto;display:block;border:1px solid #e5e7eb;border-radius:8px" alt="AWS 架構與資料流" />

<div class="foot"><span>Docker Compose（Vue＋FastAPI）→ Bedrock Converse（Claude Sonnet 5，帳戶不可用時自動降級 4.6）＋ Knowledge Base（Titan v2＋S3 Vectors）｜113-16 實測 S5 29/31</span><span>08 / 10</span></div>

<!--
建議配時：25 秒。
前端與 FastAPI 協調器用 Docker Compose 一鍵起，六個階段依序：OCR、擷取、程序檢核（純規則）、檢索、生成、檢核。四個 AI 階段都走 Bedrock Converse，預設 Claude Sonnet 5、可用環境變數換模型；帳戶拿不到時自動降級 Sonnet 4.6。檢索走自建 Knowledge Base：主辦方 141 篇 PDF 用 pdftotext 轉純文字上 S3，Titan v2 向量存 S3 Vectors，依類別過濾三次查詢並排除本案。全鏈約 2 分鐘，113-16 檢核 29/31，引用全部有據。
-->

---
class: video-demo
---

<div class="eyebrow">預錄 Demo · 網站操作展示</div>

# 訴願 AI 輔助草擬｜操作影片

<video class="demo-video" controls playsinline preload="metadata" aria-label="訴願 AI 網站操作預錄影片">
  <source src="/videos/demo-walkthrough.mp4" type="video/mp4" />
  您的瀏覽器無法播放此影片，請開啟下方影片連結。
</video>

<div class="foot"><span>預錄操作展示 · 網站部署完成後更新實機連結</span><span>09 / 10</span></div>

<!--
建議配時：60 秒。
按播放展示使用者提供的約58秒影片，保留約2秒切換時間。這是預錄操作展示，不宣稱現場即時串接。網站部署完成後再補實際網址。
影片來源：D:/mo-f2e/videos/demo-walkthrough/renders/updated-workflow-58s.mp4，複製至public/videos/demo-walkthrough.mp4，未改動影片內容。可透過原生控制列播放、暫停、調整音量或全螢幕。
檢核器自測30/30與9/30僅為構造樣本測試，不代表影片中的模型生成成效或完整法律正確性。
-->

---
class: closing
---

<div class="eyebrow">本次交付目標</div>

# 讓一件訴願案，<br>完成有依據的初稿

<img class="photo" src="/images/mountain-close.avif" alt="模板山景" /><div class="lead">文件讀得進來，引用查得到來源，<br>產出的參考稿能交由人員檢視。</div><div class="promise">一案跑通<br>引用可查<br>草稿可檢視</div>

<div class="foot"><span>工作包已備妥 · 待端到端串接與實測</span><span>10 / 10</span></div>

<!--
建議配時：15 秒。
這次用單一案例把文件、資料和草稿接起來。以可查核引用和可檢視格式，證明這段訴願文書作業具備輔助自動化的可能。已收到原案文字、模擬輸入、介面規格、模板、few-shot、引用清單、檢核程式、Demo腳本與生成提示詞；端到端串接、OCR及模型生成仍待實測。
來源：會議摘要（內容主軸）及最新提供的《訴願POC作戰計畫.pdf》（5頁），以PDF為更新依據。先前網頁參考：https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296 。補充來源：sources/poc/的00至09工作包。案例已對照提供原文、模板與範例已讀取，檢核器自測已執行；全量11／29／101資料與系統部署仍未驗證。
圖片及視覺參考：使用者指定模板 https://gamma.app/docs/Strategic-Priorities-Framework-rwelbh5m7687av6 。山景為模板視覺，不代表新北實際地景。
-->

---

<div class="eyebrow">備用頁 · 分工規劃</div>

# 五人各交付一段，再統一整合


| 角色 | 責任 | 主要產出 |
| --- | --- | --- |
| A | 案例、模板、檢核與簡報 | 模擬文件、模板、檢核表、展示腳本 |
| B | OCR 與案件資訊擷取 | 兩份辨識文字、案件摘要 JSON |
| C | AWS 資料與檢索服務 | 法條查詢、案例索引、檢索介面 |
| D | 協調器、程序檢核與生成 | 各段串接、案件狀態、參考稿 |
| E | Demo 前端（貴哥） | 上傳、結果對照、引用展開 |


<div class="foot"><span>依 POC 計畫更新；A–E 的實際人員及承諾仍需確認</span><span>備用 01</span></div>

<!--
備用頁，不計入6分鐘。
依POC計畫五人分工。模板从Speaker 1的OCR工作拆給A，並新增D整合角色；不是已獲每位成員確認的派工。頁面中的待辦仅作資料，未於此任務執行。
來源：會議摘要（內容主軸）及最新提供的《訴願POC作戰計畫.pdf》（5頁），以PDF為更新依據。先前網頁參考：https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296 。補充來源：sources/poc/的00至09工作包。案例已對照提供原文、模板與範例已讀取，檢核器自測已執行；全量11／29／101資料與系統部署仍未驗證。
-->

---

<div class="eyebrow">備用頁 · 30 小時 POC 節奏</div>

# 先接通，再替換真服務

<div class="timeline"><div><div class="time">H0–H2</div><h2>凍結介面</h2><p>確認 JSON 契約<br>驗證手寫中文辨識</p></div><div><div class="time">H2–H12</div><h2>各段並行</h2><p>以模擬資料開發<br>H12 跑通端到端</p></div><div><div class="time">H12–H20</div><h2>逐段接真</h2><p>替換檢索、生成、OCR<br>H20 真資料全通</p></div><div><div class="time">H20–H30</div><h2>凍結與排練</h2><p>修正、簡報、錄影<br>保留緩衝並繳交</p></div></div><div class="band">H12 與 H20 是整合關卡；第二案例僅在主流程穩定後考慮。</div>

<div class="foot"><span>時間表為 POC 計畫建議，不表示關卡已完成</span><span>備用 02</span></div>

<!--
備用頁，不計入6分鐘。
依POC計畫30小時節奏。原頁在A分工寫H22開始全職簡報，時間表寫H20，本頁依後者呈現。30小時依計畫，不宣稱已核對主辦時程。
來源：會議摘要（內容主軸）及最新提供的《訴願POC作戰計畫.pdf》（5頁），以PDF為更新依據。先前網頁參考：https://claude.ai/code/artifact/e1c76357-27db-4099-ad20-eb2265ad2296 。補充來源：sources/poc/的00至09工作包。案例已對照提供原文、模板與範例已讀取，檢核器自測已執行；全量11／29／101資料與系統部署仍未驗證。
-->
