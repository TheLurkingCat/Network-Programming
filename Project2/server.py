import datetime
import socket
import socketserver

import pymongo

from contentmanager import BoardManager, PostManager
from user import User
from utils import *


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

    def reply(self, response, *args):
        if args:
            self.wfile.write(response.format(*args).encode())
        else:
            self.wfile.write(response)

    def register(self):
        commands = self.commands[1:]
        if len(commands) != 3:
            self.reply(HELP_REG)
        else:
            username = commands[0]
            password = commands[2]
            if self.user.register(username, password):
                self.reply(SUCCESS_REGISTER)
            else:
                self.reply(FAIL_REG)

    def login(self):
        commands = self.commands[1:]
        if len(commands) != 2:
            self.reply(HELP_LOGIN)
        elif self.user.is_unauthorized():
            username, password = commands
            if self.user.login(username, password):
                self.reply("Welcome, {}.\r\n", username)
            else:
                self.reply(FAIL_LOGIN_INCORRECT)
        else:
            self.reply(FAIL_LOGIN_ALREADY)

    def logout(self):
        if self.user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        else:
            self.reply("Bye, {}.\r\n", self.user.whoami())
            self.user.logout()

    def whoami(self):
        if self.user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        else:
            self.reply("{}\r\n", self.user.whoami())

    def create_board(self):
        board_name = self.commands[1]
        if self.user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        else:
            if self.board.not_exist(board_name):
                document = {"board_name": board_name,
                            "mod": self.user.whoami()
                            }
                self.board.add_board(document)
                self.reply(SUCCESS_BOARD_CREATED)
            else:
                self.reply(FAIL_BOARD_EXISTS)

    def create_post(self):
        board_name = self.commands[1]
        extracted = extract_post(self.raw_command)
        if self.user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        elif self.board.not_exist(board_name):
            self.reply(FAIL_BOARD_NOT_EXISTS)
        elif extracted is None:
            self.reply(HELP_CREATE_POST)
        else:
            title = extracted.group(1)
            content = extracted.group(2).replace('<br>', '\r\n')
            date = list(datetime.datetime.now(TIMEZONE).timetuple()[:3])
            document = {'board_name': board_name,
                        'title': title,
                        'content': content,
                        'owner': self.user.whoami(),
                        'date': date,
                        'post_id': None
                        }
            self.post.add_post(document)
            self.reply(SUCCESS_POST_CREATED)

    def list_board(self):
        output = [b'\tIndex\tName\tModerator\r\n']
        extracted = extract_keyword(self.raw_command)
        document = {}
        if extracted is not None:
            keyword = extracted.group(1)
            document["board_name"] = {"$regex": keyword}

        for idx, doc in enumerate(self.board.list_all(document), start=1):
            output.append('\t{}\t{}\t{}\r\n'.format(
                idx,
                doc['board_name'],
                doc['mod']).encode())

        self.wfile.writelines(output)

    def list_post(self):
        board_name = self.commands[1]
        if self.board.not_exist(board_name):
            self.reply(FAIL_BOARD_NOT_EXISTS)
            return
        output = [b'\tID\tTitle\tAuthor\tDate\r\n']
        extracted = extract_keyword(self.raw_command)
        document = {"board_name": board_name}
        if extracted is not None:
            keyword = extracted.group(1)
            document["title"] = {"$regex": keyword}
        for doc in self.post.list_all(document):
            output.append('\t{}\t{}\t{}\t{:02d}/{:02d}\r\n'.format(
                doc['post_id'],
                doc['title'],
                doc['owner'],
                *doc['date'][1:]).encode())
        self.wfile.writelines(output)

    def read(self):
        try:
            postid = int(self.commands[1])
        except ValueError:
            self.reply(FAIL_POST_NOT_EXISTS)
            return
        if self.post.not_exist(postid):
            self.reply(FAIL_POST_NOT_EXISTS)
        else:
            document = self.post.read(postid)
            output = []
            head = "Author\t:{}\r\nTitle\t:{}\r\nDate\t:{:04d}-{:02d}-{:02d}\r\n".format(
                document['owner'],
                document['title'],
                *document['date']
            )
            output.append(head)
            body = "--\r\n{}\r\n--\r\n".format(document['content'])
            output.append(body)
            for comment in self.post.list_comment(postid):
                output.append('{}: {}\r\n'.format(
                    comment['owner'],
                    comment['content']))
            self.reply(''.join(output).encode())

    def delete_post(self):
        if self.user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        else:
            try:
                postid = int(self.commands[1])
            except ValueError:
                self.reply(FAIL_POST_NOT_EXISTS)
                return
            if self.post.not_exist(postid):
                self.reply(FAIL_POST_NOT_EXISTS)
                return
            document = {
                "post_id": postid,
                "owner": self.user.whoami()
            }
            if self.post.delete(document):
                self.reply(SUCCESS_POST_DELETED)
            else:
                self.reply(FAIL_NOT_OWNER)

    def update_post(self):
        if self.user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        try:
            postid = int(self.commands[1])
        except ValueError:
            self.reply(FAIL_POST_NOT_EXISTS)
        if self.post.not_exist(postid):
            self.reply(FAIL_POST_NOT_EXISTS)
            return
        title, content = extract_title_content(self.raw_command)
        document = {"post_id": postid,
                    "owner": self.user.whoami()
                    }
        if title is not None:
            result = self.post.update(
                document, {"$set": {"title": title.group(1)}})
        else:
            result = self.post.update(
                document, {"$set": {"content": content.group(1).replace('<br>', '\r\n')}})
        if result:
            self.reply(SUCCESS_UPDATE_POST)
        else:
            self.reply(FAIL_NOT_OWNER)

    def comment(self):
        if self.user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
            return
        try:
            postid = int(self.commands[1])
        except ValueError:
            self.reply(FAIL_POST_NOT_EXISTS)
            return
        if self.post.not_exist(postid):
            self.reply(FAIL_POST_NOT_EXISTS)
        else:
            comment = extract_comment(self.raw_command)
            if comment is None:
                return
            document = {"post_id": postid,
                        "owner": self.user.whoami(),
                        "content": comment.group(1)}
            self.post.comment(document)
            self.reply(SUCCESS_COMMENT)

    def handle(self):
        print("New connection.")
        print(ONLINE.format(*self.client_address))
        self.wfile.writelines(WELCOME)
        client = pymongo.MongoClient()
        self.user = User(client)
        self.board = BoardManager(client)
        self.post = PostManager(client)
        while True:
            self.reply(PROMPT)

            recv_data = self.rfile.readline()
            if not recv_data:
                break
            try:
                recv_data = recv_data.decode()
            except UnicodeDecodeError:
                error("Decode Error", recv_data)
                continue
            self.raw_command = apply_backspace(recv_data).strip()
            self.commands = self.raw_command.split()
            if not self.commands:
                continue

            if self.commands[0] == "exit":
                print(OFFLINE.format(*self.client_address))
                break
            func = self.function.get(self.commands[0])
            if func is None:
                error("Unknown command:", self.commands)
            else:
                func()
        self.request.shutdown(socket.SHUT_RDWR)
        self.request.close()
