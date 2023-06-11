import asyncio
from time import sleep
import click
import grpc.aio
import logging
from dataclasses import dataclass, field

from simple_term_menu import TerminalMenu
from typing import Dict

import service.service_pb2_grpc as service_pb2_grpc
import service.service_pb2 as service_pb2


@dataclass
class ClientInRoom:
    _nickname: str
    _channel: grpc.aio.Channel
    _user_id: int
    _room_id: str
    _players: Dict[int, str] = field(default_factory=dict)
    _exit_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _killed = False
    _end = False

    def __post_init__(self) -> None:
        self._stub = service_pb2_grpc.MafiaStub(self._channel)

    async def process(self) -> None:
        await asyncio.gather(
            self._subscribe_on_notification(),
            self._process()
        )

    async def _subscribe_on_notification(self) -> None:
        request = service_pb2.SubscribeOnNotificationsRequest(
            user_id=self._user_id,
            room_id=self._room_id
        )
        stub = self._stub
        async for notification in stub.SubscribeOnNotifications(request):
            if notification.type == "Join":
                nickname, user_id = notification.data.split(" ")
                user_id = int(user_id)
                print(f"Player {nickname} is joined", flush=True)
                self._players[user_id] = nickname
            elif notification.type == "Leave":
                nickname, user_id = notification.data.split(" ")
                user_id = int(user_id)
                print(f"Player {nickname} is disconnected", flush=True)
                self._players.pop(user_id, None)
                if not self._end:
                    self._killed = True
            elif notification.type == "Kill":
                nickname, user_id = notification.data.split(" ")
                user_id = int(user_id)
                print(f"Player {nickname} is killed", flush=True)
                if user_id == self._user_id:
                    self._role = "Ghost"
                self._players.pop(user_id, None)
                if not self._end:
                    self._killed = True
            elif notification.type == "StartTheGame":
                print("Game is starting", flush=True)
            elif notification.type == "End":
                self._end = True
                data = notification.data
                print(data, flush=True)
                await self._exit()

    async def _process(self) -> None:
        terminal_menu = TerminalMenu([
            "[r] Ready",
            "[e] Exit"
        ], title=f"Nickname: {self._nickname}. Room ID: {self._room_id}")
        answer = terminal_menu.show()
        if answer == 0:
            reply = await self._stub.ReadyToStart(
                service_pb2.ReadyToStartRequest(
                    user_id=self._user_id,
                    room_id=self._room_id
                )
            )
            self._role = reply.role
        else:
            await self._exit()
        for _ in range(3):
            await asyncio.sleep(2)
        print(f"Your role: {self._role}", flush=True)
        num_day = 1
        print(f"Day number №{num_day}")
        print("Alive people:")
        for id, nickname in self._players.items():
            print(f"- {nickname}\\{id}", flush=True)
        num_day += 1
        while True:
            print("Night", flush=True)
            self._killed = False
            if self._role == "Mafia":
                chs = [
                    f"{nickname}\\{id}"
                    for id, nickname in self._players.items()
                    if id != self._user_id
                ]
                terminal_menu = TerminalMenu(
                    chs + ["[e] Exit"],
                    title=f"Nickname: {self._nickname}. "
                    f"Room ID: {self._room_id}. Role: mafia"
                )
                answer = int(terminal_menu.show())
                if answer == len(chs):
                    await self._stub.Night(service_pb2.NightRequest(
                        user_id=self._user_id,
                        room_id=self._room_id
                    ))
                    await self._exit()
                _, id = chs[answer].split("\\")
                try:
                    await self._stub.Kill(service_pb2.KillRequest(
                        room_id=self._room_id,
                        user_id=self._user_id,
                        user_id_to_kill=int(id)
                    ))
                except Exception:
                    pass
            elif self._role == "Officer":
                chs = [
                    f"{nickname}\\{id}"
                    for id, nickname in self._players.items()
                    if id != self._user_id
                ]
                terminal_menu = TerminalMenu(
                    chs + ["[e] Exit"],
                    title=f"Nickname: {self._nickname}. "
                    f"Room ID: {self._room_id}. Role: officer"
                )
                answer = int(terminal_menu.show())
                if answer == len(chs):
                    await self._stub.Night(service_pb2.NightRequest(
                        user_id=self._user_id,
                        room_id=self._room_id
                    ))
                    await self._exit()
                nickname, id = chs[answer].split("\\")
                try:
                    reply = await self._stub.IsKiller(
                        service_pb2.IsKillerRequest(
                            room_id=self._room_id,
                            user_id=self._user_id,
                            user_id_to_check=int(id)
                        )
                    )
                except Exception:
                    pass
                else:
                    if reply.answer:
                        print(f"{nickname}|{id} is mafia", flush=True)
                    else:
                        print(f"{nickname}|{id} is not mafia", flush=True)
            else:
                terminal_menu = TerminalMenu(
                    ["[c] Continue", "[e] Exit"],
                    title=f"Nickname: {self._nickname}. "
                    f"Room ID: {self._room_id}. Role: {self._role}"
                )
                answer = int(terminal_menu.show())
                if answer == 1:
                    await self._stub.Night(service_pb2.NightRequest(
                        user_id=self._user_id,
                        room_id=self._room_id
                    ))
                    await self._exit()
            await self._stub.Night(service_pb2.NightRequest(
                user_id=self._user_id,
                room_id=self._room_id
            ))
            while not self._killed:
                await asyncio.sleep(1)
            await asyncio.sleep(1)
            print(f"Day number №{num_day}")
            print("Alive people:")
            for id, nickname in self._players.items():
                print(f"- {nickname}\\{id}", flush=True)
            num_day += 1
            self._killed = False
            if self._role == "Ghost":
                terminal_menu = TerminalMenu(
                    ["[c] Continue", "[e] Exit"],
                    title=f"Nickname: {self._nickname}. "
                    f"Room ID: {self._room_id}. Role: {self._role}"
                )
                answer = int(terminal_menu.show())
                if answer == 1:
                    await self._exit()
                try:
                    reply = await self._stub.Day(service_pb2.DayRequest(
                        room_id=self._room_id,
                        user_id=self._user_id,
                        user_id_to_kill=self._user_id
                    ))
                except grpc.aio.AioRpcError as e:
                    print(e.details, flush=True)
            else:
                chs = [
                    f"{nickname}\\{id}"
                    for id, nickname in self._players.items()
                    if id != self._user_id
                ]
                terminal_menu = TerminalMenu(
                    chs + ["[e] Exit"],
                    title=f"Nickname: {self._nickname}. "
                    f"Room ID: {self._room_id}. Day"
                )
                answer = int(terminal_menu.show())
                if answer == len(chs):
                    await self._exit()
                _, id = chs[answer].split("\\")
                try:
                    reply = await self._stub.Day(service_pb2.DayRequest(
                        room_id=self._room_id,
                        user_id=self._user_id,
                        user_id_to_kill=int(id)
                    ))
                except grpc.aio.AioRpcError as e:
                    print(e.details, flush=True)

            if reply.answer:
                await asyncio.sleep(1)
                while not self._killed:
                    await asyncio.sleep(1)
            else:
                for _ in range(3):
                    await asyncio.sleep(3)

    async def _exit(self) -> None:
        await self._stub.LeaveRoom(service_pb2.LeaveRoomRequest(
            user_id=self._user_id,
            room_id=self._room_id
        ))
        await self._channel.close()
        exit(0)


@dataclass
class ConnectedClient:
    _nickname: str
    _channel: grpc.aio.Channel

    def __post_init__(self) -> None:
        self._stub = service_pb2_grpc.MafiaStub(self._channel)

    async def room_process(self) -> ClientInRoom:
        while True:
            terminal_menu = TerminalMenu([
                "[c] Create a room",
                "[j] Join to the room",
                "[e] Exit"
            ], title=f"Nickname: {self._nickname}")
            answer = terminal_menu.show()
            if answer == 0:
                room = await self._create_room()
                break
            elif answer == 1:
                room_id = input("Write room key: ")
                print("\033[A" +
                      (len(room_id) + len("Write room key: ")) * " " +
                      "\033[A")
                try:
                    room = await self._join_to_the_room(room_id)
                except grpc.aio.AioRpcError as e:
                    print("Failed to connect", flush=True)
                    print(e.details)
                    continue
                break
            else:
                await self._exit()

        return room

    async def _create_room(self) -> ClientInRoom:
        reply = await self._stub.CreateRoom(service_pb2.CreateRoomRequest(
            nickname=self._nickname
        ))
        print(f"Created the room with id: {reply.room_id}", flush=True)
        return ClientInRoom(
            self._nickname,
            self._channel,
            reply.user_id,
            reply.room_id
        )

    async def _join_to_the_room(self, room_id: str) -> ClientInRoom:
        reply = await self._stub.JoinToRoom(service_pb2.JoinToRoomRequest(
            nickname=self._nickname,
            room_id=room_id
        ))
        print(f"Join the room with id: {room_id}", flush=True)
        return ClientInRoom(
            self._nickname,
            self._channel,
            reply.user_id,
            room_id
        )

    async def _exit(self) -> None:
        await self._channel.close()
        exit(0)


@dataclass
class Client:
    _host: str
    _port: int
    _nickname: str

    def connect(self) -> ConnectedClient:
        channel = grpc.aio.insecure_channel(f"{self._host}:{self._port}")
        return ConnectedClient(self._nickname, channel)


async def run(
    host: str,
    port: int,
    nickname: str,
) -> None:
    try:
        connect = Client(host, port, nickname).connect()
        room = await connect.room_process()
        await room.process()
    except SystemExit:
        pass


@click.command()
@click.option("--host", default="0.0.0.0", type=str)
@click.option("--port", default=50051, type=int)
@click.option("--nickname", type=str, prompt=True)
def main(
    host: str,
    port: int,
    nickname: str,
) -> None:
    asyncio.run(run(host, port, nickname))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
