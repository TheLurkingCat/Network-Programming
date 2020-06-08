#!/usr/bin/env python
import datetime
import socket
import socketserver
import struct
import sys
import threading
from collections import defaultdict
from queue import Queue
from time import sleep

import pymongo

from asciitree import LeftAligned
from contentmanager import BoardManager, PostManager, SubscribeManager
from user import User
from utils import *

subscribe_data = {}
online_user = set()


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
            "comment": self.comment,
            "subscribe": self.subscribe,
            "unsubscribe": self.unsubscribe,
            "list-sub": self.list_sub
        }
        self.tree_format = LeftAligned()
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
                    message = subscribe_data[username].get()
                    self.reply("*** {}在{}發表了標題為{}的文章 ***", *message)

    def reply(self, response, *args):
        if args:
            response = response.format(*args)
        if isinstance(response, str):
            response = response.encode()
        if not isinstance(response, bytes):
            raise ValueError(
                "Expected bytes, but get {}".format(type(response)))
        self.wfile.write(struct.pack('<H', len(response)) + response)

    def recv_command(self):
        try:
            length = struct.unpack('<H', self.rfile.read(2))[0]
        except (struct.error, OSError):
            return "exit"
        return self.rfile.read(length).decode()

    @fallback
    def register(self):
        username = self.commands[0]
        password = self.commands[2]
        if self.user.register(username, password):
            self.reply(b"Register successfully.")
        else:
            self.reply(b"Username is already used.")

    @fallback
    def login(self):
        if self.user.is_unauthorized():
            username, password = self.commands
            if self.user.login(username, password):
                self.reply("Welcome, {}.", username)
                online_user.add(username)
                subscribe_data[username] = Queue()
            else:
                self.reply(b"Login failed.")
        else:
            self.reply(b"Please logout first.")

    @fallback
    @login_required
    def logout(self):
        username = self.user.whoami()
        self.user.logout()
        online_user.remove(username)
        del subscribe_data[username]
        self.reply("Bye, {}.", username)

    @fallback
    @login_required
    def whoami(self):
        self.reply(self.user.whoami())

    @fallback
    @login_required
    @board_existance(False)
    def create_board(self):
        board_name = self.commands[0]
        document = {
            "board_name": board_name,
            "mod": self.user.whoami()
        }
        self.board.add_board(document)
        self.reply(b"Create board successfully.")

    @fallback
    @login_required
    @board_existance(True)
    def create_post(self):
        board_name = self.commands[0]
        extracted = NEWPOST.match(self.raw_command)
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
        boards, authors = self.sub.find_subscriber(
            board_name, self.user.whoami())
        note = set()
        message = (
            self.user.whoami(),
            board_name,
            title
        )
        for doc in boards:
            if doc['user'] in online_user and doc['keyword'] in title:
                note.add((doc['user'], message))
        for doc in authors:
            if doc['user'] in online_user and doc['keyword'] in title:
                note.add((doc['user'], message))
        for data in note:
            subscribe_data[data[0]].put(data[1])
        self.post.add_post(document)
        self.reply(b"Create post successfully")

    @fallback
    def list_board(self):
        output = ['Index\tName\tModerator']
        extracted = KEYWORD.match(self.raw_command)
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

    @fallback
    @board_existance(True)
    def list_post(self):
        board_name = self.commands[0]
        output = ['ID\tTitle\tAuthor\tDate']
        extracted = KEYWORD.match(self.raw_command)
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

    @fallback
    @parameter_check(1)
    @post_existance
    def read(self):
        """Usage: read <postid>"""
        postid = int(self.commands[0])
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

    @fallback
    @parameter_check(1)
    @login_required
    @post_existance
    def delete_post(self):
        """Usage: delete-post <post-id>"""
        postid = int(self.commands[0])
        document = {
            "post_id": postid,
            "owner": self.user.whoami()
        }

        if self.post.delete(document):
            self.reply(b"Delete successfully.")
        else:
            self.reply(b"Not the post owner.")

    @fallback
    @login_required
    @post_existance
    def update_post(self):
        postid = int(self.commands[0])
        title = TITLE.match(self.raw_command)
        content = CONTENT.match(self.raw_command)
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

    @fallback
    @parameter_check(COMMENT)
    @login_required
    @post_existance
    def comment(self):
        """Usage: comment <postid> <message>"""
        postid = int(self.commands[0])
        comment = COMMENT.match(self.raw_command)
        document = {
            "post_id": postid,
            "owner": self.user.whoami(),
            "content": comment.group(1)
        }
        self.post.comment(document)
        self.reply(b"Comment successfully.")

    @fallback
    @parameter_check(SUBSCRIPTION)
    @login_required
    def subscribe(self):
        """Usage: subscribe --(board|author) <(boardname|authorname)> --keyword <keyword>"""
        extracted = SUBSCRIPTION.match(self.raw_command)
        if self.sub.subscribe(
            self.user.whoami(),
            extracted.group(1),
            extracted.group(2),
            extracted.group(3)
        ):
            self.reply(b'Subscribe successfully.')
        else:
            self.reply(b'Already subscribed.')

    @fallback
    @parameter_check(UNSUBSCRIPTION)
    @login_required
    def unsubscribe(self):
        """Usage: unsubscribe --(board|author) <(boardname|authorname)>"""
        extracted = UNSUBSCRIPTION.match(self.raw_command)
        if self.sub.unsubscribe(
            self.user.whoami(),
            extracted.group(1),
            extracted.group(2)
        ):
            self.reply(b'Unsubscribe successfully.')
        else:
            self.reply("You haven't subscribed {}", extracted.group(2))

    @fallback
    @parameter_check(0)
    @login_required
    def list_sub(self):
        """Usage: list-sub"""
        output = defaultdict(lambda: defaultdict(
            lambda: defaultdict(dict)))
        root = output["{}'s subscription".format(self.user.whoami())]
        result = self.sub.list_all(self.user.whoami())
        for subinfo in result:
            root[subinfo['type'].capitalize()][subinfo['info']
                                               ][subinfo['keyword']] = {}
        self.reply(self.tree_format(output))

    def handle(self):
        print("New connection.")
        print(ONLINE.format(*self.client_address))
        self.reply(WELCOME)
        client = pymongo.MongoClient()
        self.user = User(client)
        self.board = BoardManager(client)
        self.post = PostManager(client)
        self.sub = SubscribeManager(client)
        notify = threading.Thread(target=self.check_self)
        notify.daemon = True
        notify.start()
        while True:
            self.raw_command = self.recv_command().strip()
            self.commands = self.raw_command.split()
            if not self.commands:
                continue

            if self.commands[0] == "exit":
                print(OFFLINE.format(*self.client_address))
                if not self.user.is_unauthorized():
                    username = self.user.whoami()
                    self.user.logout()
                    sleep(0.1)
                    while not subscribe_data[username].empty():
                        self.reply(subscribe_data[username].get())
                    online_user.remove(username)
                    del subscribe_data[username]
                break
            if self.commands[0] in self.function:
                func = self.function[self.commands[0]]
                del self.commands[0]
                func()
            else:
                print("Unknown command:", self.commands)
                self.reply("Unknown command: " + self.raw_command)

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
    print("Server is running on port", port)
    print("Waiting for connections.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\b\b", end="")
        print("Shutting down server.")
        server.shutdown()
        print("Server closed.")
        print("Resetting database.")
        client = pymongo.MongoClient()
        client['NP']['user'].drop()
        client['NP']['board'].drop()
        client['NP']['sub'].drop()
        client['NP']['seq_num'].update_one(
            {}, {"$set": {"id": 1}}, upsert=True)
        client['NP']['post'].drop()
        client['NP']['comment'].drop()
        print("All table reset.")


if __name__ == '__main__':
    main()
