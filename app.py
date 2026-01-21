from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit


@dataclass
class PlayerState:
    player_id: str
    mutations: list[str] = field(default_factory=list)
    biomass: int = 1
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


app = Flask(__name__)
app.config["SECRET_KEY"] = "primor-dev"

socketio = SocketIO(app, cors_allowed_origins="*")

GLOBAL_STATE = {
    "players": 0,
    "global_mutations": {},
    "global_biomass": 0,
}

PLAYERS: dict[str, PlayerState] = {}

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
        }
    )


@socketio.on("connect")
def handle_connect() -> None:
    player_id = request.args.get("player") or uuid4().hex
    player_state = PlayerState(player_id=player_id)
    PLAYERS[player_id] = player_state
    GLOBAL_STATE["players"] = len(PLAYERS)
    GLOBAL_STATE["global_biomass"] += player_state.biomass
    emit("session", {"player": player_id})
    emit("state", build_state(player_state), broadcast=True)


@socketio.on("disconnect")
def handle_disconnect() -> None:
    player_id = request.args.get("player")
    if not player_id or player_id not in PLAYERS:
        return
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
    player_state = PLAYERS[player_id]
    if mutation in player_state.mutations:
        return
    player_state.mutations.append(mutation)
    player_state.biomass += 1
    GLOBAL_STATE["global_biomass"] += 1
    GLOBAL_STATE["global_mutations"].setdefault(mutation, 0)
    GLOBAL_STATE["global_mutations"][mutation] += 1
    emit("state", build_state(player_state), broadcast=True)


def build_state(player_state: PlayerState) -> dict:
    return {
        "player": {
            "id": player_state.player_id,
            "mutations": player_state.mutations,
            "biomass": player_state.biomass,
            "created_at": player_state.created_at,
        },
        "world": {
            "players": GLOBAL_STATE["players"],
            "global_mutations": GLOBAL_STATE["global_mutations"],
            "global_biomass": GLOBAL_STATE["global_biomass"],
        },
    }


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
