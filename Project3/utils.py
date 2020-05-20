import datetime
import re

from colorama import Fore, Style

WELCOME = ["********************************\r\n",
           "** Welcome to the BBS server. **\r\n",
           "********************************\r\n"]
ONLINE = "Client {}{{}}:{{}}{} starts the connection.".format(
    Fore.MAGENTA, Style.RESET_ALL)
OFFLINE = "Client {}{{}}:{{}}{} closes the connection.".format(
    Fore.MAGENTA, Style.RESET_ALL)
WAITING = Fore.YELLOW + "[ ... ]" + Style.RESET_ALL
COMPLETE = Fore.GREEN + "[ OK ]" + Style.RESET_ALL
ERROR = Fore.RED + "[ FAIL ]" + Style.RESET_ALL

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
    return EXTRACT_KEYWORD.match(string)


def extract_title_content(string):
    return EXTRACT_TITLE.match(string), EXTRACT_CONTENT.match(string)


def extract_comment(string):
    return EXTRACT_COMMENT.match(string)
