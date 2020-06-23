import pymongo


class User:
    def __init__(self, connection: pymongo.MongoClient):
        self.username = None
        self.collection = connection['NP']['user']

    def exist(self, document: dict) -> bool:
        return self.collection.count_documents(document, limit=1) != 0

    def register(self, name: str, password: str) -> bool:
        document = {
            "username": name,
            "password": password
        }
        result = self.collection.update_one(
            {"username": name},
            {"$setOnInsert": document},
            upsert=True
        )
        return result.upserted_id is not None

    def login(self, name: str, password: str) -> bool:
        document = {
            "username": name,
            "password": password
        }
        if self.exist(document):
            self.username = name
            return True
        return False

    def is_unauthorized(self) -> bool:
        return self.username is None

    def logout(self):
        self.username = None
