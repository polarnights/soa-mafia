import asyncio
import typing as tp
from dataclasses import dataclass
from enum import Enum


from .player import PlayerRoles
from .mafia_room import MafiaRoom
from .room import Room


class MafiaHostError(RuntimeError):
    pass


class NotificationType(Enum):
    Join = "Join"
    Leave = "Leave"
    StartTheGame = "StartTheGame"
    Kill = "Kill"
    End = "End"


@dataclass
class Notification:
    _type: NotificationType
    _data: str

    @property
    def type(self) -> NotificationType:
        return self._type

    @property
    def data(self) -> str:
        return self._data


class MafiaHost:
    def __init__(self) -> None:
        self._room: Room = Room()
        self._mafia_room: tp.Optional[MafiaRoom] = None
        self._notifications: list[Notification] = []

    def join(self, nickname: str) -> int:
        if self._mafia_room is not None:
            raise MafiaHostError(
                "Cannot join to the room that started the game"
            )
        user_id = self._room.join(nickname)
        self._notifications.append(Notification(
            NotificationType.Join,
            f"{nickname} {user_id}"
        ))
        return user_id

    def start_the_game(self) -> None:
        if self._mafia_room is not None:
            raise MafiaHostError(
                "Game is already started"
            )
        self._mafia_room = MafiaRoom(self._room)
        self._notifications.append(Notification(
            NotificationType.StartTheGame,
            ""
        ))

    def leave(self, id: str) -> None:
        self._notifications.append(Notification(
            NotificationType.Leave,
            f"{self._room.nickname_by_user_id(id)} {id}"
        ))
        self._room.leave(id)
        if self._mafia_room is not None:
            if (is_end := self._mafia_room.leave(id)) is not None:
                self._notifications.append(Notification(
                    NotificationType.End,
                    is_end
                ))
                self._mafia_room = None

    def is_mafia(self, id: int) -> bool:
        self._game_is_started()
        return self._mafia_room.is_mafia(id)

    def is_officer(self, id: int) -> bool:
        self._game_is_started()
        return self._mafia_room.is_officer(id)

    def player_role(self, id: int) -> PlayerRoles:
        return self._mafia_room.player_role(id)

    def kill_player(self, id: int) -> None:
        self._game_is_started()
        if self._mafia_room.is_killed(id):
            raise MafiaHostError(
                f"Player {id} is killed"
            )
        self._notifications.append(Notification(
            NotificationType.Kill,
            f"{self._room.nickname_by_user_id(id)} {id}"
        ))
        if (is_end := self._mafia_room.kill_player(id)) is not None:
            self._notifications.append(Notification(
                NotificationType.End,
                is_end
            ))
            self._mafia_room = None

    async def notifications(self) -> tp.AsyncIterable[Notification]:
        i = 0
        while True:
            if self._notifications[i - 1].type == NotificationType.End:
                return
            if i < len(self._notifications):
                i += 1
                yield self._notifications[i - 1]
            else:
                await asyncio.sleep(0)

    @property
    def users_number(self) -> int:
        return self._room.users_number

    def _game_is_started(self) -> None:
        if self._mafia_room is None:
            raise MafiaHostError(
                "Game is not started or finished"
            )
