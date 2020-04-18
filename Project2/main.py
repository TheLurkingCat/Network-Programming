#!/usr/bin/python3
import socketserver
import sys

import pymongo

from server import Server
from utils import complete, waiting


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
    complete("Server is running on port", port)
    waiting("Waiting for connections.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\b\b", end="")
        waiting("Shutting down server.")
        server.shutdown()
        complete("Server closed.")
        waiting("Resetting database.")
        client = pymongo.MongoClient()
        client['NP']['user'].drop()
        client['NP']['board'].drop()
        client['NP']['seq_num'].update_one({}, {"$set": {"id": 1}})
        client['NP']['post'].drop()
        client['NP']['comment'].drop()
        complete("All table reset.")


if __name__ == '__main__':
    main()
