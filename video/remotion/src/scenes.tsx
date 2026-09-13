import React from "react";
import { AbsoluteFill, Freeze, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { T } from "./theme";
import { Brand, CountUp, Eyebrow, FadeIn, FONT, Foot, H1, Narration, Page } from "./ui";
import { DEMO_SEGMENTS, DEMO_TAIL, demoSegFrames, nar, sec } from "./timeline";

const Wrap: React.FC<{ children: React.ReactNode; top?: number }> = ({ children, top = 150 }) => (
  <div style={{ position: "absolute", left: 96, right: 96, top }}>{children}</div>
);

// ---------------------------------------------------------------- 01 開場
export const Intro: React.FC = () => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 200 } });
  return (
    <Page bg={T.forest}>
      <div style={{ position: "absolute", inset: 0, background: `radial-gradient(1200px 700px at 30% 40%, rgba(115,151,141,.35), transparent 70%)` }} />
      <Wrap top={230}>
        <div style={{ color: T.pale, fontSize: 26, letterSpacing: 4, opacity: p }}>新北市 AI 黑客松 · 法制局 · C_莫捲莫認真</div>
        <div style={{ fontFamily: FONT.serif, color: "#fff", fontSize: 128, fontWeight: 700, lineHeight: 1.15, marginTop: 24, letterSpacing: -3, transform: `translateY(${(1 - p) * 40}px)`, opacity: p }}>訴願 AI<br />輔助草擬</div>
        <FadeIn delay={25}><div style={{ color: T.pale, fontSize: 40, marginTop: 36, lineHeight: 1.6 }}>兩張照片進來，兩分鐘後<br />一份每個引用都能點回來源的決定書草稿。</div></FadeIn>
        <FadeIn delay={55}><div style={{ marginTop: 40, display: "flex", gap: 18 }}>{["單一案例", "六階段", "端到端實測"].map((t) => <span key={t} style={{ border: "1px solid rgba(232,239,235,.5)", color: T.pale, padding: "8px 18px", borderRadius: 999, fontSize: 24 }}>{t}</span>)}</div></FadeIn>
      </Wrap>
      <Narration id="01_intro" />
    </Page>
  );
};

// ---------------------------------------------------------------- 02 痛點
export const Pain: React.FC = () => (
  <Page>
    <Brand />
    <Wrap>
      <Eyebrow>痛點</Eyebrow>
      <H1>承辦人需要的，是有依據的草稿</H1>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 60, marginTop: 20 }}>
        <FadeIn delay={10}><div style={{ borderTop: `4px solid ${T.sage}`, paddingTop: 24 }}>
          <div style={{ color: T.muted, fontSize: 24 }}>新北市訴願案件量</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 24, marginTop: 8 }}>
            <span style={{ fontSize: 44, color: T.muted }}>110 年</span><CountUp from={0} to={1238} delay={15} style={{ fontSize: 96, color: T.forest, fontWeight: 500, letterSpacing: -3 }} /><span style={{ fontSize: 28, color: T.muted }}>件</span>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 24 }}>
            <span style={{ fontSize: 44, color: T.muted }}>114 年</span><CountUp from={1238} to={1566} delay={60} dur={50} style={{ fontSize: 96, color: T.forest, fontWeight: 500, letterSpacing: -3 }} /><span style={{ fontSize: 28, color: T.muted }}>件</span>
          </div>
        </div></FadeIn>
        <FadeIn delay={40}><div style={{ background: T.pale, padding: "28px 34px", borderRadius: 8 }}>
          <div style={{ color: T.forest, fontSize: 28, fontWeight: 500, marginBottom: 14 }}>大宗案類，論理高度重複</div>
          {["洗錢防制法", "廢棄物清理法", "空氣污染防制法"].map((t, i) => <FadeIn key={t} delay={70 + i * 20}><div style={{ fontSize: 34, padding: "10px 0", borderBottom: `1px solid ${T.sage}55` }}>{t}</div></FadeIn>)}
          <div style={{ color: T.muted, fontSize: 24, marginTop: 16 }}>每一份仍由承辦人逐件撰擬 → 我們接手「起草」這一段</div>
        </div></FadeIn>
      </div>
    </Wrap>
    <Foot left="命題：案件擷取分類 · 法規推薦 · 相似案比對 · 草稿生成" />
    <Narration id="02_pain" />
  </Page>
);

// ---------------------------------------------------------------- 03 單案與三情境
export const Case: React.FC = () => {
  const frame = useCurrentFrame();
  const branch = (i: number) => interpolate(frame, [110 + i * 60, 140 + i * 60], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const rows = [
    { k: "主線", v: "受騙交付提款卡與密碼，主張無故意", out: "駁回版", note: "引 114 簡上 13、立法理由第 3／5 點", color: T.forest },
    { k: "變化一", v: "送達日期改早 → 逾 30 日", out: "不受理版", note: "訴願法 14、77 條第 2 款", color: T.warn },
    { k: "變化二", v: "告誡書事實欄空白 → 96 條瑕疵", out: "撤銷版", note: "行政程序法 96、114 條，不附教示", color: T.red },
  ];
  return (
    <Page>
      <Brand />
      <Wrap>
        <Eyebrow>單案驗證 ＋ 兩個變化情境</Eyebrow>
        <H1>以洗錢告誡案，驗證完整流程</H1>
        <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", gap: 60 }}>
          <FadeIn><div>
            <div style={{ fontSize: 120, color: T.forest, letterSpacing: -5, lineHeight: 1 }}>113-16</div>
            <div style={{ fontSize: 30, marginTop: 14 }}>違反洗錢防制法事件</div>
            <div style={{ color: T.muted, fontSize: 24, marginTop: 10, lineHeight: 1.7 }}>模擬訴願書＋模擬書面告誡<br />（人名帳號皆虛構）<br />實測 S5 檢核 29 / 31</div>
          </div></FadeIn>
          <div style={{ display: "grid", gap: 18 }}>
            {rows.map((r, i) => (
              <div key={r.k} style={{ display: "grid", gridTemplateColumns: "110px 1fr 220px", alignItems: "center", gap: 20, background: T.white, border: `1px solid ${T.pale}`, borderLeft: `6px solid ${r.color}`, padding: "18px 22px", borderRadius: 8, opacity: branch(i), transform: `translateX(${(1 - branch(i)) * 30}px)` }}>
                <div style={{ color: T.muted, fontSize: 22 }}>{r.k}</div>
                <div><div style={{ fontSize: 28 }}>{r.v}</div><div style={{ color: T.muted, fontSize: 21 }}>{r.note}</div></div>
                <div style={{ fontFamily: FONT.serif, fontSize: 34, color: r.color, fontWeight: 700, textAlign: "right" }}>{r.out}</div>
              </div>
            ))}
          </div>
        </div>
      </Wrap>
      <Foot left="三種主文版本都由 S2.5 程序規則決定，模型不得自創第四種結論" />
      <Narration id="03_case" />
    </Page>
  );
};

// ---------------------------------------------------------------- 04 六階段
export const Pipeline: React.FC = () => {
  const frame = useCurrentFrame();
  const stages = [
    { id: "S1", t: "OCR 辨識", d: "Claude 多模態讀圖\n→ 個資取代後才往下", ai: true },
    { id: "S2", t: "案件擷取", d: "摘要 JSON：訴願人、處分、日期、主張", ai: true },
    { id: "S2.5", t: "程序檢核", d: "30 日／適格／處分／瑕疵", ai: false },
    { id: "S3", t: "法規與案例", d: "法條精確查表\nKB 三類向量檢索", ai: true },
    { id: "S4", t: "依模板生成", d: "主文由規則給\n引用只認檢索結果", ai: true },
    { id: "S5", t: "結果檢核", d: "與正本比對 31 項", ai: false },
  ];
  return (
    <Page>
      <Brand />
      <Wrap>
        <Eyebrow>處理流程（已實作）</Eyebrow>
        <H1>兩份文件進來，一份參考稿產出</H1>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 22, marginTop: 30 }}>
          {stages.map((s, i) => {
            const on = interpolate(frame, [30 + i * 55, 50 + i * 55], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={s.id} style={{ borderTop: `5px solid ${s.ai ? T.sage : "#3f8f5a"}`, paddingTop: 18, opacity: 0.35 + 0.65 * on, transform: `translateY(${(1 - on) * 14}px)` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ color: T.sage, fontSize: 22, fontFamily: FONT.mono }}>{s.id}</span>
                  {!s.ai && <span style={{ fontSize: 16, color: "#2f6d45", background: "#e6f2ea", padding: "2px 8px", borderRadius: 4 }}>無 AI</span>}
                </div>
                <div style={{ fontSize: 30, color: T.forest, fontWeight: 600, margin: "10px 0" }}>{s.t}</div>
                <div style={{ fontSize: 21, color: T.muted, whiteSpace: "pre-line", lineHeight: 1.6 }}>{s.d}</div>
              </div>
            );
          })}
        </div>
        <FadeIn delay={330}><div style={{ marginTop: 44, background: T.pale, color: T.forest, padding: "20px 28px", fontSize: 28, borderRadius: 6 }}>實測全鏈 100–120 秒（OCR 36 s、擷取 10 s、檢索 7 s、生成 60–70 s）；S2.5 與 S5 不呼叫模型。</div></FadeIn>
      </Wrap>
      <Foot left="Docker Compose：Vue 前端（nginx）＋ FastAPI 後端；WebSocket 即時推送階段狀態" />
      <Narration id="04_pipeline" />
    </Page>
  );
};

// ---------------------------------------------------------------- 05 架構（Ken Burns）
export const Arch: React.FC = () => {
  const frame = useCurrentFrame(); const total = sec(nar("05_arch").duration);
  const zoom = interpolate(frame, [0, total], [1.0, 1.16], { extrapolateRight: "clamp" });
  const x = interpolate(frame, [0, total], [0, -70], { extrapolateRight: "clamp" });
  return (
    <Page>
      <Brand />
      <Wrap top={110}>
        <Eyebrow>技術架構（已部署）</Eyebrow>
        <H1 size={54}>一個協調器，串接各段服務</H1>
      </Wrap>
      <div style={{ position: "absolute", left: 96, right: 96, top: 300, bottom: 150, overflow: "hidden", borderRadius: 10, border: `1px solid ${T.pale}`, background: "#F5F5F5" }}>
        <Img src={staticFile("img/aws-architecture.png")} style={{ width: "100%", transform: `scale(${zoom}) translateX(${x}px)`, transformOrigin: "55% 45%" }} />
      </div>
      <Narration id="05_arch" />
    </Page>
  );
};

// ---------------------------------------------------------------- 06–08 Demo 實錄（分段變速）
export const Demo: React.FC = () => {
  const frame = useCurrentFrame();
  let start = 0; let idx = 0; let inSeg = 0;
  for (let i = 0; i < DEMO_SEGMENTS.length; i++) { if (frame < start + demoSegFrames[i]) { idx = i; inSeg = frame - start; break; } start += demoSegFrames[i]; idx = i; inSeg = frame - start; }
  const seg = DEMO_SEGMENTS[idx];
  const label = frame >= demoSegFrames.reduce((a, b) => a + b, 0) ? DEMO_SEGMENTS[DEMO_SEGMENTS.length - 1].label : seg.label;
  // 旁白排程：06 開頭；07 在 OCR 對照頁（第 6 段開始）；08 接在 07 之後
  const s07 = demoSegFrames.slice(0, 5).reduce((a, b) => a + b, 0) + sec(1.0);
  const s08 = s07 + sec(nar("07_demo_b").duration) + sec(0.6);
  let acc = 0;
  return (
    <Page bg="#0f1a17">
      {DEMO_SEGMENTS.map((s, i) => {
        const from = acc; acc += demoSegFrames[i];
        return (
          <Sequence key={i} from={from} durationInFrames={demoSegFrames[i]} layout="none">
            {/* 不用 endAt：它以合成幀數計，不隨 playbackRate 換算，慢放時會提早變黑；Sequence 長度已限制播放區間 */}
            <OffthreadVideo src={staticFile("video/demo_cfr.mp4")} startFrom={sec(s.from)} playbackRate={s.rate} muted style={{ width: 1920, height: 1080, objectFit: "cover" }} />
          </Sequence>
        );
      })}
      <Sequence from={acc} durationInFrames={DEMO_TAIL} layout="none">
        <Freeze frame={0}>
          <OffthreadVideo src={staticFile("video/demo_cfr.mp4")} startFrom={sec(162.8)} muted style={{ width: 1920, height: 1080, objectFit: "cover" }} />
        </Freeze>
      </Sequence>
      {/* 左上狀態標籤 */}
      <div style={{ position: "absolute", top: 26, left: 26, display: "flex", gap: 10, alignItems: "center" }}>
        <span style={{ background: "rgba(6,62,51,.9)", color: "#fff", fontSize: 22, padding: "8px 16px", borderRadius: 6 }}>實際操作 · {label}</span>
        {seg.rate !== 1 && frame < demoSegFrames.reduce((a, b) => a + b, 0) && <span style={{ background: "rgba(0,0,0,.6)", color: "#fff", fontSize: 20, padding: "6px 12px", borderRadius: 6, fontFamily: FONT.mono }}>{seg.rate}×</span>}
      </div>
      <Narration id="06_demo_a" from={0} />
      <Sequence from={sec(15)} layout="none"><Narration id="06b_demo_wait" /></Sequence>
      <Sequence from={sec(15) + sec(nar("06b_demo_wait").duration) + sec(0.8)} layout="none"><Narration id="06c_demo_stream" /></Sequence>
      <Sequence from={s07} layout="none"><Narration id="07_demo_b" /></Sequence>
      <Sequence from={s08} layout="none"><Narration id="08_demo_c" /></Sequence>
    </Page>
  );
};
export const demoDuration = demoSegFrames.reduce((a, b) => a + b, 0) + DEMO_TAIL;

// ---------------------------------------------------------------- 09 結果
export const Result: React.FC = () => {
  const frame = useCurrentFrame();
  const cites = ["洗錢防制法第22條第1項", "洗錢防制法第22條第2項", "行政罰法第7條第1項", "洗錢防制法第15條之2立法理由第3點", "洗錢防制法第15條之2立法理由第5點", "臺北高等行政法院114年度簡上字第13號", "訴願法第79條第1項"];
  return (
    <Page>
      <Brand />
      <Wrap>
        <Eyebrow>輸出成果（實測）</Eyebrow>
        <H1>草稿像決定書，引用能展開</H1>
        <div style={{ display: "grid", gridTemplateColumns: "460px 1fr", gap: 60 }}>
          <div>
            <FadeIn><div style={{ borderTop: `4px solid ${T.sage}`, paddingTop: 20 }}><div style={{ color: T.muted, fontSize: 24 }}>S5 檢核（與正本比對）</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}><CountUp from={0} to={29} delay={10} dur={45} style={{ fontSize: 150, color: T.forest, letterSpacing: -6, lineHeight: 1.1 }} /><span style={{ fontSize: 44, color: T.muted }}>/ 31</span></div></div></FadeIn>
            <FadeIn delay={60}><div style={{ borderTop: `4px solid ${T.sage}`, paddingTop: 20, marginTop: 26 }}><div style={{ color: T.muted, fontSize: 24 }}>引用有據</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}><CountUp from={0} to={11} delay={70} dur={30} style={{ fontSize: 96, color: T.forest, letterSpacing: -3 }} /><span style={{ fontSize: 36, color: T.muted }}>/ 11 · 待補查 0</span></div></div></FadeIn>
          </div>
          <div style={{ background: T.white, border: `1px solid ${T.pale}`, borderTop: `6px solid ${T.forest}`, padding: "24px 30px", borderRadius: 6 }}>
            <div style={{ fontFamily: FONT.serif, fontSize: 30, color: T.forest, marginBottom: 12 }}>理由三引用（每筆可點回來源）</div>
            {cites.map((c, i) => { const on = interpolate(frame, [30 + i * 14, 42 + i * 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }); return (
              <div key={c} style={{ display: "flex", gap: 14, alignItems: "center", padding: "9px 0", borderBottom: `1px solid ${T.pale}`, opacity: on, transform: `translateX(${(1 - on) * 16}px)` }}>
                <span style={{ width: 26, height: 26, borderRadius: 13, background: "#e6f2ea", color: "#2f6d45", display: "grid", placeItems: "center", fontSize: 16 }}>✓</span><span style={{ fontSize: 26 }}>{c}</span></div>); })}
            <FadeIn delay={150}><div style={{ marginTop: 16, color: T.muted, fontSize: 22, lineHeight: 1.6 }}>未得分的 2 項是正本才有的 LINE 對話內容，輸入文件裡沒有——系統不編造。</div></FadeIn>
          </div>
        </div>
      </Wrap>
      <Narration id="09_result" />
    </Page>
  );
};

// ---------------------------------------------------------------- 10 可信與合規
export const Trust: React.FC = () => {
  const frame = useCurrentFrame();
  const stage = frame < 70 ? 0 : frame < 200 ? 1 : 2;   // 王小明 → 甲○○ → 王小明
  const names = ["王小明", "甲○○", "王小明"]; const notes = ["OCR 辨識出真名", "送模型前取代為代號；證號／電話／地址／生日遮罩", "草稿輸出時本機還原"];
  const checks = ["結論不交給模型：主文版本由程序規則決定", "引用只認檢索結果：缺依據列為待補查", "AWS 帳戶內不放個資：對照表僅存本機記憶體", "Bedrock ≤ 1 RPS · S3 不公開 · us-west-2", "帳密登入：環境變數設定，token 簽章"];
  return (
    <Page>
      <Brand />
      <Wrap>
        <Eyebrow>可信與合規</Eyebrow>
        <H1>模型從頭到尾沒看過真名</H1>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 60 }}>
          <div style={{ background: T.white, border: `1px solid ${T.pale}`, borderRadius: 10, padding: 36, textAlign: "center" }}>
            <div style={{ color: T.muted, fontSize: 24 }}>訴願人</div>
            <div style={{ fontFamily: FONT.serif, fontSize: 120, color: stage === 1 ? T.sage : T.forest, fontWeight: 700, transition: "color .3s", letterSpacing: 4, margin: "10px 0" }}>{names[stage]}</div>
            <div style={{ display: "flex", justifyContent: "center", gap: 10, marginBottom: 18 }}>{["OCR", "送模型", "草稿"].map((s, i) => <span key={s} style={{ padding: "6px 14px", borderRadius: 999, fontSize: 20, background: i === stage ? T.forest : T.pale, color: i === stage ? "#fff" : T.muted }}>{s}</span>)}</div>
            <div style={{ fontSize: 26, color: T.ink }}>{notes[stage]}</div>
            <div style={{ marginTop: 18, fontFamily: FONT.mono, fontSize: 22, color: T.muted, opacity: stage === 1 ? 1 : 0.35 }}>A1○○○○○○○○ · ○○○○-○○○-○○○ · 新店區○○路○段○○號</div>
          </div>
          <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
            {checks.map((c, i) => { const on = interpolate(frame, [40 + i * 40, 55 + i * 40], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }); return (
              <div key={c} style={{ display: "flex", gap: 14, alignItems: "flex-start", opacity: on, transform: `translateX(${(1 - on) * 20}px)` }}><span style={{ color: "#2f6d45", fontSize: 28, lineHeight: 1.4 }}>✓</span><span style={{ fontSize: 28, lineHeight: 1.5 }}>{c}</span></div>); })}
          </div>
        </div>
      </Wrap>
      <Foot left="對照黑客松環境規範逐條核過" />
      <Narration id="10_trust" />
    </Page>
  );
};

// ---------------------------------------------------------------- 11 收尾
export const Close: React.FC = () => (
  <Page bg={T.forest}>
    <div style={{ position: "absolute", inset: 0, background: `radial-gradient(1000px 600px at 70% 60%, rgba(115,151,141,.35), transparent 70%)` }} />
    <Wrap top={210}>
      <div style={{ color: T.pale, fontSize: 26, letterSpacing: 4 }}>本次交付</div>
      <FadeIn><div style={{ fontFamily: FONT.serif, color: "#fff", fontSize: 92, fontWeight: 700, lineHeight: 1.25, marginTop: 20, letterSpacing: -2 }}>一件訴願案，<br />完成有依據的初稿</div></FadeIn>
      <FadeIn delay={30}><div style={{ color: T.pale, fontSize: 34, marginTop: 30, lineHeight: 1.7 }}>文件讀得進來，引用查得到來源，<br />結論由規則把關，個資不出本機。</div></FadeIn>
      <FadeIn delay={70}><div style={{ marginTop: 40, display: "flex", gap: 16, flexWrap: "wrap" }}>{["一案跑通", "三種結論", "引用可查", "去識別化", "Docker 一鍵部署"].map((t) => <span key={t} style={{ border: "1px solid rgba(232,239,235,.5)", color: "#fff", padding: "10px 22px", borderRadius: 999, fontSize: 26 }}>{t} ✓</span>)}</div></FadeIn>
      <FadeIn delay={110}><div style={{ marginTop: 50, color: T.pale, fontSize: 26, fontFamily: FONT.mono }}>github.com/guitimliu/mo-juan-mo-renzhen</div></FadeIn>
    </Wrap>
    <Narration id="11_close" />
  </Page>
);
