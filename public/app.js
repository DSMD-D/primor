const connectionStatus = document.getElementById("connectionStatus");
const bacteriaCard = document.getElementById("bacteriaCard");
const statsGrid = document.getElementById("statsGrid");
const evolutionGrid = document.getElementById("evolutionGrid");
const worldGrid = document.getElementById("worldGrid");
const worldInfo = document.getElementById("worldInfo");
const worldCanvas = document.getElementById("worldCanvas");
const ctx = worldCanvas.getContext("2d");

let sessionId = null;
let evolutionTree = {};
let world = null;

const formatTrait = (label, value) => `
  <div class="stat">
    <span>${label}</span>
    <strong>${value}</strong>
  </div>
`;

const updateConnectionStatus = (text, isOk) => {
  connectionStatus.textContent = text;
  connectionStatus.style.background = isOk ? "#1f3d2b" : "#42222b";
  connectionStatus.style.color = isOk ? "#b8f4d6" : "#f5b8c2";
};

const renderBacteria = () => {
  if (!world || !sessionId) return;
  const bacteria = world.bacteria.find((item) => item.id === sessionId);
  if (!bacteria) return;

  bacteriaCard.innerHTML = `
    <div><strong>${bacteria.name}</strong></div>
    <div>Популяция: ${bacteria.population}</div>
    <div>Энергия: ${bacteria.energy.toFixed(1)}</div>
    <div>Эволюции: ${bacteria.evolution.length}</div>
  `;

  statsGrid.innerHTML = Object.entries(bacteria.traits)
    .map(([key, value]) => formatTrait(key, value))
    .join("");
};

const renderEvolution = () => {
  if (!sessionId) return;
  const bacteria = world?.bacteria.find((item) => item.id === sessionId);

  evolutionGrid.innerHTML = Object.values(evolutionTree)
    .map((path) => {
      const selected = bacteria?.evolution.includes(path.id);
      return `
        <div class="evolution-card ${selected ? "selected" : ""}">
          <strong>${path.name}</strong>
          <p>${path.description}</p>
          <div>Эффекты: ${Object.entries(path.effects)
            .map(([key, value]) => `${key} ${value > 0 ? "+" : ""}${value}`)
            .join(", ")}</div>
          <button data-evolution="${path.id}">
            ${selected ? "Выбрано" : "Развить"}
          </button>
        </div>
      `;
    })
    .join("");

  evolutionGrid.querySelectorAll("button[data-evolution]").forEach((button) => {
    button.addEventListener("click", () => {
      const evolutionId = button.dataset.evolution;
      if (!evolutionId) return;
      socket.send(
        JSON.stringify({ type: "evolution:select", payload: { id: evolutionId } })
      );
    });
  });
};

const renderWorld = () => {
  if (!world) return;
  worldGrid.innerHTML = `
    <div class="world-card">Тик: ${world.tick}</div>
    <div class="world-card">Нитраты: ${world.globalTraits.nutrients.toFixed(1)}</div>
    <div class="world-card">Кислотность: ${world.globalTraits.acidity.toFixed(1)}</div>
    <div class="world-card">Температура: ${world.globalTraits.temperature}°C</div>
  `;

  worldInfo.textContent = `В мире ${world.bacteria.length} видов. Наблюдайте за ростом популяций.`;

  ctx.clearRect(0, 0, worldCanvas.width, worldCanvas.height);
  world.bacteria.forEach((bacteria, index) => {
    const radius = 10 + bacteria.population * 2;
    const x = 60 + (index % 5) * 90;
    const y = 60 + Math.floor(index / 5) * 70;
    ctx.beginPath();
    ctx.fillStyle = bacteria.id === sessionId ? "#58d6ff" : "#7a8fb0";
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
  });
};

const handleWorldUpdate = (payload) => {
  world = payload;
  renderBacteria();
  renderEvolution();
  renderWorld();
};

let socket = null;
const connect = () => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${window.location.host}`);

  socket.addEventListener("open", () => {
    updateConnectionStatus("Онлайн", true);
  });

  socket.addEventListener("close", () => {
    updateConnectionStatus("Оффлайн — переподключение...", false);
    setTimeout(connect, 2000);
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "session:init") {
      sessionId = message.payload.id;
      evolutionTree = message.payload.evolutionTree;
      handleWorldUpdate(message.payload.world);
    }
    if (message.type === "world:update") {
      handleWorldUpdate(message.payload);
    }
  });
};

connect();
