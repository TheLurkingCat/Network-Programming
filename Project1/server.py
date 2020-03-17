#!/usr/bin/python3
import socketserver
import sys

import pymongo

WELCOME = "********************************\n\
** Welcome to the BBS server. **\n\
********************************\n".encode()

PROMPT = "% ".encode()

HELP_REG = "Usage: register <username> <email> <password>\n".encode()
HELP_LOGIN = "Usage: login <username> <password>\n".encode()
FAIL_REG = "Username is already used.\n".encode()
FAIL_LOGIN_ALREADY = "Please logout first.\n".encode()
FAIL_LOGIN_INCORRECT = "Login failed.\n".encode()
FAIL_LOGOUT_UNAUTH = "Please login first.\n".encode()
FAIL_UNAUTHORIZED = "Please login first.\n".encode()


class Server(socketserver.BaseRequestHandler):
    def handle(self):
        print("New connection.")
        print(self.client_address)
        self.request.sendall(WELCOME)
        client = pymongo.MongoClient()['NP']['user']
        authorized = False
        name = None
        while True:
            self.request.sendall(PROMPT)
            recv_data = self.request.recv(4096)
            if not recv_data:
                break
            try:
                commands = recv_data.decode().strip().split()
            except UnicodeDecodeError:
                print("Decode Error")
                continue
            if commands[0] == "register":
                if len(commands) != 4:
                    self.request.sendall(HELP_REG)
                    continue
                _, username, email, password = commands
                if client.find_one({"username": username}) is not None:
                    self.request.sendall(FAIL_REG)
                else:
                    client.insert_one(
                        {"username": username, "email": email, "password": password})
            elif commands[0] == "login":
                if len(commands) != 3:
                    self.request.sendall(HELP_LOGIN)
                    continue
                _, username, password = commands
                if authorized:
                    self.request.sendall(FAIL_LOGIN_ALREADY)
                elif client.find_one({"username": username, "password": password}) is None:
                    self.request.sendall(FAIL_LOGIN_INCORRECT)
                else:
                    authorized = True
                    name = username
                    self.request.sendall(
                        "Welcome, {}.\n".format(name).encode())
            elif commands[0] == "logout":
                if not authorized:
                    self.request.sendall(FAIL_UNAUTHORIZED)
                else:
                    self.request.sendall("Bye, {}.\n".format(name).encode())
                    authorized = False
                    name = None
            elif commands[0] == "whoami":
                if not authorized:
                    self.request.sendall(FAIL_UNAUTHORIZED)
                else:
                    self.request.sendall("{}\n".format(name).encode())

            elif commands[0] == "exit":
                print(self.client_address, " closed the connection.")
                self.request.close()
                break
            else:
                print(recv_data)


server = socketserver.ThreadingTCPServer(("", int(sys.argv[1])), Server)
server.serve_forever()
