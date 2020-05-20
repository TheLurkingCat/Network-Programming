import socket
from json import loads
from json.decoder import JSONDecodeError
from struct import error, pack, unpack
from sys import argv

import boto3


def recv_all(s):
    try:
        length = unpack('<H', s.recv(2))[0]
    except error:
        s.shutdown(socket.SHUT_RDWR)
        s.close()
        exit(1)
    return s.recv(length).decode()


def send(s, data):
    if isinstance(data, str):
        data = data.encode()
    length = pack('<H', len(data))
    s.sendall(length + data)


if __name__ == '__main__' and (len(argv) == 3):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((argv[1], int(argv[2])))
    print(recv_all(sock), end='')
    client = boto3.client('s3')
    try:
        while True:
            command = input("% ").strip()
            if not command:
                continue
            send(sock, command)
            if command == 'exit':
                break
            try:
                reply = loads(recv_all(sock))
            except JSONDecodeError:
                continue
            print(reply['msg'])
            # print(reply)
            if reply.get('success', False):
                if reply['type'] == 'register':
                    bucket_name = reply['bucket_name']
                    responce = client.create_bucket(
                        ACL='private',
                        Bucket=bucket_name,
                    )
                    print(responce)
                elif reply['type'] == 'login':
                    pass
                elif reply['type'] == 'create_post':
                    bucket_name = reply['bucket_name']
                    content = reply['content']
                    pid = reply['id']
                    client.put_object(
                        ACL='private',
                        Body=content.encode(),
                        Bucket=bucket_name,
                        Key=str(pid)
                    )
                elif reply['type'] == 'read':
                    bucket_name = reply['bucket_name']
                    pid = reply['id']
                    cmts = reply['comments']
                    content = client.get_object(
                        Bucket=bucket_name,
                        Key=str(pid)
                    )
                    print('--')
                    print(content['Body'].read().decode())
                    print('--')
                    for bucket, key, own in cmts:
                        cmt = client.get_object(
                            Bucket=bucket,
                            Key=key
                        )
                        print('{}: {}'.format(
                            own, cmt['Body'].read().decode()))
                elif reply['type'] == 'delete_post':
                    bucket_name = reply['bucket_name']
                    pid = reply['id']
                    client.delete_object(
                        Bucket=bucket_name,
                        Key=str(pid))
                elif reply['type'] == 'update_post':
                    bucket_name = reply['bucket_name']
                    content = reply['content']
                    pid = reply['id']
                    client.put_object(
                        ACL='private',
                        Body=content.encode(),
                        Bucket=bucket_name,
                        Key=str(pid)
                    )
                elif reply['type'] == 'comment':
                    bucket_name = reply['bucket_name']
                    content = reply['content']
                    pid = reply['id']
                    key = reply['key']
                    client.put_object(
                        ACL='private',
                        Body=content.encode(),
                        Bucket=bucket_name,
                        Key=str(pid) + key
                    )
                elif reply['type'] == 'mailto':
                    bucket_name = reply['bucket_name']
                    content = reply['content']
                    k = reply['key']
                    client.put_object(
                        ACL='private',
                        Body=content.encode(),
                        Bucket=bucket_name,
                        Key=k
                    )
                elif reply['type'] == 'retrieve_mail':
                    bucket_name = reply['bucket_name']
                    subject = reply['subject']
                    author = reply['from']
                    date = reply['date']
                    k = reply['key']
                    print("Subject :", subject)
                    print("From :", author)
                    print("Date :", date)
                    print("--")
                    content = client.get_object(
                        Bucket=bucket_name,
                        Key=k
                    )
                    print(content['Body'].read().decode())

                elif reply['type'] == 'delete_mail':
                    bucket_name = reply['bucket_name']
                    k = reply['key']
                    client.delete_object(
                        Bucket=bucket_name,
                        Key=k
                    )

    except KeyboardInterrupt:
        send(sock, "exit")
        print("\b\b  ")
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()
