# -*- coding: utf-8 -*-
"""用 Playwright 錄一段乾淨的 Demo 實錄（bedrock 模式，經 nginx）。輸出 assets/generated/demo_raw.mp4 與時間戳 demo_marks.json。
用法：BASE=http://localhost:8091 USER=clerk PASS=demo1234 python record_demo.py
"""
import json, os, pathlib, time, subprocess
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8091"); USER = os.environ.get("USER_", os.environ.get("USER", "clerk")); PASS = os.environ.get("PASS", "demo1234")
OUT = pathlib.Path(__file__).parent / "assets/generated"; OUT.mkdir(parents=True, exist_ok=True)
marks = []; t0 = None
def mark(name):
    marks.append({"t": round(time.time() - t0, 2), "name": name}); print(f"{marks[-1]['t']:7.2f}s  {name}")

with sync_playwright() as p:
    b = p.chromium.launch(args=["--force-device-scale-factor=1"])
    ctx = b.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=str(OUT / "_rec"), record_video_size={"width": 1920, "height": 1080}, locale="zh-TW")
    pg = ctx.new_page(); t0 = time.time()
    pg.goto(BASE + "/", wait_until="networkidle"); mark("login page"); time.sleep(1.5)
    pg.type("input[type=text]", USER, delay=60); pg.type("input[type=password]", PASS, delay=60); time.sleep(0.6)
    pg.click("button[type=submit]"); pg.wait_for_selector(".workspace"); mark("workspace"); time.sleep(2)
    pg.get_by_role("button", name="新建案件").first.click(); pg.wait_for_selector("text=載入 Demo 文件"); time.sleep(1.2)
    pg.get_by_role("button", name="載入 Demo 文件").click(); pg.wait_for_selector(".upload-zone img"); mark("demo files loaded"); time.sleep(2.5)
    pg.get_by_role("button", name="開始分析", exact=True).click(); mark("start analysis")
    seen = set()
    while True:
        time.sleep(1)
        txt = pg.inner_text(".processing-panel") if pg.locator(".processing-panel").count() else ""
        for key in ("OCR 文字辨識", "程序檢核", "檢索法條與相似案", "生成決定書草稿"):
            if key in txt and key not in seen and "處理中" in txt:
                # 找目前處理中的階段
                cur = pg.locator(".processing-stages li.processing h4")
                if cur.count() and cur.first.inner_text() == key: seen.add(key); mark(f"stage: {key}")
        if pg.locator(".live-wrap").count() and "streaming" not in seen: seen.add("streaming"); mark("draft streaming visible")
        if "分析完成" in txt: mark("analysis done"); break
        if time.time() - t0 > 330: mark("timeout"); break
    time.sleep(3)
    pg.locator(".side-step", has_text="OCR 辨識").click(); mark("page: OCR"); time.sleep(4)
    pg.locator(".document-tabs button", has_text="原處分書").click(); time.sleep(3)
    pg.locator(".side-step", has_text="程序檢核").click(); mark("page: procedure"); time.sleep(4)
    pg.locator(".side-step", has_text="法源檢索").click(); mark("page: retrieval"); time.sleep(4)
    pg.locator(".side-step", has_text="決定書草稿").click(); mark("page: draft"); time.sleep(3)
    try:
        pg.locator(".draft-section-title button").nth(2).click(); time.sleep(1.5)
        pg.locator(".citation-chips button").first.click(); mark("citation clicked"); time.sleep(3)
    except Exception as e: print("citation click skipped", e)
    pg.mouse.wheel(0, 600); time.sleep(2.5); pg.mouse.wheel(0, 900); time.sleep(2.5)
    mark("end"); time.sleep(1)
    ctx.close(); b.close()
webm = next((OUT / "_rec").glob("*.webm"))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-an", str(OUT / "demo_raw.mp4")], check=True)
json.dump(marks, open(OUT / "demo_marks.json", "w"), ensure_ascii=False, indent=1)
dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(OUT / "demo_raw.mp4")], capture_output=True, text=True).stdout.strip()
print("saved demo_raw.mp4", dur, "s")
