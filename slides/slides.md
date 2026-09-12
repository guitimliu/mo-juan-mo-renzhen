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
<div class="lead">以一件訴願案，走完<br>文件辨識到決定書參考稿。</div>
<div style="margin-top:30px;font-size:24px;color:var(--forest);font-weight:500">C_莫捲莫認真</div>

<div class="foot"><span>單一案例 · 完整流程 · 可展示結果</span><span>01 / 10</span></div>

---
class: side-photo
---

<div class="eyebrow">訴願流程自動化</div>

# 承辦人需要的，<br>是有依據的草稿

<img class="photo" src="/images/mountain-ridge.avif" alt="山稜照片" />
<div class="body"><p class="lead">案件事實在兩份文件裡；<br>草擬理由，還要對照法規與過往案例。</p><div style="margin-top:34px"><h2>我們支援這一段工作</h2><p>讀取文件、整理事實、找出依據，<br>依既有決定書格式形成參考稿。</p></div><p class="note">交由承辦人檢視與修正，輸出定位為參考稿。</p></div>

<div class="foot"><span>以團隊討論的草擬流程為範圍</span><span>02 / 10</span></div>

---

<div class="eyebrow">單案驗證</div>

# 以洗錢告誡案，驗證完整流程

<div class="two"><div><div class="case-id">113-16</div><div class="case-kind">違反洗錢防制法事件</div><p class="muted">本次展示案例<br>原決定結果：訴願駁回</p></div><div class="case-facts"><p><small>原處分</small>新店分局作成書面告誡</p><p><small>訴願主張</small>遭中獎詐騙，交付提款卡與密碼，<br>主張沒有故意</p><p><small>本次展示</small>模擬訴願書＋模擬原處分書<br>生成可對照理由與引用的草稿</p></div></div>

<div class="foot"><span>113-16 案例 · 展示輸入文件為模擬版本</span><span>03 / 10</span></div>

---

<div class="eyebrow">預定處理流程</div>

# 兩份文件進來，一份參考稿產出

<div class="flow"><div class="step"><div class="n">01</div><h2>OCR 辨識</h2><p>多模態模型讀圖<br>輸出兩份純文字</p></div><div class="step"><div class="n">02</div><h2>擷取與檢核</h2><p>模型擷取案件摘要<br>規則引擎檢核程序</p></div><div class="step"><div class="n">03</div><h2>法規與案例</h2><p>精確查法條<br>比對相似案件</p></div><div class="step"><div class="n">04</div><h2>依模板生成</h2><p>填入事實與理由<br>保留來源識別碼</p></div><div class="step"><div class="n">05</div><h2>結果檢核</h2><p>查核段落與引用<br>對照原決定結果</p></div></div><div class="band">OCR、案件擷取與生成呼叫模型；程序檢核依規則，法條依條號查詢。</div>

<div class="foot"><span>五階段處理流程 · 功能仍需實測驗證</span><span>04 / 10</span></div>

---
class: data-slide
---

<div class="eyebrow">資料應用</div>

# 每一類資料，都有明確用途

<div class="three"><div class="metric"><div class="huge">11<small>部</small></div><h2>法規</h2><p>切成逐條資料，支援<br>條號查詢與法規引用。</p></div><div class="metric"><div class="huge">29<small>篇</small></div><h2>判解與函釋</h2><p>提供相關實務論述，<br>作為理由草擬的參考。</p></div><div class="metric"><div class="huge">101<small>件</small></div><h2>歷史決定書</h2><p>萃取格式與相似案例，<br>支援結構化草稿生成。</p></div></div><div class="band">資料支援事實對照、法規引用與論述結構；引用需能回查來源。</div>

<div class="foot"><span>資料盤點數量；實際匯入量待核對</span><span>05 / 10</span></div>

---

<div class="eyebrow">檢索策略</div>

# 法條精確查，案例找相似

<div class="two retrieval"><div><h2>法規檢索</h2><p>以法規名稱與條號取回原文，<br>保留明確的引用來源。</p><div class="logic">逐條 JSON → 精確查詢 → 法條依據</div></div><div><h2>相似案例檢索</h2><p>先篩選同類型案件，<br>再依語意相關性排序。</p><div class="logic">類型篩選 → 向量排序 → 3–5 件參考</div></div></div><p style="margin-top:32px">草稿引用帶來源 ID，前端可展開查看對應依據。</p>

<div class="foot"><span>檢索命中與引用一致性仍需實測</span><span>06 / 10</span></div>

---

<div class="eyebrow">輸出成果</div>

# 草稿像決定書，引用能展開

<div class="output-grid"><div class="output-copy"><h2>決定書格式</h2><p>駁回、撤銷與不受理骨架；<br>本次主線使用駁回案格式。</p><h2>理由與來源一起交付</h2><p>將案件摘要、法規和相似案例<br>對應到草稿；缺少依據列為待補查。</p></div><div class="document"><div class="doc-title">訴願決定書參考稿</div><div class="doc-tag">結構示意 · 非實際生成結果</div><div class="doc-row"><b>主文</b><span>建議處理結論，待人工確認</span></div><div class="doc-row"><b>事實</b><span>處分經過與訴願主張</span></div><div class="doc-row"><b>理由</b><span>法規依據、事實對照、主張回應<br><small style="color:#73978d">引用來源可回查</small></span></div><div class="doc-row"><b>教示</b><span>依模板提供，須檢視正確性</span></div></div></div>

<div class="foot"><span>決定書參考稿 · 教示內容須由承辦人確認</span><span>07 / 10</span></div>

---

<div class="eyebrow">技術可行性</div>

# 一個協調器，串接各段服務（已實作）

<img src="/images/aws-architecture.png" style="width:92%;margin:0 auto;display:block;border:1px solid #e5e7eb;border-radius:8px" alt="AWS 架構與資料流" />

<div class="foot"><span>Docker Compose（Vue＋FastAPI）→ Bedrock Converse（Claude Sonnet 5，帳戶不可用時自動降級 4.6）＋ Knowledge Base（Titan v2＋S3 Vectors）｜113-16 實測 S5 29/31</span><span>08 / 10</span></div>

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

---
class: closing
---

<div class="eyebrow">本次交付目標</div>

# 讓一件訴願案，<br>完成有依據的初稿

<img class="photo" src="/images/mountain-close.avif" alt="山景" /><div class="lead">文件讀得進來，引用查得到來源，<br>產出的參考稿能交由人員檢視。</div><div class="promise">一案跑通<br>引用可查<br>草稿可檢視</div>

<div class="foot"><span>待端到端串接與實測</span><span>10 / 10</span></div>
