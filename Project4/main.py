#!/usr/bin/python3
import datetime
import socket
import socketserver
import struct
import sys
from queue import Queue
from time import sleep
import pymongo
from contentmanager import BoardManager, PostManager
from user import User
from utils import *

subscribe_data = {}
online_user = {}


class Server(socketserver.StreamRequestHandler):
    def __init__(self, *args):
        self.function = {
            "register": self.register,
            "login": self.login,
            "logout": self.logout,
            "whoami": self.whoami,
            "create-board": self.create_board,
            "create-post": self.create_post,
            "list-board": self.list_board,
            "list-post": self.list_post,
            "read": self.read,
            "delete-post": self.delete_post,
            "update-post": self.update_post,
            "comment": self.comment
        }
        super().__init__(*args)

    def check_self(self):
        while True:
            if self.user.is_unauthorized():
                sleep(0.1)
            else:
                username = self.user.whoami()
                if subscribe_data[username].empty():
                    sleep(0.1)
                else:
                    self.reply(subscribe_data[username].get())

    def reply(self, response, *args):
        if args:
            response = response.format(*args)
        if isinstance(response, str):
            response = response.encode()
        if not isinstance(response, bytes):
            raise ValueError("Not bytes")
        self.wfile.write(struct.pack('<H', len(response)) + response)

    def recv_command(self):
        try:
            length = struct.unpack('<H', self.rfile.read(2))[0]
        except (struct.error, OSError):
            return "exit"
        return self.rfile.read(length).decode()

    def register(self):
        username = self.commands[0]
        password = self.commands[2]
        if self.user.register(username, password):
            self.reply(b"Register successfully.")
        else:
            self.reply(b"Username is already used.")

    def login(self):
        if self.user.is_unauthorized():
            username, password = self.commands
            if self.user.login(username, password):
                self.reply("Welcome, {}.", username)
                if username in online_user:
                    online_user[username] += 1
                else:
                    online_user[username] = 1
                    subscribe_data[username] = Queue()
            else:
                self.reply(b"Login failed.")
        else:
            self.reply(b"Please logout first.")

    def logout(self):
        if self.user.is_unauthorized():
            self.reply(b"Please login first.")
        else:
            username = self.user.whoami()
            self.user.logout()
            if online_user[username] == 1:
                del online_user[username]
                del subscribe_data[username]
            else:
                online_user[username] -= 1
            self.reply("Bye, {}.", self.user.whoami())

    def whoami(self):
        if self.user.is_unauthorized():
            self.reply(b"Please login first.")
        else:
            self.reply(self.user.whoami())

    def create_board(self):
        board_name = self.commands[0]
        if self.user.is_unauthorized():
            self.reply(b"Please login first.")
        elif self.board.not_exist(board_name):
            document = {
                "board_name": board_name,
                "mod": self.user.whoami()
            }
            self.board.add_board(document)
            self.reply(b"Create board successfully.")
        else:
            self.reply(b"Board already exist.")

    def create_post(self):
        board_name = self.commands[0]
        extracted = extract_post(self.raw_command)
        if self.user.is_unauthorized():
            self.reply(b"Please login first.")
        elif self.board.not_exist(board_name):
            self.reply(b"Board does not exist.")
        else:
            title = extracted.group(1)
            content = extracted.group(2).replace('<br>', '\r\n')
            date = list(datetime.datetime.now(TIMEZONE).timetuple()[:3])
            document = {
                'board_name': board_name,
                'title': title,
                'content': content,
                'owner': self.user.whoami(),
                'date': date,
                'post_id': None
            }
            self.post.add_post(document)
            self.reply(b"Create post successfully")

    def list_board(self):
        output = ['Index\tName\tModerator']
        extracted = extract_keyword(self.raw_command)
        document = {}
        if extracted is not None:
            keyword = extracted.group(1)
            document["board_name"] = {"$regex": keyword}

        for idx, doc in enumerate(self.board.list_all(document), start=1):
            output.append('{}\t{}\t{}'.format(
                idx,
                doc['board_name'],
                doc['mod']
            ))
        self.reply('\r\n'.join(output))

    def list_post(self):
        board_name = self.commands[0]
        if self.board.not_exist(board_name):
            self.reply(b"Board does not exist.")
            return
        output = ['ID\tTitle\tAuthor\tDate']
        extracted = extract_keyword(self.raw_command)
        document = {"board_name": board_name}
        if extracted is not None:
            keyword = extracted.group(1)
            document["title"] = {"$regex": keyword}

        for doc in self.post.list_all(document):
            output.append('{}\t{}\t{}\t{:02d}/{:02d}'.format(
                doc['post_id'],
                doc['title'],
                doc['owner'],
                *doc['date'][1:]
            ))
        self.reply('\r\n'.join(output))

    def read(self):
        try:
            postid = int(self.commands[0])
        except Exception:
            self.reply(b"Post does not exist.")
            return

        if self.post.not_exist(postid):
            self.reply(b"Post does not exist.")
            return

        document = self.post.read(postid)
        output = []
        head = "Author: {}\r\nTitle:  {}\r\nDate:   {:04d}-{:02d}-{:02d}".format(
            document['owner'],
            document['title'],
            *document['date']
        )
        output.append(head)
        body = "--\r\n{}\r\n--".format(document['content'])
        output.append(body)
        for comment in self.post.list_comment(postid):
            output.append('{}: {}'.format(
                comment['owner'],
                comment['content']
            ))
        self.reply('\r\n'.join(output))

    def delete_post(self):
        if self.user.is_unauthorized():
            self.reply("Please login first.")
            return
        try:
            postid = int(self.commands[0])
        except Exception:
            self.reply(b"Post does not exist.")
            return
        if self.post.not_exist(postid):
            self.reply(b"Post does not exist.")
            return

        document = {
            "post_id": postid,
            "owner": self.user.whoami()
        }

        if self.post.delete(document):
            self.reply(b"Delete successfully.")
        else:
            self.reply(b"Not the post owner.")

    def update_post(self):
        if self.user.is_unauthorized():
            self.reply(b"Please login first.")
            return
        try:
            postid = int(self.commands[0])
        except Exception:
            self.reply(b"Post does not exist.")
            return
        if self.post.not_exist(postid):
            self.reply(b"Post does not exist.")
            return

        title, content = extract_title_content(self.raw_command)
        document = {
            "post_id": postid,
            "owner": self.user.whoami()
        }

        if title is not None:
            result = self.post.update(
                document, {"$set": {"title": title.group(1)}})
        elif content is not None:
            result = self.post.update(
                document, {"$set": {"content": content.group(1).replace('<br>', '\r\n')}})
        else:
            result = False

        if result:
            self.reply(b"Update successfully.")
        else:
            self.reply(b"Not the post owner.")

    def comment(self):
        if self.user.is_unauthorized():
            self.reply(b"Please login first.")
            return
        try:
            postid = int(self.commands[0])
        except Exception:
            self.reply(b"Post does not exist.")
            return
        if self.post.not_exist(postid):
            self.reply(b"Post does not exist.")
        else:
            comment = extract_comment(self.raw_command)
            document = {
                "post_id": postid,
                "owner": self.user.whoami(),
                "content": comment.group(1)
            }
            self.post.comment(document)
            self.reply(b"Comment successfully.")

    def handle(self):
        print("New connection.")
        print(ONLINE.format(*self.client_address))
        self.reply(WELCOME)
        client = pymongo.MongoClient()
        self.user = User(client)
        self.board = BoardManager(client)
        self.post = PostManager(client)
        while True:
            self.raw_command = self.recv_command().strip()
            self.commands = self.raw_command.split()
            if not self.commands:
                continue

            if self.commands[0] == "exit":
                print(OFFLINE.format(*self.client_address))
                if not self.user.is_unauthorized():
                    while not subscribe_data[self.user.whoami()].empty():
                        sleep(0.1)
                break
            func = self.function.get(self.commands[0])
            if func is None:
                error("Unknown command:", self.commands)
                self.reply(b'')
            else:
                del self.commands[0]
                func()
        self.request.shutdown(socket.SHUT_RDWR)
        self.request.close()


def main():
    try:
        port = int(sys.argv[1])
    except IndexError:
        port = 5000

    default_server = socketserver.ThreadingTCPServer
    default_server.allow_reuse_address = True
    server = default_server(("0.0.0.0", port), Server)
    complete("Server is running on port", port)
    waiting("Waiting for connections.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\b\b", end="")
        waiting("Shutting down server.")
        server.shutdown()
        complete("Server closed.")
        waiting("Resetting database.")
        client = pymongo.MongoClient()
        client['NP']['user'].drop()
        client['NP']['board'].drop()
        client['NP']['seq_num'].update_one(
            {}, {"$set": {"id": 1}}, upsert=True)
        client['NP']['post'].drop()
        client['NP']['comment'].drop()
        complete("All table reset.")


if __name__ == '__main__':
    main()
