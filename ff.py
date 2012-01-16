#!/usr/bin/env python

import argparse
import codecs
from datetime import datetime
import errno
import json
import os
import sys

CONFIG_DIR = os.path.expanduser('~/.ff')
SESSIONS_DIR = os.path.join(CONFIG_DIR, 'sessions')
DATE_FORMAT = "%Y%m%d%H%M"


class AttrDict(dict):
    def __getattr__(self, name):
        if name.startswith('_') or name == 'trait_names':
            raise AttributeError
        return self[name]


class Session(object):
    def __init__(self, data):
        self.data = data

    def itertabs(self):
        for window in self.data.windows:
            for tab in window.tabs:
                yield tab

    @property
    def tabs(self):
        return list(self.itertabs())


def format_date(timestamp=None):
    if timestamp:
        dt = datetime.fromtimestamp(float(timestamp))
    else:
        dt = datetime.now()
    return dt.strftime(DATE_FORMAT)


def make_dir(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass


def itersessions(include_saved=False):
    if sys.platform == 'darwin':
        path = os.path.expanduser('~/Library/Application Support/Firefox/Profiles')
    else:
        path = os.path.expanduser('~/.mozilla/firefox')
    for profile in (x for x in os.listdir(path) if x.endswith('.default')):
        yield os.path.join(path, profile, 'sessionstore.js')
    if include_saved:
        for session in os.listdir(SESSIONS_DIR):
            yield os.path.join(SESSIONS_DIR, session)

def load_session(session=None):
    if session and not os.path.exists(os.path.expanduser(session)):
        for s in itersessions(include_saved=True):
            if session in s:
                session = s
    elif not session:
        session = next(itersessions())

    with open(session) as f:
        return Session(json.load(f, object_hook=AttrDict))


def save_session():
    import shutil
    session = next(itersessions())
    shutil.copy(session, os.path.join(SESSIONS_DIR, format_date() + '.js'))


def replace_session(new_session):
    import shutil
    session = next(itersessions())
    shutil.copy(new_session, session)


def list_tabs(args):
    if args.all:
        sessions = (load_session(s) for s in itersessions(include_saved=True))
    else:
        sessions = [args.session]
    for session in sessions:
        for s_idx, tab in enumerate(session.tabs):
            for t_idx, entry in enumerate(tab.entries):
                try:
                    print ':'.join(str(x) for x in [s_idx, t_idx]), entry.title, '-', entry.url
                except KeyError:
                    pass


def list_sessions():
    for session in itersessions(include_saved=True):
        print session


# commands
def list_command(args):
    if args.sessions:
        list_sessions()
    else:
        list_tabs(args)


def read_command(args):
    try:
        s_idx, t_idx = (int(x) for x in args.idx.split(':'))
        url = args.session.tabs[s_idx].entries[t_idx].url
    except:
        print 'Invalid index'
        return

    import requests
    from readability.readability import Document
    import html2text
    h = html2text.HTML2Text()
    h.inline_links = False
    h.ignore_images = True
    h.ignore_emphasis = True
    res = requests.get(url)
    if res.ok:
        article = Document(res.content)
        print article.short_title()
        print h.handle(article.summary())
    else:
        print res.headers['status']


def open_command(args):
    import webbrowser
    try:
        s_idx, t_idx = (int(x) for x in args.idx.split(':'))
        url = args.session.tabs[s_idx].entries[t_idx].url
    except:
        print 'Invalid index'
        return
    webbrowser.open(url)


def save_command(args):
    save_session()


def clear_command(args):
    os.remove(args.session)


if __name__ == '__main__':
    # make sure config dir exists
    if not os.path.exists(SESSIONS_DIR):
        make_dir(SESSIONS_DIR)

    sys.stdout = codecs.getwriter('UTF-8')(sys.stdout)
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', action='store', help='session to operate on')
    subparsers = parser.add_subparsers()

    # list command
    list_parser = subparsers.add_parser('list', help='List sessions or tabs')
    list_parser.add_argument('--tabs', action='store_true', help='List open tabs')
    list_parser.add_argument('--sessions', action='store_true', help='List sessions')
    list_parser.add_argument('--all', action='store_true', help='List tabs from all sessions')
    list_parser.set_defaults(command=list_command)

    # save command
    save_parser = subparsers.add_parser('save', help='Save current session')
    save_parser.set_defaults(command=save_command)

    # clear command
    clear_parser = subparsers.add_parser('clear', help='Clear current session')
    clear_parser.set_defaults(command=clear_command)

    # read command
    read_parser = subparsers.add_parser('read', help='Read idx')
    read_parser.add_argument('idx', action='store', help='Index of article to read')
    read_parser.set_defaults(command=read_command)

    # open command
    open_parser = subparsers.add_parser('open', help='Open idx')
    open_parser.add_argument('idx', action='store', help='Index of article to open in Firefox')
    open_parser.set_defaults(command=open_command)

    if sys.argv[1:]:
        args = parser.parse_args()
        args.session = load_session(args.session)
        command = args.command
        command(args)
