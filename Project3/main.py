#!/usr/bin/python3
import socketserver
import sys

import boto3
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
        client['NP']['seq_num'].drop()
        client['NP']['post'].drop()
        client['NP']['mail_seq_num'].drop()
        client['NP']['mail'].drop()
        client['NP']['comment'].drop()
        complete("All table reset.")
        waiting("Resetting Amazon S3.")
        cli = boto3.client("s3")
        for b in cli.list_buckets()['Buckets']:
            this = []
            ret = cli.list_objects_v2(Bucket=b['Name']).get('Contents', None)
            if ret is not None:
                for obj in ret:
                    this.append({"Key": obj['Key']})
                cli.delete_objects(
                    Bucket=b['Name'],
                    Delete={'Objects': this}
                )
            cli.delete_bucket(
                Bucket=b['Name']
            )
        complete("All bucket emptied")


if __name__ == '__main__':
    main()
