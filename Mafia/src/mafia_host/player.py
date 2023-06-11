from enum import Enum

from .user import User


class PlayerRoles(Enum):
    Mafia = "Mafia"
    Civilian = "Civilian"
    Officer = "Officer"
    Ghost = "Ghost"


class PlayerStatus(Enum):
    Alive = "Alive"
    Dead = "Dead"


class Player(User):
    def __init__(
        self,
        id: int,
        nickname: str,
        role: PlayerRoles
    ) -> None:
        super().__init__(id, nickname)
        self._role = role
        self._status = PlayerStatus.Alive

    @property
    def role(self) -> PlayerRoles:
        return self._role

    def declare_dead(self) -> None:
        self._status = PlayerStatus.Dead

    def is_alive(self) -> bool:
        return self._status == PlayerStatus.Alive
