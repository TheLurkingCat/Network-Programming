class User:
    def __init__(self, connection):
        self.username = None
        self.connection = connection

    def register(self, name, password):
        collection = self.connection['NP']['user']
        if collection.find_one({"username": name}) is None:
            collection.insert_one({"username": name, "password": password})
            return True
        return False

    def login(self, name, password):
        auth = self.connection['NP']['user']
        if auth.find_one({"username": name, "password": password}) is None:
            return False
        self.username = name
        return True

    def is_login(self):
        return not self.is_unauthorized()

    def is_unauthorized(self):
        return self.username is None

    def logout(self):
        self.username = None

    def whoami(self):
        return self.username
