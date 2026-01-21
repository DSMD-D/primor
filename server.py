import asyncio
import contextlib
import json
import math
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from aiohttp import web, WSMsgType

BASE_DIR = Path(__file__).parent


@dataclass
class Bacteria:
    identifier: str
    name: str
    traits: dict
    evolution: list = field(default_factory=list)
    energy: float = 50.0
    population: int = 1


class World:
    def __init__(self) -> None:
        self.tick = 0
        self.bacteria: dict[str, Bacteria] = {}
        self.global_traits = {
            "acidity": 0.0,
            "temperature": 20,
            "nutrients": 50.0,
        }

    def serialize(self) -> dict:
        return {
            "tick": self.tick,
            "globalTraits": self.global_traits,
            "bacteria": [
                {
                    "id": bacteria.identifier,
                    "name": bacteria.name,
                    "traits": bacteria.traits,
                    "evolution": bacteria.evolution,
                    "energy": bacteria.energy,
                    "population": bacteria.population,
                }
                for bacteria in self.bacteria.values()
            ],
        }


EVOLUTION_TREE = {
    "membranes": {
        "id": "membranes",
        "name": "Усиленные мембраны",
        "description": "Снижают урон от кислотности.",
        "effects": {"defense": 2, "speed": -1},
    },
    "spores": {
        "id": "spores",
        "name": "Спорообразование",
        "description": "Повышает выживаемость, но снижает рост.",
        "effects": {"survival": 3, "growth": -1},
    },
    "flagella": {
        "id": "flagella",
        "name": "Жгутики",
        "description": "Ускоряют перемещение и сбор пищи.",
        "effects": {"speed": 3, "growth": 1},
    },
    "biofilm": {
        "id": "biofilm",
        "name": "Биопленка",
        "description": "Повышает защиту колонии.",
        "effects": {"defense": 3, "growth": -1},
    },
    "chemotaxis": {
        "id": "chemotaxis",
        "name": "Хемотаксис",
        "description": "Лучшая ориентация на питательные зоны.",
        "effects": {"growth": 2},
    },
    "predation": {
        "id": "predation",
        "name": "Хищничество",
        "description": "Позволяет поглощать другие клетки.",
        "effects": {"attack": 3, "growth": 1},
    },
}

world = World()
clients: set[web.WebSocketResponse] = set()


def create_bacteria(identifier: str) -> Bacteria:
    return Bacteria(
        identifier=identifier,
        name=f"Бактерия {identifier[:4]}",
        traits={
            "growth": 5,
            "defense": 1,
            "speed": 1,
            "survival": 1,
            "attack": 0,
        },
    )


def apply_evolution(bacteria: Bacteria, evolution_id: str) -> None:
    evolution = EVOLUTION_TREE.get(evolution_id)
    if not evolution or evolution_id in bacteria.evolution:
        return
    bacteria.evolution.append(evolution_id)
    for key, value in evolution["effects"].items():
        bacteria.traits[key] = bacteria.traits.get(key, 0) + value


async def broadcast(message: dict) -> None:
    if not clients:
        return
    payload = json.dumps(message)
    closed = []
    for client in clients:
        if client.closed:
            closed.append(client)
            continue
        await client.send_str(payload)
    for client in closed:
        clients.discard(client)


def update_world() -> None:
    world.tick += 1
    world.global_traits["nutrients"] = max(
        10.0, 60 + math.sin(world.tick / 10) * 15
    )
    world.global_traits["acidity"] = max(
        0.0, 10 + math.cos(world.tick / 12) * 4
    )

    for bacteria in world.bacteria.values():
        growth_boost = bacteria.traits["growth"] + bacteria.traits["speed"]
        survival_penalty = max(
            0.0, world.global_traits["acidity"] - bacteria.traits["defense"]
        )
        nutrient_bonus = world.global_traits["nutrients"] / 10

        delta = growth_boost + nutrient_bonus - survival_penalty
        bacteria.energy = max(0.0, bacteria.energy + delta)

        if bacteria.energy > 100:
            bacteria.population += 1
            bacteria.energy -= 30
        if bacteria.energy < 5:
            bacteria.population = max(1, bacteria.population - 1)
            bacteria.energy += 10


async def world_loop(app: web.Application) -> None:
    try:
        while True:
            update_world()
            await broadcast({"type": "world:update", "payload": world.serialize()})
            await asyncio.sleep(1.5)
    except asyncio.CancelledError:
        return


async def index(request: web.Request) -> web.Response:
    return web.FileResponse(BASE_DIR / "public" / "index.html")


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    socket = web.WebSocketResponse()
    await socket.prepare(request)

    identifier = secrets.token_hex(4)
    bacteria = create_bacteria(identifier)
    world.bacteria[identifier] = bacteria
    clients.add(socket)

    await socket.send_json(
        {
            "type": "session:init",
            "payload": {
                "id": identifier,
                "evolutionTree": EVOLUTION_TREE,
                "world": world.serialize(),
            },
        }
    )

    async for message in socket:
        if message.type == WSMsgType.TEXT:
            try:
                payload = json.loads(message.data)
            except json.JSONDecodeError:
                continue
            if payload.get("type") == "evolution:select":
                evolution_id = payload.get("payload", {}).get("id")
                if evolution_id:
                    apply_evolution(world.bacteria[identifier], evolution_id)
                    await broadcast(
                        {"type": "world:update", "payload": world.serialize()}
                    )
        elif message.type == WSMsgType.ERROR:
            break

    clients.discard(socket)
    world.bacteria.pop(identifier, None)
    await broadcast({"type": "world:update", "payload": world.serialize()})
    return socket


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_static("/", BASE_DIR / "public", show_index=False)

    async def on_startup(app: web.Application) -> None:
        app["world_task"] = asyncio.create_task(world_loop(app))

    async def on_cleanup(app: web.Application) -> None:
        app["world_task"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app["world_task"]

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), port=3000)
