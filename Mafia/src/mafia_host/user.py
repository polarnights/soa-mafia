from dataclasses import dataclass


@dataclass
class User:
    _id: int
    _nickname: str

    @property
    def id(self) -> int:
        return self._id

    @property
    def nickname(self) -> str:
        return self._nickname

    def __hash__(self) -> int:
        return hash(self._id)


class ProvisioningUser(User):
    def __init__(self, id: int, nickname: str) -> None:
        super().__init__(id, nickname)
        self._ready = False

    def ready(self) -> bool:
        if not self._ready:
            self._ready = True
            return True
        return False

    def cancel_ready(self) -> bool:
        if self._ready:
            self._ready = False
            return True
        return False
