#!/usr/bin/env python3
#
# Copyright (c) 2023 Jan Malakovski <oxij@oxij.org>
#
# This file can be distributed under the terms of the GNU GPL, version 3 or later.

import imaplib
import os
import signal
import ssl
import subprocess
import sys
import time
import traceback as traceback
import typing as _t

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

def connect(args : _t.Any) -> _t.Any:
    IMAP_base : type
    if args.socket in ["plain", "starttls"]:
        port = 143
        IMAP_base = imaplib.IMAP4
    elif args.socket == "ssl":
        port = 993
        IMAP_base = imaplib.IMAP4_SSL

    if args.port is not None:
        port = args.port
    args.port = port

    if args.debug:
        binstderr = os.fdopen(sys.stderr.fileno(), "wb")
        class IMAP(IMAP_base): # type: ignore
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
        IMAP = IMAP_base # type: ignore

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True
    ssl_context.load_default_certs()

    if args.socket == "ssl":
        srv = IMAP(args.host, port, ssl_context = ssl_context)
    else:
        srv = IMAP(args.host, port)
        if args.starttls:
            srv.starttls(ssl_context)

    srv.login(args.user, args.password)
    print("# " + gettext("logged in as %s to host %s port %d (%s)") % (args.user, args.host, args.port, args.socket.upper()))

    return srv

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
            else:
                args.method = "delete"

    search_filter = make_search_filter(args)
    #print(args)
    #print(search_filter, args.mark)
    #sys.exit(1)

    try:
        srv = connect(args)
    except Exception as exc:
        raise CatastrophicFailure("failed to connect to host %s port %s: %s", args.host, args.port, repr(exc))

    try:
        data = imap_check(CatastrophicFailure, "CAPABILITY", srv.capability())
        capabilities = data[0].split(b" ")
        #print(capabilities)
        if b"IMAP4rev1" not in capabilities:
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
                imap_error("SELECT", typ, data)
                continue

            try:
                typ, data = srv.uid("SEARCH", search_filter)
                if typ != "OK":
                    imap_error("SEARCH", typ, data)
                    continue

                result = data[0]
                if result == b"":
                    message_uids = []
                else:
                    message_uids = result.split(b" ")

                if args.command == "count":
                    print(gettext("folder `%s` has %d messages matching %s") % (folder, len(message_uids), search_filter))
                    continue
                elif len(message_uids) == 0:
                    # nothing to do
                    print(gettext("folder `%s` has no messages matching %s") % (folder, search_filter))
                    continue

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
                    continue
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
    finally:
        srv.logout()

def do_fetch(args : _t.Any, srv : _t.Any, message_uids : _t.List[bytes]) -> None:
    fetch_num = args.fetch_number
    batch : _t.List[bytes] = []
    batch_total = 0
    while len(message_uids) > 0:
        if want_stop: raise KeyboardInterrupt()

        to_fetch, message_uids = message_uids[:fetch_num], message_uids[fetch_num:]
        to_fetch_set : _t.Set[bytes] = set(to_fetch)
        typ, data = srv.uid("FETCH", b",".join(to_fetch), "(RFC822.SIZE)")
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
        raise CatastrophicFailure("another client is performing unknown conflicting actions in parallel with us, aborting")

    # This is an untagged response generated by the server because
    # another client changed some flags.
    # Let's check they did not add or remove the flag we use for tracking state.
    if (args.mark == "seen" and b"\\Seen" in flags) or \
       (args.mark == "unseen" and b"\\Seen" not in flags) or \
       (args.mark == "flagged" and b"\\Flagged" in flags) or \
       (args.mark == "unflagged" and b"\\Flagged" not in flags):
        raise CatastrophicFailure("another client is marking messages with conflicting flags in parallel with us, aborting")

def do_fetch_batch(args : _t.Any, srv : _t.Any, message_uids : _t.List[bytes], total_size : int) -> None:
    global had_errors
    if want_stop: raise KeyboardInterrupt()

    if len(message_uids) == 0: return
    print("... " + gettext("fetching a batch of %d messages (%d bytes)") % (len(message_uids), total_size))

    joined = b",".join(message_uids)
    typ, data = srv.uid("FETCH", joined, "(BODY.PEEK[HEADER] BODY.PEEK[TEXT])")
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

    print("... " + gettext("delivered a batch of %d messages via %s") % (len(done_message_uids), args.mda))
    do_store(args, srv, args.mark, done_message_uids)

def do_store(args : _t.Any, srv : _t.Any, method : str, message_uids : _t.List[bytes]) -> None:
    if method == "noop": return

    marking_as = "... " + gettext("marking as %s a batch of %d messages")

    store_num = args.store_number
    while len(message_uids) > 0:
        if want_stop: raise KeyboardInterrupt()

        to_store, message_uids = message_uids[:store_num], message_uids[store_num:]
        joined = b",".join(to_store)
        if method == "seen":
            print(marking_as % ("SEEN", len(to_store)))
            srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Seen")
        elif method == "unseen":
            print(marking_as % ("UNSEEN", len(to_store)))
            srv.uid("STORE", joined, "-FLAGS.SILENT", "\\Seen")
        elif method == "flagged":
            print(marking_as % ("FLAGGED", len(to_store)))
            srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Flagged")
        elif method == "unflagged":
            print(marking_as % ("UNFLAGGED", len(to_store)))
            srv.uid("STORE", joined, "-FLAGS.SILENT", "\\Flagged")
        elif method in ["delete", "delete-noexpunge"]:
            print("... " + gettext("deleting a batch of %d messages") % (len(to_store),))
            srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Deleted")
            if method == "delete":
                srv.expunge()
        elif method == "gmail-trash":
            print("... " + gettext("moving a batch of %d messages to `[GMail]/Trash`") % (len(to_store),))
            srv.uid("STORE", joined, "+X-GM-LABELS", "\\Trash")
        else:
            assert False

def add_examples(fmt : _t.Any) -> None:
    _ = gettext
    fmt.add_text("# " + _("Notes on usage"))

    fmt.add_text(_("Specifying `--folder` multiple times will perform the specified action on all specified folders."))

    fmt.add_text(_('Message search filters are connected by logical "AND"s so, e.g., `--from "github.com" --not-from "notifications@github.com"` will act on messages which have a `From:` header with `github.com` but without `notifications@github.com` as substrings.'))

    fmt.add_text(_("Also note that `fetch` and `delete` subcommands act on `--seen` messages by default."))

    fmt.add_text("# " + _("Examples"))

    fmt.start_section(_("List all available IMAP folders and count how many messages they contain"))

    fmt.start_section(_("with the password taken from the first line of the given file"))
    fmt.add_code(f'{__package__} --ssl --host imap.example.com --user myself@example.com --passfile /path/to/file/containing/myself@example.com.password count')
    fmt.end_section()

    fmt.start_section(_("with the password taken from the output of password-store util"))
    fmt.add_code(f'{__package__} --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" count')
    fmt.end_section()

    fmt.end_section()

    fmt.start_section(_("Mark all messages in `INBOX` as UNSEEN, and then fetch all UNSEEN messages marking them SEEN as you download them, so that if the process gets interrupted you could continue from where you left off"))
    fmt.add_code(f"""{__package__} --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" mark --folder "INBOX" --seen unseen
{__package__} --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" fetch --folder "INBOX"

# {_("download updates")}
while true; do
    sleep 3600
    {__package__} --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" fetch --folder "INBOX"
done
""")
    fmt.end_section()

    fmt.start_section(_(f"Similarly, but use FLAGGED instead of SEEN. This allows to use this in parallel with another instance of `{__package__}` using SEEN flag, or in parallel with `fetchmail` or other similar tool"))
    fmt.add_code(f"""{__package__} --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" mark --folder "INBOX" --flagged unflagged
{__package__} --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" fetch --folder "INBOX" --unflagged

# {_("and this will work as if nothing of the above was run")}
fetchmail
""")
    fmt.end_section()

    fmt.start_section(_("Fetch all messages from `INBOX` folder that were delivered in the last 7 days (rounded to the start of the start day by server time), but don't change any flags"))
    fmt.add_code(f'{__package__} --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --mda maildrop fetch --mark noop --folder "INBOX" --all --newer-than 7')
    fmt.end_section()

    fmt.start_section(_("Fetch all messages from `INBOX` folder that were delivered from the beginning of today (by server time)"))
    fmt.add_code(f'{__package__} --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --mda maildrop fetch --mark noop --folder "INBOX" --all --newer-than 7')
    fmt.end_section()

    fmt.start_section(_("Delete all SEEN messages older than 7 days from `INBOX` folder"))
    fmt.add_text("")
    fmt.add_text(_(f"Assuming you fetched and backed up all your messages already this allows you to keep as little as possible on the server, so that if your account gets hacked, you won't be as vulnerable."))
    fmt.add_code(f'{__package__} --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" delete --folder "INBOX" --older-than 7')
    fmt.add_text(_("Note that the above only removes `--seen` messages by default."))
    fmt.end_section()

    fmt.start_section(_("**DANGEROUS!** If you fetched and backed up all your messages already, you can skip `--older-than` and just delete all `--seen` messages instead"))
    fmt.add_code(f'{__package__} --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" delete --folder "INBOX"')
    fmt.add_text(_("Though, setting at least `--older-than 1` in case you forgot you had another fetcher running in parallel and you want to be sure you won't lose any data in case something breaks, is highly recommended anyway."))
    fmt.end_section()

    fmt.start_section(_("Count how many messages older than 7 days are in `[Gmail]/Trash` folder"))
    fmt.add_code(f'{__package__} --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" count --folder "[Gmail]/Trash" --older-than 7')
    fmt.end_section()

    fmt.start_section(_("Fetch everything GMail considers to be Spam for local filtering"))
    fmt.add_code(f"""
mkdir -p ~/Maildir/spam/new
mkdir -p ~/Maildir/spam/cur
mkdir -p ~/Maildir/spam/tmp

cat > ~/.mailfilter-spam << EOF
DEFAULT="$HOME/Maildir/spam"
EOF

{__package__} --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" mark --folder "[Gmail]/Spam" --seen unseen
{__package__} --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --mda "maildrop ~/.mailfilter-spam" fetch --folder "[Gmail]/Spam"
""")
    fmt.end_section()

    fmt.start_section(_("GMail-specific deletion mode: move (expire) old messages from `[Gmail]/All Mail` to `[Gmail]/Trash`"))

    fmt.add_text("")
    fmt.add_text(_("Unfortunately, in GMail, deleting messages from `INBOX` does not actually delete them, nor moves them to trash, just removes them from `INBOX` while keeping them available from `[Gmail]/All Mail`."))
    fmt.add_text(_("To work around this, this tool provides a GMail-specific deletion method that moves messages to `[Gmail]/Trash` in a GMail-specific way (this is not a repetition, it does require issuing special STORE commands to achieve this)."))
    fmt.add_text(_("You will probably want to run it over `[Gmail]/All Mail` folder (again, after you fetched everything from there) instead of `INBOX`:"))

    fmt.add_code(f'{__package__} --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" delete --method gmail-trash --folder "[Gmail]/All Mail" --older-than 7')
    fmt.add_text(_("which is equivalent to simply"))
    fmt.add_code(f'{__package__} --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" delete --folder "[Gmail]/All Mail" --older-than 7')
    fmt.add_text(_("since `--method gmail-trash` is the default when `--host imap.gmail.com` and `--folder` is not `[Gmail]/Trash`"))

    fmt.add_text(_("Also, note that the above only moves `--seen` messages by default."))

    fmt.add_text(_("Messages in `[Gmail]/Trash` will be automatically removed by GMail in 30 days, but you can also delete them immediately with:"))

    fmt.add_code(f'{__package__} --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" delete --method delete --folder "[Gmail]/Trash" --all --older-than 7')
    fmt.add_text(_("which is equivalent to simply"))
    fmt.add_code(f'{__package__} --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" delete --folder "[Gmail]/Trash" --all --older-than 7')
    fmt.end_section()

def main() -> None:
    _ = gettext
    global had_errors

    defenc = sys.getdefaultencoding()

    parser = argparse.BetterArgumentParser(
        prog=__package__,
        description=_("A Keep It Stupid Simple (KISS) Swiss-army-knife-like tool for performing batch operations on messages residing on IMAP4 servers.") + "\n" + \
                    _("Logins to a specified server, performs specified actions on all messages matching specified criteria in all specified folders, logs out."),
        additional_sections = [add_examples],
        add_help = True,
        add_version = True)
    parser.add_argument("--help-markdown", action="store_true", help=_("show this help message formatted in Markdown and exit"))

    agrp = parser.add_argument_group("debugging")
    agrp.add_argument("--debug", action="store_true", help=_("print IMAP conversation to stderr"))

    agrp = parser.add_argument_group("server connection")
    grp = agrp.add_mutually_exclusive_group()
    grp.add_argument("--plain", dest="socket", action="store_const", const = "plain", help=_("connect via plain-text socket"))
    grp.add_argument("--ssl", dest="socket", action="store_const", const = "ssl", help=_("connect over SSL socket") + " " + _("(default)"))
    grp.add_argument("--starttls", dest="socket", action="store_const", const = "starttls", help=_("connect via plain-text socket, but then use STARTTLS command"))
    grp.set_defaults(socket = "ssl")

    agrp.add_argument("--host", type=str, default = "localhost", help=_("IMAP server to connect to"))
    agrp.add_argument("--port", type=int, help=_("port to use") + " " + _("(default: 143 for `--plain` and `--starttls`, 993 for `--ssl`)"))

    agrp = parser.add_argument_group(_("server auth"), description=_("`--user` and either of `--passfile` or `--passcmd` are required"))
    agrp.add_argument("--user", type=str, help=_("username on the server"))

    grp = agrp.add_mutually_exclusive_group()
    grp.add_argument("--passfile", type=str, help=_("file containing the password on its first line"))
    grp.add_argument("--passcmd", type=str, help=_("shell command that returns the password as the first line of its stdout"))

    agrp = parser.add_argument_group(_("IMAP batching settings"), description=_("larger values improve performance but produce longer command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen"))
    agrp.add_argument("--store-number", metavar = "INT", type=int, default = 150, help=_("batch at most this many message UIDs in IMAP STORE requests (default: %(default)s)"))
    agrp.add_argument("--fetch-number", metavar = "INT", type=int, default = 150, help=_("batch at most this many message UIDs in IMAP FETCH metadata requests (default: %(default)s)"))
    agrp.add_argument("--batch-number", metavar = "INT", type=int, default = 150, help=_("batch at most this many message UIDs in IMAP FETCH data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: %(default)s)"))
    agrp.add_argument("--batch-size", metavar = "INT", type=int, default = 4 * 1024 * 1024, help=_("batch FETCH at most this many bytes of RFC822 messages at once; RFC822 messages larger than this will be fetchen one by one; essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted (default: %(default)s)"))

    agrp = parser.add_argument_group(_("delivery settings"))
    agrp.add_argument("--mda", dest="mda", metavar = "COMMAND", type=str,
                      help=_("shell command to use as an MDA to deliver the messages to (required for `fetch` subcommand)") + "\n" + \
                           _(f"`{__package__}` will spawn COMMAND via the shell and then feed raw RFC822 message into its `stdin`, the resulting process is then responsible for delivering the message to `mbox`, `Maildir`, etc.") + "\n" + \
                           _("`maildrop` from Courier Mail Server project is a good KISS default."))

    def no_cmd(args : _t.Any) -> None:
        parser.print_help(sys.stderr)
        sys.exit(2)
    parser.set_defaults(func=no_cmd)

    def add_dry_run(cmd : _t.Any) -> None:
        agrp = cmd.add_argument_group(_("debugging"))
        agrp.add_argument("--dry-run", action="store_true", help=_("don't perform any actions, only show what would be done"))

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

    def add_folders(cmd : _t.Any) -> None:
        agrp = cmd.add_argument_group(_("folder specification"))
        agrp.add_argument("--folder", metavar = "NAME", dest="folders", action="append", type=str, default=[],
                          help=_("mail folders to operane on; can be specified multiple times") + " " + _("(default: all available mail folders)"))

    def add_req_folders(cmd : _t.Any) -> None:
        agrp = cmd.add_argument_group(_("folder specification"))
        agrp.add_argument("--folder", metavar = "NAME", dest="folders", action="append", type=str, default=[], required = True,
                          help=_("mail folders to operate on; can be specified multiple times") + " " + _("(required)"))

    subparsers = parser.add_subparsers(title="subcommands")

    cmd = subparsers.add_parser("count", aliases = ["list"], help=_("count how many matching messages each specified folder has (counts for all available folders by default)"))
    add_filters(cmd, "all")
    add_folders(cmd)
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="count")

    cmd = subparsers.add_parser("mark", help=_("mark matching messages in specified folders in a specified way"))
    add_dry_run(cmd)
    add_filters(cmd, None)
    add_req_folders(cmd)
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

    cmd = subparsers.add_parser("fetch", aliases = ["mirror"], help=_("fetch matching messages from specified folders, feed them to an MDA, and then mark them in a specified way if MDA succeeds"))
    add_dry_run(cmd)
    add_filters(cmd, "unseen")
    add_req_folders(cmd)
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

    cmd = subparsers.add_parser("delete", aliases = ["expire"], help=_("delete matching messages from specified folders"))
    add_dry_run(cmd)
    add_filters(cmd, "seen")
    cmd.add_argument("--method", choices=["auto", "delete", "delete-noexpunge", "gmail-trash"], default="auto", help=_("delete messages how") + f""":
- `auto`: {_('`gmail-trash` when `--host imap.gmail.com` and `--folder` is not (single) `[Gmail]/Trash`, `delete` otherwise')} {_("(default)")}
- `delete`: {_('mark messages as deleted and then use IMAP `EXPUNGE` command, i.e. this does what you would expect a "delete" command to do, works for most IMAP servers')}
- `delete-noexpunge`: {_('mark messages as deleted but skip issuing IMAP `EXPUNGE` command hoping the server does as RFC2060 says and auto-`EXPUNGE`s messages on IMAP `CLOSE`; this is much faster than `delete` but some servers (like GMail) fail to implement this properly')}
- `gmail-trash`: {_(f'move messages to `[Gmail]/Trash` in GMail-specific way instead of trying to delete them immediately (GMail ignores IMAP `EXPUNGE` outside of `[Gmail]/Trash`, you can then `{__package__} delete --method delete --folder "[Gmail]/Trash"` them after, or you could just leave them there and GMail will delete them in 30 days)')}
""")
    add_req_folders(cmd)
    cmd.set_defaults(func=cmd_action)
    cmd.set_defaults(command="delete")

    args = parser.parse_args(sys.argv[1:])

    if args.help_markdown:
        parser.set_formatter_class(argparse.MarkdownBetterHelpFormatter)
        print(parser.format_help(1024))
        sys.exit(0)

    if args.user is None:
        die(_("`--user` is required"))

    if args.passfile is not None:
        with open(args.passfile, "rb") as f:
            password = f.readline().decode(defenc)
    elif args.passcmd is not None:
        with subprocess.Popen(args.passcmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, shell=True) as p:
            p.stdin.close() # type: ignore
            password = p.stdout.readline().decode(defenc) # type: ignore
            retcode = p.wait()
            if retcode != 0:
                die(_("`--passcmd` (`%s`) failed with non-zero exit code %d") % (args.passcmd, retcode))
    else:
        die(_("either `--passfile` or `--passcmd` is required"))

    if password[-1:] == "\n":
        password = password[:-1]

    args.password = password

    if args.command == "fetch":
        if args.mda is None:
            die(_("`--mda` is not set"))

    handle_signals()

    try:
        args.func(args)
    except CatastrophicFailure as exc:
        sys.stderr.write(_("error") + ": " + exc.show() + "\n")
        had_errors = True
    except KeyboardInterrupt:
        sys.stderr.write(_("Interrupted!") + "\n")
        had_errors = True
    except Exception as exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)
        had_errors = True

    if had_errors:
        sys.stderr.write(_("Had errors!") + "\n")
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
