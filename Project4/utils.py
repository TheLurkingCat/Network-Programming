import datetime
import re
from functools import wraps

from colorama import Fore, Style

WELCOME = b"********************************\r\n** Welcome to the BBS server. **\r\n********************************"

ONLINE = "Client {}{{}}:{{}}{} starts the connection.".format(
    Fore.MAGENTA, Style.RESET_ALL)
OFFLINE = "Client {}{{}}:{{}}{} closes the connection.".format(
    Fore.MAGENTA, Style.RESET_ALL)

TIMEZONE = datetime.timezone(datetime.timedelta(hours=8))
NEWPOST = re.compile(r'.*--title (.*) --content (.*)')
KEYWORD = re.compile(r'.*##(.*)')
TITLE = re.compile(r'.*--title (.*)')
CONTENT = re.compile(r'.*--content (.*)')
COMMENT = re.compile(r'comment \d+ (.*)')
SUBSCRIPTION = re.compile(r'subscribe --(board|author) (.*) --keyword (.*)')
UNSUBSCRIPTION = re.compile(
    r'unsubscribe --(board|author) (.*)')


def fallback(func):
    @wraps(func)
    def wrapper(self):
        try:
            func(self)
        except Exception as error:
            self.reply(str(error))
            print(error)
    return wrapper


def parameter_check(limits):
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            if isinstance(limits, int):
                if len(self.commands) != limits:
                    self.reply(func.__doc__)
                else:
                    func(self)
            elif limits.match(self.raw_command) is None:
                self.reply(func.__doc__)
            else:
                func(self)
        return wrapper
    return decorator


def post_existance(func):
    @wraps(func)
    def wrapper(self):
        postid = self.commands[0]
        if postid.isdigit():
            postid = int(postid)
            if self.post.not_exist(postid):
                self.reply(b"Post does not exist.")
            else:
                func(self)
        else:
            self.reply(b"Post does not exist.")
    return wrapper


def login_required(func):
    @wraps(func)
    def wrapper(self):
        if self.user.is_unauthorized():
            self.reply(b"Please login first.")
        else:
            func(self)
    return wrapper


def board_existance(condition):
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            if self.board.not_exist(self.commands[0]):
                if condition:
                    self.reply(b"Board does not exist.")
                else:
                    func(self)
            elif condition:
                func(self)
            else:
                self.reply(b"Board already exist.")
        return wrapper
    return decorator
