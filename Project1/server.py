#!/usr/bin/python3
import re
import socket
import socketserver
import sys

import pymongo
from colorama import Fore, Style

WELCOME = [b"********************************\r\n",
           b"** Welcome to the BBS server. **\r\n",
           b"********************************\r\n"]

PROMPT = b"% "
WAITING = Fore.YELLOW + "[ ... ]" + Style.RESET_ALL
COMPLETE = Fore.GREEN + "[ OK ]" + Style.RESET_ALL
ERROR = Fore.RED + "[ FAIL ]" + Style.RESET_ALL
HELP_REG = b"Usage: register <username> <email> <password>\r\n"
HELP_LOGIN = b"Usage: login <username> <password>\r\n"
FAIL_REG = b"Username is already used.\r\n"
FAIL_LOGIN_ALREADY = b"Please logout first.\r\n"
FAIL_LOGIN_INCORRECT = b"Login failed.\r\n"
FAIL_UNAUTHORIZED = b"Please login first.\r\n"
SUCESS_REGISTER = b"Register successfully.\r\n"
APPLY_BACKSPACE = re.compile('[^\x08]\x08')
REMOVE_TRAILING_BACKSPACE = re.compile('\x08+')


def apply_backspace(string):
    while True:
        temp_string = APPLY_BACKSPACE.sub('', string)
        if len(string) == len(temp_string):
            return REMOVE_TRAILING_BACKSPACE.sub('', temp_string)
        string = temp_string


class Server(socketserver.StreamRequestHandler):
    def handle(self):
        print("New connection.")
        print(
            COMPLETE + " Client {}{}:{}{} starts the connection.".format(Fore.MAGENTA, *self.client_address, Style.RESET_ALL))
        self.wfile.writelines(WELCOME)
        client = pymongo.MongoClient()
        collection = client['NP']['user']
        name = None
        while True:
            self.wfile.write(PROMPT)
            recv_data = self.rfile.readline()
            if not recv_data:
                break
            try:
                commands = recv_data.decode()
            except UnicodeDecodeError:
                print(ERROR + " Decode Error", end=' ')
                print(recv_data)
                continue
            commands = apply_backspace(commands)
            commands = commands.strip().split()
            if not commands:
                continue

            if commands[0] == "register":
                if len(commands) != 4:
                    self.wfile.write(HELP_REG)
                else:
                    _, username, email, password = commands
                    if collection.find_one({"username": username}) is None:
                        collection.insert_one(
                            {"username": username, "email": email, "password": password})
                        self.wfile.write(SUCESS_REGISTER)
                    else:
                        self.wfile.write(FAIL_REG)
            elif commands[0] == "login":
                if len(commands) != 3:
                    self.wfile.write(HELP_LOGIN)
                elif name is None:
                    _, username, password = commands
                    if collection.find_one({"username": username, "password": password}) is None:
                        self.wfile.write(FAIL_LOGIN_INCORRECT)
                    else:
                        name = username
                        self.wfile.write(
                            "Welcome, {}.\r\n".format(name).encode())
                else:
                    self.wfile.write(FAIL_LOGIN_ALREADY)

            elif commands[0] == "logout":
                if name is None:
                    self.wfile.write(FAIL_UNAUTHORIZED)
                else:
                    self.wfile.write("Bye, {}.\r\n".format(name).encode())
                    name = None
            elif commands[0] == "whoami":
                if name is None:
                    self.wfile.write(FAIL_UNAUTHORIZED)
                else:
                    self.wfile.write("{}\r\n".format(name).encode())

            elif commands[0] == "exit":
                print(COMPLETE + " Client {}{}:{}{} closes the connection.".format(
                    Fore.MAGENTA, *self.client_address, Style.RESET_ALL))
                break
            else:
                print(ERROR + " Unknown command:", commands)
        self.request.shutdown(socket.SHUT_RDWR)
        self.request.close()


def main():
    try:
        port = int(sys.argv[1])
    except IndexError:
        port = 5000
    socketserver.ForkingTCPServer.allow_reuse_address = True
    server = socketserver.ForkingTCPServer(("0.0.0.0", port), Server)
    print(COMPLETE + " Server is running on port", port)
    print(WAITING + " Waiting for connections.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\b\b" + WAITING + " Shutting down server.")
        server.shutdown()
        print(COMPLETE + " Server closed.")
        print(WAITING + " Cleaning up database.")
        client = pymongo.MongoClient()
        client['NP']['user'].drop()
        print(COMPLETE + " All table dropped.")


if __name__ == '__main__':
    main()
