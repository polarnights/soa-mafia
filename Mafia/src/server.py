import asyncio
import typing as tp
from uuid import uuid4

import click
import grpc

import service.service_pb2_grpc as service_pb2_grpc
import service.service_pb2 as service_pb2
from mafia_host import MafiaHost


class Mafia(service_pb2_grpc.MafiaServicer):
    def __init__(self) -> None:
        self._rooms: dict[str, MafiaHost] = {}
        self._ready_to_start: dict[str, int] = {}
        self._ready_to_game_cv: dict[str, asyncio.Condition] = {}
        self._pass_night_cv: dict[str, asyncio.Condition] = {}
        self._night_num: dict[str, int] = {}
        self._day_cv: dict[str, asyncio.Condition] = {}
        self._day_votes: dict[str, dict[int, int]] = {}
        self._day_num: dict[str, int] = {}
        self._day_flag: dict[str, bool] = {}

    async def CreateRoom(
        self,
        request: service_pb2.CreateRoomRequest,
        context: grpc.ServicerContext
    ) -> service_pb2.CreateRoomReply:
        room_id = uuid4().hex
        while room_id in self._rooms:
            room_id = uuid4().hex
        self._rooms[room_id] = MafiaHost()
        self._ready_to_start[room_id] = 0
        self._ready_to_game_cv[room_id] = asyncio.Condition()
        self._night_num[room_id] = 0
        self._pass_night_cv[room_id] = asyncio.Condition()
        self._day_cv[room_id] = asyncio.Condition()
        self._day_votes[room_id] = {}
        self._day_num[room_id] = 0
        self._day_flag[room_id] = False
        user_id = self._rooms[room_id].join(request.nickname)
        print(
            f"Created new room: [{room_id}] by [{request.nickname}|{user_id}]",
            flush=True
        )
        return service_pb2.CreateRoomReply(
            user_id=user_id,
            room_id=room_id
        )

    async def JoinToRoom(
        self,
        request: service_pb2.JoinToRoomRequest,
        context: grpc.ServicerContext
    ) -> service_pb2.JoinToRoomReply:
        await self._check_the_room_id(request.room_id, context)
        if self._rooms[request.room_id].users_number == 5:
            await context.abort(grpc.StatusCode.UNAVAILABLE, "Room is full")
        user_id = self._rooms[request.room_id]\
            .join(request.nickname)
        print(
            f"[{request.nickname}|{user_id}] connected "
            f"to the room: {request.room_id}",
            flush=True
        )
        return service_pb2.JoinToRoomReply(
            user_id=user_id
        )

    async def SubscribeOnNotifications(
        self,
        request: service_pb2.SubscribeOnNotificationsRequest,
        context: grpc.ServicerContext
    ) -> tp.AsyncIterable[service_pb2.SubscribeOnNotificationsReply]:
        await self._check_the_room_id(request.room_id, context)
        async for notification in self._rooms[request.room_id].notifications():
            yield service_pb2.SubscribeOnNotificationsReply(
                type=notification.type.value,
                data=notification.data
            )

    async def LeaveRoom(
        self,
        request: service_pb2.LeaveRoomRequest,
        context: grpc.ServicerContext
    ) -> service_pb2.LeaveRoomReply:
        await self._check_the_room_id(request.room_id, context)
        self._rooms[request.room_id].leave(request.user_id)
        return service_pb2.LeaveRoomReply()

    async def ReadyToStart(
        self,
        request: service_pb2.ReadyToStartRequest,
        context: grpc.ServicerContext
    ) -> service_pb2.ReadyToStartReply:
        room_id = request.room_id
        await self._check_the_room_id(room_id, context)
        self._ready_to_start[room_id] += 1
        if self._ready_to_start[room_id] == 5:
            self._rooms[room_id].start_the_game()
            async with self._ready_to_game_cv[room_id]:
                self._ready_to_game_cv[room_id].notify_all()
        else:
            async with self._ready_to_game_cv[room_id]:
                await self._ready_to_game_cv[room_id].wait()
        return service_pb2.ReadyToStartReply(
            role=self._rooms[room_id]
            .player_role(request.user_id).value
        )

    async def Kill(
        self,
        request: service_pb2.KillRequest,
        context: grpc.ServicerContext
    ):
        await self._check_the_room_id(request.room_id, context)
        room = self._rooms[request.room_id]
        if not room.is_mafia(request.user_id):
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "You are not a mafia"
            )
        room.kill_player(request.user_id_to_kill)
        return service_pb2.KillReply()

    async def IsKiller(
        self,
        request: service_pb2.IsKillerRequest,
        context: grpc.ServicerContext
    ) -> service_pb2.IsKillerReply:
        await self._check_the_room_id(request.room_id, context)
        room = self._rooms[request.room_id]
        if not room.is_officer(request.user_id):
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "You are not a officer"
            )
        answer = room.is_mafia(request.user_id_to_check)
        return service_pb2.IsKillerReply(
            answer=answer
        )

    async def Night(
        self,
        request: service_pb2.NightRequest,
        context: grpc.ServicerContext
    ) -> service_pb2.NightReply:
        room_id = request.room_id
        await self._check_the_room_id(room_id, context)
        self._night_num[room_id] += 1
        if self._night_num[room_id] == self._rooms[room_id].users_number:
            self._night_num[room_id] = 0
            async with self._pass_night_cv[room_id]:
                self._pass_night_cv[room_id].notify_all()
        else:
            async with self._pass_night_cv[room_id]:
                await self._pass_night_cv[room_id].wait()
        return service_pb2.NightReply()

    async def Day(
        self,
        request: service_pb2.DayRequest,
        context: grpc.ServicerContext
    ) -> service_pb2.DayReply:
        room_id = request.room_id
        await self._check_the_room_id(room_id, context)
        self._day_num[room_id] += 1
        if request.user_id != request.user_id_to_kill:
            self._rooms[room_id].player_role(request.user_id_to_kill)
            if request.user_id_to_kill not in self._day_votes[room_id]:
                self._day_votes[room_id][request.user_id_to_kill] = 0
            self._day_votes[room_id][request.user_id_to_kill] += 1
        if self._day_num[room_id] == self._rooms[room_id].users_number:
            self._day_num[room_id] = 0
            self._day_flag[room_id] = True
            v = max(self._day_votes[room_id].values())
            k = None
            for k_, v_ in self._day_votes[room_id].items():
                if v_ == v:
                    if k is not None:
                        self._day_flag[room_id] = False
                        break
                    k = k_
            if self._day_flag[room_id]:
                self._rooms[room_id].kill_player(k)
            async with self._day_cv[room_id]:
                self._day_cv[room_id].notify_all()
        else:
            async with self._day_cv[room_id]:
                await self._day_cv[room_id].wait()
        return service_pb2.DayReply(
            answer=self._day_flag[room_id]
        )

    async def _check_the_room_id(
        self,
        room_id: str,
        context: grpc.ServicerContext
    ) -> None:
        if room_id not in self._rooms:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "Unknow id room"
            )


async def run(host: str, port: int):
    server = grpc.aio.server()
    service_pb2_grpc.add_MafiaServicer_to_server(
        Mafia(), server
    )
    server.add_insecure_port(f"{host}:{port}")
    await server.start()
    print(f"Server is started on {host}:{port}", flush=True)
    await server.wait_for_termination()


@click.command()
@click.option("--host", default="0.0.0.0", type=str)
@click.option("--port", default=50051, type=int)
def main(
    host: str,
    port: int,
) -> None:
    asyncio.run(run(host, port))


if __name__ == "__main__":
    main()
