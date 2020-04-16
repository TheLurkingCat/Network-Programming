#!/usr/bin/python3
import datetime
import re
import socket
import socketserver
import sys

import pymongo

WELCOME = [b"********************************\r\n",
           b"** Welcome to the BBS server. **\r\n",
           b"********************************\r\n"]
READ_POST_FORMAT = "Author\t:{}\r\nTitle\t:{}\r\nDate\t:{}\r\n--\r\n{}\r\n--\r\n"
PROMPT = b"% "

HELP_REG = b"Usage: register <username> <email> <password>\r\n"
HELP_LOGIN = b"Usage: login <username> <password>\r\n"
HELP_CREATE_BOARD = b"Usage: create-board <name>\r\n"
HELP_CREATE_POST = b"Usage: create-post <board-name> --title <title> --content <content>\r\n"
HELP_LIST_BOARD = b"list-board ##<key>\r\n"
HELP_LIST_POST = b"list-post <board-name> ##<key>\r\n"
HELP_READ_POST = b"read <post-id>\r\n"
HELP_DELETE_POST = b"delete-post <post-id>\r\n"
HELP_UPDATE_POST = b"update-post <post-id> --title/content <new>\r\n"
HELP_COMMENT = b"comment <post-id> <comment>\r\n"
FAIL_REG = b"Username is already used.\r\n"
FAIL_LOGIN_ALREADY = b"Please logout first.\r\n"
FAIL_LOGIN_INCORRECT = b"Login failed.\r\n"
FAIL_UNAUTHORIZED = b"Please login first.\r\n"
FAIL_BOARD_EXISTS = b"Board is already exist.\r\n"
FAIL_BOARD_NOT_EXISTS = b"Board is not exist.\r\n"
FAIL_POST_NOT_EXISTS = b"Post is not exist.\r\n"
FAIL_NOT_OWNER = b"Not the post owner.\r\n"
SUCESS_BOARD_CREATED = b"Create board successfully.\r\n"
SUCESS_POST_CREATED = b"Create post successfully\r\n"
SUCESS_POST_DELETED = b"Delete successfully.\r\n"
SUCESS_COMMENT = b"Comment successfully.\r\n"
APPLY_BACKSPACE = re.compile('[^\x08]\x08')
REMOVE_TRAILING_BACKSPACE = re.compile('\x08+')
TIMEZONE = datetime.timezone(datetime.timedelta(hours=8))


def apply_backspace(string):
    while True:
        temp_string = APPLY_BACKSPACE.sub('', string)
        if len(string) == len(temp_string):
            return REMOVE_TRAILING_BACKSPACE.sub('', temp_string)
        string = temp_string


class Server(socketserver.StreamRequestHandler):
    def handle(self):
        print("New connection.")
        print(self.client_address, "start the connection.")
        self.wfile.writelines(WELCOME)
        client = pymongo.MongoClient()
        users = client['NP']['user']
        boards = client['NP']['board']
        posts = client['NP']['post']
        comments = client['NP']['comment']
        name = None
        while True:
            self.wfile.write(PROMPT)
            recv_data = self.rfile.readline()
            if not recv_data:
                break
            try:
                recv_data = recv_data.decode()
            except UnicodeDecodeError:
                print("Decode Error")
                continue
            recv_data = apply_backspace(recv_data).strip()
            commands = recv_data.split()
            if not commands:
                continue

            if commands[0] == "register":
                if len(commands) != 4:
                    self.wfile.write(HELP_REG)
                else:
                    _, username, email, password = commands
                    if users.find_one({"username": username}) is None:
                        users.insert_one(
                            {"username": username, "email": email, "password": password})
                    else:
                        self.wfile.write(FAIL_REG)
            elif commands[0] == "login":
                if len(commands) != 3:
                    self.wfile.write(HELP_LOGIN)
                elif name is None:
                    _, username, password = commands
                    if users.find_one({"username": username, "password": password}) is None:
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
                print(self.client_address, "closed the connection.")
                break
            elif commands[0] == "create-board":
                if len(commands) != 2:
                    self.wfile.write(HELP_CREATE_BOARD)
                elif name is None:
                    self.wfile.write(FAIL_UNAUTHORIZED)
                else:
                    board_name = commands[1]
                    board = boards.find_one({"board_name": board_name})
                    if board is not None:
                        self.wfile.write(FAIL_BOARD_EXISTS)
                    else:
                        boards.insert_one(
                            {"board_name": board_name, "mod": name})
                        self.wfile.write(SUCESS_BOARD_CREATED)
            elif commands[0] == "create-post":
                if len(commands) < 6:
                    self.wfile.write(HELP_CREATE_POST)
                elif name is None:
                    self.wfile.write(FAIL_UNAUTHORIZED)
                elif boards.find_one({"board_name": commands[1]}) is None:
                    self.wfile.write(FAIL_BOARD_NOT_EXISTS)
                else:
                    extracted = re.match(
                        r'.*--title (.*) --content (.*)', recv_data)
                    if extracted is None:
                        self.wfile.write(HELP_CREATE_POST)
                    else:
                        title = extracted.group(1)
                        content = extracted.group(2)
                        date = datetime.datetime.now(TIMEZONE)
                        date = date.strftime("%Y-%m-%d %H:%M:%S")
                        pid = posts.find({}, ['post_id'], sort={
                                         'post_id': pymongo.DESCENDING}).limit(1)['post_id']
                        posts.find_one_and_update(
                            {'post_id': pid}, {'$inc': {'post_id': 1}})
                        posts.insert_one(
                            {'board_name': commands[1], 'title': title, 'content': content, 'owner': name, 'date': date, 'post_id': pid})
                        self.wfile.write(SUCESS_POST_CREATED)
            elif commands[0] == "list-board":
                output = [b'\tIndex\tName\tModerator\r\n']
                if len(commands) == 1:
                    for idx, document in enumerate(boards.find({}, sort={"_id": pymongo.ASCENDING}), start=1):
                        output.append('\t{}\t{}\t{}\r\n'.format(
                            idx, document['borad_name'], document['mod']).encode())
                    self.wfile.writelines(output)
                else:
                    extracted = re.match(r'.*##(.*)', recv_data)
                    if extracted is None:
                        self.wfile.write(HELP_LIST_BOARD)
                    else:
                        keyword = extracted.group(1)
                        for idx, document in enumerate(boards.find({"board_name": {"$regex": ".*{}.*".format(keyword)}}, sort={"_id": pymongo.ASCENDING}), start=1):
                            output.append('\t{}\t{}\t{}\r\n'.format(
                                idx, document['board_name'], document['mod']).encode())
                        self.wfile.writelines(output)
            elif commands[0] == "list-post":
                output = [b'\tID\tTitle\tAuthor\tDate\r\n']
                if len(commands) == 2:
                    if boards.find({"board_name": commands[1]}) is None:
                        self.wfile.write(FAIL_BOARD_NOT_EXISTS)
                    else:
                        for document in posts.find({"board_name": commands[1]}, sort={"post_id": pymongo.ASCENDING}):
                            output.append('\t{}\t{}\t{}\t{}\r\n'.format(
                                document['post_id'], document['title'], document['owner'], document['date']).encode())
                        self.wfile.writelines(output)
                else:
                    extracted = re.match(r'list-post (.*) ##(.*)', recv_data)
                    if extracted is None:
                        self.wfile.write(HELP_LIST_POST)
                    elif boards.find({"board_name": extracted.group(1)}) is None:
                        self.wfile.write(FAIL_BOARD_NOT_EXISTS)
                    else:
                        keyword = extracted.group(2)
                        for document in posts.find({"board_name": extracted.group(1), "title": {"$regex": keyword}}, sort={"post_id": pymongo.ASCENDING}):
                            output.append('\t{}\t{}\t{}\t{}\r\n'.format(
                                document['post_id'], document['title'], document['owner'], document['date']).encode())
                        self.wfile.writelines(output)
            elif commands[0] == "read":
                if len(commands) != 2:
                    self.wfile.write(HELP_READ_POST)
                else:
                    try:
                        pid = int(commands[1])
                    except ValueError:
                        self.wfile.write(FAIL_POST_NOT_EXISTS)
                    else:
                        post = posts.find_one({"post_id": pid})
                        if post is None:
                            self.wfile.write(FAIL_POST_NOT_EXISTS)
                        else:
                            comment = comments.find({"post_id": pid})
                            ctx = READ_POST_FORMAT.format(
                                post['owner'], post['title'], post['date'], post['content'])
                            cmt = []
                            if comment is not None:
                                for c in comment:
                                    cmt.append('{}\t:\t{}'.format(
                                        c['owner'], c['content']))
                            self.wfile.write((ctx + '\r\n'.join(cmt)).encode())
            elif commands[0] == "delete-post":
                if len(commands) != 2:
                    self.wfile.write(HELP_DELETE_POST)
                elif name is None:
                    self.wfile.write(FAIL_UNAUTHORIZED)
                else:
                    try:
                        pid = int(commands[1])
                    except ValueError:
                        self.wfile.write(FAIL_POST_NOT_EXISTS)
                    else:
                        post = posts.find_one({"post_id": pid})
                        if post is None:
                            self.wfile.write(FAIL_POST_NOT_EXISTS)
                        elif name != post["owner"]:
                            self.wfile.write(FAIL_NOT_OWNER)
                        else:
                            posts.delete_one({"post_id": pid})
                            self.wfile.write(SUCESS_POST_DELETED)
            elif commands[0]:
                pass
            elif commands[0] == "comment":
                if len(commands) < 3:
                    self.wfile.write(HELP_COMMENT)
                elif name is None:
                    self.wfile.write(FAIL_UNAUTHORIZED)
                else:
                    try:
                        pid = int(commands[1])
                    except ValueError:
                        self.wfile.write(FAIL_POST_NOT_EXISTS)
                    else:
                        post = posts.find_one({"post_id": pid})
                        if post is None:
                            self.wfile.write(FAIL_POST_NOT_EXISTS)
                        else:
                            comments.insert_one(
                                {"post_id": pid, "owner": name, "content": commands[2]})
                            self.wfile.write(SUCESS_COMMENT)
            else:
                print("Unknown command:", commands)
        self.request.shutdown(socket.SHUT_RDWR)
        self.request.close()


def main():
    try:
        port = int(sys.argv[1])
    except IndexError:
        port = 23
    server = socketserver.ThreadingTCPServer(("0.0.0.0", port), Server)
    server.serve_forever()


if __name__ == '__main__':
    main()
