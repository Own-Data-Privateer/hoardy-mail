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
from .exceptions import *

def imap_parse_data(data : str, literals : _t.List[bytes] = [], top_level : bool = True) -> _t.Tuple[_t.Any, str]:
    "Parse IMAP response string into a tree of strings."
    acc : _t.List[_t.Union[str, bytes]] = []
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
                res, data = imap_parse_data(data[i+1:], literals, False)
                acc.append(res)
                res = ""
                i = 0
                if len(data) == 0:
                    return acc, ""
                elif data[i] not in [" ", ")"]:
                    raise ValueError("expecting space or end parens")
            elif c == ")":
                acc.append(res)
                return acc, data[i+1:]
            elif c == "{":
                if res != "":
                    raise ValueError("unexpected curly")
                endcurly = data.find("}", i + 1)
                if endcurly == -1:
                    raise ValueError("expected curly")
                acc.append(literals.pop(0))
                i = endcurly + 1
                if i >= len(data):
                    return acc, ""
                elif data[i] not in [" ", ")"]:
                    raise ValueError("expecting space or end parens")
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

def imap_parse(line : bytes, literals : _t.List[bytes] = []) -> _t.Any:
    res, rest = imap_parse_data(line.decode("utf-8"), literals)
    if rest != "":
        raise ValueError("unexpected tail", rest)
    return res

##print(imap_parse(b'(0 1) (1 2 3'))
#print(imap_parse(b'(\\Trash \\Nya) "." "\\"All Mail"'))
#print(imap_parse(b'(1 2 3)'))
#print(imap_parse(b'(0 1) ((1 2 3))'))
#print(imap_parse(b'(0 1) ((1 2 3) )'))
#print(imap_parse(b'1 2 3 4 "\\\\Nya" 5 6 7'))
#print(imap_parse(b'(1 2 3) 4 "\\\\Nya" 5 6 7'))
#print(imap_parse(b'1 (UID 123 RFC822.SIZE 128)'))
#print(imap_parse(b'1 (UID 123 BODY[HEADER] {128})', [b"128"]))
#sys.exit(1)

def imap_parse_attrs(data : _t.List[_t.Union[str, bytes]]) -> _t.Dict[_t.Union[str, bytes], _t.Union[str, bytes]]:
    if len(data) % 2 != 0:
        raise ValueError("data array of non-even length")

    res = {}
    for i in range(0, len(data), 2):
        name = data[i].upper()
        value = data[i+1]
        res[name] = value
    return res

def connect(args : _t.Any) -> _t.Any:
    IMAP_base : type
    if args.plain or args.starttls:
        port = 143
        IMAP_base = imaplib.IMAP4
    elif args.ssl:
        port = 993
        IMAP_base = imaplib.IMAP4_SSL

    if args.port is not None:
        port = args.port

    if args.debug:
        binstderr = os.fdopen(sys.stderr.fileno(), "wb")
        class IMAP(IMAP_base):
            def send(self, data):
                binstderr.write(b"C: " + data)
                binstderr.flush()
                return super().send(data)

            def read(self, size):
                res = super().read(size)
                binstderr.write(b"S: " + res)
                binstderr.flush()
                return res

            def readline(self):
                res = super().readline()
                binstderr.write(b"S: " + res)
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
    elif args.messages == "flagged":
        filters.append(f"FLAGGED")
    elif args.messages == "unflagged":
        filters.append(f"UNFLAGGED")
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

def error(command : str, desc : str, data : _t.Any = None) -> None:
    global had_errors
    had_errors = True
    if data is None:
        sys.stderr.write("error: %s command failed: %s" % (command, desc) + "\n")
    else:
        sys.stderr.write("error: %s command failed: %s %s" % (command, desc, repr(data)) + "\n")

def imap_check(exc, command, v):
    global had_errors
    typ, data = v
    if typ != "OK":
        had_errors = True
        raise exc("%s command failed: %s %s", command, typ, repr(data))
    return data

def cmd_action(args):
    search_filter = make_search_filter(args)
    #print(search_filter)
    #sys.exit(1)

    if args.command == "fetch":
        if args.mark == "auto":
            if args.messages == "unseen":
                args.mark = "seen"
            elif args.messages == "unflagged":
                args.mark = "flagged"
            else:
                args.mark = "noop"
    elif args.command == "delete":
        if args.method == "auto":
            if args.host in ["imap.gmail.com"] and \
               args.folders != ["[Gmail]/Trash"]:
                args.method = "gmail-trash"
            else:
                args.method = "delete"

    try:
        srv = connect(args)
    except Exception as exc:
        raise CatastrophicFailure("failed to connect to host %s port %s: %s", args.host, args.port, repr(exc))

    data = imap_check(CatastrophicFailure, "CAPABILITY", srv.capability())
    capabilities = data[0].decode("utf-8").split(" ")
    #print(capabilities)
    if "IMAP4rev1" not in capabilities:
        raise CatastrophicFailure("host %s port %s does not speak IMAP4rev1, sorry but server software is too old to be supported", args.host, args.port)

    if len(args.folders) == 0:
        assert args.command in ["count", "fetch"]

        typ, data = srv.list()
        for el in data:
            tags, _, arg = imap_parse(el)
            if "\\Noselect" in tags:
                continue
            args.folders.append(arg)

    for folder in args.folders:
        typ, data = srv.select(imap_quote(folder))
        if typ != "OK":
            error("SELECT", typ, data)
            continue

        typ, data = srv.uid("SEARCH", search_filter)
        if typ != "OK":
            error("SEARCH", typ, data)
            srv.close()
            continue

        result = data[0].decode("utf-8")
        if result == "":
            message_uids = []
        else:
            message_uids = result.split(" ")

        if args.command == "count":
            print(f"{folder} has {len(message_uids)} messages matching {search_filter}")
            srv.close()
            continue
        elif len(message_uids) == 0:
            # nothing to do
            print(f"no messages matching {search_filter} in {folder}")
            srv.close()
            continue

        if args.command == "mark":
            act = f"marking as {args.mark.upper()} {len(message_uids)} messages matching {search_filter} from {folder}"
        elif args.command == "fetch":
            act = f"fetching {len(message_uids)} messages matching {search_filter} from {folder}"
        elif args.command == "delete":
            if args.method in ["delete", "delete-noexpunge"]:
                act = f"deleting {len(message_uids)} messages matching {search_filter} from {folder}"
            elif args.method == "gmail-trash":
                act = f"moving {len(message_uids)} messages matching {search_filter} from {folder} to [GMail]/Trash"
            else:
                assert False
        else:
            assert False

        if args.dry_run:
            print(f"dry-run, not {act}")
            srv.close()
            continue
        else:
            print(act)

        if args.command == "mark":
            do_store(args, srv, args.mark, message_uids, search_filter, folder)
        elif args.command == "fetch":
            do_fetch(args, srv, message_uids, search_filter, folder)
        elif args.command == "delete":
            do_store(args, srv, args.method, message_uids, search_filter, folder)

        srv.close()

    srv.logout()

def do_fetch(args, srv, message_uids, search_filter, folder):
    fetch_num = args.fetch_number
    batch = []
    batch_total = 0
    while len(message_uids) > 0:
        to_fetch, message_uids = message_uids[:fetch_num], message_uids[fetch_num:]
        to_fetch_set = set(to_fetch)
        typ, data = srv.uid("FETCH", ",".join(to_fetch), "(RFC822.SIZE)")
        if typ != "OK":
            error("FETCH", typ, data)
            continue

        new = []
        for el in data:
            _, attrs_ = imap_parse(el)
            attrs = imap_parse_attrs(attrs_)

            uid = attrs["UID"]
            size = int(attrs["RFC822.SIZE"])
            new.append((uid, size))
            to_fetch_set.remove(uid)

        if len(to_fetch_set) > 0:
            error("FETCH", "did not get enough elements")
            continue

        while True:
            leftovers = []
            for uel in new:
                uid, size = uel
                if len(batch) < args.batch_number and batch_total + size < args.batch_size:
                    batch_total += size
                    batch.append(uid)
                else:
                    leftovers.append(uel)

            if len(leftovers) == 0:
                break

            if len(batch) == 0:
                uid, size = leftovers.pop(0)
                batch_total += size
                batch.append(uid)

            do_fetch_batch(args, srv, batch, batch_total, search_filter, folder)
            batch = []
            batch_total = 0
            new = leftovers

    do_fetch_batch(args, srv, batch, batch_total, search_filter, folder)

def do_fetch_batch(args, srv, messages, total_size, search_filter, folder):
    global had_errors

    if len(messages) == 0: return
    print(f"... fetching a batch of {len(messages)} messages ({total_size} bytes) matching {search_filter} from {folder}")

    joined = ",".join(messages)
    typ, data = srv.uid("FETCH", joined, "(BODY.PEEK[HEADER] BODY.PEEK[TEXT])")
    if typ != "OK":
        error("FETCH", typ, data)
        return

    done_messages = []
    while len(data) > 0:
        # have to do this whole thing beacause imaplib returns
        # multiple outputs as a flat list of partially-parsed chunks,
        # so we need (xxx) detector to make any sense of it
        chunks = []
        literals = []
        while len(data) > 0:
            el = data.pop(0)
            if isinstance(el, tuple):
                piece, lit = el
                chunks.append(piece)
                literals.append(lit)
            else:
                chunks.append(el)
                if el.endswith(b")"):
                    # (xxx)
                    break

        line = b"".join(chunks)
        _, attrs_ = imap_parse(line, literals)
        attrs = imap_parse_attrs(attrs_)
        #print(attrs)

        uid = attrs["UID"]
        header = attrs["BODY[HEADER]"]
        body = attrs["BODY[TEXT]"]
        if True:
            # strip \r like fetchmail does
            header = header.replace(b"\r\n", b"\n")
            body = body.replace(b"\r\n", b"\n")

        # try delivering to MDA
        delivered = True
        with subprocess.Popen(args.mda, stdin=subprocess.PIPE, stdout=None, stderr=None, shell=True) as p:
            fd : _t.Any = p.stdin # type: ignore
            try:
                fd.write(header)
                fd.write(body)
            except BrokenPipeError:
                delivered = False
            finally:
                fd.close()

            retcode = p.wait()
            if retcode != 0:
                delivered = False

        if delivered:
            done_messages.append(uid)
        else:
            sys.stderr.write("MDA failed to deliver message %s" % (uid,) + "\n")
            had_errors = True

    print(f"! delivered a batch of {len(done_messages)} messages matching {search_filter} from {folder} via {args.mda}")
    do_store(args, srv, args.mark, done_messages, search_filter, folder)

def do_store(args, srv, method, message_uids, search_filter, folder):
    if method == "noop": return

    store_num = args.store_number
    while len(message_uids) > 0:
        to_store, message_uids = message_uids[:store_num], message_uids[store_num:]
        joined = ",".join(to_store)
        if method == "seen":
            print(f"... marking as SEEN a batch of {len(to_store)} messages matching {search_filter} from {folder}")
            srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Seen")
        elif method == "unseen":
            print(f"... marking as UNSEEN a batch of {len(to_store)} messages matching {search_filter} from {folder}")
            srv.uid("STORE", joined, "-FLAGS.SILENT", "\\Seen")
        elif method == "flagged":
            print(f"... marking as FLAGGED a batch of {len(to_store)} messages matching {search_filter} from {folder}")
            srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Flagged")
        elif method == "unflagged":
            print(f"... marking as UNFLAGGED a batch of {len(to_store)} messages matching {search_filter} from {folder}")
            srv.uid("STORE", joined, "-FLAGS.SILENT", "\\Flagged")
        elif method in ["delete", "delete-noexpunge"]:
            print(f"... deleting a batch of {len(to_store)} messages matching {search_filter} from {folder}")
            srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Deleted")
            if method == "delete":
                srv.expunge()
        elif method == "gmail-trash":
            print(f"... moving a batch of {len(to_store)} messages matching {search_filter} from {folder} to [GMail]/Trash")
            srv.uid("STORE", joined, "+X-GM-LABELS", "\\Trash")
        else:
            assert False

def add_examples(fmt):
    fmt.add_text("# Notes on usage")

    fmt.add_text("Specifying `--folder` multiple times will perform the specified action on all specified folders.")

    fmt.add_text('Message search filters are connected by logical "AND"s so `--from "github.com" --not-from "notifications@github.com"` will act on messages from "github.com" but not from "notifications@github.com".')

    fmt.add_text("Also note that `fetch` and `delete` subcommands act on `--seen` messages by default.")

    fmt.add_text("# Examples")

    fmt.start_section("List all available IMAP folders and count how many messages they contain")

    fmt.start_section("with the password taken from the first line of the given file")
    fmt.add_code('imaparms count --ssl --host imap.example.com --user myself@example.com --passfile /path/to/file/containing/myself@example.com.password')
    fmt.end_section()

    fmt.start_section("with the password taken from the output of password-store util")
    fmt.add_code('imaparms count --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com"')
    fmt.end_section()

    fmt.end_section()

    fmt.start_section("Mark all messages in `INBOX` as UNSEEN, and then fetch all UNSEEN messages marking them SEEN as you download them, so that if the process gets interrupted you could continue from where you left off")
    fmt.add_code('imaparms mark unseen --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX" --all')
    fmt.add_code('imaparms fetch --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX"')
    fmt.end_section()

    fmt.start_section("Fetch all messages from `INBOX` folder that were delivered in the last 7 days, but don't change any flags")
    fmt.add_code('imaparms fetch --mark noop --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX" --all --newer-than 7')
    fmt.end_section()

    fmt.start_section('Delete all SEEN messages older than 7 days from `INBOX` folder')
    fmt.add_text("""
Assuming you fetched and backed up all your messages already this allows you to keep as little as possible on the server, so that if your account gets hacked, you won't be as vulnerable.""")
    fmt.add_code('imaparms delete --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX" --older-than 7')
    fmt.add_text("Note that the above only removes `--seen` messages by default.")
    fmt.end_section()

    fmt.start_section("""**DANGEROUS!** If you fetched and backed up all your messages already, you can skip `--older-than` and just delete all `--seen` messages instead""")
    fmt.add_code('imaparms delete --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX"')
    fmt.add_text("Though, setting at least `--older-than 1` in case you forgot you had another fetcher running in parallel and you want to be sure you won't lose any data in case something breaks, is highly recommended anyway.")
    fmt.end_section()

    fmt.start_section('Count how many messages older than 7 days are in `[Gmail]/Trash` folder')
    fmt.add_code('imaparms count --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --older-than 7')
    fmt.end_section()

    fmt.start_section('GMail-specific deletion mode: move (expire) old messages from `[Gmail]/All Mail` to `[Gmail]/Trash`')

    fmt.add_text("""
Unfortunately, in GMail, deleting messages from `INBOX` does not actually delete them, nor moves them to trash, just removes them from `INBOX` while keeping them available from `[Gmail]/All Mail`.""")
    fmt.add_text("""To work around this, this tool provides a GMail-specific deletion method that moves messages to `[Gmail]/Trash` in a GMail-specific way (this is not a repetition, it does require issuing special STORE commands to achieve this).""")
    fmt.add_text("""You will probably want to run it over `[Gmail]/All Mail` folder (again, after you fetched everything from there) instead of `INBOX`:""")

    fmt.add_code('imaparms delete --method gmail-trash --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/All Mail" --older-than 7')
    fmt.add_text("which is equivalent to simply")
    fmt.add_code('imaparms delete --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/All Mail" --older-than 7')
    fmt.add_text("""since `--method gmail-trash` is the default when `--host imap.gmail.com` and `--folder` is not `[Gmail]/Trash`""")

    fmt.add_text("Also, note that the above only moves `--seen` messages by default.")

    fmt.add_text("""Messages in `[Gmail]/Trash` will be automatically removed by GMail in 30 days, but you can also delete them immediately with""")

    fmt.add_code('imaparms delete --method delete --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --all --older-than 7')
    fmt.add_text("which is equivalent to simply")
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

    agrp = parser.add_argument_group("IMAP batching settings", description = "larger values improve performance but produce longer command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen")
    agrp.add_argument("--store-number", metavar = "INT", type=int, default = 150, help="batch at most this many message UIDs in IMAP STORE requests (default: %(default)s)")
    agrp.add_argument("--fetch-number", metavar = "INT", type=int, default = 150, help="batch at most this many message UIDs in IMAP FETCH metadata requests (default: %(default)s)")
    agrp.add_argument("--batch-number", metavar = "INT", type=int, default = 150, help="batch at most this many message UIDs in IMAP FETCH data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: %(default)s)")
    agrp.add_argument("--batch-size", metavar = "INT", type=int, default = 4 * 1024 * 1024, help="FETCH at most this many bytes of RFC822 messages at once; essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted (default: %(default)s)")

    agrp = parser.add_argument_group("delivery settings")
    agrp.add_argument("--mda", dest="mda", metavar = "COMMAND", type=str, help="shell command to use as an MDA to deliver the messages to (required for `fetch` subcommand)" + "\n" + """`imaparms` will spawn COMMAND via the shell and then feed raw RFC822 message into its `stdin`, the resulting process is then responsible for delivering the message to `mbox`, `Maildir`, etc.
`maildrop` from Courier Mail Server project is a good KISS default.
""")

    def no_cmd(args):
        parser.print_help(sys.stderr)
        sys.exit(2)
    parser.set_defaults(func=no_cmd)

    def add_common(cmd, dry_run : bool = False):
        agrp = cmd.add_argument_group("debugging")
        agrp.add_argument("--debug", action="store_true", help="print IMAP conversation to stderr")
        if dry_run:
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

    def add_filters(cmd, messages):
        def_req = ""
        def_str = " (default)"
        def_all, def_seen, def_unseen = "", "", ""
        if messages is None:
            def_req = " (required)"
        elif messages == "all":
            def_all = def_str
        elif messages == "seen":
            def_seen = def_str
        elif messages == "unseen":
            def_unseen = def_str
        else:
            assert False

        agrp = cmd.add_argument_group("message search filters" + def_req)
        grp = agrp.add_mutually_exclusive_group(required = messages is None)
        grp.add_argument("--all", dest="messages", action="store_const", const = "all", help="operate on all messages" + def_all)
        grp.add_argument("--seen", dest="messages", action="store_const", const = "seen", help="operate on messages marked as SEEN" + def_seen)
        grp.add_argument("--unseen", dest="messages", action="store_const", const = "unseen", help="operate on messages not marked as SEEN" + def_unseen)
        grp.add_argument("--flagged", dest="messages", action="store_const", const = "flagged", help="operate on messages marked as FLAGGED")
        grp.add_argument("--unflagged", dest="messages", action="store_const", const = "unflagged", help="operate on messages not marked as FLAGGED")
        grp.set_defaults(messages = messages)

        agrp.add_argument("--older-than", metavar = "DAYS", type=int, help="operate on messages older than this many days")
        agrp.add_argument("--newer-than", metavar = "DAYS", type=int, help="operate on messages not older than this many days")

        agrp.add_argument("--from", dest="hfrom", metavar = "ADDRESS", action = "append", type=str, default = [], help="operate on messages that have this string as substring of their header's FROM field; can be specified multiple times")
        agrp.add_argument("--not-from", dest="hnotfrom", metavar = "ADDRESS", action = "append", type=str, default = [], help="operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times")

    def add_folders(cmd):
        agrp = cmd.add_argument_group("folder specification")
        agrp.add_argument("--folder", metavar = "NAME", dest="folders", action="append", type=str, default=[], help='mail folders to operane on; can be specified multiple times (default: all available mail folders)')

    def add_req_folders(cmd):
        agrp = cmd.add_argument_group("folder specification")
        agrp.add_argument("--folder", metavar = "NAME", dest="folders", action="append", type=str, default=[], required = True, help='mail folders to operate on; can be specified multiple times (required)')

    subparsers = parser.add_subparsers(title="subcommands")

    cmd = subparsers.add_parser("count", help="count how many matching messages specified folders (or all of them, by default) contain")
    add_common(cmd)
    add_filters(cmd, "all")
    add_folders(cmd)
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="count")

    cmd = subparsers.add_parser("mark", help="mark matching messages in specified folders with a specified way")
    add_common(cmd, True)
    add_filters(cmd, None)
    add_req_folders(cmd)
    agrp = cmd.add_argument_group("marking")
    agrp.add_argument("mark", choices=["seen", "unseen", "flagged", "unflagged"], help="""mark how (required):
- `seen`: add `SEEN` flag
- `unseen`: remove `SEEN` flag
- `flag`: add `FLAGGED` flag
- `unflag`: remove `FLAGGED` flag
""")
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="mark")

    cmd = subparsers.add_parser("fetch", help="fetch matching messages from specified folders, feed them to an MDA, and then mark them in a specified way if MDA succeeds")
    add_common(cmd, True)
    add_filters(cmd, "unseen")
    add_req_folders(cmd)
    agrp = cmd.add_argument_group("marking")
    agrp.add_argument("--mark", choices=["auto", "noop", "seen", "unseen", "flagged", "unflagged"], default = "auto", help="""after the message was fetched:
- `auto`: `flagged` when `--unflagged`, `--seen` when `--unseen`, `noop` otherwise (default)
- `noop`: do nothing
- `seen`: add `SEEN` flag
- `unseen`: remove `SEEN` flag
- `flagged`: add `FLAGGED` flag
- `unflagged`: remove `FLAGGED` flag
""")
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="fetch")

    cmd = subparsers.add_parser("delete", help="delete matching messages from specified folders")
    add_common(cmd, True)
    add_filters(cmd, "seen")
    cmd.add_argument("--method", choices=["auto", "delete", "delete-noexpunge", "gmail-trash"], default="auto", help="""delete messages how:
- `auto`: `gmail-trash` when `--host imap.gmail.com` and `--folder` is not (single) `[Gmail]/Trash`, `delete` otherwise (default)
- `delete`: mark messages with `\\Deleted` flag and then use IMAP `EXPUNGE` command, i.e. this does what you would expect a "delete" command to do, works for most IMAP servers
- `delete-noexpunge`: mark messages with `\\Deleted` flag but skip issuing IMAP `EXPUNGE` command hoping the server does as RFC2060 says and auto-`EXPUNGE`s messages on IMAP `CLOSE`; this is much faster than `delete` but some servers (like GMail) fail to implement this properly
- `gmail-trash`: move messages to `[Gmail]/Trash` in GMail-specific way instead of trying to delete them immediately (GMail ignores IMAP `EXPUNGE` outside of `[Gmail]/Trash`, you can then `imaparms delete --method delete --folder "[Gmail]/Trash"` them after, or you could just leave them there and GMail will delete them in 30 days)
""")
    add_req_folders(cmd)
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="delete")

    args = parser.parse_args(sys.argv[1:])

    if args.help_markdown:
        parser.set_formatter_class(argparse.MarkdownBetterHelpFormatter)
        print(parser.format_help(1024))
        parser.exit()

    if args.passfile is not None:
        with open(args.passfile, "rb") as f:
            password = f.readline().decode("utf-8")
    elif args.passcmd is not None:
        with subprocess.Popen(args.passcmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, shell=True) as p:
            p.stdin.close() # type: ignore
            password = p.stdout.readline().decode("utf-8") # type: ignore
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
    except CatastrophicFailure as exc:
        sys.stderr.write("error: " + exc.show() + "\n")
        print("Had errors!")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Interrupted.")
        if had_errors:
            print("Had errors!")
            sys.exit(5)
        sys.exit(4)
    else:
        if had_errors:
            print("Had errors!")
            sys.exit(1)
        sys.exit(0)

if __name__ == '__main__':
    main()
