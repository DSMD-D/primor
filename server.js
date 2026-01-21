import express from "express";
import { WebSocketServer } from "ws";
import { createServer } from "http";

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server });

const PORT = process.env.PORT || 3000;

app.use(express.static("public"));

const worldState = {
  tick: 0,
  bacteria: new Map(),
  globalTraits: {
    acidity: 0,
    temperature: 20,
    nutrients: 50
  }
};

const evolutionTree = {
  membranes: {
    id: "membranes",
    name: "Усиленные мембраны",
    description: "Снижают урон от кислотности.",
    effects: { defense: 2, speed: -1 }
  },
  spores: {
    id: "spores",
    name: "Спорообразование",
    description: "Повышает выживаемость, но снижает рост.",
    effects: { survival: 3, growth: -1 }
  },
  flagella: {
    id: "flagella",
    name: "Жгутики",
    description: "Ускоряют перемещение и сбор пищи.",
    effects: { speed: 3, growth: 1 }
  },
  biofilm: {
    id: "biofilm",
    name: "Биопленка",
    description: "Повышает защиту колонии.",
    effects: { defense: 3, growth: -1 }
  },
  chemotaxis: {
    id: "chemotaxis",
    name: "Хемотаксис",
    description: "Лучшая ориентация на питательные зоны.",
    effects: { growth: 2 }
  },
  predation: {
    id: "predation",
    name: "Хищничество",
    description: "Позволяет поглощать другие клетки.",
    effects: { attack: 3, growth: 1 }
  }
};

const broadcast = (data) => {
  const payload = JSON.stringify(data);
  for (const client of wss.clients) {
    if (client.readyState === client.OPEN) {
      client.send(payload);
    }
  }
};

const createBacteria = (id) => ({
  id,
  name: `Бактерия ${id.slice(0, 4)}`,
  traits: {
    growth: 5,
    defense: 1,
    speed: 1,
    survival: 1,
    attack: 0
  },
  evolution: [],
  energy: 50,
  population: 1
});

const applyEvolution = (bacteria, evolutionId) => {
  const evolution = evolutionTree[evolutionId];
  if (!evolution || bacteria.evolution.includes(evolutionId)) return;
  bacteria.evolution.push(evolutionId);
  Object.entries(evolution.effects).forEach(([key, value]) => {
    bacteria.traits[key] = (bacteria.traits[key] || 0) + value;
  });
};

const updateWorld = () => {
  worldState.tick += 1;
  worldState.globalTraits.nutrients = Math.max(
    10,
    60 + Math.sin(worldState.tick / 10) * 15
  );

  worldState.globalTraits.acidity = Math.max(
    0,
    10 + Math.cos(worldState.tick / 12) * 4
  );

  for (const bacteria of worldState.bacteria.values()) {
    const growthBoost = bacteria.traits.growth + bacteria.traits.speed;
    const survivalPenalty = Math.max(0, worldState.globalTraits.acidity - bacteria.traits.defense);
    const nutrientBonus = worldState.globalTraits.nutrients / 10;

    const delta = growthBoost + nutrientBonus - survivalPenalty;
    bacteria.energy = Math.max(0, bacteria.energy + delta);

    if (bacteria.energy > 100) {
      bacteria.population += 1;
      bacteria.energy -= 30;
    }
    if (bacteria.energy < 5) {
      bacteria.population = Math.max(1, bacteria.population - 1);
      bacteria.energy += 10;
    }
  }

  broadcast({ type: "world:update", payload: serializeWorld() });
};

const serializeWorld = () => ({
  tick: worldState.tick,
  globalTraits: worldState.globalTraits,
  bacteria: Array.from(worldState.bacteria.values())
});

wss.on("connection", (socket) => {
  const id = Math.random().toString(36).slice(2, 10);
  const bacteria = createBacteria(id);
  worldState.bacteria.set(id, bacteria);

  socket.send(
    JSON.stringify({
      type: "session:init",
      payload: {
        id,
        evolutionTree,
        world: serializeWorld()
      }
    })
  );

  socket.on("message", (raw) => {
    try {
      const message = JSON.parse(raw.toString());
      if (message.type === "evolution:select") {
        const target = worldState.bacteria.get(id);
        if (target) {
          applyEvolution(target, message.payload.id);
          broadcast({ type: "world:update", payload: serializeWorld() });
        }
      }
    } catch (error) {
      console.error("Invalid message", error);
    }
  });

  socket.on("close", () => {
    worldState.bacteria.delete(id);
    broadcast({ type: "world:update", payload: serializeWorld() });
  });
});

setInterval(updateWorld, 1500);

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
