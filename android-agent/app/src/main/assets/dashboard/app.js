const state = {
  servers: [],
  events: [],
  timer: null,
  connected: false,
};

const els = {
  stripMode: document.getElementById("strip-mode"),
  stripDevice: document.getElementById("strip-device"),
  stripHost: document.getElementById("strip-host"),
  stripListening: document.getElementById("strip-listening"),
  stripLastEvent: document.getElementById("strip-last-event"),
  linkState: document.getElementById("link-state"),
  gameToggle: document.getElementById("game-toggle"),
  gameModal: document.getElementById("game-modal"),
  gameClose: document.getElementById("game-close"),
  gameCanvas: document.getElementById("game-canvas"),
  gameScore: document.getElementById("game-score"),
  gameBest: document.getElementById("game-best"),
  gameState: document.getElementById("game-state"),
  globalState: document.getElementById("global-state"),
  lastUpdated: document.getElementById("last-updated"),
  heroTitle: document.getElementById("hero-title"),
  serverCount: document.getElementById("server-count"),
  criticalCount: document.getElementById("critical-count"),
  avgCpu: document.getElementById("avg-cpu"),
  avgRam: document.getElementById("avg-ram"),
  avgLoad: document.getElementById("avg-load"),
  recentCalls: document.getElementById("recent-calls"),
  activeCalls: document.getElementById("active-calls"),
  eventsHour: document.getElementById("events-hour"),
  primaryName: document.getElementById("primary-name"),
  primaryMeta: document.getElementById("primary-meta"),
  primaryState: document.getElementById("primary-state"),
  primaryHost: document.getElementById("primary-host"),
  primaryCpuBar: document.getElementById("primary-cpu-bar"),
  primaryRamBar: document.getElementById("primary-ram-bar"),
  primaryDiskBar: document.getElementById("primary-disk-bar"),
  bootAge: document.getElementById("boot-age"),
  maxDisk: document.getElementById("max-disk"),
  serverList: document.getElementById("server-list"),
  eventStream: document.getElementById("event-stream"),
  bg: document.getElementById("bg"),
};

const bgCtx = els.bg.getContext("2d");
const gameCtx = els.gameCanvas.getContext("2d");
const game = {
  open: false,
  running: false,
  started: false,
  score: 0,
  best: Number(localStorage.getItem("santral-game-best") || "0"),
  lastStep: 0,
  stepMs: 140,
  cell: 0,
  cols: 0,
  rows: 0,
  direction: "right",
  nextDirection: "right",
  snake: [],
  food: { x: 0, y: 0 },
};

function getServerUrl() {
  try {
    if (window.SantralBridge && typeof window.SantralBridge.getServerUrl === "function") {
      return window.SantralBridge.getServerUrl();
    }
  } catch (_err) {
    return "";
  }
  return "";
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function nowTime() {
  const d = new Date();
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function serverState(server) {
  if (server.cpu >= 90 || server.ram >= 92 || server.disk >= 95) return "CRIT";
  if (server.cpu >= 70 || server.ram >= 78 || server.disk >= 85) return "WARN";
  return "OK";
}

function serverStateClass(server) {
  const state = serverState(server);
  if (state === "CRIT") return "crit";
  if (state === "WARN") return "warn";
  return "ok";
}

function generateDemoData() {
  const base = [
    { name: "api-core", cpu: 38, ram: 61, disk: 54, net: "8.2 MB/s", uptime: "12d 4h" },
    { name: "db-main", cpu: 67, ram: 74, disk: 81, net: "4.6 MB/s", uptime: "37d 1h" },
    { name: "gateway", cpu: 18, ram: 33, disk: 44, net: "1.9 MB/s", uptime: "8d 13h" },
    { name: "queue-node", cpu: 91, ram: 86, disk: 72, net: "12.4 MB/s", uptime: "3d 6h" },
  ];

  return base.map((server, index) => ({
    ...server,
    cpu: Math.max(4, Math.min(99, server.cpu + Math.floor(Math.random() * 13) - 6)),
    ram: Math.max(8, Math.min(99, server.ram + Math.floor(Math.random() * 11) - 5)),
    disk: Math.max(10, Math.min(99, server.disk + Math.floor(Math.random() * 5) - 2)),
    id: index + 1,
  }));
}

function updateSummary(servers, remoteSummary = null) {
  const critical = servers.filter((server) => serverState(server) === "CRIT").length;
  const avgCpu = servers.length
    ? Math.round(servers.reduce((sum, server) => sum + server.cpu, 0) / servers.length)
    : 0;
  const avgRam = servers.length
    ? Math.round(servers.reduce((sum, server) => sum + server.ram, 0) / servers.length)
    : 0;

  els.serverCount.textContent = String(servers.length);
  els.criticalCount.textContent = String(critical);
  els.avgCpu.textContent = `%${avgCpu}`;
  els.avgRam.textContent = `%${avgRam}`;
  els.activeCalls.textContent = String(remoteSummary?.active_calls ?? 0);
  els.eventsHour.textContent = String(remoteSummary?.events_last_hour ?? 0);
  els.avgLoad.textContent = String(remoteSummary?.avg_load ?? "0.00");
  els.recentCalls.textContent = String(remoteSummary?.recent_calls ?? 0);
  els.maxDisk.textContent = `%${remoteSummary?.max_disk ?? 0}`;
  els.lastUpdated.textContent = nowTime();
  const globalMode = critical ? "ALERT" : state.connected ? "LIVE" : "DEMO";
  els.globalState.textContent = globalMode;
  els.stripMode.textContent = globalMode;
  els.linkState.textContent = state.connected ? "ONLINE" : "DEMO";

  const primary = [...servers].sort((a, b) => b.cpu + b.ram - (a.cpu + a.ram))[0];
  if (!primary) return;
  els.primaryName.textContent = primary.name;
  els.primaryMeta.textContent = `CPU ${primary.cpu}% | RAM ${primary.ram}% | Disk ${primary.disk}% | ${primary.net}`;
  els.primaryState.textContent = serverState(primary);
  els.primaryState.className = `server-state ${serverStateClass(primary)}`;
  els.primaryHost.textContent = `HOST ${(primary.host || "--").toUpperCase()}`;
  els.primaryCpuBar.style.width = `${primary.cpu}%`;
  els.primaryRamBar.style.width = `${primary.ram}%`;
  els.primaryDiskBar.style.width = `${primary.disk}%`;
}

function updatePanel(panel = null) {
  els.heroTitle.textContent = panel?.title || "SANTRAL CORE PANEL";
  els.stripDevice.textContent = panel?.device_name || "zk-santral-agent";
  els.stripHost.textContent = panel?.host_name || "--";
  els.stripListening.textContent = panel?.listening || "--";
  els.stripLastEvent.textContent = panel?.last_event_age_text || "veri yok";
  els.bootAge.textContent = panel?.boot_age_text || "--";
}

function resizeGameCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const rect = els.gameCanvas.getBoundingClientRect();
  els.gameCanvas.width = Math.floor(rect.width * ratio);
  els.gameCanvas.height = Math.floor(rect.height * ratio);
  gameCtx.setTransform(ratio, 0, 0, ratio, 0, 0);
  game.cell = Math.max(18, Math.floor(Math.min(rect.width, rect.height) / 18));
  game.cols = Math.max(12, Math.floor(rect.width / game.cell));
  game.rows = Math.max(8, Math.floor(rect.height / game.cell));
}

function resetGame() {
  game.running = false;
  game.started = false;
  game.score = 0;
  game.lastStep = 0;
  game.stepMs = 140;
  game.direction = "right";
  game.nextDirection = "right";
  const startX = Math.floor(game.cols / 2);
  const startY = Math.floor(game.rows / 2);
  game.snake = [
    { x: startX, y: startY },
    { x: startX - 1, y: startY },
    { x: startX - 2, y: startY },
  ];
  placeFood();
  els.gameScore.textContent = "0";
  els.gameBest.textContent = String(game.best);
  els.gameState.textContent = "Hazir";
}

function placeFood() {
  let x = 0;
  let y = 0;
  do {
    x = Math.floor(Math.random() * game.cols);
    y = Math.floor(Math.random() * game.rows);
  } while (game.snake.some((part) => part.x === x && part.y === y));
  game.food = { x, y };
}

function setDirection(direction) {
  const opposite = {
    up: "down",
    down: "up",
    left: "right",
    right: "left",
  };
  if (opposite[game.direction] === direction) return;
  game.nextDirection = direction;
}

function handleGameInput(clientX, clientY) {
  if (!game.running) {
    game.running = true;
    game.started = true;
    game.lastStep = 0;
    els.gameState.textContent = "Akis";
    return;
  }
  const rect = els.gameCanvas.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const dx = clientX - cx;
  const dy = clientY - cy;
  if (Math.abs(dx) > Math.abs(dy)) {
    setDirection(dx >= 0 ? "right" : "left");
  } else {
    setDirection(dy >= 0 ? "down" : "up");
  }
}

function openGame() {
  game.open = true;
  els.gameModal.classList.remove("hidden");
  resizeGameCanvas();
  resetGame();
}

function closeGame() {
  game.open = false;
  els.gameModal.classList.add("hidden");
  resetGame();
}

function gameOver() {
  game.running = false;
  els.gameState.textContent = "Bitti";
  if (game.score > game.best) {
    game.best = game.score;
    localStorage.setItem("santral-game-best", String(game.best));
    els.gameBest.textContent = String(game.best);
  }
}

function gameFrame(ts) {
  const rect = els.gameCanvas.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;
  if (!game.open) {
    requestAnimationFrame(gameFrame);
    return;
  }
  if (!game.lastStep) game.lastStep = ts;

  gameCtx.clearRect(0, 0, width, height);
  gameCtx.fillStyle = "rgba(67,255,149,0.06)";
  for (let x = 0; x < game.cols; x += 1) {
    for (let y = 0; y < game.rows; y += 1) {
      gameCtx.strokeStyle = "rgba(67,255,149,0.08)";
      gameCtx.strokeRect(x * game.cell, y * game.cell, game.cell, game.cell);
    }
  }

  if (game.running && ts - game.lastStep >= game.stepMs) {
    game.lastStep = ts;
    game.direction = game.nextDirection;
    const head = { ...game.snake[0] };
    if (game.direction === "up") head.y -= 1;
    if (game.direction === "down") head.y += 1;
    if (game.direction === "left") head.x -= 1;
    if (game.direction === "right") head.x += 1;

    const hitWall =
      head.x < 0 || head.y < 0 || head.x >= game.cols || head.y >= game.rows;
    const hitBody = game.snake.some((part) => part.x === head.x && part.y === head.y);
    if (hitWall || hitBody) {
      gameOver();
    } else {
      game.snake.unshift(head);
      const ateFood = head.x === game.food.x && head.y === game.food.y;
      if (ateFood) {
        game.score += 1;
        game.stepMs = Math.max(70, game.stepMs - 2);
        els.gameScore.textContent = String(game.score);
        placeFood();
      } else {
        game.snake.pop();
      }
    }
  }

  gameCtx.fillStyle = "#ff6464";
  gameCtx.fillRect(
    game.food.x * game.cell + 3,
    game.food.y * game.cell + 3,
    game.cell - 6,
    game.cell - 6,
  );

  game.snake.forEach((part, index) => {
    gameCtx.fillStyle = index === 0 ? "#9dffbe" : "#43ff95";
    gameCtx.fillRect(
      part.x * game.cell + 2,
      part.y * game.cell + 2,
      game.cell - 4,
      game.cell - 4,
    );
  });

  if (!game.started) {
    gameCtx.fillStyle = "rgba(236,255,238,0.92)";
    gameCtx.font = "700 28px sans-serif";
    gameCtx.fillText("Dokun ve baslat", 42, 58);
  } else if (!game.running) {
    gameCtx.fillStyle = "rgba(236,255,238,0.92)";
    gameCtx.font = "700 28px sans-serif";
    gameCtx.fillText("Oyun bitti - tekrar dokun", 42, 58);
  }

  requestAnimationFrame(gameFrame);
}

function renderServers(servers) {
  els.serverList.innerHTML = "";
  servers.forEach((server) => {
    const card = document.createElement("article");
    card.className = "server-card";
    card.innerHTML = `
      <div class="server-top">
        <div class="server-name">${server.name}</div>
        <div class="server-state ${serverStateClass(server)}">${serverState(server)}</div>
      </div>
      <div class="server-meta">
        HOST ${(server.host || "--").toUpperCase()} | LOAD ${server.load ?? 0} | UPTIME ${server.uptime}
      </div>
      <div class="mini-bars">
        ${miniBar("CPU", server.cpu)}
        ${miniBar("RAM", server.ram)}
        ${miniBar("DSK", server.disk)}
      </div>
    `;
    els.serverList.appendChild(card);
  });
}

function miniBar(label, value) {
  return `
    <div class="mini-row">
      <span>${label}</span>
      <div class="mini-track"><div class="mini-fill" style="width:${value}%"></div></div>
      <strong>${value}%</strong>
    </div>
  `;
}

function buildEvents(servers) {
  const events = [];
  servers.forEach((server) => {
    const state = serverState(server);
    if (state === "CRIT") {
      events.push({
        title: `${server.name} kritik esikte`,
        text: `CPU ${server.cpu}% / RAM ${server.ram}% / Disk ${server.disk}%`,
      });
    } else if (state === "WARN") {
      events.push({
        title: `${server.name} dikkat gerektiriyor`,
        text: `Kaynak kullanimi yukseliyor. CPU ${server.cpu}%`,
      });
    } else {
      events.push({
        title: `${server.name} stabil`,
        text: `Servis cevap veriyor. Uptime ${server.uptime}`,
      });
    }
  });
  return events.slice(0, 6);
}

function renderEvents(events) {
  els.eventStream.innerHTML = "";
  events.forEach((event) => {
    const card = document.createElement("article");
    card.className = "event-card";
    card.innerHTML = `<strong>${event.title}</strong><span>${event.text}</span>`;
    els.eventStream.appendChild(card);
  });
}

async function pullRemote() {
  const serverUrl = getServerUrl();
  if (!serverUrl || serverUrl.includes("__SERVER_URL__")) {
    return null;
  }
  try {
    const response = await fetch(`${serverUrl}/api/status`);
    if (!response.ok) return null;
    const payload = await response.json();
    if (!Array.isArray(payload.servers)) return null;
    return payload;
  } catch (_err) {
    return null;
  }
}

async function refresh() {
  const remote = await pullRemote();
  state.connected = Boolean(remote);
  state.servers = remote && remote.servers && remote.servers.length ? remote.servers : generateDemoData();
  state.events = remote && Array.isArray(remote.events) && remote.events.length
    ? remote.events
    : buildEvents(state.servers);
  updatePanel(remote?.panel || null);
  updateSummary(state.servers, remote?.summary || null);
  renderServers(state.servers);
  renderEvents(state.events);
}

function sizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const rect = els.bg.getBoundingClientRect();
  els.bg.width = Math.floor(rect.width * ratio);
  els.bg.height = Math.floor(rect.height * ratio);
  bgCtx.setTransform(ratio, 0, 0, ratio, 0, 0);
}

function animateBg() {
  sizeCanvas();
  const width = els.bg.width / (window.devicePixelRatio || 1);
  const height = els.bg.height / (window.devicePixelRatio || 1);
  const fontSize = 18;
  const cols = Math.floor(width / fontSize);
  const drops = Array.from({ length: cols }, () => Math.random() * height);
  const chars = "01ABCDEF#$%@";

  function frame() {
    bgCtx.fillStyle = "rgba(2, 8, 5, 0.12)";
    bgCtx.fillRect(0, 0, width, height);
    bgCtx.fillStyle = "rgba(67,255,149,0.65)";
    bgCtx.font = `${fontSize}px monospace`;
    drops.forEach((drop, index) => {
      bgCtx.fillText(chars[Math.floor(Math.random() * chars.length)], index * fontSize, drop);
      drops[index] = drop > height && Math.random() > 0.985 ? 0 : drop + fontSize * (0.75 + Math.random() * 0.7);
    });
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

function init() {
  animateBg();
  resizeGameCanvas();
  els.gameBest.textContent = String(game.best);
  els.gameToggle.addEventListener("click", openGame);
  els.gameClose.addEventListener("click", closeGame);
  els.gameCanvas.addEventListener("click", (event) => {
    handleGameInput(event.clientX, event.clientY);
  });
  window.addEventListener("keydown", (event) => {
    if (!game.open) return;
    if (event.key === "ArrowUp") setDirection("up");
    if (event.key === "ArrowDown") setDirection("down");
    if (event.key === "ArrowLeft") setDirection("left");
    if (event.key === "ArrowRight") setDirection("right");
    if (event.key === "Enter" || event.key === " ") {
      handleGameInput(window.innerWidth / 2, window.innerHeight / 2);
    }
  });
  window.addEventListener("resize", resizeGameCanvas);
  requestAnimationFrame(gameFrame);
  refresh();
  state.timer = setInterval(refresh, 5000);
  window.addEventListener("resize", sizeCanvas);
}

init();
