# 前端持久層 UI 煙霧測試（需前後端 compose 啟動且 DB 已有 poc-001）：BASE=http://localhost:8091 AUTH_PASSWORD=... python tests/persistence_ui.py
import asyncio, sys
from playwright.async_api import async_playwright
import os
BASE=os.environ.get('BASE','http://localhost:8091'); PW=os.environ.get('AUTH_PASSWORD','')
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":1440,"height":900})
        errors=[]; pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type=="error" else None)
        await pg.goto(BASE); await pg.wait_for_timeout(800)
        # 登入
        await pg.fill("input[autocomplete='username'], input[name='username'], input[type='text']", "clerk")
        await pg.fill("input[type='password']", PW); await pg.keyboard.press("Enter"); await pg.wait_for_timeout(1500)
        # 1. 側欄案件列表
        items=await pg.locator(".case-item").all_text_contents(); print("case list:", items)
        assert any("poc-001" in t for t in items), "案件列表沒有 poc-001"
        # 2. 開啟案件 → 草稿頁
        await pg.locator(".case-item", has_text="poc-001").first.click(); await pg.wait_for_timeout(2500)
        print("toast:", await pg.locator(".toast").text_content() if await pg.locator(".toast").count() else "-")
        print("heading tag:", await pg.locator(".section-heading .tag").first.text_content())
        print("draft sections:", await pg.locator(".draft-section h3").all_text_contents())
        # 影像回看
        await pg.locator(".pipeline button").nth(1).click(); await pg.wait_for_timeout(800)
        src=await pg.locator(".scan-preview img").get_attribute("src"); print("preview img:", (src or "")[:40])
        assert src and src.startswith("blob:"), "影像沒有從 DB 回看"
        # 3. 法源頁歷史統計
        await pg.locator(".pipeline button").nth(3).click(); await pg.wait_for_timeout(600)
        print("history bar:", await pg.locator(".history-bar").text_content())
        tags=await pg.locator(".source-result .tag").all_text_contents(); print("source tags:", sorted(set(tags)))
        # 4. 編輯草稿 → 儲存版本
        await pg.locator(".pipeline button").nth(4).click(); await pg.wait_for_timeout(600)
        await pg.get_by_role("button", name="編輯草稿").click(); await pg.wait_for_timeout(300)
        ta=pg.locator("textarea.draft-edit").first; await ta.fill("訴願駁回。（UI 測試修改）")
        await pg.fill(".edit-bar input", "Playwright 測試版"); await pg.get_by_role("button", name="儲存版本").click(); await pg.wait_for_timeout(1500)
        print("after save tag:", await pg.locator(".section-heading .tag").first.text_content())
        print("holding now:", await pg.locator(".draft-section p").first.text_content())
        opts=await pg.locator(".version-select option").all_text_contents(); print("versions:", opts)
        # 5. 還原 AI 原稿
        await pg.locator(".version-select select").select_option("0"); await pg.wait_for_timeout(1200)
        print("after restore tag:", await pg.locator(".section-heading .tag").first.text_content(), "| holding:", await pg.locator(".draft-section p").first.text_content())
        await pg.screenshot(path="/tmp/ui_draft.png", full_page=False)
        print("JS errors:", errors)
        await b.close()
asyncio.run(main())
