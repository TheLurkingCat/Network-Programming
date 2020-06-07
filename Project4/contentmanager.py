from typing import Tuple

from pymongo import MongoClient
from pymongo.cursor import Cursor


class BBSManager:
    def __init__(self, connection: MongoClient):
        self.connection = connection


class BoardManager(BBSManager):
    def not_exist(self, board_name: str) -> bool:
        board = self.connection['NP']['board'].find_one(
            {"board_name": board_name}, {"_id": True})
        return board is None

    def add_board(self, document):
        self.connection['NP']['board'].insert_one(document)

    def list_all(self, document):
        collection = self.connection['NP']['board']
        return collection.find(document, sort=[("_id", 1)])  # ASCENDING


class PostManager(BBSManager):
    def next_sequence_id(self):
        collection = self.connection['NP']['seq_num']
        document = collection.find_one_and_update({}, {'$inc': {'id': 1}})
        return document['id']

    def not_exist(self, postid):
        collection = self.connection['NP']['post']
        post = collection.find_one({"post_id": postid}, {"_id": True})
        return post is None

    def add_post(self, document):
        document['post_id'] = self.next_sequence_id()
        self.connection['NP']['post'].insert_one(document)

    def list_all(self, document):
        collection = self.connection['NP']['post']
        return collection.find(document, sort=[("post_id", 1)])  # ASCENDING

    def list_comment(self, post_id):
        collection = self.connection['NP']['comment']
        # ASCENDING
        return collection.find({"post_id": post_id}, sort=[("_id", 1)])

    def clean_comment(self, post_id):
        collection = self.connection['NP']['comment']
        collection.delete_many({"post_id": post_id})

    def read(self, post_id):
        collection = self.connection['NP']['post']
        return collection.find_one({"post_id": post_id})

    def delete(self, document):
        collection = self.connection['NP']['post']
        result = collection.delete_one(document)
        if result.deleted_count:
            self.clean_comment(document['post_id'])
            return True
        return False

    def update(self, document, modified):
        collection = self.connection['NP']['post']
        result = collection.update_one(document, modified)
        return bool(result.matched_count)

    def comment(self, document):
        collection = self.connection['NP']['comment']
        collection.insert_one(document)


class SubscribeManager(BBSManager):
    def list_all(self, username: str) -> Cursor:
        collection = self.connection['NP']['sub']
        return collection.find({'user': username})

    def subscribe(self, username: str, subtype: str, subinfo: str, keyword: str) -> bool:
        collection = self.connection['NP']['sub']
        document = {
            "user": username,
            "type": subtype,
            "info": subinfo,
            "keyword": keyword
        }
        if collection.find_one(document, {"_id": True}) is None:
            collection.insert_one(document)
            return True
        return False

    def unsubscribe(self, username: str, subtype: str, subinfo: str) -> bool:
        collection = self.connection['NP']['sub']
        document = {
            "user": username,
            "type": subtype,
            "info": subinfo
        }

        result = collection.delete_many(document)
        return result.deleted_count != 0

    def find_subscriber(self, board: str, author: str) -> Tuple[Cursor]:
        collection = self.connection['NP']['sub']
        mask = {
            "_id": False,
            "user": True,
            "keyword": True
        }
        boards = collection.find({"type": "board", "info": board}, mask)
        authors = collection.find({"type": "author", "info": author}, mask)
        return boards, authors
