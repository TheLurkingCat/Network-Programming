import datetime
import socket
import socketserver

import pymongo

from contentmanager import BoardManager, PostManager
from user import User
from utils import *


class Server(socketserver.StreamRequestHandler):
    def reply(self, response, *args):
        if args:
            self.wfile.write(response.format(*args).encode())
        else:
            self.wfile.write(response)

    def register(self, commands, user):
        if len(commands) != 3:
            self.reply(HELP_REG)
        else:
            username = commands[0]
            password = commands[2]
            if user.register(username, password):
                self.reply(SUCCESS_REGISTER)
                complete("Register successfully!")
            else:
                self.reply(FAIL_REG)
                error("Register failed!")

    def login(self, commands, user):
        if len(commands) != 2:
            self.reply(HELP_LOGIN)
        elif user.is_unauthorized():
            username, password = commands
            if user.login(username, password):
                self.reply("Welcome, {}.\r\n", username)
            else:
                self.reply(FAIL_LOGIN_INCORRECT)
        else:
            self.reply(FAIL_LOGIN_ALREADY)

    def logout(self, user):
        if user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        else:
            self.reply("Bye, {}.\r\n", user.whoami())
            user.logout()

    def whoami(self, user):
        if user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        else:
            self.reply("{}\r\n", user.whoami())

    def create_board(self, board_name, user, board):
        if user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        else:
            if board.not_exist(board_name):
                document = {"board_name": board_name,
                            "mod": user.whoami()
                            }
                board.add_board(document)
                self.reply(SUCCESS_BOARD_CREATED)
            else:
                self.reply(FAIL_BOARD_EXISTS)

    def create_post(self, raw_command, board_name, user, board, post):
        extracted = extract_post(raw_command)
        if user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        elif board.not_exist(board_name):
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
                        'owner': user.whoami(),
                        'date': date,
                        'post_id': None
                        }
            post.add_post(document)
            self.reply(SUCCESS_POST_CREATED)

    def list_board(self, raw_command, board):
        output = [b'\tIndex\tName\tModerator\r\n']
        extracted = extract_keyword(raw_command)
        document = {}
        if extracted is not None:
            keyword = extracted.group(1)
            document["board_name"] = {"$regex": keyword}

        for idx, doc in enumerate(board.list_all(document), start=1):
            output.append('\t{}\t{}\t{}\r\n'.format(
                idx,
                doc['board_name'],
                doc['mod']).encode())

        self.wfile.writelines(output)

    def list_post(self, raw_command, board_name, board, post):
        if board.not_exist(board_name):
            self.reply(FAIL_BOARD_NOT_EXISTS)
            return
        output = [b'\tID\tTitle\tAuthor\tDate\r\n']
        extracted = extract_keyword(raw_command)
        document = {"board_name": board_name}
        if extracted is not None:
            keyword = extracted.group(1)
            document["title"] = {"$regex": keyword}
            for doc in post.list_all(document):
                output.append('\t{}\t{}\t{}\t{}/{}\r\n'.format(
                    doc['post_id'],
                    doc['title'],
                    doc['owner'],
                    *doc['date'][1:]).encode())
            self.wfile.writelines(output)

    def read(self, pid_string, post):
        try:
            postid = int(pid_string)
        except ValueError:
            self.wfile.write(FAIL_POST_NOT_EXISTS)
            return
        if post.not_exist(postid):
            self.wfile.write(FAIL_POST_NOT_EXISTS)
        else:
            output = []
            head = "Author\t:{}\r\nTitle\t:{}\r\nDate\t:{}-{}-{}\r\n".format(
                post['owner'],
                post['title'],
                *post['date']
            )
            output.append(head)
            body = "--\r\n{}\r\n--\r\n".format(post['content'])
            output.append(body)
            for comment in post.list_comment(postid):
                output.append('{}: {}\r\n'.format(
                    comment['owner'],
                    comment['content']))
            self.reply(''.join(output).encode())

    def delete_post(self, pid_string, post, user):
        if user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        else:
            try:
                postid = int(pid_string)
            except ValueError:
                self.reply(FAIL_POST_NOT_EXISTS)
                return
            if post.not_exist(postid):
                self.reply(FAIL_POST_NOT_EXISTS)
                return
            document = {
                "post_id": postid,
                "owner": user.whoami()
            }
            if post.delete(document):
                self.wfile.write(SUCCESS_POST_DELETED)
            else:
                self.wfile.write(FAIL_NOT_OWNER)

    def update_post(self, raw_command, pid_string, post, user):
        if user.is_unauthorized():
            self.reply(FAIL_UNAUTHORIZED)
        try:
            postid = int(pid_string)
        except Exception:
            self.reply(FAIL_POST_NOT_EXISTS)
        if post.not_exist(postid):
            self.reply(FAIL_POST_NOT_EXISTS)
            return
        title, content = extract_title_content(raw_command)
        document = {"post_id": postid,
                    "owner": user.whoami()
                    }
        if title is not None:
            result = post.update(document, {"$set": {"title": title.group(1)}})
        else:
            result = post.update(
                document, {"$set": {"content": content.group(1).replace('<br>', '\r\n')}})
        if result:
            self.reply(SUCCESS_UPDATE_POST)
        else:
            self.reply(FAIL_NOT_OWNER)

    def comment(self, raw_command, pid_string, post,  user):
        if user.is_unauthorized():
            self.wfile.write(FAIL_UNAUTHORIZED)
            return
        try:
            postid = int(pid_string)
        except ValueError:
            self.wfile.write(FAIL_POST_NOT_EXISTS)
            return
        if post.not_exist(postid):
            self.wfile.write(FAIL_POST_NOT_EXISTS)
        else:
            comment = extract_comment(raw_command)
            if comment is None:
                return
            document = {"post_id": postid,
                        "owner": user.whoami(),
                        "content": comment.group(1)}
            post.add_comment(document)
            self.reply(SUCCESS_COMMENT)

    def handle(self):
        print("New connection.")
        print(ONLINE.format(*self.client_address))
        self.wfile.writelines(WELCOME)
        client = pymongo.MongoClient()
        user = User(client)
        board = BoardManager(client)
        post = PostManager(client)
        while True:
            self.reply(PROMPT)

            recv_data = self.rfile.readline()
            if not recv_data:
                break
            try:
                raw_command = recv_data.decode()
            except UnicodeDecodeError:
                error("Decode Error", recv_data)
                continue
            raw_command = apply_backspace(raw_command).strip()
            commands = raw_command.split()
            if not commands:
                continue

            if commands[0] == "register":
                self.register(commands[1:], user)
            elif commands[0] == "login":
                self.login(commands[1:], user)
            elif commands[0] == "logout":
                self.logout(user)
            elif commands[0] == "whoami":
                self.whoami(user)
            elif commands[0] == "create-board":
                self.create_board(commands[1], user, board)
            elif commands[0] == "create-post":
                self.create_post(raw_command, commands[1], user, board, post)
            elif commands[0] == "list-board":
                self.list_board(raw_command, board)
            elif commands[0] == "list-post":
                self.list_post(raw_command, commands[1], board, post)
            elif commands[0] == "read":
                self.read(commands[1], post)
            elif commands[0] == "delete-post":
                self.delete_post(commands[1], post, user)
            elif commands[0] == 'update-post':
                self.update_post(raw_command, commands[1], post, user)
            elif commands[0] == "comment":
                self.comment(raw_command, commands[1], post,  user)
            elif commands[0] == "exit":
                print(OFFLINE.format(*self.client_address))
                break
            else:
                error("Unknown command:", commands)
        self.request.shutdown(socket.SHUT_RDWR)
        self.request.close()
