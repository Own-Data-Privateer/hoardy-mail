#!/usr/bin/env python3
#
# Copyright (c) 2023 Jan Malakovski <oxij@oxij.org>
#
# This file can be distributed under the terms of the GNU GPL, version 3 or later.

import dataclasses as _dc
import os
import signal
import ssl
import subprocess
import sys
import time
import traceback as traceback
import typing as _t

from imaplib import IMAP4, IMAP4_SSL
from gettext import gettext, ngettext

from . import argparse
from .exceptions import *

want_stop = False
raise_once = False
def sig_handler(signal : int, frame : _t.Any) -> None:
    global want_stop
    global raise_once
    want_stop = True
    if raise_once:
        raise_once = False
        raise KeyboardInterrupt()

def handle_signals() -> None:
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

def imap_parse_data(data : bytes, literals : _t.List[bytes] = [], top_level : bool = True) -> _t.Tuple[_t.Any, bytes]:
    "Parse IMAP response string into a tree of strings."
    acc : _t.List[bytes] = []
    res = b""
    i = 0
    state = False
    while i < len(data):
        c = data[i:i+1]
        #print(c)
        if state == False:
            if c == b'"':
                if res != b"":
                    raise ValueError("unexpected quote")
                res = b""
                state = True
            elif c == b" ":
                acc.append(res)
                res = b""
            elif c == b"(":
                if res != b"":
                    raise ValueError("unexpected parens")
                res, data = imap_parse_data(data[i+1:], literals, False)
                acc.append(res)
                res = b""
                i = 0
                if len(data) == 0:
                    return acc, b""
                elif data[i:i+1] not in [b" ", b")"]:
                    raise ValueError("expecting space or end parens")
            elif c == b")":
                acc.append(res)
                return acc, data[i+1:]
            elif c == b"{":
                if res != b"":
                    raise ValueError("unexpected curly")
                endcurly = data.find(b"}", i + 1)
                if endcurly == -1:
                    raise ValueError("expected curly")
                acc.append(literals.pop(0))
                i = endcurly + 1
                if i >= len(data):
                    return acc, b""
                elif data[i:i+1] not in [b" ", b")"]:
                    raise ValueError("expecting space or end parens")
            else:
                if type(res) is not bytes:
                    raise ValueError("unexpected char")
                res += c
        elif state == True:
            if c == b'"':
                state = False
            elif c == b"\\":
                i+=1
                if i >= len(data):
                    raise ValueError("unfinished escape sequence")
                res += data[i:i+1]
            else:
                res += c
        i+=1
    if res != b"":
        if state or not top_level:
            raise ValueError("unfinished quote or parens")
        acc.append(res)
    return acc, b""

def imap_parse(line : bytes, literals : _t.List[bytes] = []) -> _t.Any:
    res, rest = imap_parse_data(line, literals)
    if rest != b"":
        raise ValueError("unexpected tail", rest)
    return res

##print(imap_parse(b'(0 1) (1 2 3'))
#print(imap_parse(b'(\\Trash \\Nya) "." "All Mail"'))
#print(imap_parse(b'(\\Trash \\Nya) "." "All\\"Mail"'))
#print(imap_parse(b'(1 2 3)'))
#print(imap_parse(b'(0 1) ((1 2 3))'))
#print(imap_parse(b'(0 1) ((1 2 3) )'))
#print(imap_parse(b'1 2 3 4 "\\\\Nya" 5 6 7'))
#print(imap_parse(b'(1 2 3) 4 "\\\\Nya" 5 6 7'))
#print(imap_parse(b'1 (UID 123 RFC822.SIZE 128)'))
#print(imap_parse(b'1 (UID 123 BODY[HEADER] {128})', [b'128bytesofdata']))
#sys.exit(1)

def imap_parse_attrs(data : _t.List[bytes]) -> _t.Dict[bytes, bytes]:
    if len(data) % 2 != 0:
        raise ValueError("data array of non-even length")

    res = {}
    for i in range(0, len(data), 2):
        name = data[i].upper()
        value = data[i+1]
        res[name] = value
    return res

#print(imap_parse_attrs(imap_parse(b'UID 123 BODY[HEADER] {128}', [b'128bytesofdata'])))
#sys.exit(1)

def imap_quote(arg : str) -> str:
    arg = arg[:]
    arg = arg.replace('\\', '\\\\')
    arg = arg.replace('"', '\\"')
    return '"' + arg + '"'

imap_months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def imap_date(date : time.struct_time) -> str:
    return f"{str(date.tm_mday)}-{imap_months[date.tm_mon-1]}-{str(date.tm_year)}"

def make_search_filter(args : _t.Any) -> str:
    filters = []

    if args.seen is not None:
        if args.seen:
            filters.append("SEEN")
        else:
            filters.append("UNSEEN")

    if args.flagged is not None:
        if args.flagged:
            filters.append("FLAGGED")
        else:
            filters.append("UNFLAGGED")

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

def die(desc : str, code : int = 1) -> None:
    _ = gettext
    sys.stderr.write(_("error") + ": " + desc + "\n")
    sys.exit(code)

had_errors = False
def imap_error(command : str, desc : str, data : _t.Any = None) -> None:
    _ = gettext
    global had_errors
    had_errors = True
    if data is None:
        sys.stderr.write(_("error") + ": " + (_("%s command failed") + ": %s") % (command, desc) + "\n")
    else:
        sys.stderr.write(_("error") + ": " + (_("%s command failed") + ": %s %s") % (command, desc, repr(data)) + "\n")

def imap_check(exc : _t.Any, command : str, v : _t.Tuple[str, _t.Any]) -> _t.Any:
    global had_errors
    typ, data = v
    if typ != "OK":
        had_errors = True
        raise exc("%s command failed: %s %s", command, typ, repr(data))
    return data

@_dc.dataclass
class Account:
    socket : str
    host : str
    port : int
    user : str
    password : str
    IMAP_base : type

def connect(account : Account, debug : bool) -> _t.Any:
    if debug:
        binstderr = os.fdopen(sys.stderr.fileno(), "wb")
        class IMAP(account.IMAP_base): # type: ignore
            def send(self, data : bytes) -> int:
                binstderr.write(b"C: " + data)
                binstderr.flush()
                return super().send(data) # type: ignore

            def read(self, size : int) -> bytes:
                res = super().read(size)
                binstderr.write(b"S: " + res)
                binstderr.flush()
                return res # type: ignore

            def readline(self) -> bytes:
                res = super().readline()
                binstderr.write(b"S: " + res)
                binstderr.flush()
                return res # type: ignore
    else:
        IMAP = account.IMAP_base # type: ignore

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True
    ssl_context.load_default_certs()

    try:
        if account.socket == "ssl":
            srv = IMAP(account.host, account.port, ssl_context = ssl_context)
        else:
            srv = IMAP(account.host, account.port)
            if account.socket == "starttls":
                srv.starttls(ssl_context)
    except Exception as exc:
        raise CatastrophicFailure("failed to connect to host %s port %s: %s", account.host, account.port, repr(exc))

    return srv

def for_each_account_poll(cfg : _t.Any, func : _t.Callable[..., None], *args : _t.Any) -> None:
    global raise_once

    fmt = "[%Y-%m-%d %H:%M:%S]"
    cycle = cfg.every

    while True:
        if want_stop: raise KeyboardInterrupt()

        now = time.time()
        repeat_at = now + cycle
        ftime = time.strftime(fmt, time.localtime(now))
        print("# " + gettext("polling starts at %s") % (ftime,))

        for_each_account(cfg, func, *args)

        now = time.time()
        to_sleep = max(60, repeat_at - now)
        ttime = time.strftime(fmt, time.localtime(now + to_sleep))
        print("# " + gettext("sleeping until %s") % (ttime,))

        raise_once = True
        if want_stop: raise KeyboardInterrupt()
        time.sleep(to_sleep)

def for_each_account(cfg : _t.Any, func : _t.Callable[..., None], *args : _t.Any) -> None:
    global had_errors
    #print(cfg.accounts)
    #sys.exit(1)

    account : Account
    for account in cfg.accounts:
        if want_stop: raise KeyboardInterrupt()

        try:
            srv = connect(account, cfg.debug)
            typ, data = srv._simple_command("LOGIN", imap_quote(account.user), imap_quote(account.password))
            if typ != "OK":
                raise CatastrophicFailure("failed to login as %s to host %s port %d: %s", account.user, account.host, account.port, repr(data))
            srv.state = "AUTH"

            sys.stdout.write("# " + gettext("logged in as %s to host %s port %d (%s)") % (account.user, account.host, account.port, account.socket.upper()) + "\n")
            sys.stdout.flush()

            func(cfg, srv, *args)
        except CatastrophicFailure as exc:
            had_errors = True
            sys.stderr.write(gettext("error") + ": " + exc.show() + "\n")
        finally:
            try:
                srv.logout()
            except:
                pass
            srv = None

def cmd_list(cfg : _t.Any) -> None:
    for_each_account_poll(cfg, do_list)

def do_list(cfg : _t.Any, srv : IMAP4) -> None:
    folders = get_folders(srv)
    for e in folders:
        print(e)

def get_folders(srv : IMAP4) -> _t.List[str]:
    res = []
    data = imap_check(Failure, "LIST", srv.list())
    for el in data:
        tags, _, arg = imap_parse(el)
        if b"\\Noselect" in tags:
            continue
        res.append(arg.decode("utf-8"))
    return res

def cmd_action(args : _t.Any) -> None:
    if args.all is None and args.seen is None and args.flagged is None:
        if args.flag_default is None:
            pass
        elif args.flag_default == "all":
            args.all = True
        elif args.flag_default == "seen":
            args.seen = True
        elif args.flag_default == "unseen":
            args.seen = False
        else:
            assert False

    if args.command == "mark":
        if args.all is None and args.seen is None and args.flagged is None:
            if args.mark == "seen":
                args.seen = False
            elif args.mark == "unseen":
                args.seen = True
            elif args.mark == "flagged":
                args.flagged = False
            elif args.mark == "unflagged":
                args.flagged = True
    elif args.command == "fetch":
        if args.mda is None:
            die(gettext("`--mda` is not set"))

        if args.mark == "auto":
            if args.all is None and args.seen == False and args.flagged is None:
                args.mark = "seen"
            elif args.all is None and args.seen is None and args.flagged == False:
                args.mark = "flagged"
            else:
                args.mark = "noop"
    elif args.command == "delete":
        if args.method == "auto":
            if args.host in ["imap.gmail.com"] and \
               args.folders != ["[Gmail]/Trash"]:
                args.method = "gmail-trash"
                args.not_folders.append("[Gmail]/Trash")
            else:
                args.method = "delete"

    search_filter = make_search_filter(args)

    if "mark" in args:
        print("# " + gettext("searching %s and marking %s") % (search_filter, args.mark))
    else:
        print("# " + gettext("searching %s") % (search_filter,))
    #sys.exit(1)

    for_each_account_poll(args, do_action, search_filter)

def do_action(args : _t.Any, srv : IMAP4, search_filter : str) -> None:
    data = imap_check(CatastrophicFailure, "CAPABILITY", srv.capability())
    capabilities = data[0].split(b" ")
    #print(capabilities)
    if b"IMAP4rev1" not in capabilities:
        raise CatastrophicFailure("host %s port %s does not speak IMAP4rev1, sorry but server software is too old to be supported", args.host, args.port)

    if args.all_folders and len(args.folders) == 0:
        folders = get_folders(srv)
    else:
        folders = args.folders

    for folder in filter(lambda f: f not in args.not_folders, folders):
        if want_stop: raise KeyboardInterrupt()

        do_folder_action(args, srv, search_filter, folder)

def do_folder_action(args : _t.Any, srv : IMAP4, search_filter : str, folder : str) -> None:
    typ, data = srv.select(imap_quote(folder))
    if typ != "OK":
        imap_error("SELECT", typ, data)
        return

    try:
        typ, data = srv.uid("SEARCH", search_filter)
        if typ != "OK":
            imap_error("SEARCH", typ, data)
            return

        result : _t.Optional[bytes] = data[0]
        if result is None:
            imap_error("SEARCH", typ, data)
            return
        elif result == b"":
            message_uids = []
        else:
            message_uids = result.split(b" ")

        if args.command == "count":
            if args.porcelain:
                print(f"{len(message_uids)} {folder}")
            else:
                print(gettext("folder `%s` has %d messages matching %s") % (folder, len(message_uids), search_filter))
            return
        elif len(message_uids) == 0:
            # nothing to do
            print(gettext("folder `%s` has no messages matching %s") % (folder, search_filter))
            return

        act : str
        actargs : _t.Any
        if args.command == "mark":
            act = "marking as %s %d messages matching %s from folder `%s`"
            actargs  = (args.mark.upper(), len(message_uids), search_filter, folder)
        elif args.command == "fetch":
            act = "fetching %d messages matching %s from folder `%s`"
            actargs  = (len(message_uids), search_filter, folder)
        elif args.command == "delete":
            if args.method in ["delete", "delete-noexpunge"]:
                act = "deleting %d messages matching %s from folder `%s`"
                actargs  = (len(message_uids), search_filter, folder)
            elif args.method == "gmail-trash":
                act = f"moving %d messages matching %s from folder `%s` to `[GMail]/Trash`"
                actargs  = (len(message_uids), search_filter, folder)
            else:
                assert False
        else:
            assert False

        if args.dry_run:
            print(gettext("dry-run, not " + act) % actargs)
            return
        else:
            print(gettext(act) % actargs)

        if args.command == "mark":
            do_store(args, srv, args.mark, message_uids)
        elif args.command == "fetch":
            do_fetch(args, srv, message_uids)
        elif args.command == "delete":
            do_store(args, srv, args.method, message_uids)
    finally:
        srv.close()

def do_fetch(args : _t.Any, srv : IMAP4, message_uids : _t.List[bytes]) -> None:
    fetch_num = args.fetch_number
    batch : _t.List[bytes] = []
    batch_total = 0
    while len(message_uids) > 0:
        if want_stop: raise KeyboardInterrupt()

        to_fetch, message_uids = message_uids[:fetch_num], message_uids[fetch_num:]
        to_fetch_set : _t.Set[bytes] = set(to_fetch)
        typ, data = srv.uid("FETCH", b",".join(to_fetch), "(RFC822.SIZE)") # type: ignore
        if typ != "OK":
            imap_error("FETCH", typ, data)
            continue

        new = []
        for el in data:
            _, attrs_ = imap_parse(el)
            attrs = imap_parse_attrs(attrs_)
            #print(attrs)

            try:
                uid = attrs[b"UID"]
                size = int(attrs[b"RFC822.SIZE"])
            except KeyError:
                fetch_check_untagged(args, attrs)
                continue

            new.append((uid, size))
            to_fetch_set.remove(uid)

        if len(to_fetch_set) > 0:
            imap_error("FETCH", "did not get enough elements")
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

            do_fetch_batch(args, srv, batch, batch_total)
            batch = []
            batch_total = 0
            new = leftovers

    do_fetch_batch(args, srv, batch, batch_total)

def fetch_check_untagged(args : _t.Any, attrs : _t.Dict[bytes, bytes]) -> None:
    try:
        flags = attrs[b"FLAGS"]
        if len(attrs) != 1:
            raise KeyError()
    except KeyError:
        sys.stderr.write("attrs dump: %s" % (repr(attrs),) + "\n")
        raise Failure("another client is performing unknown conflicting actions in parallel with us, aborting")

    # This is an untagged response generated by the server because
    # another client changed some flags.
    # Let's check they did not add or remove the flag we use for tracking state.
    if (args.mark == "seen" and b"\\Seen" in flags) or \
       (args.mark == "unseen" and b"\\Seen" not in flags) or \
       (args.mark == "flagged" and b"\\Flagged" in flags) or \
       (args.mark == "unflagged" and b"\\Flagged" not in flags):
        raise Failure("another client is marking messages with conflicting flags in parallel with us, aborting")

def do_fetch_batch(args : _t.Any, srv : IMAP4, message_uids : _t.List[bytes], total_size : int) -> None:
    global had_errors
    if want_stop: raise KeyboardInterrupt()

    if len(message_uids) == 0: return
    print("... " + gettext("fetching a batch of %d messages (%d bytes)") % (len(message_uids), total_size))

    joined = b",".join(message_uids)
    typ, data = srv.uid("FETCH", joined, "(BODY.PEEK[HEADER] BODY.PEEK[TEXT])") # type: ignore
    if typ != "OK":
        imap_error("FETCH", typ, data)
        return

    done_message_uids = []
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

        try:
            uid = attrs[b"UID"]
            header = attrs[b"BODY[HEADER]"]
            body = attrs[b"BODY[TEXT]"]
        except KeyError:
            fetch_check_untagged(args, attrs)
            continue

        if True:
            # strip \r like fetchmail does
            header = header.replace(b"\r\n", b"\n")
            body = body.replace(b"\r\n", b"\n")

        # try delivering to MDA
        delivered = True
        with subprocess.Popen(args.mda, stdin=subprocess.PIPE, stdout=None, stderr=None, shell=True) as p:
            fd : _t.Any = p.stdin
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
            done_message_uids.append(uid)
        else:
            imap_error("FETCH", "MDA failed to deliver message", uid)

    print("... " + gettext("delivered a batch of %d messages via `%s`") % (len(done_message_uids), args.mda))
    do_store(args, srv, args.mark, done_message_uids)

def do_store(args : _t.Any, srv : IMAP4, method : str, message_uids : _t.List[bytes]) -> None:
    if method == "noop": return

    marking_as = "... " + gettext("marking a batch of %d messages as %s")

    store_num = args.store_number
    while len(message_uids) > 0:
        if want_stop: raise KeyboardInterrupt()

        to_store, message_uids = message_uids[:store_num], message_uids[store_num:]
        joined = b",".join(to_store)
        if method == "seen":
            print(marking_as % (len(to_store), "SEEN"))
            srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Seen") # type: ignore
        elif method == "unseen":
            print(marking_as % (len(to_store), "UNSEEN"))
            srv.uid("STORE", joined, "-FLAGS.SILENT", "\\Seen") # type: ignore
        elif method == "flagged":
            print(marking_as % (len(to_store), "FLAGGED"))
            srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Flagged") # type: ignore
        elif method == "unflagged":
            print(marking_as % (len(to_store), "UNFLAGGED"))
            srv.uid("STORE", joined, "-FLAGS.SILENT", "\\Flagged") # type: ignore
        elif method in ["delete", "delete-noexpunge"]:
            print("... " + gettext("deleting a batch of %d messages") % (len(to_store),))
            srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Deleted") # type: ignore
            if method == "delete":
                srv.expunge()
        elif method == "gmail-trash":
            print("... " + gettext("moving a batch of %d messages to `[GMail]/Trash`") % (len(to_store),))
            srv.uid("STORE", joined, "+X-GM-LABELS", "\\Trash") # type: ignore
        else:
            assert False

def add_examples(fmt : _t.Any) -> None:
    _ = gettext
    fmt.add_text("# " + _("Notes on usage"))

    fmt.add_text(_('Message search filters are connected by logical "AND"s so, e.g., `--from "github.com" --not-from "notifications@github.com"` will act on messages which have a `From:` header with `github.com` but without `notifications@github.com` as substrings.'))

    fmt.add_text(_("Note that `fetch` and `delete` subcommands act on `--seen` messages by default."))

    fmt.add_text(_("Specifying `--folder` multiple times will perform the specified action on all specified folders."))

    fmt.add_text("# " + _("Examples"))

    fmt.start_section(_("List all available IMAP folders and count how many messages they contain"))

    fmt.start_section(_("with the password taken from the first line of the given file"))
    fmt.add_code(f'{__package__} count --ssl --host imap.example.com --user myself@example.com --passfile /path/to/file/containing/myself@example.com.password')
    fmt.end_section()

    fmt.start_section(_("with the password taken from the output of password-store util"))
    fmt.add_code(f'{__package__} count --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com"')
    fmt.end_section()

    fmt.start_section(_("with two accounts on the same server"))
    fmt.add_code(f"""{__package__} count --porcelain \\
         --ssl --host imap.example.com \\
         --user myself@example.com --passcmd "pass show mail/myself@example.com" \\
         --user another@example.com --passcmd "pass show mail/another@example.com"
""")
    fmt.end_section()

    fmt.end_section()

    fmt.add_text(_("Now, assuming the following are set:"))
    fmt.add_code("""common_no_mda=(--ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com")
common=("${{common_no_mda[@]}}" --mda maildrop)
gmail_common_no_mda=(--ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com")
gmail_common=("${{gmail_common_no_mda[@]}}" --mda maildrop)
""")

    fmt.start_section(_("Count how many messages older than 7 days are in `[Gmail]/Trash` folder"))
    fmt.add_code(f'{__package__} count "${{gmail_common[@]}}" --folder "[Gmail]/Trash" --older-than 7')
    fmt.end_section()

    fmt.start_section(_(f"Mark all messages in `INBOX` as UNSEEN, fetch all UNSEEN messages marking them SEEN as you download them so that if the process gets interrupted you could continue from where you left off, and then run `{__package__} fetch` as daemon to download updates every hour"))
    fmt.add_code(f"""# {_("setup: do once")}
{__package__} mark "${{common[@]}}" --folder "INBOX" unseen

# {_("repeatable part")}
{__package__} fetch "${{common[@]}}" --folder "INBOX"

# {_("yes, with this you can skip the previous command")}
# {_("download updates every hour")}
{__package__} fetch "${{common[@]}}" --folder "INBOX" --every 3600
""")
    fmt.end_section()

    fmt.start_section(_("Fetch all messages from `INBOX` folder that were delivered in the last 7 days (rounded to the start of the start day by server time), but don't change any flags"))
    fmt.add_code(f'{__package__} fetch "${{common[@]}}" --folder "INBOX" --all --newer-than 7')
    fmt.end_section()

    fmt.start_section(_("Fetch all messages from `INBOX` folder that were delivered from the beginning of today (by server time)"))
    fmt.add_code(f'{__package__} fetch "${{common[@]}}" --folder "INBOX" --all --newer-than 0')
    fmt.end_section()

    fmt.start_section(_("Delete all SEEN messages older than 7 days from `INBOX` folder"))
    fmt.add_text("")
    fmt.add_text(_(f"Assuming you fetched and backed up all your messages already this allows you to keep as little as possible on the server, so that if your account gets cracked/hacked, you won't be as vulnerable."))
    fmt.add_code(f'{__package__} delete "${{common[@]}}" --folder "INBOX" --older-than 7')
    fmt.add_text(_("(`--seen` is implied by default)"))
    fmt.end_section()

    fmt.start_section(_("**DANGEROUS!** If you fetched and backed up all your messages already, you can skip `--older-than` and just delete all SEEN messages instead"))
    fmt.add_code(f'{__package__} delete "${{common[@]}}" --folder "INBOX"')
    fmt.add_text(_("Though, setting at least `--older-than 1` to make sure you won't lose any data in case something breaks is highly recommended anyway."))
    fmt.end_section()

    fmt.start_section(_(f"Similarly to the above, but use FLAGGED instead of SEEN. This allows to use this in parallel with another instance of `{__package__}` using the SEEN flag, e.g. if you want to backup to two different machines independently, or if you want to use `{__package__}` simultaneously in parallel with `fetchmail` or other similar tool"))
    fmt.add_code(f"""# {_("setup: do once")}
{__package__} mark "${{common[@]}}" --folder "INBOX" unflagged

# {_("repeatable part")}
{__package__} fetch "${{common[@]}}" --folder "INBOX" --unflagged

# {_("this will work as if nothing of the above was run")}
fetchmail

# {_("in this use case you should use both `--seen` and `--flagged` when expiring old messages to only delete messages fetched by both imaparms and fetchmail")}
{__package__} delete "${{common[@]}}" --folder "INBOX" --older-than 7 --seen --flagged
""")
    fmt.end_section()

    fmt.start_section(_("Fetch everything GMail considers to be Spam for local filtering"))
    fmt.add_code(f"""# {_("setup: do once")}
mkdir -p ~/Mail/spam/{{new,cur,tmp}}

cat > ~/.mailfilter-spam << EOF
DEFAULT="$HOME/Mail/spam"
EOF

{__package__} mark "${{gmail_common_no_mda[@]}}" --folder "[Gmail]/Spam" unseen

# {_("repeatable part")}
{__package__} fetch "${{gmail_common_no_mda[@]}}" --mda "maildrop ~/.mailfilter-spam" --folder "[Gmail]/Spam"
""")
    fmt.end_section()

    fmt.start_section(_("GMail-specific deletion mode: move (expire) old messages from `[Gmail]/All Mail` to `[Gmail]/Trash`"))

    fmt.add_text("")
    fmt.add_text(_("In GMail, deleting messages from `INBOX` does not actually delete them, nor moves them to trash, just removes them from `INBOX` while keeping them available from `[Gmail]/All Mail`."))
    fmt.add_text(_("To work around this, this tool provides a GMail-specific `--method gmail-trash` that moves messages to `[Gmail]/Trash` in a GMail-specific way (this is not a repetition, it does require issuing special IMAP `STORE` commands to achieve this):"))
    fmt.add_code(f'{__package__} delete "${{gmail_common[@]}}" --folder "[Gmail]/All Mail" --older-than 7')
    fmt.add_text(_("(`--method gmail-trash` is implied by `--host imap.gmail.com` and `--folder` not being `[Gmail]/Trash`)"))
    fmt.add_text(_("(`--seen` is still implied by default)"))

    fmt.add_text(_("Messages in `[Gmail]/Trash` will be automatically removed by GMail in 30 days, but you can also delete them immediately with:"))

    fmt.add_code(f'{__package__} delete "${{gmail_common[@]}}" --folder "[Gmail]/Trash" --all --older-than 7')
    fmt.add_text(_("(`--method delete` is implied by `--host imap.gmail.com` but `--folder` being `[Gmail]/Trash`)"))
    fmt.end_section()

def main() -> None:
    _ = gettext
    global had_errors

    defenc = sys.getdefaultencoding()

    parser = argparse.BetterArgumentParser(
        prog=__package__,
        description=_("A Keep It Stupid Simple (KISS) Swiss-army-knife-like tool for fetching and performing batch operations on messages residing on IMAP4 servers.") + "\n" + \
                    _("Logins to a specified server, performs specified actions on all messages matching specified criteria in all specified folders, logs out."),
        additional_sections = [add_examples],
        add_help = True,
        add_version = True)
    parser.add_argument("--help-markdown", action="store_true", help=_("show this help message formatted in Markdown and exit"))

    class EmitAccount(argparse.Action):
        def __init__(self, option_strings : str, dest : str, default : _t.Any = None, **kwargs : _t.Any) -> None:
            self.ptype = default
            super().__init__(option_strings, dest, type=str, **kwargs)

        def __call__(self, parser : _t.Any, cfg : _t.Any, value : _t.Any, option_string : _t.Optional[str] = None) -> None:
            if cfg.host is None:
                return die(_("`--host` is required"))

            host : str = cfg.host

            IMAP_base : type
            if cfg.socket in ["plain", "starttls"]:
                port = 143
                IMAP_base = IMAP4
            elif cfg.socket == "ssl":
                port = 993
                IMAP_base = IMAP4_SSL

            if cfg.port is not None:
                port = cfg.port

            if cfg.user is None:
                return die(_("`--user` is required"))

            user = cfg.user
            cfg.user = None

            if self.ptype == "file":
                with open(value, "rb") as f:
                    password = f.readline().decode(defenc)
            elif self.ptype == "cmd":
                with subprocess.Popen(value, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, shell=True) as p:
                    p.stdin.close() # type: ignore
                    password = p.stdout.readline().decode(defenc) # type: ignore
                    retcode = p.wait()
                    if retcode != 0:
                        die(_("`--passcmd` (`%s`) failed with non-zero exit code %d") % (args.passcmd, retcode))
            else:
                assert False

            if password[-1:] == "\n":
                password = password[:-1]
            if password[-1:] == "\r":
                password = password[:-1]

            cfg.accounts.append(Account(cfg.socket, host, port, user, password, IMAP_base))

    def add_common(cmd : _t.Any, all_folders_by_default : bool) -> None:
        cmd.set_defaults(accounts = [])

        agrp = cmd.add_argument_group(_("debugging"))
        agrp.add_argument("--debug", action="store_true", help=_("print IMAP conversation to stderr"))
        agrp.add_argument("--dry-run", action="store_true", help=_("don't perform any actions, only show what would be done"))

        agrp = cmd.add_argument_group("polling/daemon options")
        agrp.add_argument("--every", metavar = "SECONDS", type=int, help=_("run this command, wait SECONDS seconds, repeat (until interrupted)"))

        agrp = cmd.add_argument_group("server connection")
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--plain", dest="socket", action="store_const", const = "plain", help=_("connect via plain-text socket"))
        grp.add_argument("--ssl", dest="socket", action="store_const", const = "ssl", help=_("connect over SSL socket") + " " + _("(default)"))
        grp.add_argument("--starttls", dest="socket", action="store_const", const = "starttls", help=_("connect via plain-text socket, but then use STARTTLS command"))
        grp.set_defaults(socket = "ssl")

        agrp.add_argument("--host", type=str, help=_("IMAP server to connect to (required)"))
        agrp.add_argument("--port", type=int, help=_("port to use") + " " + _("(default: 143 for `--plain` and `--starttls`, 993 for `--ssl`)"))

        agrp = cmd.add_argument_group(_("server auth"), description=_("either of `--passfile` or `--passcmd` are required"))
        agrp.add_argument("--user", type=str, help=_("username on the server (required)"))

        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--passfile", action=EmitAccount, default="file", help=_("file containing the password on its first line"))
        grp.add_argument("--passcmd", action=EmitAccount, default="cmd", help=_("shell command that returns the password as the first line of its stdout"))
        grp.set_defaults(password = None)

        def_all, def_req = "", ""
        if all_folders_by_default:
            def_all = " " + _("(default)")
        else:
            def_req = " " + _("(required)")

        agrp = cmd.add_argument_group(_("folder search filters"))
        egrp = agrp.add_mutually_exclusive_group(required = not all_folders_by_default)
        egrp.add_argument("--all-folders", action="store_true", default = all_folders_by_default,
                          help=_("operate on all folders") + def_all)
        egrp.add_argument("--folder", metavar = "NAME", dest="folders", action="append", type=str, default=[],
                          help=_("mail folders to include; can be specified multiple times") + def_req)
        agrp.add_argument("--not-folder", metavar = "NAME", dest="not_folders", action="append", type=str, default=[],
                          help=_("mail folders to exclude; can be specified multiple times"))

        agrp = cmd.add_argument_group(_("IMAP batching settings"), description=_("larger values improve performance but produce longer command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen"))
        agrp.add_argument("--store-number", metavar = "INT", type=int, default = 150, help=_("batch at most this many message UIDs in IMAP `STORE` requests (default: %(default)s)"))
        agrp.add_argument("--fetch-number", metavar = "INT", type=int, default = 150, help=_("batch at most this many message UIDs in IMAP `FETCH` metadata requests (default: %(default)s)"))
        agrp.add_argument("--batch-number", metavar = "INT", type=int, default = 150, help=_("batch at most this many message UIDs in IMAP `FETCH` data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: %(default)s)"))
        agrp.add_argument("--batch-size", metavar = "INT", type=int, default = 4 * 1024 * 1024, help=_(f"batch FETCH at most this many bytes of RFC822 messages at once; RFC822 messages larger than this will be fetched one by one (i.e. without batching); essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted while `{__package__}` is batching (default: %(default)s)"))

        agrp = cmd.add_argument_group(_("delivery settings"))
        agrp.add_argument("--mda", dest="mda", metavar = "COMMAND", type=str,
                          help=_("shell command to use as an MDA to deliver the messages to (required for `fetch` subcommand)") + "\n" + \
                               _(f"`{__package__}` will spawn COMMAND via the shell and then feed raw RFC822 message into its `stdin`, the resulting process is then responsible for delivering the message to `mbox`, `Maildir`, etc.") + "\n" + \
                               _("`maildrop` from Courier Mail Server project is a good KISS default."))

    def add_filters(cmd : _t.Any, default : _t.Optional[str]) -> None:
        cmd.set_defaults(flag_default = default)

        def_req = ""
        def_str = " " + _("(default)")
        def_all, def_seen, def_unseen = "", "", ""
        if default is None:
            def_req = " " + _("(default: depends on other arguments)")
        elif default == "all":
            def_all = def_str
        elif default == "seen":
            def_seen = def_str
        elif default == "unseen":
            def_unseen = def_str
        else:
            assert False

        agrp = cmd.add_argument_group(_("message search filters"))

        bgrp = cmd.add_argument_group(_("message flag filters") + def_req)
        egrp = bgrp.add_mutually_exclusive_group()
        egrp.add_argument("--all", dest="all", action="store_true", default = None, help=_("operate on all messages") + def_all)

        grp = egrp.add_mutually_exclusive_group()
        grp.add_argument("--seen", dest="seen", action="store_true", help=_("operate on messages marked as SEEN") + def_seen)
        grp.add_argument("--unseen", dest="seen", action="store_false", help=_("operate on messages not marked as SEEN") + def_unseen)
        grp.set_defaults(seen = None)

        grp = egrp.add_mutually_exclusive_group()
        grp.add_argument("--flagged", dest="flagged", action="store_true", help=_("operate on messages marked as FLAGGED"))
        grp.add_argument("--unflagged", dest="flagged", action="store_false", help=_("operate on messages not marked as FLAGGED"))
        grp.set_defaults(flagged = None)

        agrp.add_argument("--older-than", metavar = "DAYS", type=int, help=_("operate on messages older than this many days"))
        agrp.add_argument("--newer-than", metavar = "DAYS", type=int, help=_("operate on messages not older than this many days"))

        agrp.add_argument("--from", dest="hfrom", metavar = "ADDRESS", action = "append", type=str, default = [], help=_("operate on messages that have this string as substring of their header's FROM field; can be specified multiple times"))
        agrp.add_argument("--not-from", dest="hnotfrom", metavar = "ADDRESS", action = "append", type=str, default = [], help=_("operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times"))

    def no_cmd(args : _t.Any) -> None:
        parser.print_help(sys.stderr)
        sys.exit(2)
    parser.set_defaults(func=no_cmd)

    subparsers = parser.add_subparsers(title="subcommands")

    cmd = subparsers.add_parser("list", help=_("list all available folders on the server, one per line"),
                                description = _("Login, perform IMAP `LIST` command to get all folders, print them one per line."))
    add_common(cmd, True)
    cmd.set_defaults(func=cmd_list)

    cmd = subparsers.add_parser("count", help=_("count how many matching messages each specified folder has (counts for all available folders by default)"),
                                description = _("Login, (optionally) perform IMAP `LIST` command to get all folders, perform IMAP `SEARCH` command with specified filters in each folder, print message counts for each folder one per line."))
    add_common(cmd, True)
    add_filters(cmd, "all")
    cmd.add_argument("--porcelain", action="store_true", help=_("print in a machine-readable format"))
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="count")

    cmd = subparsers.add_parser("mark", help=_("mark matching messages in specified folders in a specified way"),
                                description = _("Login, perform IMAP `SEARCH` command with specified filters for each folder, mark resulting messages in specified way by issuing IMAP `STORE` commands."))
    add_common(cmd, False)
    add_filters(cmd, None)
    agrp = cmd.add_argument_group("marking")
    sets_x_if = _("sets `%s` if no message search filter is specified")
    agrp.add_argument("mark", choices=["seen", "unseen", "flagged", "unflagged"], help=_("mark how") + " " + _("(required)") + f""":
- `seen`: {_("add `SEEN` flag")}, {sets_x_if % ("--unseen",)}
- `unseen`: {_("remove `SEEN` flag")}, {sets_x_if % ("--seen",)}
- `flag`: {_("add `FLAGGED` flag")}, {sets_x_if % ("--unflagged",)}
- `unflag`: {_("remove `FLAGGED` flag")}, {sets_x_if % ("--flagged",)}
""")
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="mark")

    cmd = subparsers.add_parser("fetch", help=_("fetch matching messages from specified folders, feed them to an MDA, and then mark them in a specified way if MDA succeeds"),
                                description = _("Login, perform IMAP `SEARCH` command with specified filters for each folder, fetch resulting messages in (configurable) batches, feed each batch of messages to an MDA, mark each message for which MDA succeded in a specified way by issuing IMAP `STORE` commands."))
    add_common(cmd, True)
    add_filters(cmd, "unseen")
    agrp = cmd.add_argument_group("marking")
    agrp.add_argument("--mark", choices=["auto", "noop", "seen", "unseen", "flagged", "unflagged"], default = "auto", help=_("after the message was fetched") + f""":
- `auto`: {_('`seen` when only `--unseen` is set (default), `flagged` when only `--unflagged` is set, `noop` otherwise')}
- `noop`: {_("do nothing")}
- `seen`: {_("add `SEEN` flag")}
- `unseen`: {_("remove `SEEN` flag")}
- `flagged`: {_("add `FLAGGED` flag")}
- `unflagged`: {_("remove `FLAGGED` flag")}
""")
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="fetch")

    cmd = subparsers.add_parser("delete", aliases = ["expire"], help=_("delete matching messages from specified folders"),
                                description = _("Login, perform IMAP `SEARCH` command with specified filters for each folder, delete them from the server using a specified method."))
    add_common(cmd, False)
    add_filters(cmd, "seen")
    cmd.add_argument("--method", choices=["auto", "delete", "delete-noexpunge", "gmail-trash"], default="auto", help=_("delete messages how") + f""":
- `auto`: {_('`gmail-trash` when `--host imap.gmail.com` and `--folder` is not (single) `[Gmail]/Trash`, `delete` otherwise')} {_("(default)")}
- `delete`: {_('mark messages as deleted and then use IMAP `EXPUNGE` command, i.e. this does what you would expect a "delete" command to do, works for most IMAP servers')}
- `delete-noexpunge`: {_('mark messages as deleted but skip issuing IMAP `EXPUNGE` command hoping the server does as RFC2060 says and auto-`EXPUNGE`s messages on IMAP `CLOSE`; this is much faster than `delete` but some servers (like GMail) fail to implement this properly')}
- `gmail-trash`: {_(f'move messages to `[Gmail]/Trash` in GMail-specific way instead of trying to delete them immediately (GMail ignores IMAP `EXPUNGE` outside of `[Gmail]/Trash`, you can then `{__package__} delete --method delete --folder "[Gmail]/Trash"` them after, or you could just leave them there and GMail will delete them in 30 days)')}
""")
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="delete")

    args = parser.parse_args(sys.argv[1:])

    if args.help_markdown:
        parser.set_formatter_class(argparse.MarkdownBetterHelpFormatter)
        print(parser.format_help(1024))
        sys.exit(0)

    if len(args.accounts) == 0:
        return die(_("no accounts specified, need at least one `--host`, `--user`, and either of `--passfile` or `--passcmd`"))

    handle_signals()

    try:
        args.func(args)
    except CatastrophicFailure as exc:
        had_errors = True
        sys.stderr.write(_("error") + ": " + exc.show() + "\n")
    except KeyboardInterrupt:
        had_errors = True
        sys.stderr.write(_("Interrupted!") + "\n")
    except Exception as exc:
        had_errors = True
        traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)

    if had_errors:
        sys.stderr.write(_("Had errors!") + "\n")
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
