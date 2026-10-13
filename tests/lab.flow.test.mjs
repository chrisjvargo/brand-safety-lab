// Full user-flow test for the Brand Safety Lab (runs the real app.js in jsdom).
// Covers: login, feed batches, safe/unsafe judging, GARM dialog, hints, blur,
// references, analytics, CSV export, reset, and timer behavior.
import { strict as assert } from "node:assert";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const APP_URL = "https://lab.test/brand-safety-lab/app.js";

function read(p) {
  return fs.readFileSync(path.join(ROOT, p), "utf8");
}

async function setup() {
  const dom = new JSDOM(read("index.html"), {
    url: "https://lab.test/brand-safety-lab/",
    runScripts: "outside-only",
    pretendToBeVisual: true,
  });
  const { window } = dom;
  const ctx = {
    alerts: [],
    confirms: [],
    confirmQueue: [],
    downloads: [],
    blobs: [],
    observerCallbacks: [],
  };

  window.alert = (msg) => ctx.alerts.push(String(msg));
  window.confirm = (msg) => {
    ctx.confirms.push(String(msg));
    return ctx.confirmQueue.length ? ctx.confirmQueue.shift() : true;
  };
  window.prompt = () => null;
  window.IntersectionObserver = class {
    constructor(cb) {
      ctx.observerCallbacks.push(cb);
    }
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  const dialogProto =
    window.HTMLDialogElement?.prototype ?? window.HTMLElement.prototype;
  dialogProto.showModal = function () {
    this.open = true;
  };
  dialogProto.close = function () {
    this.open = false;
  };
  window.fetch = async (url) => {
    const file = path.basename(new URL(String(url)).pathname);
    try {
      const data = JSON.parse(read(path.join("data", file)));
      return { ok: true, status: 200, json: async () => data };
    } catch {
      return { ok: false, status: 404, json: async () => ({}) };
    }
  };
  window.URL.createObjectURL = (blob) => {
    ctx.blobs.push(blob);
    return "blob:fake";
  };
  window.URL.revokeObjectURL = () => {};
  window.HTMLAnchorElement.prototype.click = function () {
    ctx.downloads.push({ download: this.download, href: String(this.href) });
    this.dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
  };
  if (!window.CSS?.escape) {
    window.CSS = { escape: (s) => s };
  }

  const context = vm.createContext(window);
  const mod = new vm.SourceTextModule(read("app.js"), {
    identifier: APP_URL,
    context,
    initializeImportMeta(meta) {
      meta.url = APP_URL;
    },
  });
  await mod.link(async () => {
    throw new Error("app.js must have no imports");
  });
  await mod.evaluate();
  window.document.dispatchEvent(new window.Event("DOMContentLoaded"));

  const $ = (sel) => window.document.querySelector(sel);
  const $$ = (sel) => [...window.document.querySelectorAll(sel)];
  async function waitFor(fn, timeout = 6000) {
    const start = Date.now();
    for (;;) {
      const v = fn();
      if (v) return v;
      if (Date.now() - start > timeout) throw new Error("waitFor timeout");
      await new Promise((r) => setTimeout(r, 50));
    }
  }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  await waitFor(() => $$("#timeline .post").length > 0);
  return { dom, window, $, $$, waitFor, sleep, ctx };
}

function login(window, $, identikey, name = "Test Student") {
  $("#nameInput").value = name;
  $("#identikeyInput").value = identikey;
  $("#loginForm").dispatchEvent(
    new window.Event("submit", { bubbles: true, cancelable: true })
  );
}

test("loads first batch and requires login", async () => {
  const { $, $$, dom } = await setup();
  try {
    assert.equal($$("#timeline .post:not(.ad-card)").length, 12);
    assert.equal($$("#timeline .ad-card").length, 12);
    assert.equal($("#queueRemaining").textContent, "12");
    assert.equal($("#labeledCount").textContent, "0");
    assert.ok(Number($("#hintCount").textContent) > 0);
    assert.equal($("#loginOverlay").hidden, false);
  } finally {
    dom.window.close();
  }
});

test("login validation", async () => {
  const { $, dom, window } = await setup();
  try {
    login(window, $, "xx");
    assert.equal($("#loginError").hidden, false);
    assert.equal($("#loginOverlay").hidden, false);
    login(window, $, "abcd1234", "");
    assert.equal($("#loginError").hidden, false);
    assert.equal($("#loginOverlay").hidden, false);
    login(window, $, "abcd1234");
    assert.equal($("#loginOverlay").hidden, true);
    assert.equal(window.localStorage.getItem("brandSafetyLab.identikey"), "abcd1234");
    assert.equal(window.localStorage.getItem("brandSafetyLab.name"), "Test Student");
  } finally {
    dom.window.close();
  }
});

test("safe judging records label and gold feedback", async () => {
  const { $, $$, dom, window } = await setup();
  try {
    login(window, $, "abcd1234");
    const ad = $$("#timeline .ad-card")[0];
    ad.querySelector(".ok").click();
    assert.equal($("#labeledCount").textContent, "1");
    const labels = JSON.parse(window.localStorage.getItem("brandSafetyLab.labels"));
    const [id, label] = Object.entries(labels)[0];
    assert.equal(label.decision, "ACCEPTABLE");
    assert.equal(label.postId, $$("#timeline .post:not(.ad-card)")[0].dataset.id);
    assert.match(ad.querySelector(".feedback").textContent, /gold standard|Matches/);
    assert.ok(["correct", "incorrect"].includes(ad.dataset.correct));
    assert.ok(ad.querySelector(".ok").classList.contains("active"));
  } finally {
    dom.window.close();
  }
});

test("unsafe judging requires a GARM pick", async () => {
  const { $, $$, dom, window } = await setup();
  try {
    login(window, $, "abcd1234");
    const ad = $$("#timeline .ad-card")[1];
    ad.querySelector(".unsafe").click();
    const dialog = $("#garmDialog");
    assert.equal(dialog.open, true);
    assert.equal($$("#garmGrid input[type=radio]").length, 12);
    dialog.querySelector("form").dispatchEvent(
      new window.Event("submit", { bubbles: true, cancelable: true })
    );
    assert.equal($("#garmError").hidden, false);
    assert.equal($("#labeledCount").textContent, "0");
    $$("#garmGrid input[type=radio]")[0].checked = true;
    const picked = $$("#garmGrid input[type=radio]")[0].value;
    dialog.querySelector("form").dispatchEvent(
      new window.Event("submit", { bubbles: true, cancelable: true })
    );
    await new Promise((r) => setTimeout(r, 20));
    assert.equal(dialog.open, false);
    assert.equal($("#labeledCount").textContent, "1");
    const labels = JSON.parse(window.localStorage.getItem("brandSafetyLab.labels"));
    const label = Object.values(labels)[0];
    assert.equal(label.decision, "UNSAFE");
    assert.equal(label.garm, picked);
    assert.match(ad.querySelector(".feedback").textContent, /Gold standard|Matches/);
  } finally {
    dom.window.close();
  }
});

test("canceling GARM saves nothing", async () => {
  const { $, $$, dom, window } = await setup();
  try {
    login(window, $, "abcd1234");
    const ad = $$("#timeline .ad-card")[0];
    ad.querySelector(".unsafe").click();
    assert.equal($("#garmDialog").open, true);
    $("#garmDialog [data-action=cancel]").click();
    assert.equal($("#garmDialog").open, false);
    assert.equal($("#labeledCount").textContent, "0");
  } finally {
    dom.window.close();
  }
});

test("hint, blur toggle, references, analytics", async () => {
  const { $, $$, dom, window, ctx } = await setup();
  try {
    login(window, $, "abcd1234");
    const hint = $$("#timeline .hint").find((b) => !b.hidden);
    assert.ok(hint, "expected a visible hint button");
    hint.click();
    assert.equal(ctx.alerts.length, 2); // welcome + hint
    const blurred = $("#timeline .media.blurred");
    if (blurred) {
      blurred.click();
      assert.equal(blurred.classList.contains("blurred"), false);
    }
    $("#openReferences").click();
    assert.equal($("#referencesDialog").open, true);
    assert.ok($("#referenceList").querySelectorAll("a").length >= 1);
    $("#referencesDialog").close();
    $("#openAnalytics").click();
    assert.equal($("#analyticsDialog").open, true);
    assert.ok($("#heatmapPlaceholder").textContent.length > 0);
  } finally {
    dom.window.close();
  }
});

test("second batch renders the full feed without trimming", async () => {
  const { $, $$, dom, window, ctx } = await setup();
  try {
    login(window, $, "abcd1234");
    assert.equal(ctx.observerCallbacks.length, 1);
    ctx.observerCallbacks[0]([{ isIntersecting: true }]);
    assert.equal($$("#timeline .post:not(.ad-card)").length, 24);
    assert.equal($$("#timeline .ad-card").length, 24);
    assert.equal($("#queueRemaining").textContent, "0");
  } finally {
    dom.window.close();
  }
});

test("timer starts on login, not on page load", async () => {
  const { $, dom, window, sleep } = await setup();
  try {
    await sleep(1300);
    assert.equal($("#timer").textContent, "15:00");
    login(window, $, "abcd1234");
    await sleep(1200);
    assert.match($("#timer").textContent, /^14:5[0-9]$/);
  } finally {
    dom.window.close();
  }
});

test("CSV export carries identikey filename and guards empty sessions", async () => {
  const { $, $$, dom, window, ctx } = await setup();
  try {
    login(window, $, "abcd1234");
    $("#exportCsv").click();
    assert.equal(ctx.downloads.length, 0);
    assert.match(ctx.alerts.at(-1), /at least one|nothing to export/i);
    $$("#timeline .ad-card")[0].querySelector(".ok").click();
    $("#exportCsv").click();
    assert.equal(ctx.downloads.length, 1);
    assert.match(ctx.downloads[0].download, /abcd1234.*\.csv$/);
    const text = await ctx.blobs[0].text();
    const [header, row] = text.trim().split("\n");
    assert.equal(header, '"identikey","name","ad_id","brand","brand_key","post_id","decision","garm","timestamp"');
    assert.match(row, /^"abcd1234","Test Student",/);
  } finally {
    dom.window.close();
  }
});

test("reset clears labels and counters", async () => {
  const { $, $$, dom, window } = await setup();
  try {
    login(window, $, "abcd1234");
    $$("#timeline .ad-card")[0].querySelector(".ok").click();
    assert.equal($("#labeledCount").textContent, "1");
    $("#resetSession").click();
    assert.equal($("#labeledCount").textContent, "0");
    assert.equal(window.localStorage.getItem("brandSafetyLab.labels"), null);
  } finally {
    dom.window.close();
  }
});

test("pairing gold judges post+brand together; real ads show provenance", async () => {
  const { $, $$, dom, window } = await setup();
  try {
    login(window, $, "abcd1234");
    const cards = $$("#timeline .ad-card");
    // Pairing 1 (safe marathon + Stanley) is gold-safe; pairing 2 (political
    // satire + charity) is gold-unsafe. Same SAFE click, opposite verdicts.
    cards[0].querySelector(".ok").click();
    assert.equal(cards[0].dataset.correct, "correct");
    cards[1].querySelector(".ok").click();
    assert.equal(cards[1].dataset.correct, "incorrect");
    assert.match(cards[1].querySelector(".feedback").textContent, /UNSAFE/);
    assert.match(cards[0].querySelector(".provenance").textContent, /Meta Ad Library #\d+/);
    assert.ok(cards[0].querySelector(".ad-media img, .ad-media video"));
  } finally {
    dom.window.close();
  }
});

test("no stale internal copy in student UI", async () => {
  const html = read("index.html");
  assert.doesNotMatch(html, /facilitation notes/);
  assert.doesNotMatch(html, /Local mirror is required/);
});
