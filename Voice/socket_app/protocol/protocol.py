import asyncio
import base64
import json
import socket
from dataclasses import dataclass


@dataclass
class Packet:
    command: str
    data: bytes

    def serialization(self) -> bytes:
        return json\
            .dumps({
                "command": self.command,
                "data": base64.b64encode(self.data).decode("ascii"),
            })\
            .encode()

    @classmethod
    def deserialization(cls, bytes_: bytes) -> "Packet":
        js = json.loads(bytes_)
        return Packet(
            command=js["command"],
            data=base64.b64decode(js["data"].encode("ascii"))
        )


def recv_exactly(socket: socket.SocketType, size: int) -> bytes:
    result: bytes = b""
    while len(result) < size:
        new_data = socket.recv(size - len(result))
        result += new_data
    return new_data


def read_packet(socket: socket.SocketType) -> Packet:
    size_b = recv_exactly(socket, 8)
    size = int.from_bytes(size_b, "little", signed=False)
    packet = recv_exactly(socket, size)
    return Packet.deserialization(packet)


def write_packet(
    socket: socket.SocketType,
    packet: Packet
) -> None:
    packet_b = packet.serialization()
    size = len(packet_b).to_bytes(8, "little", signed=False)
    socket.sendall(size)
    socket.sendall(packet_b)


async def async_read_packet(reader: asyncio.StreamReader) -> Packet:
    size_b = await reader.readexactly(8)
    size = int.from_bytes(size_b, "little", signed=False)
    packet = await reader.readexactly(size)
    return Packet.deserialization(packet)


async def async_write_packet(
    writer: asyncio.StreamWriter,
    packet: Packet
) -> None:
    packet_b = packet.serialization()
    size = len(packet_b).to_bytes(8, "little", signed=False)
    writer.write(size)
    writer.write(packet_b)
    await writer.drain()
