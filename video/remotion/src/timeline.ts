import tl from "./timeline.json";
import { FPS } from "./theme";
export type SegId = keyof typeof tl.narration;
export const nar = (id: SegId) => tl.narration[id];
export const sec = (s: number) => Math.round(s * FPS);
// 場景時長 = 該場景旁白總長 + 尾端留白
export const PAD = 1.2;
export const sceneLen = (ids: SegId[], extra = 0) => sec(ids.reduce((a, id) => a + nar(id).duration, 0) + PAD + extra);
// Demo 影片（demo_cfr.mp4，164 s）各段：影片時間 → 播放倍速（由畫面差異偵測定位）
export const DEMO_SEGMENTS: { from: number; to: number; rate: number; label: string }[] = [
  { from: 0.5, to: 14.0, rate: 1.0, label: "登入、載入 Demo 文件、開始分析" },
  { from: 14.0, to: 61.5, rate: 8.0, label: "OCR 辨識中（8×）" },
  { from: 61.5, to: 72.5, rate: 1.5, label: "程序檢核・法源檢索" },
  { from: 72.5, to: 133.5, rate: 2.5, label: "草稿即時串流（2.5×）" },
  { from: 133.5, to: 137.5, rate: 1.0, label: "分析完成" },
  { from: 137.5, to: 163.0, rate: 0.72, label: "OCR 對照・程序檢核・法源檢索・決定書草稿" },
];
export const demoSegFrames = DEMO_SEGMENTS.map((s) => sec((s.to - s.from) / s.rate));
export const DEMO_TAIL = sec(10);
export const demoTotal = demoSegFrames.reduce((a, b) => a + b, 0) + DEMO_TAIL;
