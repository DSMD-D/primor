const state = {
  playerId: null,
  mutations: [],
};

const elements = {
  playersCount: document.getElementById("players-count"),
  globalBiomass: document.getElementById("global-biomass"),
  playerId: document.getElementById("player-id"),
  playerBiomass: document.getElementById("player-biomass"),
  playerMutations: document.getElementById("player-mutations"),
  mutationTimeline: document.getElementById("mutation-timeline"),
  globalMutations: document.getElementById("global-mutations"),
  evolutionTree: document.getElementById("evolution-tree"),
};

const socket = io({
  transports: ["websocket"],
});

socket.on("session", (payload) => {
  state.playerId = payload.player;
  elements.playerId.textContent = payload.player;
});

socket.on("state", (payload) => {
  if (payload.player && payload.player.id === state.playerId) {
    state.mutations = payload.player.mutations;
    renderPlayer(payload.player);
  }
  renderWorld(payload.world);
  renderEvolution();
});

function renderPlayer(player) {
  elements.playerBiomass.textContent = player.biomass;
  elements.playerMutations.textContent = player.mutations.length;

  if (!player.mutations.length) {
    elements.mutationTimeline.innerHTML =
      '<p class="muted">Пока нет мутаций. Выберите путь эволюции ниже.</p>';
    return;
  }

  elements.mutationTimeline.innerHTML = player.mutations
    .map(
      (mutation, index) =>
        `<div class="mutation-item">${index + 1}. ${mutation}</div>`
    )
    .join("");
}

function renderWorld(world) {
  elements.playersCount.textContent = world.players;
  elements.globalBiomass.textContent = world.global_biomass;

  const entries = Object.entries(world.global_mutations || {});
  if (!entries.length) {
    elements.globalMutations.innerHTML =
      '<p class="muted">Ожидаем первые данные от игроков.</p>';
    return;
  }

  elements.globalMutations.innerHTML = entries
    .sort((a, b) => b[1] - a[1])
    .map(
      ([mutation, count]) =>
        `<div class="global-item"><span>${mutation}</span><strong>${count}</strong></div>`
    )
    .join("");
}

function renderEvolution() {
  elements.evolutionTree.innerHTML = "";
  Object.entries(window.EVOLUTION_TREE).forEach(([key, node]) => {
    const card = document.createElement("div");
    card.className = "evolution-card";

    const title = document.createElement("h3");
    title.textContent = node.label;
    card.append(title);

    const description = document.createElement("p");
    description.textContent = node.description;
    card.append(description);

    const list = document.createElement("div");
    list.className = "evolution-branch";

    Object.entries(node.children || {}).forEach(([childKey, child]) => {
      list.appendChild(renderMutationButton(childKey, child, 1));
    });

    card.append(list);
    elements.evolutionTree.append(card);
  });
}

function renderMutationButton(key, node, depth) {
  const container = document.createElement("div");
  container.style.display = "grid";
  container.style.gap = "8px";
  container.style.marginLeft = `${depth * 8}px`;

  const button = document.createElement("button");
  button.className = "mutation-button";
  button.textContent = node.label;
  button.disabled = state.mutations.includes(node.label);
  button.addEventListener("click", () => {
    socket.emit("mutate", { player: state.playerId, mutation: node.label });
  });

  const caption = document.createElement("span");
  caption.className = "muted";
  caption.textContent = node.description;

  container.append(button, caption);

  if (node.children) {
    Object.entries(node.children).forEach(([childKey, child]) => {
      container.appendChild(renderMutationButton(childKey, child, depth + 1));
    });
  }

  return container;
}

renderEvolution();
