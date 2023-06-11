import typing as tp
from random import shuffle


from .player import Player, PlayerRoles
from .room import Room


class MafiaRoomError(RuntimeError):
    pass


class MafiaRoom:
    def __init__(self, room: Room) -> None:
        if room.users_number < 3:
            raise MafiaRoomError("Not enough players. Need at least 3")
        self._mafia_nums = room.users_number // 3
        self._civilian_nums = room.users_number - self._mafia_nums
        free_roles: list[PlayerRoles] = (
            [PlayerRoles.Officer] +
            [PlayerRoles.Civilian
             for _ in range(room.users_number - self._mafia_nums - 1)] +
            [PlayerRoles.Mafia for _ in range(self._mafia_nums)]
        )
        assert len(free_roles) == room.users_number
        shuffle(free_roles)
        self._players: dict[int, Player] = dict()
        for user in room.users():
            assert user.id not in self._players
            self._players[user.id] = Player(
                user.id,
                user.nickname,
                free_roles.pop()
            )

    def leave(self, id: int) -> tp.Optional[str]:
        self._player_in_room(id)
        if self.is_mafia(id) and self._players[id].is_alive():
            self._mafia_nums -= 1
        elif self._players[id].is_alive():
            self._civilian_nums -= 1
        del self._players[id]
        return self._check_end()

    def is_mafia(self, id: int) -> bool:
        self._player_in_room(id)
        return self._players[id].role == PlayerRoles.Mafia

    def is_officer(self, id: int) -> bool:
        self._player_in_room(id)
        return self._players[id].role == PlayerRoles.Officer

    def is_killed(self, id: int) -> bool:
        self._player_in_room(id)
        return not self._players[id].is_alive()

    def kill_player(self, id: int) -> tp.Optional[str]:
        self._player_in_room(id)
        if self._players[id].is_alive():
            if self.is_mafia(id):
                self._mafia_nums -= 1
            else:
                self._civilian_nums -= 1
            self._players[id].declare_dead()
        else:
            raise MafiaRoomError(f"Player {id} already dead")
        return self._check_end()

    def player_role(self, id: int) -> PlayerRoles:
        self._player_in_room(id)
        return self._players[id].role

    def players(self) -> tp.Generator[Player, None, None]:
        for player in self._players.values():
            yield player

    def _player_in_room(self, id: int) -> None:
        if id not in self._players:
            raise MafiaRoom(f"{self._players[id].nickname} not in room")

    def _check_end(self) -> tp.Optional[str]:
        if self._mafia_nums == 0:
            return "Civilians win"
        if self._civilian_nums <= self._mafia_nums:
            return "Mafia wins"
        return None
