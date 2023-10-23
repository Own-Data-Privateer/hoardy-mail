#!/usr/bin/env python3
#
# Copyright (c) 2023 Jan Malakovski <oxij@oxij.org>
#
# This file can be distributed under the terms of the GNU GPL, version 3 or later.

import imaplib
import os
import ssl
import subprocess
import sys
import time
import typing as _t

from gettext import gettext as _, ngettext

from . import argparse

def imap_parse_data(data : str, top_level : bool = True) -> _t.Tuple[_t.Any, str]:
    "Parse IMAP response string into a tree of strings."
    acc = []
    res = ""
    i = 0
    state = False
    while i < len(data):
        c = data[i:i+1]
        #print(c)
        if state == False:
            if c == '"':
                if res != "":
                    raise ValueError("unexpected quote")
                res = ""
                state = True
            elif c == " ":
                acc.append(res)
                res = ""
            elif c == "(":
                if res != "":
                    raise ValueError("unexpected parens")
                res, data = imap_parse_data(data[i+1:], False)
                acc.append(res)
                res = ""
                if len(data) == 0:
                    return acc, ""
                elif data[0] != " ":
                    raise ValueError("expecting space")
            elif c == ")":
                acc.append(res)
                return acc, data[i+1:]
            else:
                if type(res) is not str:
                    raise ValueError("unexpected char")
                res += c
        elif state == True:
            if c == '"':
                state = False
            elif c == "\\":
                i+=1
                if i >= len(data):
                    raise ValueError("unfinished escape sequence")
                res += data[i:i+1]
            else:
                res += c
        i+=1
    if res != "":
        if state or not top_level:
            raise ValueError("unfinished quote or parens")
        acc.append(res)
    return acc, ""

def imap_parse(data : str) -> _t.Any:
    res, rest = imap_parse_data(data)
    if rest != "":
        raise ValueError("unexpected tail", rest)
    return res

#print(imap_parse('(\\Trash \\Nya) "." "\\"All Mail"'))
#print(imap_parse('(1 2 3)'))
#print(imap_parse('1 2 3 4 "\\\\Nya" 5 6 7'))
#print(imap_parse('(1 2 3) 4 "\\\\Nya" 5 6 7'))
#print(imap_parse('(0 1) (1 2 3'))

def connect(args : _t.Any) -> _t.Any:
    IMAP_base : type
    if args.plain or args.starttls:
        port = 143
        IMAP_base = imaplib.IMAP4
    elif args.ssl:
        port = 993
        IMAP_base = imaplib.IMAP4_SSL

    if args.debug:
        binstderr = os.fdopen(sys.stderr.fileno(), "wb")
        class IMAP(IMAP_base):
            def send(self, data):
                binstderr.write(data)
                binstderr.flush()
                return super().send(data)

            def read(self, size):
                res = super().read(size)
                binstderr.write(res)
                binstderr.flush()
                return res

            def readline(self):
                res = super().readline()
                binstderr.write(res)
                binstderr.flush()
                return res
    else:
        IMAP = IMAP_base # type: ignore

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True
    ssl_context.load_default_certs()

    if args.ssl:
        srv = IMAP(args.host, port, ssl_context = ssl_context)
    else:
        srv = IMAP(args.host, port)
        if args.starttls:
            srv.starttls(ssl_context)

    srv.login(args.user, args.password)
    print(f"! logged in as {args.user} to {args.host}")

    return srv

def imap_quote(arg : str) -> str:
    arg = arg[:]
    arg = arg.replace('\\', '\\\\')
    arg = arg.replace('"', '\\"')
    return '"' + arg + '"'

imap_months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def imap_date(date):
    return f"{str(date.tm_mday)}-{imap_months[date.tm_mon-1]}-{str(date.tm_year)}"

def make_search_filter(args):
    filters = []

    if args.messages == "all":
        pass
    elif args.messages == "seen":
        filters.append(f"SEEN")
    elif args.messages == "unseen":
        filters.append(f"UNSEEN")
    else:
        assert False

    for f in args.hfrom:
        filters.append(f'FROM {imap_quote(f)}')

    for f in args.hnotfrom:
        filters.append(f'NOT FROM {imap_quote(f)}')

    now = int(time.time())
    if args.older_than is not None:
        date = time.gmtime(now - args.older_than * 86400)
        filters.append(f"BEFORE {imap_date(date)}")

    if args.newer_than is not None:
        date = time.gmtime(now - args.newer_than * 86400)
        filters.append(f"NOT BEFORE {imap_date(date)}")

    if len(filters) == 0:
        return "(ALL)"
    else:
        return "(" + " ".join(filters) + ")"

had_errors = False

def cmd_action(args):
    global had_errors

    search_filter = make_search_filter(args)
    #print(search_filter)
    #sys.exit(1)

    srv = connect(args)

    if len(args.folders) == 0:
        assert args.command == "count"

        typ, data = srv.list()
        for el in data:
            line = str(el, "utf-8")
            tags, _, arg = imap_parse(line)
            if "\\Noselect" in tags:
                continue
            args.folders.append(arg)

    for folder in args.folders:
        typ, data = srv.select(imap_quote(folder))
        if typ != "OK":
            sys.stderr.write("SELECT command failed: " + str(data[0], "utf-8") + "\n")
            had_errors = True
            continue

        typ, data = srv.uid("SEARCH", search_filter)
        if typ != "OK":
            sys.stderr.write("SEARCH command failed: " + str(data[0], "utf-8") + "\n")
            had_errors = True
            srv.close()
            continue

        result = str(data[0], "utf-8")
        if result == "":
            # nothing to do
            print(f"{folder} has 0 messages matching {search_filter}")
            srv.close()
            continue

        message_uids = result.split(" ")
        prefix = ""
        if args.command == "count":
            print(f"{folder} has {len(message_uids)} messages matching {search_filter}")
            srv.close()
            continue

        if args.dry_run:
            if args.command == "gmail_trash":
                print(f"--dry-run, otherwise would move {len(message_uids)} messages matching {search_filter} from {folder} to [GMail]/Trash")
            elif args.command == "delete":
                print(f"--dry-run, otherwise would delete {len(message_uids)} messages matching {search_filter} from {folder}")
            else:
                assert False
            srv.close()
            continue

        if args.command == "gmail_trash":
            print(f"moving {len(message_uids)} messages matching {search_filter} from {folder} to [GMail]/Trash")
        elif args.command == "delete":
            print(f"deleting {len(message_uids)} messages matching {search_filter} from {folder}")
        else:
            assert False

        while len(message_uids) > 0:
            to_delete = message_uids[:100]
            message_uids = message_uids[100:]
            joined = ",".join(to_delete)
            if args.command == "gmail_trash":
                print(f"... moving a batch of {len(to_delete)} messages matching {search_filter} from {folder} to [GMail]/Trash")
                srv.uid('STORE', joined, '+X-GM-LABELS', '\\Trash')
            elif args.command == "delete":
                print(f"... deleting a batch of {len(to_delete)} messages matching {search_filter} from {folder}")
                srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Deleted")
                srv.expunge()
            else:
                assert False

        srv.close()

    srv.logout()

def add_examples(fmt):
    fmt.add_text("# Notes on usage")

    fmt.add_text("Specifying `--folder` multiple times will perform the specified action on all specified folders.")

    fmt.add_text('Message search filters are connected by logical "AND"s so `--from "github.com" --not-from "notifications@github.com"` will act on messages from "github.com" but not from "notifications@github.com".')

    fmt.add_text("Also note that destructive actions act on `--seen` messages by default.")

    fmt.add_text("# Examples")

    fmt.start_section("List all available IMAP folders and count how many messages they contain")

    fmt.start_section("with the password taken from the first line of the given file")
    fmt.add_code('imaparms count --ssl --host imap.example.com --user myself@example.com --passfile /path/to/file/containing/myself@example.com.password')
    fmt.end_section()

    fmt.start_section("with the password taken from the output of password-store util")
    fmt.add_code('imaparms count --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com"')
    fmt.end_section()

    fmt.end_section()

    fmt.start_section('Delete all seen messages older than 7 days from `INBOX` folder')
    fmt.add_text("""
Assuming you fetched and backed up all your messages already this allows you to keep as little as possible on the server, so that if your account gets hacked, you won't be as vulnerable.""")
    fmt.add_code('imaparms delete --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX" --older-than 7')
    fmt.add_text("Note that the above only removes `--seen` messages by default.")
    fmt.end_section()

    fmt.start_section("""**DANGEROUS!** If you fetched and backed up all your messages already, you can skip `--older-than` and just delete all `--seen` messages instead:""")
    fmt.add_code('imaparms delete --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX"')
    fmt.add_text("Though, setting at least `--older-than 1` in case you forgot you had another fetcher running in parallel and you want to be sure you won't lose any data in case something breaks, is highly recommended anyway.")
    fmt.end_section()

    fmt.start_section('Count how many messages older than 7 days are in "[Gmail]/Trash" folder')
    fmt.add_code('imaparms count --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --older-than 7')
    fmt.end_section()

    fmt.start_section('GMail-specific mode: move old messages from "[Gmail]/All Mail" to Trash')

    fmt.add_text("""
Unfortunately, in GMail, deleting messages from "INBOX" does not actually delete them, nor moves them to "Trash", just removes them from "INBOX", so this tool provides a GMail-specific command that moves messages to "Trash" on GMail:""")

    fmt.add_code('imaparms gmail-trash --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/All Mail" --older-than 7')

    fmt.add_text("Also, note that the above only moves `--seen` messages by default.")

    fmt.add_text("after which you can now delete them (and other matching messages in Trash) with")

    fmt.add_code('imaparms delete --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --all --older-than 7')
    fmt.end_section()

def main() -> None:
    global _

    parser = argparse.BetterArgumentParser(
        prog="imaparms",
        description="Login to an IMAP4 server and perform actions on messages in specified folders matching specified criteria.",
        additional_sections = [add_examples],
        add_help = True,
        add_version = True)
    parser.add_argument("--help-markdown", action="store_true", help=_("show this help message formatted in Markdown and exit"))

    def no_cmd(args):
        parser.print_help(sys.stderr)
        sys.exit(2)
    parser.set_defaults(func=no_cmd)

    def add_common(cmd):
        agrp = cmd.add_argument_group("debugging")
        agrp.add_argument("--debug", action="store_true", help="print IMAP conversation to stderr")
        agrp.add_argument("--dry-run", action="store_true", help="don't perform any actions, only show what would be done")

        agrp = cmd.add_argument_group("server connection")
        grp = agrp.add_mutually_exclusive_group(required = True)
        grp.add_argument("--plain", action="store_true", help="connect via plain-text socket")
        grp.add_argument("--ssl", action="store_true", help="connect over SSL socket")
        grp.add_argument("--starttls", action="store_true", help="connect via plain-text socket, but then use STARTTLS command")

        agrp.add_argument("--host", type=str, required=True, help="IMAP server to connect to")
        agrp.add_argument("--port", type=int, help="port to use; default: 143 for `--plain` and `--starttls`, 993 for `--ssl`")
        agrp.add_argument("--user", type=str, required = True, help="username on the server")

        grp = agrp.add_mutually_exclusive_group(required = True)
        grp.add_argument("--passfile", type=str, help="file containing the password")
        grp.add_argument("--passcmd", type=str, help="shell command that returns the password as the first line of its stdout")

    def add_filters_min(cmd, seen_by_default = True):
        agrp = cmd.add_argument_group("message search filters")
        grp = agrp.add_mutually_exclusive_group()

        def_all = ""
        def_seen = ""
        def_str = " (default)"
        if not seen_by_default:
            grp.set_defaults(messages = "all")
            def_all = def_str
        else:
            grp.set_defaults(messages = "seen")
            def_seen = def_str
        grp.add_argument("--all", dest="messages", action="store_const", const = "all", help=f"operate on all messages{def_all}")
        grp.add_argument("--seen", dest="messages", action="store_const", const = "seen", help=f"operate on messages marked as seen{def_seen}")
        grp.add_argument("--unseen", dest="messages", action="store_const", const = "unseen", help="operate on messages not marked as seen")

        agrp.add_argument("--older-than", metavar = "DAYS", type=int, help="operate on messages older than this many days")
        agrp.add_argument("--newer-than", metavar = "DAYS", type=int, help="operate on messages not older than this many days")

        agrp.add_argument("--from", dest="hfrom", metavar = "ADDRESS", action = "append", type=str, default = [], help="operate on messages that have this string as substring of their header's FROM field; can be specified multiple times")
        agrp.add_argument("--not-from", dest="hnotfrom", metavar = "ADDRESS", action = "append", type=str, default = [], help="operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times")

    def add_filters_act(cmd):
        cmd.add_argument("--folder", dest="folders", action="append", type=str, default=[], required = True, help='mail folders to operate on; can be specified multiple times; required')
        add_filters_min(cmd)

    subparsers = parser.add_subparsers(title="subcommands")

    cmd = subparsers.add_parser("count", help="count how many matching messages specified folders (or all of them, by default) contain")
    add_common(cmd)
    cmd.add_argument("--folder", dest="folders", action="append", type=str, default=[], help='mail folders to operane on; can be specified multiple times; default: all available mail folders')
    add_filters_min(cmd, False)
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="count")

    cmd = subparsers.add_parser("delete", help="delete (and expunge) matching messages from all specified folders")
    add_common(cmd)
    add_filters_act(cmd)
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="delete")

    cmd = subparsers.add_parser("gmail-trash", help="GMail-specific: move matching messages to GMail's Trash folder from all specified folders")
    add_common(cmd)
    add_filters_act(cmd)
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="gmail_trash")

    args = parser.parse_args(sys.argv[1:])

    if args.help_markdown:
        parser.set_formatter_class(argparse.MarkdownBetterHelpFormatter)
        print(parser.format_help(1024))
        parser.exit()

    if args.passfile is not None:
        with open(args.passfile, "rb") as f:
            password = str(f.readline(), "utf-8")
    elif args.passcmd is not None:
        with subprocess.Popen(args.passcmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, shell=True) as p:
            p.stdin.close() # type: ignore
            password = str(p.stdout.readline(), "utf-8") # type: ignore
            retcode = p.wait()
            if retcode != 0:
                raise SystemError("failed to execute passcmd")
    else:
        assert False

    if password[-1:] == "\n":
        password = password[:-1]

    args.password = password

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("Interrupted.\n")
        if had_errors:
            print("Had errors!\n")
            sys.exit(5)
        sys.exit(4)
    else:
        if had_errors:
            print("Had errors!\n")
            sys.exit(1)
        sys.exit(0)

if __name__ == '__main__':
    main()
