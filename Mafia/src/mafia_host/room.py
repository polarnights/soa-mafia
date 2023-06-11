import typing as tp
from dataclasses import dataclass, field
from random import getrandbits

from typing import Dict

from .user import ProvisioningUser


class RoomError(RuntimeError):
    pass


@dataclass
class Room:
    _users: Dict[int, ProvisioningUser] = field(default_factory=dict)
    _ready_number = 0

    def join(self, nickname: str) -> int:
        id = getrandbits(64)
        while id in self._users:
            id = getrandbits(64)
        self._users[id] = ProvisioningUser(id, nickname)
        return id

    def leave(self, id: int) -> None:
        self._user_in_room(id)
        del self._users[id]

    def users(self) -> tp.Generator[ProvisioningUser, None, None]:
        for user in self._users.values():
            yield user

    def nickname_by_user_id(self, id: int) -> str:
        self._user_in_room(id)
        return self._users[id].nickname

    @property
    def users_number(self) -> int:
        return len(self._users)

    def ready(self, id: int) -> None:
        if self._users[id].ready():
            self._ready_number += 1

    def cancel_ready(self, id: int) -> None:
        if self._users[id].cancel_ready():
            self._ready_number -= 1

    @property
    def ready_number(self) -> int:
        return self._ready_number

    def _user_in_room(self, id: int) -> None:
        if id not in self._users:
            raise RoomError(f"{id} not in the room")
