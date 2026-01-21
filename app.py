from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import random
import threading
import time
from uuid import uuid4

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit


@dataclass
class PlayerState:
    player_id: str
    mutations: list[str] = field(default_factory=list)
    biomass: int = 1
    hp: int = 10
    x: int = 0
    y: int = 0
    is_bot: bool = False
    display_name: str = "Вы"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


app = Flask(__name__)
app.config["SECRET_KEY"] = "primor-dev"

socketio = SocketIO(app, cors_allowed_origins="*")

MAP_WIDTH = 12
MAP_HEIGHT = 8
BOT_COUNT = 4
BOT_NAMES = [
    "Сапрофит",
    "Микроклон",
    "Биофаг",
    "Ферментор",
    "Нейтрализатор",
]

GLOBAL_STATE = {
    "players": 0,
    "global_mutations": {},
    "global_biomass": 0,
    "map": {"width": MAP_WIDTH, "height": MAP_HEIGHT},
}

PLAYERS: dict[str, PlayerState] = {}
LOCK = threading.Lock()
BOT_TASK_STARTED = False

EVOLUTION_TREE = {
    "metabolism": {
        "label": "Метаболизм",
        "description": "Ускоряет сбор энергии и переработку среды.",
        "children": {
            "solar": {
                "label": "Солнечные мембраны",
                "description": "Получение энергии от света.",
                "children": {
                    "prism": {
                        "label": "Призматические рецепторы",
                        "description": "Эффективнее в тумане.",
                    },
                    "radiant": {
                        "label": "Радиантная защита",
                        "description": "Стабильность в радиации.",
                    },
                },
            },
            "chemo": {
                "label": "Хемо-биореакторы",
                "description": "Поглощает минеральные соединения.",
                "children": {
                    "acid": {
                        "label": "Кислотный распад",
                        "description": "Растворяет ресурсы быстрее.",
                    },
                    "ferment": {
                        "label": "Брожение",
                        "description": "Надежность без кислорода.",
                    },
                },
            },
        },
    },
    "mobility": {
        "label": "Передвижение",
        "description": "Расширяет зоны обитания.",
        "children": {
            "flagella": {
                "label": "Жгутики",
                "description": "Ускоряет миграцию.",
                "children": {
                    "swarm": {
                        "label": "Стайная тяга",
                        "description": "Согласованное движение.",
                    },
                    "burst": {
                        "label": "Импульсный рывок",
                        "description": "Краткие ускорения.",
                    },
                },
            },
            "float": {
                "label": "Пузырьки газа",
                "description": "Парит в плотной среде.",
                "children": {
                    "thermal": {
                        "label": "Термальные лифты",
                        "description": "Использует температурные потоки.",
                    },
                    "camouflage": {
                        "label": "Камуфляжная пленка",
                        "description": "Труднее заметить.",
                    },
                },
            },
        },
    },
    "defense": {
        "label": "Защита",
        "description": "Повышает выживаемость.",
        "children": {
            "shell": {
                "label": "Минеральный панцирь",
                "description": "Снижает урон.",
                "children": {
                    "spikes": {
                        "label": "Шипы",
                        "description": "Отпугивает хищников.",
                    },
                    "reflect": {
                        "label": "Отражающие пластины",
                        "description": "Сдерживает лазеры.",
                    },
                },
            },
            "toxin": {
                "label": "Токсичные капли",
                "description": "Атака при контакте.",
                "children": {
                    "cloud": {
                        "label": "Ядовитое облако",
                        "description": "Контроль зоны.",
                    },
                    "stun": {
                        "label": "Нейро-блок",
                        "description": "Парализует угрозы.",
                    },
                },
            },
        },
    },
}


@app.route("/")
def index() -> str:
    return render_template("index.html", evolution_tree=EVOLUTION_TREE)


@app.route("/api/state")
def state() -> str:
    return jsonify(
        {
            "players": GLOBAL_STATE["players"],
            "global_mutations": GLOBAL_STATE["global_mutations"],
            "global_biomass": GLOBAL_STATE["global_biomass"],
            "map": GLOBAL_STATE["map"],
        }
    )


@socketio.on("connect")
def handle_connect() -> None:
    player_id = request.args.get("player") or uuid4().hex
    with LOCK:
        player_state = PlayerState(
            player_id=player_id,
            x=random.randint(0, MAP_WIDTH - 1),
            y=random.randint(0, MAP_HEIGHT - 1),
        )
        PLAYERS[player_id] = player_state
        GLOBAL_STATE["players"] = len(PLAYERS)
        GLOBAL_STATE["global_biomass"] += player_state.biomass
        ensure_bots_running()
    emit("session", {"player": player_id})
    emit("state", build_state(player_state), broadcast=True)


@socketio.on("disconnect")
def handle_disconnect() -> None:
    player_id = request.args.get("player")
    if not player_id or player_id not in PLAYERS:
        return
    with LOCK:
        player_state = PLAYERS.pop(player_id)
        GLOBAL_STATE["players"] = len(PLAYERS)
        GLOBAL_STATE["global_biomass"] = max(
            0, GLOBAL_STATE["global_biomass"] - player_state.biomass
        )
    emit("state", build_state(player_state), broadcast=True)


@socketio.on("mutate")
def handle_mutate(payload: dict) -> None:
    player_id = payload.get("player")
    mutation = payload.get("mutation")
    if not player_id or player_id not in PLAYERS or not mutation:
        return
    with LOCK:
        player_state = PLAYERS[player_id]
        if mutation in player_state.mutations:
            return
        player_state.mutations.append(mutation)
        player_state.biomass += 1
        player_state.hp = min(20, player_state.hp + 1)
        GLOBAL_STATE["global_biomass"] += 1
        GLOBAL_STATE["global_mutations"].setdefault(mutation, 0)
        GLOBAL_STATE["global_mutations"][mutation] += 1
    emit("state", build_state(player_state), broadcast=True)


@socketio.on("move")
def handle_move(payload: dict) -> None:
    player_id = payload.get("player")
    direction = payload.get("direction")
    if not player_id or player_id not in PLAYERS or not direction:
        return
    with LOCK:
        player_state = PLAYERS[player_id]
        dx, dy = direction_to_delta(direction)
        player_state.x = clamp(player_state.x + dx, 0, MAP_WIDTH - 1)
        player_state.y = clamp(player_state.y + dy, 0, MAP_HEIGHT - 1)
    emit("state", build_state(player_state), broadcast=True)


@socketio.on("attack")
def handle_attack(payload: dict) -> None:
    player_id = payload.get("player")
    if not player_id or player_id not in PLAYERS:
        return
    with LOCK:
        player_state = PLAYERS[player_id]
        targets = find_targets(player_state)
        for target in targets:
            target.hp -= 2
            if target.hp <= 0:
                respawn(target)
                GLOBAL_STATE["global_biomass"] = max(
                    0, GLOBAL_STATE["global_biomass"] - 1
                )
    emit("state", build_state(player_state), broadcast=True)


def build_state(player_state: PlayerState) -> dict:
    return {
        "player": {
            "id": player_state.player_id,
            "name": player_state.display_name,
            "mutations": player_state.mutations,
            "biomass": player_state.biomass,
            "hp": player_state.hp,
            "x": player_state.x,
            "y": player_state.y,
            "is_bot": player_state.is_bot,
            "created_at": player_state.created_at,
        },
        "world": {
            "players": GLOBAL_STATE["players"],
            "global_mutations": GLOBAL_STATE["global_mutations"],
            "global_biomass": GLOBAL_STATE["global_biomass"],
            "map": GLOBAL_STATE["map"],
            "actors": [
                {
                    "id": state.player_id,
                    "name": state.display_name,
                    "hp": state.hp,
                    "x": state.x,
                    "y": state.y,
                    "is_bot": state.is_bot,
                    "mutations": state.mutations,
                }
                for state in PLAYERS.values()
            ],
        },
    }


def clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, value))


def direction_to_delta(direction: str) -> tuple[int, int]:
    mapping = {
        "up": (0, -1),
        "down": (0, 1),
        "left": (-1, 0),
        "right": (1, 0),
    }
    return mapping.get(direction, (0, 0))


def find_targets(player_state: PlayerState) -> list[PlayerState]:
    targets: list[PlayerState] = []
    for state in PLAYERS.values():
        if state.player_id == player_state.player_id:
            continue
        if abs(state.x - player_state.x) <= 1 and abs(state.y - player_state.y) <= 1:
            targets.append(state)
    return targets


def respawn(player_state: PlayerState) -> None:
    player_state.hp = 10
    player_state.x = random.randint(0, MAP_WIDTH - 1)
    player_state.y = random.randint(0, MAP_HEIGHT - 1)


def ensure_bots_running() -> None:
    global BOT_TASK_STARTED
    if BOT_TASK_STARTED:
        return
    BOT_TASK_STARTED = True
    for _ in range(BOT_COUNT):
        bot_id = f"bot-{uuid4().hex[:8]}"
        PLAYERS[bot_id] = PlayerState(
            player_id=bot_id,
            x=random.randint(0, MAP_WIDTH - 1),
            y=random.randint(0, MAP_HEIGHT - 1),
            is_bot=True,
            display_name=random.choice(BOT_NAMES),
        )
    GLOBAL_STATE["players"] = len(PLAYERS)
    socketio.start_background_task(bot_loop)


def bot_loop() -> None:
    while True:
        time.sleep(1.5)
        with LOCK:
            bots = [state for state in PLAYERS.values() if state.is_bot]
            if not bots:
                continue
            for bot in bots:
                direction = random.choice(["up", "down", "left", "right"])
                dx, dy = direction_to_delta(direction)
                bot.x = clamp(bot.x + dx, 0, MAP_WIDTH - 1)
                bot.y = clamp(bot.y + dy, 0, MAP_HEIGHT - 1)
                targets = find_targets(bot)
                for target in targets:
                    if target.is_bot:
                        continue
                    target.hp -= 1
                    if target.hp <= 0:
                        respawn(target)
        emit_world_state()


def emit_world_state() -> None:
    if not PLAYERS:
        return
    sample_state = next(iter(PLAYERS.values()))
    socketio.emit("state", build_state(sample_state), broadcast=True)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
