import pymongo


class BBSManager:
    def __init__(self, connection):
        self.connection = connection


class BoardManager(BBSManager):
    def not_exist(self, board_name):
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
