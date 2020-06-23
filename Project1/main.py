#!/usr/bin/env python3
import socketserver
import sys
import threading

import pymongo
from console.utils import wait_key

from server import Server


def cleanup():
    client = pymongo.MongoClient(serverSelectionTimeoutMS=1)
    try:
        client['NP']['user'].drop()
    except pymongo.errors.ServerSelectionTimeoutError:
        print("Server is not open?")


def main():
    try:
        port = int(sys.argv[1])
    except (ValueError, IndexError):
        port = 5000
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    server = socketserver.ThreadingTCPServer(("0.0.0.0", port), Server)
    print("Server started")
    with server:
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        print("Press any key to exit.")
        wait_key()
        print("Server shutdown.")
        server.shutdown()
    cleanup()


if __name__ == '__main__':
    main()
