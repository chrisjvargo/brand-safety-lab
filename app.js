const STORAGE_KEY = "brandSafetyLab.labels";
const IDENTIKEY_STORAGE_KEY = "brandSafetyLab.identikey";
const NAME_STORAGE_KEY = "brandSafetyLab.name";
const TIMER_SECONDS = 15 * 60;
const BATCH_SIZE = 12;
const DATA_ROOT = new URL("./data/", import.meta.url);

const state = {
  taxonomy: null,
  brandProfiles: {},
  defaultBrand: "lowes",
  allPosts: [],
  ads: [],
  adIndex: 0,
  garmCategories: [],
  labels: JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"),
  identikey: localStorage.getItem(IDENTIKEY_STORAGE_KEY) || "",
  name: localStorage.getItem(NAME_STORAGE_KEY) || "",
  answerKey: {},
  queue: [],
  rendered: new Map(),
  blurOn: true,
  hintCount: 0,
  timerHandle: null
};

document.addEventListener("DOMContentLoaded", init);

function resolveAsset(path) {
  if (!path) return "";
  if (/^https?:/i.test(path)) return path;
  return new URL(path.replace(/^\/+/, ""), document.baseURI).href;
}

async function init() {
  try {
    const [taxonomy, brandProfiles, postsResponse, adsResponse, answerKey] = await Promise.all([
      fetchJSON("taxonomy.json"),
      fetchJSON("brand_profiles.json"),
      fetchJSON("posts.json"),
      fetchJSON("ads.json"),
      fetchJSON("answer_key.json")
    ]);

    state.taxonomy = taxonomy;
    state.brandProfiles = brandProfiles?.profiles || {};
    state.defaultBrand = brandProfiles?.default || "lowes";
    state.garmCategories = taxonomy?.garm?.categories || [];
    state.ads = Array.isArray(adsResponse) ? adsResponse : [];
    state.adIndex = 0;
    state.answerKey = answerKey || {};

    const flatPosts = (postsResponse?.pages || []).flat();
    state.allPosts = flatPosts;
    state.queue = flatPosts.slice();
    sanitizeStoredLabels();

    bindUI();
    updateLabeledCounter();
    updateQueueCounter();
    updateHintCounter();
    setupInfiniteScroll();
    loadNextBatch();
    setupLogin();
  } catch (error) {
    console.error("Failed to initialize app:", error);
    alert("Failed to load lab data. Please refresh the page. Error: " + error.message);
  }
}

function sanitizeStoredLabels() {
  const filtered = {};
  Object.entries(state.labels).forEach(([key, value]) => {
    if (!key.startsWith("ad-")) return;
    if (value?.decision === "UNSAFE" && !value?.garm) return;
    if (value?.decision !== "UNSAFE" && value?.garm) {
      delete value.garm;
    }
    filtered[key] = value;
  });
  if (Object.keys(filtered).length !== Object.keys(state.labels).length) {
    state.labels = filtered;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.labels));
  }
}

function setupLogin() {
  const overlay = document.getElementById("loginOverlay");
  const form = document.getElementById("loginForm");
  const input = document.getElementById("identikeyInput");
  const nameInput = document.getElementById("nameInput");
  const errorEl = document.getElementById("loginError");
  if (!overlay || !form || !input || !nameInput) return;

  if (state.identikey && state.name) {
    overlay.hidden = true;
    document.body.classList.remove("login-active");
    input.value = state.identikey;
    nameInput.value = state.name;
    Object.keys(state.labels).forEach(applyAnswerFeedback);
    startTimer(TIMER_SECONDS);
    return;
  }

  overlay.hidden = false;
  document.body.classList.add("login-active");
  if (state.identikey) input.value = state.identikey;
  if (state.name) nameInput.value = state.name;
  (state.name ? input : nameInput).focus();

  if (!form.dataset.bound) {
    form.addEventListener("submit", event => {
      event.preventDefault();
      const value = input.value.trim().toLowerCase();
      const name = nameInput.value.trim().replace(/\s+/g, " ");
      if (name.length < 2) {
        if (errorEl) {
          errorEl.textContent = "Enter your full name so your submission can be matched.";
          errorEl.hidden = false;
        }
        return;
      }
      if (!/^[a-z]{3,4}\d{2,5}$/i.test(value)) {
        if (errorEl) {
          errorEl.textContent = "Enter a valid Identikey (letters followed by numbers).";
          errorEl.hidden = false;
        }
        return;
      }
      if (errorEl) errorEl.hidden = true;
      state.identikey = value;
      localStorage.setItem(IDENTIKEY_STORAGE_KEY, value);
      state.name = name;
      localStorage.setItem(NAME_STORAGE_KEY, name);
      overlay.hidden = true;
      document.body.classList.remove("login-active");
      startTimer(TIMER_SECONDS);
      alert("Thanks for jumping in! You’ll be graded on how thoughtfully you engage—make your best call, learn from the gold standard, and have fun.");
      Object.keys(state.labels).forEach(applyAnswerFeedback);
    });
    form.dataset.bound = "true";
  }
}

function bindUI() {
  const exportBtn = document.getElementById("exportCsv");
  if (exportBtn) exportBtn.addEventListener("click", exportCsv);

  const resetBtn = document.getElementById("resetSession");
  if (resetBtn) resetBtn.addEventListener("click", resetSession);

  const referencesLink = document.getElementById("openReferences");
  if (referencesLink) {
    referencesLink.addEventListener("click", e => {
      e.preventDefault();
      openReferencesDialog();
    });
  }

  const analyticsBtn = document.getElementById("openAnalytics");
  if (analyticsBtn) {
    analyticsBtn.addEventListener("click", () => {
      openAnalyticsDialog();
    });
  }

  const referencesDialog = document.getElementById("referencesDialog");
  if (referencesDialog) {
    referencesDialog.addEventListener("close", () => {
      referencesLink?.focus();
    });
  }

  const analyticsDialog = document.getElementById("analyticsDialog");
  if (analyticsDialog) {
    analyticsDialog.addEventListener("close", () => {
      analyticsBtn?.focus();
    });
  }
}

function setupInfiniteScroll() {
  const sentinel = document.getElementById("sentinel");
  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) {
      loadNextBatch();
    }
  }, { rootMargin: "1600px" });
  observer.observe(sentinel);
}

function loadNextBatch() {
  if (!state.queue.length) return;
  const batch = takeNextBatch();
  if (!batch.length) return;
  renderBatch(batch);
  updateQueueCounter();
}

function takeNextBatch() {
  if (!state.queue.length) return [];
  const batch = state.queue.slice(0, BATCH_SIZE);
  state.queue = state.queue.slice(batch.length);
  return batch;
}

function renderBatch(batch) {
  const template = document.getElementById("postTemplate");
  const adTemplate = document.getElementById("adTemplate");
  const timeline = document.getElementById("timeline");
  batch.forEach(post => {
    const clone = template.content.firstElementChild.cloneNode(true);
    populatePost(clone, post);
    timeline.appendChild(clone);
    state.rendered.set(post.id, { ...post, type: "post" });

    const ad = getNextAd();
    if (ad) {
      const adNode = adTemplate.content.firstElementChild.cloneNode(true);
      populateAd(adNode, post, ad);
      timeline.appendChild(adNode);
      state.rendered.set(adNode.dataset.id, { ...ad, type: "ad", postId: post.id, answerId: ad.id });
      applyLabelUI(adNode.dataset.id);
    }
  });
}

function populatePost(node, post) {
  node.dataset.id = post.id;
  const avatarSrc = resolveAsset(post.author?.avatar || "media/avatars/avatar-default.svg");
  node.querySelector(".avatar").src = avatarSrc;
  node.querySelector(".avatar").alt = post.author?.name ? `${post.author.name} avatar` : "Author avatar";
  node.querySelector(".displayName").textContent = post.author?.name || "User";
  const handle = node.querySelector(".handle");
  handle.textContent = post.author?.handle || "@user";
  const verified = node.querySelector(".verified");
  verified.style.display = post.author?.verified ? "inline" : "none";
  const time = node.querySelector(".time");
  time.dateTime = post.created_at;
  time.textContent = formatTimestamp(post.created_at);
  node.querySelector(".text").textContent = post.text;
  const metadata = node.querySelector(".placement-note");
  if (metadata) {
    metadata.textContent = "";
  }
  const hintButton = node.querySelector(".hint");
  if (shouldHint(post)) {
    hintButton.hidden = false;
    hintButton.addEventListener("click", () => {
      alert(post.notes || "Look closely at the context before labeling.");
    });
    state.hintCount += 1;
    updateHintCounter();
  }
  const media = node.querySelector(".media");
  const blur = state.blurOn && shouldBlur(post);
  media.classList.toggle("blurred", blur);
  media.addEventListener("click", () => {
    media.classList.toggle("blurred");
  });
  media.addEventListener("keypress", e => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      media.classList.toggle("blurred");
    }
  });
  (post.media || []).forEach(item => {
    if (item.type === "image") {
      const img = document.createElement("img");
      img.src = resolveAsset(item.src);
      img.alt = item.alt || "";
      media.appendChild(img);
    }
    if (item.type === "video") {
      const video = document.createElement("video");
      video.controls = true;
      video.preload = "metadata";
      if (item.poster) video.poster = resolveAsset(item.poster);
      video.src = resolveAsset(item.src);
      media.appendChild(video);
    }
  });
  const actions = node.querySelector(".actions");
  if (actions) actions.remove();
}

function getNextAd() {
  if (!state.ads.length) return null;
  const ad = state.ads[state.adIndex % state.ads.length];
  state.adIndex = (state.adIndex + 1) % state.ads.length;
  return ad;
}

function populateAd(node, post, ad) {
  const brandProfile = state.brandProfiles[ad.brand_key] || {};
  const adId = `ad-${post.id}-${ad.id}`;
  node.dataset.id = adId;
  node.dataset.answerKey = `${post.id}__${ad.id}`;
  const logo = node.querySelector(".brandLogo");
  if (logo) {
    const logoPath = brandProfile.logo || "media/brands/brand-placeholder.svg";
    logo.src = resolveAsset(logoPath);
    logo.alt = `${brandProfile.name || ad.brand_key} logo`;
  }
  const brandName = node.querySelector(".brandName");
  if (brandName) brandName.textContent = brandProfile.name || ad.brand_key;
  const sponsored = node.querySelector(".sponsored");
  if (sponsored) sponsored.textContent = "Sponsored placement";
  const placement = node.querySelector(".placement-note");
  if (placement) {
    const handle = post.author?.handle || post.author?.name || "this account";
    placement.textContent = `Appearing directly after ${handle}`;
  }
  const media = node.querySelector(".ad-media");
  if (media) {
    media.innerHTML = "";
    if (ad.video) {
      const video = document.createElement("video");
      video.controls = true;
      video.preload = "metadata";
      if (ad.image) video.poster = resolveAsset(ad.image);
      video.src = resolveAsset(ad.video);
      media.appendChild(video);
    } else if (ad.image) {
      const img = document.createElement("img");
      img.src = resolveAsset(ad.image);
      img.alt = ad.headline || "Sponsored creative";
      media.appendChild(img);
    } else {
      const tile = document.createElement("div");
      tile.className = "ad-fallback";
      if (brandProfile.color) tile.style.background = brandProfile.color;
      const tileBrand = document.createElement("span");
      tileBrand.className = "ad-fallback-brand";
      tileBrand.textContent = ad.advertiser || brandProfile.name || ad.brand_key;
      const tileNote = document.createElement("span");
      tileNote.className = "ad-fallback-note";
      tileNote.textContent = "Sponsored · real ad copy below";
      tile.append(tileBrand, tileNote);
      media.appendChild(tile);
    }
  }
  const headline = node.querySelector(".headline");
  if (headline) headline.textContent = ad.headline || "";
  const body = node.querySelector(".body");
  if (body) body.textContent = ad.body || "";
  const tagline = node.querySelector(".tagline");
  if (tagline) tagline.textContent = ad.tagline || "";
  const cta = node.querySelector(".cta");
  if (cta) {
    cta.textContent = ad.cta || "Learn more";
    cta.href = ad.url || "#";
  }
  const provenance = node.querySelector(".provenance");
  if (provenance) provenance.textContent = ad.provenance || "";

  const baseLabel = {
    adId,
    postId: post.id,
    brand_key: ad.brand_key,
    brand: brandProfile.name || ad.brand_key,
    answerId: ad.id
  };

  const okButton = node.querySelector(".ok");
  const unsafeButton = node.querySelector(".unsafe");
  if (okButton) {
    okButton.addEventListener("click", () => {
      setLabel(adId, { ...baseLabel, decision: "ACCEPTABLE" });
    });
  }
  if (unsafeButton) {
    unsafeButton.addEventListener("click", async () => {
      const garm = await chooseGarmCategory({
        adId,
        brand: brandProfile.name || ad.brand_key,
        headline: ad.headline
      });
      if (!garm) return;
      setLabel(adId, { ...baseLabel, decision: "UNSAFE", garm });
    });
  }
}

function shouldBlur(post) {
  if (!post) return false;
  if (post.suggested_risk === "FLOOR") return true;
  const floorCategories = new Set(
    state.garmCategories.filter(cat => cat.floor).map(cat => cat.name)
  );
  return (post.suggested_garm || []).some(cat => floorCategories.has(cat));
}

function shouldHint(post) {
  if (!post) return false;
  if (post.suggested_risk && ["MEDIUM", "HIGH"].includes(post.suggested_risk)) return true;
  const text = `${post.text} ${post.notes || ""}`.toLowerCase();
  return ["satire", "debate", "news", "context", "reclaim"].some(token => text.includes(token));
}

function formatTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function setLabel(id, patch) {
  if (!id) return;
  if (!state.identikey) {
    const overlay = document.getElementById("loginOverlay");
    if (overlay) overlay.hidden = false;
    document.body.classList.add("login-active");
    alert("Please enter your Identikey before labeling.");
    return;
  }
  const previous = state.labels[id] || {};
  const next = { ...previous, ...patch, ts: Date.now() };
  if (next.decision !== "UNSAFE") {
    delete next.garm;
  }
  state.labels[id] = next;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.labels));
  applyLabelUI(id);
  updateLabeledCounter();
}

function applyLabelUI(id) {
  const node = document.querySelector(`.post[data-id="${CSS.escape(id)}"]`);
  if (!node) return;
  const label = state.labels[id] || {};
  node.dataset.decision = label.decision || "";
  const riskSelect = node.querySelector(".risk");
  if (riskSelect) riskSelect.value = label.risk || "";
  const okButton = node.querySelector(".ok");
  if (okButton) okButton.classList.toggle("active", label.decision === "ACCEPTABLE");
  const unsafeButton = node.querySelector(".unsafe");
  if (unsafeButton) unsafeButton.classList.toggle("active", label.decision === "UNSAFE");
  applyAnswerFeedback(id);
}

function updateLabeledCounter() {
  const total = Object.keys(state.labels).length;
  document.getElementById("labeledCount").textContent = total;
}

function applyAnswerFeedback(id) {
  const node = document.querySelector(`.post[data-id="${CSS.escape(id)}"]`);
  if (!node) return;
  const answerKeyId = node.dataset.answerKey;
  const answer = answerKeyId
    ? state.answerKey?.[answerKeyId] || state.answerKey?.[answerKeyId.split("__").pop()]
    : null;
  const feedbackEl = node.querySelector(".feedback");
  if (!answer || !feedbackEl) {
    node.dataset.correct = "";
    if (feedbackEl) feedbackEl.textContent = "";
    return;
  }
  const label = state.labels[id];
  if (!label?.decision) {
    node.dataset.correct = "";
    feedbackEl.textContent = "";
    return;
  }
  const labelGarm = label.garm || "";
  const answerGarm = answer.garm || "";
  const decisionMatch = answer.decision === label.decision;
  const garmMatch = !answerGarm || answerGarm === labelGarm;
  const correct = decisionMatch && garmMatch;
  node.dataset.correct = correct ? "correct" : "incorrect";

  if (!decisionMatch) {
    feedbackEl.textContent = `✕ Gold standard: ${answer.decision}`;
  } else if (!garmMatch) {
    feedbackEl.textContent = `✕ Gold standard GARM: ${answerGarm}`;
  } else {
    feedbackEl.textContent = "✓ Matches the gold standard";
  }

  if (labelGarm) {
    feedbackEl.textContent += correct ? ` • You selected: ${labelGarm}` : ` • You selected: ${labelGarm || "None"}`;
  }

  if (answer.notes) {
    feedbackEl.textContent += ` – ${answer.notes}`;
  }
}

function chooseGarmCategory(context) {
  return new Promise(resolve => {
    const dialog = document.getElementById("garmDialog");
    const grid = document.getElementById("garmGrid");
    const errorEl = document.getElementById("garmError");
    const subtitle = document.getElementById("garmDialogSubtitle");
    if (!dialog || !grid || !state.garmCategories?.length) {
      const fallback = prompt("Select a GARM category for this placement:");
      resolve(fallback || null);
      return;
    }

    const existing = state.labels[context.adId]?.garm || "";
    grid.innerHTML = "";
    state.garmCategories.forEach(cat => {
      const radioId = `garm-${cat.id}-${Math.random().toString(16).slice(2)}`;
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "garmOption";
      input.value = cat.name;
      input.id = radioId;
      if (existing === cat.name) input.checked = true;
      const span = document.createElement("span");
      span.innerHTML = `<strong>${cat.name}</strong><br><small>${cat.tooltip || ""}</small>`;
      label.appendChild(input);
      label.appendChild(span);
      grid.appendChild(label);
    });

    if (subtitle) {
      subtitle.textContent = context.brand
        ? `Blocking placement for ${context.brand}${context.headline ? ` – "${context.headline}"` : ""}`
        : "Select the most accurate unsafe category.";
    }
    if (errorEl) errorEl.hidden = true;

    let settled = false;
    const form = dialog.querySelector("form");
    const cancelBtn = dialog.querySelector("[data-action=\"cancel\"]");

    const finish = value => {
      if (settled) return;
      settled = true;
      dialog.removeEventListener("cancel", onCancel);
      if (cancelBtn) cancelBtn.removeEventListener("click", onCancel);
      if (form) form.removeEventListener("submit", onSubmit);
      if (errorEl) errorEl.hidden = true;
      if (dialog.open) dialog.close();
      resolve(value);
    };

    const onCancel = event => {
      if (event) event.preventDefault();
      finish(null);
    };

    const onSubmit = event => {
      event.preventDefault();
      const selected = dialog.querySelector("input[name=\"garmOption\"]:checked");
      if (!selected) {
        if (errorEl) errorEl.hidden = false;
        return;
      }
      finish(selected.value);
    };

    dialog.addEventListener("cancel", onCancel);
    if (cancelBtn) cancelBtn.addEventListener("click", onCancel);
    if (form) form.addEventListener("submit", onSubmit);
    dialog.showModal();
  });
}

function openReferencesDialog() {
  const dialog = document.getElementById("referencesDialog");
  const list = document.getElementById("referenceList");
  list.innerHTML = "";
  const garmSources = state.taxonomy?.garm?.about?.sources || [];
  const iabSource = state.taxonomy?.iab_taxonomy?.about?.source;
  [...garmSources, iabSource].filter(Boolean).forEach(item => {
    const li = document.createElement("li");
    li.innerHTML = `<a href="${item.url}" target="_blank" rel="noreferrer noopener">${item.label}</a>`;
    list.appendChild(li);
  });
  dialog.showModal();
}

function openAnalyticsDialog() {
  const dialog = document.getElementById("analyticsDialog");
  populateAnalytics();
  dialog.showModal();
}

function populateAnalytics() {
  const heatmap = document.getElementById("heatmapPlaceholder");
  const divisive = document.getElementById("divisiveList");
  const analytics = buildAnalytics();
  heatmap.textContent = analytics.summary.length
    ? analytics.summary.join(" • ")
    : "Label additional posts or combine CSVs to unlock heat map insights.";
  divisive.innerHTML = "";
  analytics.divisive.forEach(item => {
    const li = document.createElement("li");
    li.textContent = `${item.id}: ${item.spread.toFixed(1)}% disagreement`;
    divisive.appendChild(li);
  });
}

function buildAnalytics() {
  const summary = [];
  const divisive = [];
  const counts = {};
  Object.entries(state.labels).forEach(([id, label]) => {
    const key = `${label.brand || "Unknown"}|${label.decision || "UNDECIDED"}`;
    counts[key] = (counts[key] || 0) + 1;
  });
  Object.entries(counts).forEach(([key, value]) => {
    const [brand, decision] = key.split("|");
    summary.push(`${brand} → ${decision}: ${value}`);
  });
  // Track potential contention when both safe/unsafe decisions recorded on same placement.
  Object.entries(state.labels).forEach(([id, label]) => {
    const twin = Object.values(state.labels).find(
      other => other !== label && other.postId === label.postId && other.brand_key === label.brand_key && other.decision !== label.decision
    );
    if (twin) divisive.push({ id, spread: 100 });
  });
  return { summary, divisive };
}

function exportCsv() {
  if (!Object.keys(state.labels).length) {
    alert("Judge at least one placement before exporting.");
    return;
  }
  const header = ["identikey", "name", "ad_id", "brand", "brand_key", "post_id", "decision", "garm", "timestamp"];
  const rows = Object.entries(state.labels).map(([id, label]) => ([
    state.identikey || "",
    state.name || "",
    id,
    label.brand || "",
    label.brand_key || "",
    label.postId || "",
    label.decision || "",
    label.garm || "",
    label.ts || ""
  ]));
  const csv = [header, ...rows].map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${state.identikey || "session"}-${Date.now()}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function resetSession() {
  if (!confirm("Clear all local labels and restart the session?")) return;
  state.labels = {};
  localStorage.removeItem(STORAGE_KEY);
  document.querySelectorAll(".post").forEach(post => {
    post.dataset.decision = "";
    const riskSelect = post.querySelector(".risk");
    if (riskSelect) riskSelect.value = "";
    post.querySelector(".ok")?.classList.remove("active");
    post.querySelector(".unsafe")?.classList.remove("active");
    post.dataset.correct = "";
    const feedback = post.querySelector(".feedback");
    if (feedback) feedback.textContent = "";
  });
  updateLabeledCounter();
}

function startTimer(duration) {
  let remaining = duration;
  const timerEl = document.getElementById("timer");
  if (state.timerHandle) clearInterval(state.timerHandle);
  const render = () => {
    const minutes = String(Math.floor(remaining / 60)).padStart(2, "0");
    const seconds = String(remaining % 60).padStart(2, "0");
    timerEl.textContent = `${minutes}:${seconds}`;
    if (remaining <= 0) {
      clearInterval(state.timerHandle);
      timerEl.textContent = "00:00";
      return;
    }
    remaining -= 1;
  };
  render();
  state.timerHandle = setInterval(render, 1000);
}

function updateQueueCounter() {
  document.getElementById("queueRemaining").textContent = state.queue.length;
}

function updateHintCounter() {
  document.getElementById("hintCount").textContent = state.hintCount;
}

async function fetchJSON(path) {
  const url = new URL(path, DATA_ROOT);
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    console.error(`Failed to load ${url.href}`, response.status);
    return {};
  }
  try {
    return await response.json();
  } catch (error) {
    console.error(`Invalid JSON at ${url.href}`, error);
    return {};
  }
}
