import pymongo

client = pymongo.MongoClient()
client['NP']['user'].drop()
client['NP']['board'].drop()
client['NP']['post'].drop()
client['NP']['comment'].drop()
posts = client['NP']['post']
posts.insert_one({"post_id": 1})
boards = client['NP']['post']
boards.insert_one({"board_id": 1})
posts.create_index('post_id', pymongo.DESCENDING, unique=True)
