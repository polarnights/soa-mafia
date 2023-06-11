import os
import socket
import sys
import threading
import typing as tp
from concurrent.futures import Future

import click
import pyaudio

from simple_term_menu import TerminalMenu
from typing import List

from Voice.socket_app.protocol import Packet, read_packet, write_packet

class UserList:
    def __init__(self, lst: List[str]):
        self._lock = threading.Lock()
        self._list: List[str] = lst.copy()

    def add(self, user: str) -> None:
        with self._lock:
            self._list.append(user)

    def delete(self, user: str) -> None:
        with self._lock:
            if user in self._list:
                self._list.remove(user)

    def get(self) -> List[str]:
        with self._lock:
            return self._list.copy()


class Client:
    def __init__(self, host: str, port: int, username: int) -> None:
        self._host = host
        self._port = port
        self._buffer = 1024
        self._username = username
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._cur_talk = "Nobody"
        try:
            self._socket.connect((self._host, self._port))
        except Exception as ex:
            print("Couldn't connect to server")
            raise ex

        print(f"Connected to server {self._host}:{self._port}")

        self._socket.settimeout(5)
        self._menu()
        os.close(sys.stderr.fileno())
        self._core()

    def _menu(self) -> None:
        menu_title = "Menu"

        while True:
            terminal_menu = TerminalMenu([
                "[c] Create a room",
                "[j] Join to the room",
                "[e] Exit"
            ], title=menu_title)
            print()
            answer = terminal_menu.show()
            if answer == 0:
                try:
                    write_packet(
                        self._socket, Packet(f"create {self._username}", b"")
                    )
                    resp = read_packet(self._socket)
                except Exception:
                    print("Restart client!", flush=True)
                    self._socket.close()
                    exit(1)
                data = resp.command.split(" ")
                if len(data) != 2 or data[0] != "OK":
                    print("Restart client!", flush=True)
                    self._socket.close()
                    return
                self._list = UserList([])
                self._room_num = data[1]
                break
            elif answer == 1:
                room_exp = input("Write room key: ")
                print("\033[A" +
                      (len(room_exp) + len("Write room key: ")) * " " +
                      "\033[A")
                try:
                    write_packet(
                        self._socket,
                        Packet(f"join {self._username} {room_exp}", b"")
                    )
                    resp = read_packet(self._socket)
                except Exception:
                    print("Restart client!", flush=True)
                    self._socket.close()
                    exit(1)
                if resp.command == "OK":
                    self._list = UserList(resp.data.decode().split(" "))
                    self._room_num = room_exp
                    break
                elif resp.command == "FAIL":
                    menu_title = "Failed to connect to the room"
                else:
                    print("Restart client!", flush=True)
                    self._socket.close()
                    exit(1)
            else:
                if answer != 2:
                    print("Restart client!", flush=True)
                self._socket.close()
                exit(0)

    def _core(self) -> None:
        self._audio_format = pyaudio.paInt16
        self._channels = 1
        self._rate = 20000

        self._audio = pyaudio.PyAudio()
        self._init_receive()
        self._turn_on_receive()
        self._init_send()
        talk_str: str = "Talk"
        while True:
            terminal_menu = TerminalMenu([
                f"[t] {talk_str}",
                "[u] Users",
                "[c] Last speaker",
                "[e] Exit",
            ], title=f"Room key: {self._room_num}")
            answer = terminal_menu.show()
            if answer == 0:
                if self._send_thread is None:
                    self._turn_on_send()
                    talk_str = "Mute"
                    continue
                self._turn_off_send()
                talk_str = "Talk"
            elif answer == 1:
                lst = self._list.get()
                if len(lst) == 0:
                    lst = ["Empty"]
                users = TerminalMenu(
                    lst,
                    title=f"Room key: {self._room_num}. "
                    "Click enter to cancel.",
                    show_search_hint=True
                )
                _ = users.show()
            elif answer == 2:
                while True:
                    users = TerminalMenu(
                        [self._cur_talk, "[c] Cancel"],
                        title=f"Room key: {self._room_num}. "
                        "Click enter on name to refresh."
                    )
                    cl = users.show()
                    if cl == 1:
                        break
            else:
                if answer != 3:
                    print("Restart client!", flush=True)
                else:
                    print("Please wait 5 second!", flush=True)
                self._turn_off_send()
                self._turn_off_receive()
                self._socket.close()
                return

    def _init_send(self) -> None:
        self._recording_stream: tp.Optional[pyaudio.Stream] = None
        self._send_future: tp.Optional[Future] = None
        self._send_thread: tp.Optional[threading.Thread] = None

    def _turn_on_send(self) -> None:
        if self._send_thread is None:
            self._send_future = Future()
            self._recording_stream = self._audio.open(
                format=self._audio_format,
                channels=self._channels,
                rate=self._rate,
                input=True,
                frames_per_buffer=self._buffer
            )
            self._send_thread = threading.Thread(
                target=self._send_data_to_server
            )
            self._send_thread.start()

    def _turn_off_send(self) -> None:
        if self._send_thread is not None:
            self._send_future.set_result(1)
            self._send_thread.join()
            self._recording_stream.close()
            self._recording_stream = None
            self._send_thread = None
            self._send_future = None

    def _init_receive(self) -> None:
        self._playing_stream: tp.Optional[pyaudio.Stream] = None
        self._receive_thread: tp.Optional[threading.Thread] = None
        self._receive_future: tp.Optional[Future] = None

    def _turn_on_receive(self) -> None:
        if self._receive_thread is None:
            self._playing_stream = self._audio.open(
                format=self._audio_format,
                channels=self._channels,
                rate=self._rate,
                output=True,
                frames_per_buffer=self._buffer
            )
            self._receive_future = Future()
            self._receive_thread = threading.Thread(
                target=self._receive_server_data
            )
            self._receive_thread.start()

    def _turn_off_receive(self) -> None:
        if self._receive_thread is not None:
            self._receive_future.set_result(1)
            self._receive_thread.join()
            self._playing_stream.close()
            self._receive_future = None
            self._receive_thread = None
            self._playing_stream = None
            self._list = UserList([])

    def _receive_server_data(self) -> None:
        assert self._receive_future is not None
        while not self._receive_future.done():
            try:
                packet = read_packet(self._socket)
                command = packet.command
                if command.startswith("Add "):
                    self._list.add(packet.data.decode())
                elif command.startswith("Delete "):
                    self._list.delete(packet.data.decode())
                elif command.startswith("Audio "):
                    self._playing_stream.write(packet.data)
                    self._cur_talk = command[len("Audio "):]
                else:
                    print("Restart client!", flush=True)
                    self._turn_off_send()
                    self._turn_off_receive()
                    self._socket.close()
                    exit(1)
            except Exception:
                pass

    def _send_data_to_server(self) -> None:
        assert self._send_future is not None
        while not self._send_future.done():
            try:
                data = self._recording_stream.read(
                    self._buffer, exception_on_overflow=False
                )
                write_packet(
                    self._socket, Packet(f"Audio {self._username}", data)
                )
            except Exception:
                pass


@click.command()
@click.option("--host", default="0.0.0.0", type=str)
@click.option("--port", default=10080, type=int)
@click.option("--username", type=str, prompt=True)
def main(
    host: str,
    port: int,
    username: str,
) -> None:
    Client(host, port, username)


if __name__ == "__main__":
    main()
