import socket
import socketserver
import typing

import pymongo

from constant import WELCOME, backspace, fail, success, usage
from user import User


class Server(socketserver.StreamRequestHandler):
    def __init__(self, *args):
        self.function = {
            "register": self.register,
            "login": self.login,
            "logout": self.logout,
            "whoami": self.whoami
        }
        self.connection_close = False
        super().__init__(*args)

    def reply(self, response: typing.Union[str, bytes], *args):
        if args:
            response = response.format(*args)
        if isinstance(response, str):
            response = response.encode()
        self.wfile.write(response)

    def receive(self) -> typing.List[str]:
        recv = self.rfile.readline().decode()
        recv = backspace(recv)
        return recv.strip().split()

    def register(self):
        if len(self.commands) != 4:
            self.reply(usage("register"))
        else:
            username, _, password = self.commands
            if self.user.register(username, password):
                self.reply(success("register"))
            else:
                self.reply(fail("username_exists"))

    def login(self):
        if len(self.commands) != 3:
            self.reply(usage("login"))
        elif self.user.is_unauthorized():
            username, password = self.commands
            if self.user.login(username, password):
                self.reply("Welcome, {}.\r\n", username)
            else:
                self.reply(fail("login_incorrect"))
        else:
            self.reply(fail("login_already"))

    def logout(self):
        if self.user.is_unauthorized():
            self.reply(fail("unauthorized"))
        else:
            self.user.logout()
            self.reply("Bye, {}.\r\n", self.user.username)

    def whoami(self):
        if self.user.is_unauthorized():
            self.reply(fail("unauthorized"))
        else:
            self.wfile.write("{}\r\n", self.user.username)

    def exit(self):
        self.connection_close = True

    def handle(self):
        print("New connection.")
        self.reply(WELCOME)
        client = pymongo.MongoClient(serverSelectionTimeoutMS=1)
        self.user = User(client)
        while not self.connection_close:
            self.reply(b"% ")
            self.commands = self.receive()
            if not self.commands:
                continue
            selection = self.commands[0]
            del self.commands[0]
            try:
                getattr(self, selection)()
            except AttributeError:
                print("Unknown command:", self.commands)
        self.request.shutdown(socket.SHUT_RDWR)
        self.request.close()
