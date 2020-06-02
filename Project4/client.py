import socket
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
    print(recv_all(sock))
    try:
        while True:
            command = input("% ").strip()
            if not command:
                continue
            send(sock, command)
            if command == 'exit':
                break
            reply = recv_all(sock)
            if reply:
                print(reply)
    except KeyboardInterrupt:
        send(sock, "exit")
        print("\b\b  ")
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()
