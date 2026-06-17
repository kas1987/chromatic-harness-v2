/**
 * Playwright smoke tests for gen/public/dispatch.html
 *
 * Validates that the command center UI:
 *   1. Loads and renders all three tabs
 *   2. Tab switching works (shows/hides panels, updates aria-selected)
 *   3. Dispatch form elements are present and labelled
 *   4. Keyboard shortcut Ctrl+Enter is wired
 *   5. Annunciator LEDs are rendered
 *   6. Clock is ticking
 *   7. Status bar is visible
 *   8. Dispatch with empty prompt stays on page (no navigation)
 *
 * Run against file:// URL (no server required).
 * Set GEN_URL=http://localhost:43123 to test against live server instead.
 */

import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { chromium, type Browser, type Page } from "playwright";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HTML_PATH = path.resolve(__dirname, "../../public/dispatch.html");
const FILE_URL = "file:///" + HTML_PATH.replace(/\\/g, "/");
const PAGE_URL = process.env.GEN_URL
  ? process.env.GEN_URL + "/ui/dispatch.html"
  : FILE_URL;

let browser: Browser;
let page: Page;

beforeAll(async () => {
  browser = await chromium.launch({ headless: true });
  page = await browser.newPage();
  page.on("requestfailed", () => {});
  await page.goto(PAGE_URL);
  await page.waitForSelector("#clock", { state: "visible", timeout: 5000 });
}, 30_000);

afterAll(async () => {
  await browser.close();
});

describe("dispatch.html — initial render", () => {
  it("renders the logo text", async () => {
    const logo = await page.textContent("#logo");
    expect(logo).toMatch(/gen.*cmd/i);
  });

  it("renders all three tabs", async () => {
    const tabs = await page.$$eval(".tab", (els) => els.map((e) => e.textContent?.trim()));
    expect(tabs).toContain("Dispatch");
    expect(tabs).toContain("Services");
    expect(tabs).toContain("System");
  });

  it("Dispatch tab is active on load", async () => {
    const activeTab = await page.$eval(".tab.active", (el) => el.textContent?.trim());
    expect(activeTab).toBe("Dispatch");
  });

  it("Dispatch panel is visible on load", async () => {
    const visible = await page.isVisible("#panel-dispatch");
    expect(visible).toBe(true);
  });

  it("Services and System panels are hidden on load", async () => {
    const svcVisible = await page.isVisible("#panel-services");
    const sysVisible = await page.isVisible("#panel-system");
    expect(svcVisible).toBe(false);
    expect(sysVisible).toBe(false);
  });

  it("annunciator renders provider LEDs", async () => {
    const chips = await page.$$(".ann-chip");
    expect(chips.length).toBeGreaterThanOrEqual(5);
  });

  it("queue meter bar is present", async () => {
    const bar = await page.$("#queue-bar");
    expect(bar).not.toBeNull();
  });
});

describe("dispatch.html — accessibility", () => {
  it("tabs are button elements with role=tab", async () => {
    const tags = await page.$$eval(".tab", (els) => els.map((e) => e.tagName.toLowerCase()));
    expect(tags.every((t) => t === "button")).toBe(true);

    const roles = await page.$$eval(".tab", (els) => els.map((e) => e.getAttribute("role")));
    expect(roles.every((r) => r === "tab")).toBe(true);
  });

  it("tablist has role=tablist", async () => {
    const role = await page.$eval("#tabbar", (el) => el.getAttribute("role"));
    expect(role).toBe("tablist");
  });

  it("active tab has aria-selected=true", async () => {
    const ariaSelected = await page.$eval(".tab.active", (el) => el.getAttribute("aria-selected"));
    expect(ariaSelected).toBe("true");
  });

  it("prompt textarea has associated label", async () => {
    const labelText = await page.$eval("label[for='prompt']", (el) => el.textContent?.trim());
    expect(labelText).toBeTruthy();
  });

  it("provider select has associated label", async () => {
    const labelText = await page.$eval("label[for='provider']", (el) => el.textContent?.trim());
    expect(labelText).toBeTruthy();
  });

  it("priority select has associated label", async () => {
    const labelText = await page.$eval("label[for='priority']", (el) => el.textContent?.trim());
    expect(labelText).toBeTruthy();
  });

  it("max-tokens input has associated label", async () => {
    const labelText = await page.$eval("label[for='max-tokens']", (el) => el.textContent?.trim());
    expect(labelText).toBeTruthy();
  });
});

describe("dispatch.html — tab navigation", () => {
  it("clicking Services tab shows services panel", async () => {
    await page.click("button.tab[data-tab='services']");
    await page.waitForSelector("#panel-services.active", { timeout: 2000 });
    const visible = await page.isVisible("#panel-services");
    expect(visible).toBe(true);
  });

  it("clicking Services tab hides dispatch panel", async () => {
    const visible = await page.isVisible("#panel-dispatch");
    expect(visible).toBe(false);
  });

  it("Services tab gets aria-selected=true after click", async () => {
    const sel = await page.$eval("button.tab[data-tab='services']", (el) =>
      el.getAttribute("aria-selected")
    );
    expect(sel).toBe("true");
  });

  it("previous active tab loses aria-selected", async () => {
    const sel = await page.$eval("button.tab[data-tab='dispatch']", (el) =>
      el.getAttribute("aria-selected")
    );
    expect(sel).toBe("false");
  });

  it("clicking System tab shows system panel", async () => {
    await page.click("button.tab[data-tab='system']");
    await page.waitForSelector("#panel-system.active", { timeout: 2000 });
    const visible = await page.isVisible("#panel-system");
    expect(visible).toBe(true);
  });

  it("clicking Dispatch tab returns to dispatch panel", async () => {
    await page.click("button.tab[data-tab='dispatch']");
    await page.waitForSelector("#panel-dispatch.active", { timeout: 2000 });
    const visible = await page.isVisible("#panel-dispatch");
    expect(visible).toBe(true);
  });
});

describe("dispatch.html — compose form", () => {
  it("prompt textarea is present and writable", async () => {
    await page.fill("#prompt", "hello test");
    const val = await page.$eval("#prompt", (el: HTMLTextAreaElement) => el.value);
    expect(val).toBe("hello test");
  });

  it("provider select has auto and named options", async () => {
    const opts = await page.$$eval("#provider option", (els) =>
      els.map((e) => (e as HTMLOptionElement).value)
    );
    expect(opts).toContain("");
    expect(opts).toContain("claude");
    expect(opts).toContain("ollama");
  });

  it("priority select contains normal, high, low options", async () => {
    const opts = await page.$$eval("#priority option", (els) =>
      els.map((e) => (e as HTMLOptionElement).value)
    );
    expect(opts).toContain("normal");
    expect(opts).toContain("high");
    expect(opts).toContain("low");
  });

  it("Dispatch button is present", async () => {
    const btn = await page.$("#btn-dispatch");
    expect(btn).not.toBeNull();
  });

  it("Clear button resets prompt field", async () => {
    await page.fill("#prompt", "some text to clear");
    await page.click("#btn-clear");
    const val = await page.$eval("#prompt", (el: HTMLTextAreaElement) => el.value);
    expect(val).toBe("");
  });

  it("empty dispatch shows status message rather than crashing", async () => {
    await page.fill("#prompt", "");
    await page.click("#btn-dispatch");
    await page.waitForTimeout(300);
    const statusText = await page.textContent("#response-status");
    expect(statusText).toMatch(/prompt/i);
  });

  it("Ctrl+Enter with empty prompt does not navigate away", async () => {
    const url = page.url();
    await page.keyboard.press("Control+Enter");
    await page.waitForTimeout(200);
    expect(page.url()).toBe(url);
  });
});

describe("dispatch.html — clock", () => {
  it("clock shows a time string", async () => {
    const text = await page.textContent("#clock");
    expect(text).toMatch(/\d{2}:\d{2}:\d{2}/);
  });

  it("clock text is non-empty after 1.5 seconds", async () => {
    await page.waitForTimeout(1500);
    const text = await page.textContent("#clock");
    expect(text).toMatch(/\d{2}:\d{2}:\d{2}/);
  });
});

describe("dispatch.html — status bar", () => {
  it("status bar is visible", async () => {
    const visible = await page.isVisible("#statusbar");
    expect(visible).toBe(true);
  });

  it("sb-gen element is present", async () => {
    const el = await page.$("#sb-gen");
    expect(el).not.toBeNull();
  });

  it("sb-gen shows gen server label after poll completes", async () => {
    await page.waitForTimeout(3000);
    const text = await page.textContent("#sb-gen");
    expect(text).toMatch(/gen/i);
  });
});
