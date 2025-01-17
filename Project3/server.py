import datetime
import socket
import socketserver
import struct
from json import dumps
from time import time

import pymongo

from contentmanager import BoardManager, MailManager, PostManager
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
            "mail-to": self.mailto,
            "list-mail": self.listmail,
            "retr-mail": self.retrieve_mail,
            "delete-mail": self.delete_mail,
            "comment": self.comment
        }
        super().__init__(*args)

    def reply(self, response, *args):
        if args:
            response = response.format(*args)
        if isinstance(response, dict):
            response = dumps(response)
        if isinstance(response, str):
            response = response.encode()
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
        ret = {
            "type": "register",
            "bucket_name": "0716061-{}-{}".format(username.lower(), int(time())),
            "success": False
        }
        if self.user.register(username, password, ret['bucket_name']):
            ret['msg'] = "Register successfully."
            ret['success'] = True
        else:
            ret['bucket_name'] = None
            ret['msg'] = "Username is already used."
        self.reply(ret)

    def login(self):
        ret = {
            "type": "login",
            "bucket_name": None,
            "success": False}
        if self.user.is_unauthorized():
            username, password = self.commands
            if self.user.login(username, password):
                ret['bucket_name'] = self.user.bucket_name
                ret['msg'] = "Welcome, {}.".format(username)
                ret['success'] = True
            else:
                ret['msg'] = "Login failed."
        else:
            ret['msg'] = "Please logout first."
        self.reply(ret)

    def logout(self):
        ret = {}
        if self.user.is_unauthorized():
            ret['msg'] = "Please login first."
        else:
            ret['msg'] = "Bye, {}.".format(self.user.username)
            self.user.logout()
        self.reply(ret)

    def whoami(self):
        ret = {}
        if self.user.is_unauthorized():
            ret['msg'] = "Please login first."
        else:
            ret['msg'] = self.user.username
        self.reply(ret)

    def create_board(self):
        ret = {}
        if self.user.is_unauthorized():
            ret['msg'] = "Please login first."
        else:
            if self.board.not_exist(self.commands[0]):
                document = {"board_name": self.commands[0],
                            "mod": self.user.username
                            }
                self.board.add_board(document)
                ret['msg'] = "Create board successfully."
            else:
                ret['msg'] = "Board already exist."
        self.reply(ret)

    def create_post(self):
        ret = {
            "type": "create_post",
            "bucket_name": None,
            "success": False
        }
        board_name = self.commands[0]
        extracted = extract_post(self.raw_command)
        if self.user.is_unauthorized():
            ret['msg'] = "Please login first."
        elif self.board.not_exist(board_name):
            ret['msg'] = "Board does not exist."
        else:
            title = extracted.group(1)
            content = extracted.group(2).replace('<br>', '\r\n')

            ret['bucket_name'] = self.user.bucket_name
            ret['success'] = True
            ret['msg'] = "Create post successfully."
            ret['content'] = content

            date = list(datetime.datetime.now(TIMEZONE).timetuple()[:3])
            document = {'board_name': board_name,
                        'title': title,
                        'owner': self.user.username,
                        'date': date,
                        'post_id': None,
                        'bucket_name': self.user.bucket_name
                        }
            ret['id'] = self.post.add_post(document)
        self.reply(ret)

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
                doc['mod']))

        self.reply({"msg": '\n'.join(output)})

    def list_post(self):
        board_name = self.commands[0]
        if self.board.not_exist(board_name):
            self.reply({"msg": "Board does not exist."})
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
                *doc['date'][1:]))
        self.reply({"msg": '\n'.join(output)})

    def read(self):
        ret = {
            "type": "read",
            "success": False
        }
        postid = int(self.commands[0])
        if self.post.not_exist(postid):
            ret['msg'] = "Post does not exist."
        else:
            doc = self.post.read(postid)
            cmts = []
            head = "Author\t:{}\r\nTitle\t:{}\r\nDate\t:{:04d}-{:02d}-{:02d}".format(
                doc['owner'],
                doc['title'],
                *doc['date']
            )
            for comment in self.post.list_comment(postid):
                cmts.append([comment['bucket_name'],
                             comment['key'],
                             comment['owner']])
            ret['comments'] = cmts
            ret['msg'] = head
            ret['id'] = postid
            ret["bucket_name"] = doc['bucket_name']
            ret['success'] = True
        self.reply(ret)

    def delete_post(self):
        ret = ret = {
            "type": "delete_post",
            "bucket_name": None,
            "success": False}
        if self.user.is_unauthorized():
            ret['msg'] = "Please login first."
        else:
            postid = int(self.commands[0])
            if self.post.not_exist(postid):
                ret['msg'] = "Post does not exist."
            else:
                document = {
                    "post_id": postid,
                    "owner": self.user.username
                }
                delete_result = self.post.delete(document)
                if delete_result[0]:
                    ret['bucket_name'] = self.user.bucket_name
                    ret['success'] = True
                    ret['id'] = postid
                    ret['comments'] = delete_result[1]
                    ret['msg'] = "Delete successfully."
                else:
                    ret['msg'] = "Not the post owner."
        self.reply(ret)

    def update_post(self):
        ret = {
            "type": "update_post",
            "bucket_name": None,
            "success": False}
        if self.user.is_unauthorized():
            ret['msg'] = "Please login first."
        else:
            postid = int(self.commands[0])
            if self.post.not_exist(postid):
                ret['msg'] = "Post does not exist."
            else:
                title, content = extract_title_content(self.raw_command)
                document = {"post_id": postid,
                            "owner": self.user.username
                            }
                if title is not None:
                    result = self.post.update(
                        document, {"$set": {"title": title.group(1)}})
                    if result:
                        ret['msg'] = "Update successfully."
                    else:
                        ret['msg'] = "Not the post owner."
                else:
                    try:
                        next(self.post.list_all(document))
                    except StopIteration:
                        ret['msg'] = "Not the post owner."
                    else:
                        ret['bucket_name'] = self.user.bucket_name
                        ret['msg'] = "Update successfully."
                        ret['success'] = True
                        ret['content'] = content.group(
                            1).replace('<br>', '\r\n')
                        ret['id'] = postid

        self.reply(ret)

    def comment(self):
        ret = {
            "type": "comment",
            "bucket_name": None,
            "success": False
        }
        if self.user.is_unauthorized():
            ret['msg'] = "Please login first."
        else:
            postid = int(self.commands[0])
            if self.post.not_exist(postid):
                ret['msg'] = "Post does not exist."
            else:
                comment = extract_comment(self.raw_command)
                if comment is not None:
                    t = str(int(time()))
                    document = {"post_id": postid,
                                "owner": self.user.username,
                                "bucket_name": self.user.bucket_name,
                                "key": str(postid) + '_' + t}
                    self.post.comment(document)
                    ret['success'] = True
                    ret['bucket_name'] = self.user.bucket_name
                    ret['msg'] = "Comment successfully."
                    ret['content'] = comment.group(1)
                    ret['id'] = str(postid)
                    ret['key'] = '_' + t
        self.reply(ret)

    def mailto(self):
        ret = {
            "type": "mailto",
            "bucket_name": None,
            "success": False
        }
        username = self.commands[0]
        extracted = extract_mail(self.raw_command)
        subject = extracted.group(1)
        content = extracted.group(2).replace('<br>', '\r\n')
        date = list(datetime.datetime.now(TIMEZONE).timetuple()[:3])
        if self.user.is_unauthorized():
            ret['msg'] = "Please login first."
        else:
            bkt_name = self.user.get_bucket(username)
            if bkt_name is None:
                ret['msg'] = username + " does not exist."
            else:
                seq = self.mail.mailto(
                    self.user.username, username, subject, date)
                ret['msg'] = "Sent successfully."
                ret['success'] = True
                ret['bucket_name'] = bkt_name
                ret['content'] = content
                ret['key'] = 'mail_' + str(seq)
        self.reply(ret)

    def listmail(self):
        if self.user.is_unauthorized():
            self.reply({'msg': "Please login first."})
        else:
            out = ["ID\tSubject\tFrom\tDate"]
            mails = self.mail.list_all(self.user.username)
            for idx, mail in enumerate(mails, start=1):
                out.append('{}\t{}\t{}\t{:02d}/{:02d}'.format(
                    idx,
                    mail['subject'],
                    mail['from'],
                    *mail['date'][1:]
                ))
            self.reply({'msg': '\n'.join(out)})

    def retrieve_mail(self):
        mail_num = int(self.commands[0])
        ret = {
            "type": "retrieve_mail",
            "bucket_name": None,
            "success": False
        }
        if self.user.is_unauthorized():
            ret['msg'] = "Please login first."
        else:
            mail_metadata = self.mail.exist(self.user.username, mail_num)
            if mail_metadata is None:
                ret['msg'] = "No such mail."
            else:
                ret['bucket_name'] = self.user.bucket_name
                ret['success'] = True
                ret['msg'] = 'Subject :' + mail_metadata['subject']
                ret['from'] = mail_metadata['from']
                ret['date'] = '{:04d}-{:02d}-{:02d}'.format(
                    *mail_metadata['date'])
                ret['key'] = "mail_" + str(mail_num)
        self.reply(ret)

    def delete_mail(self):
        mail_num = int(self.commands[0])
        ret = {
            "type": "delete_mail",
            "bucket_name": None,
            "success": False
        }
        if self.user.is_unauthorized():
            ret['msg'] = "Please login first."
        else:
            isdeleted = self.mail.delete(self.user.username, mail_num)
            if isdeleted:
                ret['bucket_name'] = self.user.bucket_name
                ret['success'] = True
                ret['key'] = 'mail_' + str(mail_num)
                ret['msg'] = 'Mail deleted.'
            else:
                ret['msg'] = "No such mail."

        self.reply(ret)

    def handle(self):
        print("New connection.")
        print(ONLINE.format(*self.client_address))
        self.reply(''.join(WELCOME))
        mongoclient = pymongo.MongoClient()
        self.user = User(mongoclient)
        self.board = BoardManager(mongoclient)
        self.post = PostManager(mongoclient)
        self.mail = MailManager(mongoclient)
        while True:
            self.raw_command = self.recv_command()
            self.commands = self.raw_command.split()
            if not self.commands:
                continue

            if self.commands[0] == "exit":
                print(OFFLINE.format(*self.client_address))
                break
            func = self.function.get(self.commands[0])
            del self.commands[0]
            if func is None:
                error("Unknown command:", self.commands)
                self.reply('')
            else:
                func()

        self.request.shutdown(socket.SHUT_RDWR)
        self.request.close()
