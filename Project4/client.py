#!/usr/bin/env python
import socket
import threading
from struct import error, pack, unpack
from sys import argv


def recv_all(s):
    while True:
        try:
            length = unpack('<H', s.recv(2))[0]
            print(s.recv(length).decode(), "\r\n% ", end='')
        except Exception:
            break


def send(s, data):
    if isinstance(data, str):
        data = data.encode()
    length = pack('<H', len(data))
    s.sendall(length + data)


if __name__ == '__main__' and (len(argv) == 3):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((argv[1], int(argv[2])))
    reciver = threading.Thread(target=recv_all, args=(sock,))
    reciver.daemon = True
    reciver.start()
    try:
        while True:
            command = input().strip()
            if not command:
                continue
            send(sock, command)
            if command == 'exit':
                break
    except KeyboardInterrupt:
        send(sock, "exit")
        print("\b\b  ")
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()
