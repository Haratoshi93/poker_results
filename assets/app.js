(() => {
  "use strict";

  const DATA_URL = "./data/results.csv";
  const INITIAL_RATING = 1000;
  const K_FACTOR = 300;
  const PALETTE = [
    "#D4AF37",
    "#52D681",
    "#5BC0EB",
    "#FF7B7B",
    "#C792EA",
    "#FFB86C",
    "#8BE9FD",
    "#F1FA8C",
    "#FF92DF",
    "#A3BE8C",
  ];

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
      throw new Error("CSV の列形式が想定と異なります。");
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

  function calcRatings(rows) {
    if (!rows.length) {
      return { history: [], summary: [], gameOrder: [] };
    }

    const groupsMap = new Map();
    for (const row of rows) {
      const key = `${row.date}__${String(row.round).padStart(6, "0")}`;
      if (!groupsMap.has(key)) {
        groupsMap.set(key, {
          date: row.date,
          round: row.round,
          totalGameChips: row.totalGameChips,
          rows: [],
        });
      }
      groupsMap.get(key).rows.push(row);
    }

    // pandas groupby(['Date', 'Round']) と同じ昇順ソート
    const sortedGroups = Array.from(groupsMap.values()).sort((a, b) => {
      if (a.date !== b.date) return a.date < b.date ? -1 : 1;
      return a.round - b.round;
    });

    const ratings = new Map();
    const history = [];
    const gameLabels = [];

    for (const group of sortedGroups) {
      const gameLabel = `${group.date} (R${group.round})`;
      gameLabels.push(gameLabel);

      const currentGameRatings = new Map();
      for (const r of group.rows) {
        if (!ratings.has(r.player)) {
          ratings.set(r.player, INITIAL_RATING);
        }
        currentGameRatings.set(r.player, ratings.get(r.player));
      }

      let sumExpected = 0;
      for (const rating of currentGameRatings.values()) {
        sumExpected += Math.pow(10, rating / 400.0);
      }

      for (const r of group.rows) {
        const actualShare =
          group.totalGameChips > 0 ? r.finalChips / group.totalGameChips : 0;
        const expectedShare =
          Math.pow(10, currentGameRatings.get(r.player) / 400.0) / sumExpected;
        const deltaR = K_FACTOR * (actualShare - expectedShare);
        const newRating = ratings.get(r.player) + deltaR;
        ratings.set(r.player, newRating);

        history.push({
          date: group.date,
          round: group.round,
          gameLabel,
          player: r.player,
          finalChips: r.finalChips,
          deltaRating: deltaR,
          newRating,
        });
      }
    }

    const summary = [];
    for (const [player, rating] of ratings.entries()) {
      const playerHist = history.filter((h) => h.player === player);
      const lastDelta = playerHist.length
        ? playerHist[playerHist.length - 1].deltaRating
        : 0;
      summary.push({
        player,
        rating,
        roundedRating: Math.round(rating),
        lastDelta,
        gamesPlayed: playerHist.length,
      });
    }

    summary.sort((a, b) => b.rating - a.rating);

    // rank(method='min') と同じ同率順位計算（四捨五入した整数値で判定）
    let currentRank = 1;
    for (let i = 0; i < summary.length; i += 1) {
      if (i > 0 && summary[i].roundedRating < summary[i - 1].roundedRating) {
        currentRank = i + 1;
      }
      summary[i].rankNum = currentRank;
    }

    return { history, summary, gameOrder: ["開始", ...gameLabels] };
  }

  function getMedal(rank) {
    if (rank === 1) return "🥇";
    if (rank === 2) return "🥈";
    if (rank === 3) return "🥉";
    return `${rank}位`;
  }

  function formatDeltaText(delta, withUnit = false) {
    const val = Math.round(delta);
    const suffix = withUnit ? " pt" : "";
    if (val > 0) return `📈 +${val}${suffix}`;
    if (val < 0) return `📉 ${val}${suffix}`;
    return `➖ 0${suffix}`;
  }

  function renderHeroMeta(summary, history) {
    const metaEl = document.getElementById("hero-meta");
    metaEl.replaceChildren();

    if (!summary.length || !history.length) {
      const span = document.createElement("span");
      span.className = "poker-hero-stat";
      span.textContent = "対戦データを追加すると最新順位が表示されます";
      metaEl.appendChild(span);
      return;
    }

    const topScore = summary[0].roundedRating;
    const topNames = summary
      .filter((s) => s.roundedRating === topScore)
      .map((s) => s.player)
      .join("・");

    const uniqueGames = new Set(history.map((h) => h.gameLabel)).size;
    const latestDate = history[history.length - 1].date;

    const badge = document.createElement("span");
    badge.className = "poker-hero-badge";
    badge.textContent = `👑 現在の1位: ${topNames} (${topScore} pt)`;

    const stat = document.createElement("span");
    stat.className = "poker-hero-stat";
    stat.textContent = `全 ${uniqueGames} ラウンド / 最終プレイ ${latestDate}`;

    metaEl.append(badge, stat);
  }

  function renderRankingTable(summary) {
    const tbody = document.getElementById("ranking-tbody");
    tbody.replaceChildren();

    if (!summary.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 2;
      td.className = "empty-cell";
      td.textContent = "データがありません。";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    for (const item of summary) {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.scope = "row";
      th.textContent = `${getMedal(item.rankNum)} ${item.player}`;

      const td = document.createElement("td");
      td.textContent = `${item.roundedRating} pt (${formatDeltaText(item.lastDelta)})`;

      tr.append(th, td);
      tbody.appendChild(tr);
    }
  }

  function renderLatestGame(history) {
    const metaText = document.getElementById("latest-meta-text");
    const metricsEl = document.getElementById("latest-metrics");
    const tbody = document.getElementById("latest-tbody");

    metricsEl.replaceChildren();
    tbody.replaceChildren();

    if (!history.length) {
      metaText.textContent = "";
      return;
    }

    const latestDate = history[history.length - 1].date;
    const latestRound = history[history.length - 1].round;
    metaText.textContent = `最終プレイ: ${latestDate} (Round ${latestRound})`;

    const latestRows = history
      .filter((h) => h.date === latestDate && h.round === latestRound)
      .sort((a, b) => b.deltaRating - a.deltaRating);

    const topGainers = latestRows.slice(0, 3);
    for (const row of topGainers) {
      const card = document.createElement("div");
      card.className = "metric-card";

      const label = document.createElement("div");
      label.className = "metric-label";
      label.textContent = row.player;

      const value = document.createElement("div");
      value.className = "metric-value";
      value.textContent = `${Math.round(row.newRating)} pt`;

      const deltaVal = Math.round(row.deltaRating);
      const delta = document.createElement("div");
      delta.className = `metric-delta ${
        deltaVal > 0 ? "delta-pos" : deltaVal < 0 ? "delta-neg" : "delta-zero"
      }`;
      delta.textContent = `${deltaVal > 0 ? "+" : ""}${deltaVal} pt`;

      card.append(label, value, delta);
      metricsEl.appendChild(card);
    }

    for (const row of latestRows) {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.scope = "row";
      th.textContent = row.player;

      const tdChips = document.createElement("td");
      tdChips.textContent = `${row.finalChips} 枚`;

      const tdDelta = document.createElement("td");
      tdDelta.textContent = formatDeltaText(row.deltaRating, true);

      tr.append(th, tdChips, tdDelta);
      tbody.appendChild(tr);
    }
  }

  function buildPlayerSeries(players, history, gameOrder) {
    const seriesMap = new Map();
    const gameLookup = new Map();

    for (const h of history) {
      if (!gameLookup.has(h.player)) {
        gameLookup.set(h.player, new Map());
      }
      gameLookup.get(h.player).set(h.gameLabel, h.newRating);
    }

    for (const player of players) {
      const pMap = gameLookup.get(player) || new Map();
      let currentVal = INITIAL_RATING;
      const points = [];
      for (const game of gameOrder) {
        if (game !== "開始" && pMap.has(game)) {
          currentVal = pMap.get(game);
        }
        points.push({ game, rating: currentVal });
      }
      seriesMap.set(player, points);
    }
    return seriesMap;
  }

  function renderChart(selectedPlayers, colorByPlayer, history, gameOrder) {
    const emptyMsg = document.getElementById("chart-empty-msg");
    const svgWrap = document.getElementById("chart-svg-wrap");
    svgWrap.replaceChildren();

    if (!selectedPlayers.length) {
      emptyMsg.classList.remove("is-hidden");
      svgWrap.classList.add("is-hidden");
      return;
    }

    emptyMsg.classList.add("is-hidden");
    svgWrap.classList.remove("is-hidden");

    const seriesMap = buildPlayerSeries(selectedPlayers, history, gameOrder);
    const allValues = [];
    for (const pts of seriesMap.values()) {
      for (const pt of pts) allValues.push(pt.rating);
    }

    let minY = Math.min(...allValues);
    let maxY = Math.max(...allValues);
    if (minY === maxY) {
      minY -= 50;
      maxY += 50;
    } else {
      const pad = Math.max(20, (maxY - minY) * 0.12);
      minY = Math.floor((minY - pad) / 10) * 10;
      maxY = Math.ceil((maxY + pad) / 10) * 10;
    }

    const width = 680;
    const height = 340;
    const margin = { top: 20, right: 20, bottom: 72, left: 52 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;

    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("class", "chart-svg");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "選択したプレイヤーのレート推移折れ線グラフ");

    const xForIndex = (idx) => {
      if (gameOrder.length <= 1) return margin.left + plotW / 2;
      return margin.left + (idx / (gameOrder.length - 1)) * plotW;
    };
    const yForValue = (val) =>
      margin.top + plotH - ((val - minY) / (maxY - minY)) * plotH;

    // 横グリッド線 & Y軸ラベル
    const ticks = 5;
    for (let i = 0; i <= ticks; i += 1) {
      const val = minY + ((maxY - minY) * i) / ticks;
      const y = yForValue(val);

      const line = document.createElementNS(svgNS, "line");
      line.setAttribute("x1", String(margin.left));
      line.setAttribute("x2", String(width - margin.right));
      line.setAttribute("y1", String(y));
      line.setAttribute("y2", String(y));
      line.setAttribute("stroke", "rgba(255, 255, 255, 0.08)");
      svg.appendChild(line);

      const label = document.createElementNS(svgNS, "text");
      label.setAttribute("x", String(margin.left - 8));
      label.setAttribute("y", String(y + 4));
      label.setAttribute("text-anchor", "end");
      label.setAttribute("fill", "#C2BCB0");
      label.setAttribute("font-size", "11");
      label.textContent = String(Math.round(val));
      svg.appendChild(label);
    }

    // X軸ラベル（間引き表示）
    const step = Math.max(1, Math.ceil(gameOrder.length / 8));
    for (let i = 0; i < gameOrder.length; i += 1) {
      if (i % step !== 0 && i !== gameOrder.length - 1) continue;
      const x = xForIndex(i);
      const y = height - margin.bottom + 14;
      const label = document.createElementNS(svgNS, "text");
      label.setAttribute("x", String(x));
      label.setAttribute("y", String(y));
      label.setAttribute("text-anchor", "end");
      label.setAttribute("transform", `rotate(-35 ${x} ${y})`);
      label.setAttribute("fill", "#C2BCB0");
      label.setAttribute("font-size", "10");
      label.textContent = gameOrder[i];
      svg.appendChild(label);
    }

    const tooltip = document.createElement("div");
    tooltip.className = "chart-tooltip is-hidden";

    // 折れ線とポイント描画
    for (const player of selectedPlayers) {
      const pts = seriesMap.get(player);
      const color = colorByPlayer.get(player) || "#D4AF37";

      const pathData = pts
        .map((pt, idx) => `${idx === 0 ? "M" : "L"}${xForIndex(idx).toFixed(1)},${yForValue(pt.rating).toFixed(1)}`)
        .join(" ");

      const path = document.createElementNS(svgNS, "path");
      path.setAttribute("d", pathData);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", color);
      path.setAttribute("stroke-width", "2.5");
      path.setAttribute("stroke-linejoin", "round");
      path.setAttribute("stroke-linecap", "round");
      svg.appendChild(path);

      pts.forEach((pt, idx) => {
        const cx = xForIndex(idx);
        const cy = yForValue(pt.rating);
        const circle = document.createElementNS(svgNS, "circle");
        circle.setAttribute("cx", cx.toFixed(1));
        circle.setAttribute("cy", cy.toFixed(1));
        circle.setAttribute("r", "4");
        circle.setAttribute("fill", color);
        circle.setAttribute("stroke", "#0B1310");
        circle.setAttribute("stroke-width", "1.5");

        const showTip = () => {
          tooltip.textContent = `${player} | ${pt.game}: ${Math.round(pt.rating)} pt`;
          tooltip.classList.remove("is-hidden");
          const leftPct = Math.min(72, Math.max(4, (cx / width) * 100));
          const topPct = Math.max(4, (cy / height) * 100 - 14);
          tooltip.style.left = `${leftPct}%`;
          tooltip.style.top = `${topPct}%`;
        };
        circle.addEventListener("mouseenter", showTip);
        circle.addEventListener("click", showTip);
        circle.addEventListener("mouseleave", () => tooltip.classList.add("is-hidden"));

        svg.appendChild(circle);
      });
    }

    svgWrap.append(svg, tooltip);
  }

  function setupChartControls(summary, history, gameOrder) {
    const selectorEl = document.getElementById("player-selector");
    const top3Btn = document.getElementById("select-top3-btn");
    const clearBtn = document.getElementById("clear-players-btn");
    selectorEl.replaceChildren();

    const selectedSet = new Set();
    const colorByPlayer = new Map();
    const orderedPlayers = summary.map((s) => s.player);

    orderedPlayers.forEach((player, idx) => {
      const color = PALETTE[idx % PALETTE.length];
      colorByPlayer.set(player, color);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "player-chip";
      btn.setAttribute("aria-pressed", "false");

      const dot = document.createElement("span");
      dot.className = "player-chip-dot";
      dot.style.backgroundColor = color;

      const nameSpan = document.createElement("span");
      nameSpan.textContent = player;

      btn.append(dot, nameSpan);
      btn.addEventListener("click", () => {
        if (selectedSet.has(player)) {
          selectedSet.delete(player);
          btn.setAttribute("aria-pressed", "false");
        } else {
          selectedSet.add(player);
          btn.setAttribute("aria-pressed", "true");
        }
        const active = orderedPlayers.filter((p) => selectedSet.has(p));
        renderChart(active, colorByPlayer, history, gameOrder);
      });

      selectorEl.appendChild(btn);
    });

    const syncButtons = () => {
      const buttons = selectorEl.querySelectorAll(".player-chip");
      buttons.forEach((btn, idx) => {
        const player = orderedPlayers[idx];
        btn.setAttribute("aria-pressed", selectedSet.has(player) ? "true" : "false");
      });
      const active = orderedPlayers.filter((p) => selectedSet.has(p));
      renderChart(active, colorByPlayer, history, gameOrder);
    };

    top3Btn.addEventListener("click", () => {
      selectedSet.clear();
      orderedPlayers.slice(0, 3).forEach((p) => selectedSet.add(p));
      syncButtons();
    });

    clearBtn.addEventListener("click", () => {
      selectedSet.clear();
      syncButtons();
    });

    renderChart([], colorByPlayer, history, gameOrder);
  }

  async function init() {
    try {
      const resp = await fetch(DATA_URL, { cache: "no-cache" });
      if (!resp.ok) {
        throw new Error(`データの読み込みに失敗しました (HTTP ${resp.status})`);
      }
      const csvText = await resp.text();
      const rows = parseCsv(csvText);
      const { history, summary, gameOrder } = calcRatings(rows);

      renderHeroMeta(summary, history);
      renderRankingTable(summary);
      renderLatestGame(history);
      setupChartControls(summary, history, gameOrder);
    } catch (err) {
      const banner = document.getElementById("error-banner");
      banner.textContent = err instanceof Error ? err.message : "読み込みエラーが発生しました。";
      banner.classList.remove("is-hidden");
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
