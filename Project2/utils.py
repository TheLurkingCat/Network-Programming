
import datetime
import re

from colorama import Fore, Style

WELCOME = [b"********************************\r\n",
           b"** Welcome to the BBS server. **\r\n",
           b"********************************\r\n"]
READ_POST_FORMAT = "Author\t:{}\r\nTitle\t:{}\r\nDate\t:{}\r\n--\r\n{}\r\n--\r\n"
PROMPT = b"% "
ONLINE = "Client {}{{}}:{{}}{} starts the connection.".format(
    Fore.MAGENTA, Style.RESET_ALL)
OFFLINE = "Client {}{{}}:{{}}{} closes the connection.".format(
    Fore.MAGENTA, Style.RESET_ALL)
WAITING = Fore.YELLOW + "[ ... ]" + Style.RESET_ALL
COMPLETE = Fore.GREEN + "[ OK ]" + Style.RESET_ALL
ERROR = Fore.RED + "[ FAIL ]" + Style.RESET_ALL
HELP_REG = b"Usage: register <username> <email> <password>\r\n"
HELP_LOGIN = b"Usage: login <username> <password>\r\n"
HELP_CREATE_BOARD = b"Usage: create-board <name>\r\n"
HELP_CREATE_POST = b"Usage: create-post <board-name> --title <title> --content <content>\r\n"
HELP_LIST_BOARD = b"list-board ##<key>\r\n"
HELP_LIST_POST = b"list-post <board-name> ##<key>\r\n"
HELP_READ_POST = b"read <post-id>\r\n"
HELP_DELETE_POST = b"delete-post <post-id>\r\n"
HELP_UPDATE_POST = b"update-post <post-id> --title/content <new>\r\n"
HELP_COMMENT = b"comment <post-id> <comment>\r\n"
FAIL_REG = b"Username is already used.\r\n"
FAIL_LOGIN_ALREADY = b"Please logout first.\r\n"
FAIL_LOGIN_INCORRECT = b"Login failed.\r\n"
FAIL_UNAUTHORIZED = b"Please login first.\r\n"
FAIL_BOARD_EXISTS = b"Board already exist.\r\n"
FAIL_BOARD_NOT_EXISTS = b"Board is not exist.\r\n"
FAIL_POST_NOT_EXISTS = b"Post is not exist.\r\n"
FAIL_NOT_OWNER = b"Not the post owner.\r\n"
SUCCESS_REGISTER = b"Register successfully.\r\n"
SUCCESS_BOARD_CREATED = b"Create board successfully.\r\n"
SUCCESS_POST_CREATED = b"Create post successfully\r\n"
SUCCESS_POST_DELETED = b"Delete successfully.\r\n"
SUCCESS_UPDATE_POST = b"Update successfully.\r\n"
SUCCESS_COMMENT = b"Comment successfully.\r\n"
APPLY_BACKSPACE = re.compile('[^\x08]\x08')
REMOVE_TRAILING_BACKSPACE = re.compile('\x08+')
TIMEZONE = datetime.timezone(datetime.timedelta(hours=8))
EXTRACT_NEW_POST_FORMAT = re.compile(r'.*--title (.*) --content (.*)')
EXTRACT_KEYWORD = re.compile(r'.*##(.*)')
EXTRACT_TITLE = re.compile(r'.*--title (.*)')
EXTRACT_CONTENT = re.compile(r'.*--content (.*)')
EXTRACT_COMMENT = re.compile(r'comment \d+ (.*)')


def error(*args):
    print(ERROR, *args)


def waiting(*args):
    print(WAITING, *args)


def complete(*args):
    print(COMPLETE, *args)


def extract_post(string):
    return EXTRACT_NEW_POST_FORMAT.match(string)


def extract_keyword(string):
    return EXTRACT_KEYWORD(string)


def extract_title_content(string):
    return EXTRACT_TITLE(string), EXTRACT_CONTENT(string)


def extract_comment(string):
    return EXTRACT_COMMENT(string)


def apply_backspace(string):
    while True:
        temp_string = APPLY_BACKSPACE.sub('', string)
        if len(string) == len(temp_string):
            return REMOVE_TRAILING_BACKSPACE.sub('', temp_string)
        string = temp_string
