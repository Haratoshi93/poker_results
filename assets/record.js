(() => {
  "use strict";

  const REPO_OWNER = "Haratoshi93";
  const REPO_NAME = "poker_results";
  const REPO_BRANCH = "main";
  const CSV_PATH = "data/results.csv";
  const LOCAL_CSV_URL = "./data/results.csv";
  const TOKEN_STORAGE_KEY = "poker_results_github_token_v1";

  const state = {
    rows: [],
    allPlayers: [],
    lastGamePlayers: [],
    selectedPlayers: new Set(),
    chipValues: new Map(),
    latestTotalChips: 4500,
    csvRawText: "",
    csvSha: null,
    isSubmitting: false,
  };

  // --- Utilities ---

  function getLocalTodayIso() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  function normalizeDigits(str) {
    return String(str)
      .replace(/[０-９]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
      .replace(/[,\s]/g, "")
      .trim();
  }

  function utf8ToBase64(str) {
    const bytes = new TextEncoder().encode(str);
    let binary = "";
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
    }
    return btoa(binary);
  }

  function base64ToUtf8(base64) {
    const clean = base64.replace(/\s/g, "");
    const binary = atob(clean);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return new TextDecoder("utf-8").decode(bytes);
  }

  function parseCsv(text) {
    const lines = text
      .replace(/^\uFEFF/, "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    if (lines.length < 2) {
      return [];
    }

    const headers = lines[0].split(",").map((h) => h.trim());
    const idxDate = headers.indexOf("Date");
    const idxRound = headers.indexOf("Round");
    const idxTotal = headers.indexOf("TotalGameChips");
    const idxPlayer = headers.indexOf("Player");
    const idxChips = headers.indexOf("FinalChips");

    if ([idxDate, idxRound, idxTotal, idxPlayer, idxChips].some((i) => i < 0)) {
      throw new Error("CSVの列構成が想定と異なります。");
    }

    const rows = [];
    for (let i = 1; i < lines.length; i += 1) {
      const cols = lines[i].split(",").map((c) => c.trim());
      if (cols.length < headers.length) continue;
      rows.push({
        date: cols[idxDate],
        round: Number(cols[idxRound]),
        totalGameChips: Number(cols[idxTotal]),
        player: cols[idxPlayer],
        finalChips: Number(cols[idxChips]),
      });
    }
    return rows;
  }

  function appendRowsToCsv(existingText, newRows) {
    const header = "Date,Round,TotalGameChips,Player,FinalChips";
    const base = (existingText || "").replace(/^\uFEFF/, "").trimEnd();
    const lines = base ? [base] : [header];
    for (const r of newRows) {
      lines.push(`${r.date},${r.round},${r.totalGameChips},${r.player},${r.finalChips}`);
    }
    return `${lines.join("\n")}\n`;
  }

  // --- Accessible validation sync (matches :user-invalid) ---

  const announcer = document.createElement("div");
  announcer.setAttribute("aria-live", "polite");
  announcer.className = "visually-hidden";
  let announceTimer;
  let announcedField;
  const flagged = new WeakSet();
  const announced = new WeakSet();

  function linkError(el, shown) {
    const errorId = el.dataset.error;
    if (!errorId) return;
    const ids = (el.getAttribute("aria-describedby") || "")
      .split(/\s+/)
      .filter((id) => id && id !== errorId);
    if (shown) ids.push(errorId);
    if (ids.length) el.setAttribute("aria-describedby", ids.join(" "));
    else el.removeAttribute("aria-describedby");
  }

  function spokenText(node) {
    const copy = node.cloneNode(true);
    copy.querySelectorAll('[aria-hidden="true"]').forEach((n) => n.remove());
    copy.querySelectorAll('[role="img"][aria-label]').forEach((n) => {
      n.replaceWith(`${n.getAttribute("aria-label")}: `);
    });
    return copy.textContent.replace(/\s+/g, " ").trim();
  }

  function announceError(el) {
    const errorEl = el.dataset.error ? document.getElementById(el.dataset.error) : null;
    if (!errorEl) return;
    const label = el.labels?.[0] ? `${spokenText(el.labels[0])}: ` : "";
    clearTimeout(announceTimer);
    announcer.textContent = "";
    announcedField = el;
    announceTimer = setTimeout(() => {
      announcer.textContent = label + spokenText(errorEl);
    }, 500);
  }

  function syncAria(el, shouldAnnounce = false) {
    if (!el || !el.matches?.("input, select, textarea")) return;
    let isInvalid = false;
    try {
      isInvalid = el.matches(":user-invalid") || el.classList.contains("user-invalid-fallback");
    } catch {
      isInvalid = el.classList.contains("user-invalid-fallback");
    }

    if (isInvalid) {
      if (shouldAnnounce && !announced.has(el)) {
        announceError(el);
        announced.add(el);
      }
      el.setAttribute("aria-invalid", "true");
      linkError(el, true);
      flagged.add(el);
    } else if (flagged.has(el) || el.getAttribute("aria-invalid") !== "true") {
      el.setAttribute("aria-invalid", "false");
      linkError(el, false);
      flagged.delete(el);
      announced.delete(el);
      if (announcedField === el) {
        clearTimeout(announceTimer);
        announcer.textContent = "";
      }
    }
  }

  function initValidationSync() {
    document.body.append(announcer);
    document.querySelectorAll("input, select, textarea").forEach((el) => {
      if (!el.hasAttribute("aria-invalid")) {
        el.setAttribute("aria-invalid", "false");
      }
    });

    const supportsUserInvalid = CSS.supports?.("selector(:user-invalid)") ?? false;

    document.addEventListener(
      "blur",
      (e) => {
        const el = e.target;
        if (!el?.matches?.("input, select, textarea")) return;
        if (!supportsUserInvalid && el.value !== "") {
          el.classList.toggle("user-invalid-fallback", !el.validity.valid);
        }
        syncAria(el, true);
      },
      true
    );

    document.addEventListener("input", (e) => {
      const el = e.target;
      if (!el?.matches?.("input, select, textarea")) return;
      el.setCustomValidity("");
      if (!supportsUserInvalid) {
        el.classList.toggle("user-invalid-fallback", !el.validity.valid);
      }
      if (el.hasAttribute("aria-invalid")) {
        syncAria(el);
      }
    });

    document.addEventListener(
      "invalid",
      (e) => {
        const el = e.target;
        if (!supportsUserInvalid) {
          el.classList.add("user-invalid-fallback");
        }
        announced.add(el);
        syncAria(el);
      },
      true
    );
  }

  // --- GitHub API ---

  function getSavedToken() {
    try {
      return (localStorage.getItem(TOKEN_STORAGE_KEY) || "").trim();
    } catch {
      return "";
    }
  }

  function saveToken(token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token.trim());
  }

  function removeToken() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }

  async function fetchCsvFromGitHubApi(token) {
    const url = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${CSV_PATH}?ref=${encodeURIComponent(REPO_BRANCH)}`;
    const resp = await fetch(url, {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
      },
    });

    if (resp.status === 401 || resp.status === 403) {
      throw new Error("鍵が無効か、このリポジトリへの権限が足りません。鍵を確認してください。");
    }
    if (!resp.ok) {
      throw new Error(`GitHubからのデータ取得に失敗しました (HTTP ${resp.status})`);
    }

    const data = await resp.json();
    const content = base64ToUtf8(data.content || "");
    return { content, sha: data.sha };
  }

  async function updateCsvOnGitHub(token, newContent, sha, commitMessage) {
    const url = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/contents/${CSV_PATH}`;
    const resp = await fetch(url, {
      method: "PUT",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({
        message: commitMessage,
        content: utf8ToBase64(newContent),
        sha,
        branch: REPO_BRANCH,
      }),
    });

    if (resp.status === 401 || resp.status === 403) {
      throw new Error("書き込み権限がありません。鍵の「Contents: Read and write」設定を確認してください。");
    }
    if (resp.status === 409) {
      throw new Error("他の端末で同時に更新されました。もう一度「記録して公開する」を押してください。");
    }
    if (!resp.ok) {
      let detail = "";
      try {
        const errJson = await resp.json();
        detail = errJson.message ? ` (${errJson.message})` : "";
      } catch {
        // ignore JSON parse failure
      }
      throw new Error(`保存に失敗しました (HTTP ${resp.status})${detail}`);
    }

    return resp.json();
  }

  // --- UI Helpers ---

  function showBanner(type, message, withRankingLink = false) {
    const banner = document.getElementById("status-banner");
    banner.replaceChildren();
    banner.className = `status-banner status-banner-${type}`;

    const text = document.createElement("span");
    text.textContent = message;
    banner.appendChild(text);

    if (withRankingLink) {
      const link = document.createElement("a");
      link.href = "./index.html";
      link.className = "banner-link";
      link.textContent = "ランキングを開く →";
      banner.appendChild(link);
    }

    banner.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function hideBanner() {
    const banner = document.getElementById("status-banner");
    banner.className = "status-banner is-hidden";
    banner.replaceChildren();
  }

  function updateConnectionStatus(connected) {
    const badge = document.getElementById("connection-badge");
    const settingsBox = document.getElementById("settings-box");
    if (connected) {
      badge.className = "status-pill status-pill-ok";
      badge.textContent = "🟢 保存準備OK";
      settingsBox.open = false;
    } else {
      badge.className = "status-pill status-pill-warn";
      badge.textContent = "🔑 初回設定が必要です";
      settingsBox.open = true;
    }
  }

  function computeNextRoundForDate(dateStr) {
    const sameDateRounds = state.rows
      .filter((r) => r.date === dateStr && Number.isFinite(r.round))
      .map((r) => r.round);
    if (!sameDateRounds.length) return 1;
    return Math.max(...sameDateRounds) + 1;
  }

  function hasDuplicateRound(dateStr, roundNum) {
    return state.rows.some((r) => r.date === dateStr && r.round === roundNum);
  }

  function hydrateStateFromCsv(csvText, sha = null) {
    state.csvRawText = csvText;
    state.csvSha = sha;
    state.rows = parseCsv(csvText);

    const playerSet = new Set(state.allPlayers);
    for (const r of state.rows) {
      if (r.player) playerSet.add(r.player);
    }
    state.allPlayers = Array.from(playerSet);

    const infoEl = document.getElementById("latest-record-info");
    if (state.rows.length > 0) {
      const sortedGames = [...state.rows].sort((a, b) => {
        if (a.date !== b.date) return a.date < b.date ? -1 : 1;
        return a.round - b.round;
      });
      const last = sortedGames[sortedGames.length - 1];
      state.latestTotalChips = last.totalGameChips || 4500;
      state.lastGamePlayers = sortedGames
        .filter((r) => r.date === last.date && r.round === last.round)
        .map((r) => r.player);

      infoEl.textContent = `最新記録: ${last.date} (Round ${last.round})`;
    } else {
      state.lastGamePlayers = [];
      infoEl.textContent = "まだ記録がありません";
    }
  }

  function renderMemberPicker() {
    const picker = document.getElementById("member-picker");
    picker.replaceChildren();

    if (!state.allPlayers.length) {
      const p = document.createElement("p");
      p.className = "field-hint";
      p.textContent = "下の入力欄からメンバーを追加してください。";
      picker.appendChild(p);
      return;
    }

    for (const player of state.allPlayers) {
      const selected = state.selectedPlayers.has(player);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "player-chip member-toggle-chip";
      btn.setAttribute("aria-pressed", selected ? "true" : "false");

      const check = document.createElement("span");
      check.className = "member-check-mark";
      check.setAttribute("aria-hidden", "true");
      check.textContent = selected ? "✓" : "+";

      const name = document.createElement("span");
      name.textContent = player;

      btn.append(check, name);
      btn.addEventListener("click", () => {
        if (state.selectedPlayers.has(player)) {
          state.selectedPlayers.delete(player);
        } else {
          state.selectedPlayers.add(player);
          if (!state.chipValues.has(player)) {
            state.chipValues.set(player, "0");
          }
        }
        renderMemberPicker();
        renderChipsList();
      });

      picker.appendChild(btn);
    }
  }

  function renderChipsList() {
    const listEl = document.getElementById("chips-list");
    listEl.replaceChildren();

    const activePlayers = state.allPlayers.filter((p) => state.selectedPlayers.has(p));
    if (!activePlayers.length) {
      const empty = document.createElement("p");
      empty.className = "info-box";
      empty.textContent = "上で参加メンバーを選んでください。";
      listEl.appendChild(empty);
      return;
    }

    activePlayers.forEach((player, idx) => {
      const row = document.createElement("div");
      row.className = "chip-input-row";

      const inputId = `chips-player-${idx}`;
      const errorId = `chips-error-${idx}`;

      const label = document.createElement("label");
      label.className = "chip-player-label";
      label.htmlFor = inputId;
      label.textContent = player;

      const controlWrap = document.createElement("div");
      controlWrap.className = "chip-input-wrap";

      const input = document.createElement("input");
      input.type = "text";
      input.id = inputId;
      input.name = `chips_${idx}`;
      input.dataset.player = player;
      input.dataset.error = errorId;
      input.className = "form-input chip-number-input";
      input.inputMode = "numeric";
      input.pattern = "[0-9]+";
      input.required = true;
      input.enterKeyhint = idx === activePlayers.length - 1 ? "done" : "next";
      input.value = state.chipValues.get(player) ?? "0";
      input.setAttribute("aria-invalid", "false");

      input.addEventListener("focus", () => {
        if (input.value === "0") {
          input.select();
        }
      });

      input.addEventListener("input", () => {
        state.chipValues.set(player, input.value);
      });

      input.addEventListener("blur", () => {
        const cleaned = normalizeDigits(input.value);
        input.value = cleaned === "" ? "0" : cleaned;
        state.chipValues.set(player, input.value);
      });

      const unit = document.createElement("span");
      unit.className = "chip-unit";
      unit.setAttribute("aria-hidden", "true");
      unit.textContent = "枚";

      const err = document.createElement("div");
      err.id = errorId;
      err.className = "field-error";
      const errIcon = document.createElement("span");
      errIcon.setAttribute("role", "img");
      errIcon.setAttribute("aria-label", "エラー");
      errIcon.textContent = "❌";
      err.append(errIcon, " 0以上の半角数字を入力してください。");

      controlWrap.append(input, unit);
      row.append(label, controlWrap, err);
      listEl.appendChild(row);
    });
  }

  function applyInitialFormDefaults() {
    const dateInput = document.getElementById("game-date");
    const roundInput = document.getElementById("game-round");
    const totalInput = document.getElementById("total-chips");

    if (!dateInput.value) {
      dateInput.value = getLocalTodayIso();
    }
    roundInput.value = String(computeNextRoundForDate(dateInput.value));
    if (!totalInput.value) {
      totalInput.value = String(state.latestTotalChips);
    }

    if (state.selectedPlayers.size === 0 && state.lastGamePlayers.length > 0) {
      state.lastGamePlayers.forEach((p) => {
        state.selectedPlayers.add(p);
        state.chipValues.set(p, "0");
      });
    }

    renderMemberPicker();
    renderChipsList();
  }

  function addNewPlayer() {
    const input = document.getElementById("new-player-name");
    const rawName = input.value.trim();
    if (!rawName) return;

    if (/[,\r\n]/.test(rawName)) {
      showBanner("error", "プレイヤー名にカンマ（,）は使えません。");
      input.focus();
      return;
    }

    if (!state.allPlayers.includes(rawName)) {
      state.allPlayers.push(rawName);
    }
    state.selectedPlayers.add(rawName);
    if (!state.chipValues.has(rawName)) {
      state.chipValues.set(rawName, "0");
    }

    input.value = "";
    hideBanner();
    renderMemberPicker();
    renderChipsList();
  }

  // --- Data Loading ---

  async function loadLatestData() {
    const token = getSavedToken();
    const tokenInput = document.getElementById("github-token");
    if (token) {
      tokenInput.value = token;
      try {
        const { content, sha } = await fetchCsvFromGitHubApi(token);
        hydrateStateFromCsv(content, sha);
        updateConnectionStatus(true);
        return true;
      } catch (err) {
        updateConnectionStatus(false);
        showBanner("error", err instanceof Error ? err.message : "接続確認に失敗しました。");
      }
    } else {
      updateConnectionStatus(false);
    }

    // Fallback: read public CSV so existing members and round defaults are still shown
    try {
      const resp = await fetch(LOCAL_CSV_URL, { cache: "no-cache" });
      if (resp.ok) {
        const text = await resp.text();
        hydrateStateFromCsv(text, null);
      }
    } catch {
      document.getElementById("latest-record-info").textContent = "既存データを読み込めませんでした";
    }
    return false;
  }

  // --- Event Handlers ---

  async function handleSaveSettings(e) {
    e.preventDefault();
    hideBanner();

    const tokenInput = document.getElementById("github-token");
    const token = tokenInput.value.trim();
    if (!token) {
      tokenInput.setCustomValidity("書き込み用の鍵を入力してください。");
      tokenInput.reportValidity();
      tokenInput.focus();
      return;
    }

    const saveBtn = document.getElementById("save-token-btn");
    saveBtn.disabled = true;
    saveBtn.textContent = "接続を確認中…";

    try {
      const { content, sha } = await fetchCsvFromGitHubApi(token);
      saveToken(token);
      hydrateStateFromCsv(content, sha);
      applyInitialFormDefaults();
      updateConnectionStatus(true);
      showBanner("success", "鍵を保存し、接続を確認しました！このまま記録を保存できます。");
    } catch (err) {
      updateConnectionStatus(false);
      showBanner("error", err instanceof Error ? err.message : "接続に失敗しました。");
      tokenInput.focus();
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "鍵を保存して接続確認";
    }
  }

  function handleClearSettings() {
    removeToken();
    document.getElementById("github-token").value = "";
    updateConnectionStatus(false);
    showBanner("info", "このブラウザに保存していた鍵を削除しました。");
  }

  async function handleSubmitRecord(e) {
    e.preventDefault();
    if (state.isSubmitting) return;
    hideBanner();

    const token = getSavedToken();
    if (!token) {
      updateConnectionStatus(false);
      showBanner("error", "先に「書き込み用の鍵（初回設定）」を保存してください。");
      const tokenInput = document.getElementById("github-token");
      tokenInput.focus();
      return;
    }

    const dateInput = document.getElementById("game-date");
    const roundInput = document.getElementById("game-round");
    const totalInput = document.getElementById("total-chips");

    roundInput.value = normalizeDigits(roundInput.value);
    totalInput.value = normalizeDigits(totalInput.value);

    const chipInputs = Array.from(document.querySelectorAll("#chips-list .chip-number-input"));
    for (const input of chipInputs) {
      const cleaned = normalizeDigits(input.value);
      input.value = cleaned === "" ? "0" : cleaned;
      state.chipValues.set(input.dataset.player, input.value);
    }

    // Validate game fields
    const form = document.getElementById("record-form");
    const roundNum = Number(roundInput.value);
    const totalChips = Number(totalInput.value);

    if (!Number.isInteger(roundNum) || roundNum < 1) {
      roundInput.setCustomValidity("1以上の半角数字を入力してください。");
    } else {
      roundInput.setCustomValidity("");
    }

    if (!Number.isInteger(totalChips) || totalChips < 1) {
      totalInput.setCustomValidity("1以上の半角数字を入力してください。");
    } else {
      totalInput.setCustomValidity("");
    }

    if (!form.checkValidity()) {
      const firstInvalid = form.querySelector(":invalid");
      if (firstInvalid) {
        firstInvalid.focus();
        firstInvalid.reportValidity();
      }
      return;
    }

    if (chipInputs.length === 0) {
      showBanner("error", "参加メンバーを1人以上選択してください。");
      document.getElementById("member-picker").scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    const newRows = [];
    for (const input of chipInputs) {
      const player = input.dataset.player;
      const chips = Number(input.value);
      if (!Number.isInteger(chips) || chips < 0) {
        input.setCustomValidity("0以上の半角数字を入力してください。");
        input.focus();
        input.reportValidity();
        return;
      }
      newRows.push({
        date: dateInput.value,
        round: roundNum,
        totalGameChips: totalChips,
        player,
        finalChips: chips,
      });
    }

    const submitBtn = document.getElementById("submit-record-btn");
    state.isSubmitting = true;
    submitBtn.disabled = true;
    submitBtn.textContent = "記録を保存中…";

    try {
      // Always fetch latest file from GitHub before writing to avoid stale SHA or duplicates
      const latest = await fetchCsvFromGitHubApi(token);
      hydrateStateFromCsv(latest.content, latest.sha);

      if (hasDuplicateRound(dateInput.value, roundNum)) {
        showBanner(
          "error",
          `${dateInput.value} の Round ${roundNum} はすでに記録されています。ラウンド番号を確認してください。`
        );
        roundInput.focus();
        return;
      }

      const updatedCsv = appendRowsToCsv(latest.content, newRows);
      const commitMsg = `record: add ${dateInput.value} Round ${roundNum} results`;
      const result = await updateCsvOnGitHub(token, updatedCsv, latest.sha, commitMsg);

      hydrateStateFromCsv(updatedCsv, result.content?.sha || null);

      // Prepare cleanly for the next round with the same date/members/total chips
      roundInput.value = String(computeNextRoundForDate(dateInput.value));
      for (const player of state.selectedPlayers) {
        state.chipValues.set(player, "0");
      }
      renderChipsList();

      showBanner(
        "success",
        `${dateInput.value} (Round ${roundNum}) を記録しました！数十秒ほどでランキングに反映されます。`,
        true
      );
    } catch (err) {
      showBanner("error", err instanceof Error ? err.message : "保存中にエラーが発生しました。");
    } finally {
      state.isSubmitting = false;
      submitBtn.disabled = false;
      submitBtn.textContent = "このラウンドを記録して公開する";
    }
  }

  function setupListeners() {
    document.getElementById("settings-form").addEventListener("submit", handleSaveSettings);
    document.getElementById("clear-token-btn").addEventListener("click", handleClearSettings);
    document.getElementById("record-form").addEventListener("submit", handleSubmitRecord);

    const toggleTokenBtn = document.getElementById("toggle-token-btn");
    const tokenInput = document.getElementById("github-token");
    toggleTokenBtn.addEventListener("click", () => {
      const isShowing = toggleTokenBtn.getAttribute("aria-pressed") === "true";
      const next = !isShowing;
      tokenInput.type = next ? "text" : "password";
      toggleTokenBtn.setAttribute("aria-pressed", String(next));
      toggleTokenBtn.textContent = next ? "隠す" : "表示";
      toggleTokenBtn.setAttribute("aria-label", next ? "鍵の文字を隠す" : "鍵の文字を表示");
    });

    document.getElementById("game-date").addEventListener("change", (e) => {
      const val = e.target.value;
      if (val) {
        document.getElementById("game-round").value = String(computeNextRoundForDate(val));
      }
    });

    ["game-round", "total-chips"].forEach((id) => {
      const el = document.getElementById(id);
      el.addEventListener("blur", () => {
        el.value = normalizeDigits(el.value);
      });
    });

    document.getElementById("select-last-members-btn").addEventListener("click", () => {
      state.selectedPlayers.clear();
      state.lastGamePlayers.forEach((p) => {
        state.selectedPlayers.add(p);
        if (!state.chipValues.has(p)) state.chipValues.set(p, "0");
      });
      renderMemberPicker();
      renderChipsList();
    });

    document.getElementById("clear-members-btn").addEventListener("click", () => {
      state.selectedPlayers.clear();
      renderMemberPicker();
      renderChipsList();
    });

    document.getElementById("add-player-btn").addEventListener("click", addNewPlayer);
    document.getElementById("new-player-name").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.isComposing) {
        e.preventDefault();
        addNewPlayer();
      }
    });
  }

  async function init() {
    initValidationSync();
    setupListeners();
    await loadLatestData();
    applyInitialFormDefaults();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
