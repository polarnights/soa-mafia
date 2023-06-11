import asyncio
import socket
import typing as tp
from uuid import uuid4

import click
from typing import Dict

from Voice.socket_app.protocol.protocol import Packet, async_read_packet, async_write_packet


class Server:
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._buffer = 1024

        self._connections: \
            Dict[str, Dict[asyncio.StreamWriter, str]] = {}
        asyncio.run(self._setup_server())

    async def _setup_server(self) -> None:
        async def handle_socket(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter
        ) -> None:
            print("New connection!", flush=True)
            username: tp.Optional[str] = None
            cur_room: tp.Optional[str] = None
            while True:
                try:
                    packet = await async_read_packet(reader)
                except Exception:
                    await self._close_connection(cur_room, writer)
                    return
                data = packet.command.split(" ")
                if data[0] == "create":
                    if len(data) != 2:
                        await self._close_connection(cur_room, writer)
                        return
                    username = data[1]
                    key = uuid4().hex
                    while key in self._connections:
                        key = uuid4().hex
                    cur_room = key
                    self._connections[cur_room] = {}
                    self._connections[cur_room][writer] = username
                    try:
                        await async_write_packet(
                            writer, Packet(f"OK {cur_room}", b"")
                        )
                    except Exception:
                        await self._close_connection(cur_room, writer)
                        return
                    print(
                        f"Created new room {cur_room} by {username}",
                        flush=True
                    )
                    break
                elif data[0] == "join":
                    data = [e for e in data if len(e) != 0]
                    if len(data) != 3:
                        await self._close_connection(cur_room, writer)
                        return
                    username = data[1]
                    key = data[2]
                    if key not in self._connections:
                        await async_write_packet(
                            writer, Packet("FAIL", b"")
                        )
                        continue
                    cur_room = key
                    self._connections[cur_room][writer] = username
                    try:
                        lst = [
                            v
                            for k, v in self._connections[cur_room].items()
                            if k != writer
                        ]
                        t = (" ".join(lst)).encode()
                        await async_write_packet(writer, Packet("OK", t))
                        await self._broadcast(
                            writer, "Add", cur_room,
                            f"{self._connections[cur_room][writer]}".encode()
                        )
                        print(f"{username} join to {cur_room}", flush=True)
                    except Exception:
                        await self._close_connection(cur_room, writer)
                        return
                    break
                await self._close_connection(cur_room, writer)
                return
            while True:
                try:
                    packet = await async_read_packet(reader)
                    if not packet.command.startswith("Audio "):
                        raise Exception()
                    await self._broadcast(
                        writer, "Audio", cur_room, packet.data
                    )
                except Exception:
                    await self._close_connection(cur_room, writer)
                    return

        server = await asyncio.start_server(
            handle_socket, self._host,
            self._port, family=socket.AF_INET,
        )
        print(f"Serving on {self._host}:{self._port}", flush=True)

        await server.serve_forever()

    async def _broadcast_helper(
        self,
        writer: asyncio.StreamWriter,
        type_: str,
        key: str,
        data: bytes,
        name: str,
    ) -> None:
        try:
            await async_write_packet(
                writer,
                Packet(f"{type_} {name}", data)
            )
        except Exception:
            await self._close_connection(key, writer)
            return

    async def _broadcast(
        self,
        writer: asyncio.StreamWriter,
        type_: str,
        key: str,
        data: bytes,
    ) -> None:
        await asyncio.gather(*(
            self._broadcast_helper(
                writer_c, type_, key, data, self._connections[key][writer]
            )
            for writer_c in self._connections[key]
            if writer_c != writer
        ))

    async def _close_connection(
        self, key: tp.Optional[str], writer: asyncio.StreamWriter
    ) -> None:
        if (
            key is not None and
            key in self._connections and
            writer in self._connections[key]
        ):
            await self._broadcast(
                writer, "Delete", key,
                f"{self._connections[key][writer]}".encode()
            )
            print(
                f"Connection is closed in {key} "
                f"with {self._connections[key][writer]}",
                flush=True
            )
            del self._connections[key][writer]
            if len(self._connections[key]) == 0:
                del self._connections[key]
                print(f"{key} room is deleted", flush=True)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


@click.command()
@click.option("--host", default="0.0.0.0", type=str)
@click.option("--port", default=10080, type=int)
def main(
    host: str,
    port: int,
) -> None:
    Server(host, port)


if __name__ == "__main__":
    main()
