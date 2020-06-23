import re

__all__ = [
    "usage", "fail", "success", "backspace", "WELCOME"
]

WELCOME = b"\
********************************\r\n\
** Welcome to the BBS server. **\r\n\
********************************\r\n"


HELP = {
    "REGISTER": b"Usage: register <username> <email> <password>\r\n",
    "LOGIN": b"Usage: login <username> <password>\r\n"
}

FAIL = {
    "USERNAME_EXISTS": b"Username is already used.\r\n",
    "LOGIN_ALREADY": b"Please logout first.\r\n",
    "LOGIN_INCORRECT": b"Login failed.\r\n",
    "UNAUTHORIZED": b"Please login first.\r\n"
}

SUCCESS = {
    "REGISTER": b"Register successfully.\r\n"
}


def backspace(string: str) -> str:
    apply = re.compile('[^\x08]\x08')
    remove_trailing = re.compile('\x08+')
    while True:
        temp_string = apply.sub('', string)
        if len(string) == len(temp_string):
            return remove_trailing.sub('', temp_string)
        string = temp_string


def usage(string: str) -> bytes:
    return HELP[string.upper()]


def fail(string: str) -> bytes:
    return FAIL[string.upper()]


def success(string: str) -> bytes:
    return SUCCESS[string.upper()]
