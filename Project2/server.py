#!/usr/bin/python3
import datetime
import re
import socket
import socketserver
import sys

import pymongo

from defines import *


def apply_backspace(string):
    while True:
        temp_string = APPLY_BACKSPACE.sub('', string)
        if len(string) == len(temp_string):
            return REMOVE_TRAILING_BACKSPACE.sub('', temp_string)
        string = temp_string


class Server(socketserver.StreamRequestHandler):
    def handle(self):
        print("New connection.")
        print(ONLINE.format(*self.client_address))
        self.wfile.writelines(WELCOME)
        client = pymongo.MongoClient()
        users = client['NP']['user']
        boards = client['NP']['board']
        posts = client['NP']['post']
        comments = client['NP']['comment']
        idx = client['NP']['idx']
        name = None
        while True:
            self.wfile.write(PROMPT)
            recv_data = self.rfile.readline()
            if not recv_data:
                break
            try:
                recv_data = recv_data.decode()
            except UnicodeDecodeError:
                print(ERROR + " Decode Error", recv_data)
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
                        self.wfile.write(SUCESS_REGISTER)
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
                print(OFFLINE.format(*self.client_address))
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
                        content = extracted.group(2).replace('<br>', '\r\n')
                        date = datetime.datetime.now(TIMEZONE)
                        date = list(date.timetuple()[:3])
                        pid = idx.find_one_and_update(
                            {"type": "post_id"}, {'$inc': {'idx': 1}}, return_document=pymongo.ReturnDocument.AFTER)['idx']

                        posts.insert_one(
                            {'board_name': commands[1], 'title': title, 'content': content, 'owner': name, 'date': date, 'post_id': pid})
                        self.wfile.write(SUCESS_POST_CREATED)
            elif commands[0] == "list-board":
                output = [b'\tIndex\tName\tModerator\r\n']
                if len(commands) == 1:
                    for idx, document in enumerate(boards.find({}, sort=[("_id", pymongo.ASCENDING)]), start=1):
                        output.append('\t{}\t{}\t{}\r\n'.format(
                            idx, document['board_name'], document['mod']).encode())
                    self.wfile.writelines(output)
                else:
                    extracted = re.match(r'.*##(.*)', recv_data)
                    if extracted is None:
                        self.wfile.write(HELP_LIST_BOARD)
                    else:
                        keyword = extracted.group(1)
                        for idx, document in enumerate(boards.find({"board_name": {"$regex": ".*{}.*".format(keyword)}}, sort=[("_id", pymongo.ASCENDING)]), start=1):
                            output.append('\t{}\t{}\t{}\r\n'.format(
                                idx, document['board_name'], document['mod']).encode())
                        self.wfile.writelines(output)
            elif commands[0] == "list-post":
                output = [b'\tID\tTitle\tAuthor\tDate\r\n']
                if len(commands) == 2:
                    if boards.find_one({"board_name": commands[1]}) is None:
                        self.wfile.write(FAIL_BOARD_NOT_EXISTS)
                    else:
                        for document in posts.find({"board_name": commands[1]}, sort=[("post_id", pymongo.ASCENDING)]):
                            output.append('\t{}\t{}\t{}\t{}\r\n'.format(
                                document['post_id'], document['title'], document['owner'], '{}/{}'.format(*document['date'][1:])).encode())
                        self.wfile.writelines(output)
                else:
                    extracted = re.match(r'list-post (.*) ##(.*)', recv_data)
                    if extracted is None:
                        self.wfile.write(HELP_LIST_POST)
                    elif boards.find({"board_name": extracted.group(1)}) is None:
                        self.wfile.write(FAIL_BOARD_NOT_EXISTS)
                    else:
                        keyword = extracted.group(2)
                        for document in posts.find({"board_name": extracted.group(1), "title": {"$regex": keyword}}, sort=[("post_id", pymongo.ASCENDING)]):
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
                                post['owner'], post['title'], '{}-{}-{}'.format(*post['date']), post['content'])
                            cmt = []
                            if comment is not None:
                                for c in comment:
                                    cmt.append('{}: {}'.format(
                                        c['owner'], c['content']))
                                cmt.append('')
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
                            comments.delete_many({"post_id": pid})
                            self.wfile.write(SUCESS_POST_DELETED)
            elif commands[0] == 'update-post':
                if len(commands) < 4:
                    self.wfile.write(HELP_UPDATE_POST)
                elif name is None:
                    self.wfile.write(FAIL_UNAUTHORIZED)
                try:
                    pid = int(commands[1])
                except Exception:
                    self.wfile.write(FAIL_POST_NOT_EXISTS)
                post = posts.find_one({"post_id": pid})
                if post is None:
                    self.wfile.write(FAIL_POST_NOT_EXISTS)
                else:
                    if post['owner'] != name:
                        self.wfile.write(FAIL_NOT_OWNER)
                    elif "title" in recv_data:
                        extracted = re.match(r'.*--title (.*)', recv_data)
                        posts.find_one_and_update(
                            {"post_id": pid}, {"$set": {"title": extracted.group(1)}})
                        self.wfile.write(SUCESS_UPDATE_POST)
                    elif "content" in recv_data:
                        extracted = re.match(r'.*--content (.*)', recv_data)
                        posts.find_one_and_update(
                            {"post_id": pid}, {"$set": {"content": extracted.group(1).replace('<br>', '\r\n')}})
                        self.wfile.write(SUCESS_UPDATE_POST)
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
                            extracted = re.match(
                                r'comment \d+ (.*)', recv_data)

                            comments.insert_one(
                                {"post_id": pid, "owner": name, "content": extracted.group(1)})
                            self.wfile.write(SUCESS_COMMENT)
            else:
                print(ERROR + " Unknown command:", commands)
        self.request.shutdown(socket.SHUT_RDWR)
        self.request.close()


def main():
    try:
        port = int(sys.argv[1])
    except IndexError:
        port = 5000
    try:
        default_server = socketserver.ForkingTCPServer
    except AttributeError:
        default_server = socketserver.ThreadingTCPServer
    default_server.allow_reuse_address = True
    server = default_server(("0.0.0.0", port), Server)
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
        client['NP']['board'].drop()
        client['NP']['idx'].drop()
        client['NP']['post'].drop()
        client['NP']['comment'].drop()
        idx = client['NP']['idx']
        idx.insert_one({"type": "post_id", "idx": 0})
        print(COMPLETE + " All table dropped.")


if __name__ == '__main__':
    main()
