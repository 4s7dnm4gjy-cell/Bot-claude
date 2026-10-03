"""Exécution des ordres : broker simulé (papier) ou Alpaca (papier / réel)."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

import requests

from .strategy import Order


class Broker(ABC):
    @abstractmethod
    def get_cash(self) -> float: ...

    @abstractmethod
    def get_positions(self) -> dict[str, float]: ...

    @abstractmethod
    def submit(self, order: Order) -> str: ...

    def is_market_open(self) -> bool:
        return True


class PaperBroker(Broker):
    """Portefeuille simulé persistant dans un fichier JSON local."""

    def __init__(self, state_file: str | Path = "state/paper.json", initial_cash: float = 0.0, fee_bps: float = 0.0, fee_fixed: float = 0.0):
        self.path = Path(state_file)
        self.fee_bps = fee_bps
        self.fee_fixed = fee_fixed
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
        else:
            self.state = {"cash": initial_cash, "positions": {}}
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2))

    def deposit(self, amount: float) -> None:
        self.state["cash"] += amount
        self._save()

    def get_cash(self) -> float:
        return float(self.state["cash"])

    def get_positions(self) -> dict[str, float]:
        return {t: float(q) for t, q in self.state["positions"].items() if q}

    def submit(self, order: Order) -> str:
        fee = order.value * self.fee_bps / 1e4 + self.fee_fixed
        pos = self.state["positions"]
        if order.side == "buy":
            cost = order.value + fee
            if cost > self.state["cash"] + 1e-6:
                raise RuntimeError(f"Cash insuffisant pour {order.ticker}")
            self.state["cash"] -= cost
            pos[order.ticker] = pos.get(order.ticker, 0.0) + order.quantity
        else:
            if order.quantity > pos.get(order.ticker, 0.0) + 1e-9:
                raise RuntimeError(f"Position insuffisante pour {order.ticker}")
            self.state["cash"] += order.value - fee
            pos[order.ticker] = pos[order.ticker] - order.quantity
        self._save()
        return "paper"


class AlpacaBroker(Broker):
    """API Alpaca. Clés lues dans ALPACA_API_KEY / ALPACA_SECRET_KEY.

    `live=False` -> compte papier d'Alpaca (argent fictif, vrais cours).
    """

    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"

    def __init__(self, live: bool = False):
        key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
        if not key or not secret:
            raise RuntimeError("Définissez ALPACA_API_KEY et ALPACA_SECRET_KEY")
        self.base = self.LIVE_URL if live else self.PAPER_URL
        self.session = requests.Session()
        self.session.headers.update({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})

    def _req(self, method: str, path: str, **kw):
        r = self.session.request(method, self.base + path, timeout=30, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"Alpaca {method} {path} -> {r.status_code}: {r.text}")
        return r.json()

    def get_cash(self) -> float:
        return float(self._req("GET", "/v2/account")["cash"])

    def get_positions(self) -> dict[str, float]:
        return {p["symbol"]: float(p["qty"]) for p in self._req("GET", "/v2/positions")}

    def is_market_open(self) -> bool:
        return bool(self._req("GET", "/v2/clock")["is_open"])

    def submit(self, order: Order) -> str:
        body = {
            "symbol": order.ticker,
            "side": order.side,
            "type": "market",
            "time_in_force": "day",
            "qty": str(order.quantity),
        }
        return self._req("POST", "/v2/orders", json=body)["id"]
