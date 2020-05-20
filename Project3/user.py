class User:
    def __init__(self, connection):
        self.username = None
        self.bucket_name = None
        self.connection = connection

    def register(self, name, password, bucket_name):
        collection = self.connection['NP']['user']
        if collection.find_one({"username": name}) is None:
            collection.insert_one(
                {"username": name, "password": password, "bucket": bucket_name})
            return True
        return False

    def login(self, name, password):
        auth = self.connection['NP']['user']
        user_info = auth.find_one({"username": name, "password": password})
        if user_info is None:
            return False
        self.username = name
        self.bucket_name = user_info["bucket"]
        return True

    def is_login(self):
        return not self.is_unauthorized()

    def is_unauthorized(self):
        return self.username is None

    def logout(self):
        self.bucket_name = None
        self.username = None
