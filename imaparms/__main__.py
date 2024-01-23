#!/usr/bin/env python3
#
# This file is a part of imaparms project.
#
# Copyright (c) 2023 Jan Malakhovski <oxij@oxij.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import dataclasses as _dc
import decimal
import fcntl as _fcntl
import hashlib as _hashlib
import os
import random
import signal
import socket as _socket
import ssl
import subprocess
import sys
import time
import traceback as traceback
import typing as _t

from imaplib import IMAP4, IMAP4_SSL
from gettext import gettext, ngettext

from . import argparse_better as argparse
from .argparse_better import Namespace
from .exceptions import *

defenc = sys.getdefaultencoding()
myhostname = _socket.gethostname()
smypid = str(os.getpid())

def issue(message : str) -> None:
    if sys.stderr.isatty():
        sys.stderr.write("\033[31m" + message + "\033[0m\n")
    else:
        sys.stderr.write(message + "\n")
    sys.stderr.flush()

def error(message : str) -> None:
    issue(gettext("error") + ": " + message)

def die(message : str, code : int = 1) -> _t.NoReturn:
    error(message)
    sys.exit(code)

interrupt_msg = "\n" + gettext("Gently finishing up... Press ^C again to forcefully interrupt.")
want_stop = False
should_raise = True
def sig_handler(sig : int, frame : _t.Any) -> None:
    global want_stop
    global should_raise
    want_stop = True
    if should_raise:
        raise KeyboardInterrupt()
    if sig == signal.SIGINT:
        issue(interrupt_msg)
    should_raise = True

class SleepInterrupt(BaseException): pass

should_unsleep = False
def sig_unsleep(sig : int, frame : _t.Any) -> None:
    global should_unsleep
    if should_unsleep:
        raise SleepInterrupt()

def handle_signals() -> None:
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGUSR1, sig_unsleep)

def pinentry(host : str, user : str) -> str:
    with subprocess.Popen(["pinentry"], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as p:
        def check(beginning : str) -> str:
            res = p.stdout.readline().decode(defenc) # type: ignore
            if not res.endswith("\n") or not res.startswith(beginning):
                raise Failure("pinentry conversation failed")
            return res[len(beginning):-1]
        check("OK ")
        def opt(what : str, beginning : str) -> str:
            p.stdin.write(what.encode(defenc) + b"\n") # type: ignore
            p.stdin.flush() # type: ignore
            return check(beginning)
        opt("SETDESC " + gettext("Please enter the passphrase for user %s on host %s") % (user, host), "OK")
        opt("SETPROMPT " + gettext("Passphrase:"), "OK")
        pin = opt("GETPIN", "D ")
        return pin

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

def make_search_filter(cfg : Namespace, now : int) -> _t.Tuple[str, bool]:
    filters = []
    dynamic = False

    if cfg.seen is not None:
        if cfg.seen:
            filters.append("SEEN")
        else:
            filters.append("UNSEEN")

    if cfg.flagged is not None:
        if cfg.flagged:
            filters.append("FLAGGED")
        else:
            filters.append("UNFLAGGED")

    for f in cfg.hfrom:
        filters.append(f'FROM {imap_quote(f)}')

    for f in cfg.hnotfrom:
        filters.append(f'NOT FROM {imap_quote(f)}')

    def read_timestamp(path : str) -> int:
        with open(path, "rb") as f:
            try:
                data = f.readline().decode(defenc).strip()
                # converting via Decimal to preserve all 9 digits after the dot
                return int(decimal.Decimal(data) * 10**9)
            except Exception:
                raise Failure("failed to decode a timestamp from the first line of %s", path)

    older_than = []
    for dt in cfg.older_than:
        older_than.append(now - dt * 86400 * 10**9)

    for path in cfg.older_than_timestamp_in:
        older_than.append(read_timestamp(os.path.expanduser(path)))

    for path in cfg.older_than_mtime_of:
        older_than.append(os.stat(os.path.expanduser(path)).st_mtime_ns)

    if len(older_than) > 0:
        date = time.gmtime(min(older_than) / 10**9)
        filters.append(f"BEFORE {imap_date(date)}")
        dynamic = True

    newer_than = []
    for dt in cfg.newer_than:
        newer_than.append(now - dt * 86400 * 10**9)

    for path in cfg.newer_than_timestamp_in:
        newer_than.append(read_timestamp(os.path.expanduser(path)))

    for path in cfg.newer_than_mtime_of:
        newer_than.append(os.stat(os.path.expanduser(path)).st_mtime_ns)

    if len(newer_than) > 0:
        date = time.gmtime(max(newer_than) / 10**9)
        filters.append(f"NOT BEFORE {imap_date(date)}")
        dynamic = True

    if len(filters) == 0:
        return "(ALL)", dynamic
    else:
        return "(" + " ".join(filters) + ")", dynamic

def report(message : str) -> None:
    sys.stdout.write(message + "\n")
    sys.stdout.flush()

def info(cfg : Namespace, message : str) -> None:
    if cfg.quiet: return
    report(message)

def run_hook(hook : str) -> None:
    try:
        with subprocess.Popen(hook, shell=True) as p:
            # __exit__ will do everything we need
            pass
    except Exception as exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)

def run_hook_stdin(hook : str, data : bytes) -> None:
    try:
        with subprocess.Popen(hook, stdin=subprocess.PIPE, shell=True) as p:
            fd : _t.Any = p.stdin
            fd.write(data)
            fd.flush()
            fd.close()
    except Exception as exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)

def notify_send(typ : str, title : str, body : str) -> None:
    try:
        with subprocess.Popen(["notify-send", "-a", "imaparms", "-i", typ, "--", title, body]) as p:
            pass
    except Exception as exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)

def notify_success(cfg : Namespace, title : str, body : str) -> None:
    if cfg.notify_success:
        notify_send("info", title, body)

    for cmd in cfg.success_cmd:
        run_hook_stdin(cmd, title.encode(defenc) + b"\n" + body.encode(defenc) + b"\n")

def notify_failure(cfg : Namespace, title : str, body : str) -> None:
    if cfg.notify_failure:
        notify_send("error", title, body)

    for cmd in cfg.failure_cmd:
        run_hook_stdin(cmd, title.encode(defenc) + b"\n" + body.encode(defenc) + b"\n")

def notify_error(cfg : Namespace, title : str, body : str = "") -> None:
    error(title)
    notify_failure(cfg, title, body)

class AccountFailure(Failure): pass
class FolderFailure(AccountFailure): pass

def format_imap_error(command : str, typ : str, data : _t.Any = None) -> _t.Any:
    if data is None:
        return gettext("IMAP %s command failed: %s") % (command, typ)
    else:
        return gettext("IMAP %s command failed: %s %s") % (command, typ, repr(data))

def imap_exc(exc : _t.Any, command : str, typ : str, data : _t.Any) -> _t.Any:
    return exc(format_imap_error(command, typ, data))

def imap_check(exc : _t.Any, command : str, v : _t.Tuple[str, _t.Any]) -> _t.Any:
    typ, data = v
    if typ != "OK":
        raise imap_exc(exc, command, typ, data)
    return data

@_dc.dataclass
class Account:
    socket : str
    host : str
    port : int
    user : str
    password : str
    allow_login : bool
    IMAP_base : type

    num_delivered : int = _dc.field(default = 0)
    num_undelivered : int = _dc.field(default = 0)
    num_marked : int = _dc.field(default = 0)
    num_moved : int = _dc.field(default = 0)
    num_deleted : int = _dc.field(default = 0)
    log : _t.List[str] = _dc.field(default_factory = lambda: [])
    errors : _t.List[str] = _dc.field(default_factory = lambda: [])

def account_error(account : Account, message : str) -> None:
    account.errors.append(message)
    error(message)

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

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
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
        raise AccountFailure("failed to connect to host %s port %s: %s", account.host, account.port, repr(exc))

    return srv

def unsleep(seconds : _t.Union[int, float]) -> None:
    global should_unsleep

    should_unsleep = True
    try:
        time.sleep(seconds)
    except SleepInterrupt:
        sys.stdout.write("# " + gettext("received SIGUSR1") + "\n")
        sys.stdout.flush()
    finally:
        should_unsleep = False

@_dc.dataclass
class State:
    num_errors : int = _dc.field(default = 0)
    hooks : _t.List[str] = _dc.field(init = False)

    def __post_init__(self) -> None:
        self.hooks = []

def for_each_account_poll(cfg : Namespace, state : State, *args : _t.Any) -> None:
    if cfg.every is None:
        for_each_account(cfg, state, *args)
        return

    fmt = "[%Y-%m-%d %H:%M:%S]"
    cycle = cfg.every

    def do_sleep(ttime : str) -> None:
        report("# " + gettext("sleeping until %s, send SIGUSR1 to PID %s or hit ^C to start immediately, hit ^C twice to abort") % (ttime, smypid))
        try:
            unsleep(to_sleep)
        except KeyboardInterrupt:
            global want_stop
            want_stop = False

            # give user the time to abort
            report("# " + gettext("starting in a little bit, last chance to abort..."))
            unsleep(1)

    to_sleep = random.randint(0, cfg.every_add_random)
    if to_sleep > 0:
        now = time.time()
        ttime = time.strftime(fmt, time.localtime(now + to_sleep))
        do_sleep(ttime)

    while True:
        now = time.time()
        repeat_at = now + cycle
        ftime = time.strftime(fmt, time.localtime(now))
        info(cfg, "# " + gettext("poll: starting at %s") % (ftime,))

        for_each_account(cfg, state, *args)

        now = time.time()
        ntime = time.strftime(fmt, time.localtime(now))

        info(cfg, "# " + gettext("poll: finished at %s") % (ntime,))

        to_sleep = max(60, repeat_at - now + random.randint(0, cfg.every_add_random))
        ttime = time.strftime(fmt, time.localtime(now + to_sleep))
        do_sleep(ttime)

def for_each_account(cfg : Namespace, state : State, *args : _t.Any) -> None:
    global should_raise
    should_raise = False
    try:
        for_each_account_(cfg, state, *args)
    finally:
        should_raise = True

def for_each_account_(cfg : Namespace, state : State, func : _t.Callable[..., None], *args : _t.Any) -> None:
    num_delivered, num_undelivered = 0, 0
    num_marked, num_moved, num_deleted = 0, 0, 0
    log = []
    errors = []

    account : Account
    for account in cfg.accounts:
        if want_stop: raise KeyboardInterrupt()

        try:
            srv = connect(account, cfg.debug)

            data = imap_check(AccountFailure, "CAPABILITY", srv.capability())
            try:
                capabilities = data[0].decode("ascii").split(" ")
                if "IMAP4rev1" not in capabilities:
                    raise ValueError()
            except (UnicodeDecodeError, KeyError, ValueError):
                raise AccountFailure("host %s port %s does not speak IMAP4rev1, your IMAP server appears to be too old", cfg.host, cfg.port)

            #print(capabilities)

            method : str
            if "AUTH=CRAM-MD5" in capabilities:
                def do_cram_md5(challenge : bytes) -> str:
                    import hmac
                    pwd = account.password.encode("utf-8")
                    return imap_quote(account.user) + " " + hmac.HMAC(pwd, challenge, "md5").hexdigest()
                method = "AUTHENTICATE CRAM-MD5"
                typ, data = srv.authenticate("CRAM-MD5", do_cram_md5)
            elif account.allow_login:
                method = "LOGIN PLAIN"
                typ, data = srv._simple_command("LOGIN", imap_quote(account.user), imap_quote(account.password))
            else:
                raise AccountFailure("authentication with plain-text credentials is disabled, set both `--auth-allow-login` and `--auth-allow-plain` if you really want to do this")

            if typ != "OK":
                raise AccountFailure("failed to login (%s) as %s to host %s port %d: %s", method, account.user, account.host, account.port, repr(data))
            srv.state = "AUTH"

            report("# " + gettext("logged in (%s) as %s to host %s port %d (%s)") % (method, account.user, account.host, account.port, account.socket.upper()))

            func(cfg, state, account, srv, *args)
        except AccountFailure as exc:
            state.num_errors += 1
            account_error(account, str(exc))
        finally:
            try:
                srv.logout()
            except:
                pass
            srv = None

            num_delivered += account.num_delivered
            num_marked += account.num_marked
            num_moved += account.num_moved
            num_deleted += account.num_deleted
            num_undelivered += account.num_undelivered
            if len(account.log) > 0:
                log.append(gettext("%s on %s:") % \
                           (account.user, account.host) + \
                           "\n- " + "\n- ".join(account.log))
            errors += account.errors

            account.num_delivered, account.num_undelivered = 0, 0
            account.num_marked, account.num_moved, account.num_deleted = 0, 0, 0
            account.log = []
            account.errors = []

    if len(state.hooks) > 0:
        for hook in state.hooks:
            report("# " + gettext("running `%s`") % (hook,))
            run_hook(hook)
        state.hooks = []

    good = []
    if num_delivered > 0:
        good.append(ngettext("fetched %d new message", "fetched %d new messages", num_delivered) % (num_delivered,))
    if num_marked > 0:
        good.append(ngettext("marked %d message", "marked %d messages", num_marked) % (num_marked,))
    if num_moved > 0:
        good.append(ngettext("moved %d message", "moved %d messages", num_moved) % (num_moved,))
    if num_deleted > 0:
        good.append(ngettext("deleted %d message", "deleted %d messages", num_deleted) % (num_deleted,))

    bad = []
    if num_undelivered > 0:
        bad.append(ngettext("failed to fetch %d message", "failed to fetch %d messages", num_undelivered) % (num_undelivered,))
    num_errors = len(errors)
    if num_errors > 0:
        bad.append(ngettext("produced %d new error", "produced %d new errors", num_errors) % (num_errors,))

    if len(good) > 0:
        title = gettext(", ").join(good)
        info(cfg, "# " + gettext("poll: ") + title)
        notify_success(cfg, title, "\n".join(log))

    if len(bad) > 0:
        title = gettext(", ").join(bad)
        issue("# " + gettext("poll: ") + title)
        notify_failure(cfg, title, "\n".join(errors))

def check_cmd(cfg : Namespace) -> None:
    if len(cfg.accounts) == 0:
        die(gettext("no accounts are specified, need at least one `--host`, `--user`, and either of `--passfile` or `--passcmd`"))

    if cfg.command == "fetch" and cfg.maildir is None and cfg.mda is None:
        die(gettext("no delivery method is specified, either `--maildir` or `--mda` is required"))

def cmd_list(cfg : Namespace, state : State) -> None:
    check_cmd(cfg)

    if cfg.very_dry_run:
        sys.exit(1)

    for_each_account_poll(cfg, state, do_list)

def do_list(cfg : Namespace, state : State, account : Account, srv : IMAP4) -> None:
    folders = get_folders(srv)
    for e in folders:
        print(e)

def get_folders(srv : IMAP4) -> _t.List[str]:
    res = []
    data = imap_check(AccountFailure, "LIST", srv.list())
    for el in data:
        tags, _, arg = imap_parse(el)
        if b"\\Noselect" in tags:
            continue
        res.append(arg.decode("utf-8"))
    return res

def print_prelude(cfg : Namespace) -> None:
    _ = gettext
    every = ""
    if cfg.every is not None:
        every = _("every %d seconds, ") % (cfg.every,)
    info(cfg, "# " + every + _("for each of"))
    for acc in cfg.accounts:
        info(cfg, "... " + _("user %s on host %s port %d (%s)") % (acc.user, acc.host, acc.port, acc.socket.upper()))
    info(cfg, "# " + _("do"))

def prepare_cmd(cfg : Namespace, now : int) -> str:
    if cfg.command == "mark":
        if cfg.seen is None and cfg.flagged is None:
            if cfg.mark == "seen":
                cfg.seen = False
            elif cfg.mark == "unseen":
                cfg.seen = True
            elif cfg.mark == "flagged":
                cfg.flagged = False
            elif cfg.mark == "unflagged":
                cfg.flagged = True
    elif cfg.command == "fetch":
        if cfg.mark == "auto":
            if cfg.seen == False and cfg.flagged is None:
                cfg.mark = "seen"
            elif cfg.seen is None and cfg.flagged == False:
                cfg.mark = "flagged"
            else:
                cfg.mark = "noop"

    if len(cfg.folders) != 0:
        cfg.all_folders = False

    if cfg.all_folders:
        place = gettext("in all folders")
    else:
        place = gettext("in %s") % (", ".join(map(repr, cfg.folders)),)

    if cfg.not_folders:
        place += " " + gettext("excluding %s") % (", ".join(map(repr, cfg.not_folders)),)

    search_filter, dynamic = make_search_filter(cfg, now)
    sf = search_filter
    if cfg.every is not None and dynamic:
        sf += " " + gettext("{dynamic}")

    if "mark" in cfg:
        what = gettext(f"search %s, perform {cfg.command}, mark them as %s") % (sf, cfg.mark.upper())
    else:
        what = gettext(f"search %s, perform {cfg.command}") % (sf,)

    info(cfg, f"... {place}: {what}")

    return search_filter

def cmd_action(cfg : Namespace, state : State) -> None:
    check_cmd(cfg)
    print_prelude(cfg)
    now = time.time_ns()
    cfg.search_filter = prepare_cmd(cfg, now)

    if cfg.very_dry_run:
        sys.exit(1)

    for_each_account_poll(cfg, state, for_each_folder_multi, [cfg])

def cmd_multi_action(common_cfg : Namespace, state : State, subcfgs : _t.List[Namespace]) -> None:
    print_prelude(common_cfg)
    now = time.time_ns()
    for subcfg in subcfgs:
        subcfg.search_filter = prepare_cmd(subcfg, now)

    if common_cfg.very_dry_run:
        sys.exit(1)

    for_each_account_poll(common_cfg, state, for_each_folder_multi, subcfgs)

def for_each_folder_multi(common_cfg : Namespace, state : State, account : Account, srv : IMAP4,
                          subcfgs : _t.List[Namespace]) -> None:
    if common_cfg.every is not None:
        now = time.time_ns()
        for subcfg in subcfgs:
            subcfg.search_filter, _ = make_search_filter(subcfg, now)

    for subcfg in subcfgs:
        for_each_folder_(subcfg, state, account, srv, do_folder_action, subcfg.command)

def for_each_folder_(cfg : Namespace, state : State, account : Account, srv : IMAP4,
                     func : _t.Callable[..., None], *args : _t.Any) -> None:
    if cfg.all_folders:
        folders = get_folders(srv)
    else:
        folders = cfg.folders

    for folder in filter(lambda f: f not in cfg.not_folders, folders):
        if want_stop: raise KeyboardInterrupt()

        typ, data = srv.select(imap_quote(folder))
        if typ != "OK":
            state.num_errors += 1
            error(format_imap_error("SELECT", typ, data))
            account_error(account, gettext("failed to IMAP SELECT folder `%s`, skipping") % (folder,))
            continue

        try:
            func(cfg, state, account, srv, folder, *args)
        except FolderFailure as exc:
            state.num_errors += 1
            account_error(account, str(exc))
        finally:
            srv.close()

def do_folder_action(cfg : Namespace, state : State, account : Account, srv : IMAP4,
                     folder : str, command : str) -> None:

    typ, data = srv.uid("SEARCH", cfg.search_filter)
    if typ != "OK":
        raise imap_exc(FolderFailure, "SEARCH", typ, data)

    result : _t.Optional[bytes] = data[0]
    if result is None:
        raise imap_exc(FolderFailure, "SEARCH", typ, data)
    elif result == b"":
        message_uids = []
    else:
        message_uids = result.split(b" ")
    num_messages = len(message_uids)

    if command == "count":
        if cfg.porcelain:
            print(f"{num_messages} {folder}")
        else:
            report(ngettext("folder `%s` has %d message matching %s", "folder `%s` has %d messages matching %s", num_messages) % (folder, num_messages, cfg.search_filter))
        return

    act : str
    actargs : _t.Any
    method = None
    if command == "mark":
        act = "marking as %s %d messages matching %s from folder `%s`"
        actargs  = (cfg.mark.upper(), num_messages, cfg.search_filter, folder)
    elif command == "fetch":
        act = "fetching %d messages matching %s from folder `%s`"
        actargs  = (num_messages, cfg.search_filter, folder)
    elif command == "delete":
        if cfg.method == "auto":
            if account.host == "imap.gmail.com" and folder != "[Gmail]/Trash":
                method = "gmail-trash"
            else:
                method = "delete"
        else:
            method = cfg.method

        if method in ["delete", "delete-noexpunge"]:
            act = "deleting %d messages matching %s from folder `%s`"
            actargs  = (num_messages, cfg.search_filter, folder)
        elif method == "gmail-trash":
            act = f"moving %d messages matching %s from folder `%s` to `[GMail]/Trash`"
            actargs  = (num_messages, cfg.search_filter, folder)
        else:
            assert False
    else:
        assert False

    if cfg.dry_run:
        report(gettext("dry-run: (not) " + act) % actargs)
        return
    elif command == "delete" and len(account.errors) > 0:
        account_error(account, gettext("one of the previous commands produced errors, not " + act) % actargs)
        return
    else:
        report(gettext(act) % actargs)

    if num_messages == 0:
        # nothing to do
        return

    if command == "mark":
        old_num_marked = account.num_marked
        try:
            do_store(cfg, state, account, srv, cfg.mark, message_uids)
        finally:
            num_marked = account.num_marked - old_num_marked
            if num_marked > 0:
                account.log.append("`%s`: " % (folder,) + \
                                   ngettext("marked %d message", "marked %d messages", num_marked) % (num_marked,))
    elif command == "fetch":
        old_num_delivered = account.num_delivered
        old_num_marked = account.num_marked
        try:
            do_fetch(cfg, state, account, srv, message_uids)
        finally:
            num_delivered = account.num_delivered - old_num_delivered
            num_marked = account.num_marked - old_num_marked
            if num_delivered > 0:
                if num_delivered == num_marked:
                    msg = ngettext("fetched and marked %d message", "fetched and marked %d messages", \
                                   num_delivered) % (num_delivered,)
                else:
                    msg = ngettext("fetched %d but marked %d message", "fetched %d but marked %d messages", \
                                   num_delivered) % (num_delivered, num_marked)
                account.log.append("`%s`: " % (folder,) + msg)

                for hook in cfg.new_mail_cmd:
                    if hook not in state.hooks:
                        state.hooks.append(hook)
    elif command == "delete":
        assert method is not None
        old_num_deleted = account.num_deleted
        try:
            do_store(cfg, state, account, srv, method, message_uids)
        finally:
            num_deleted = account.num_deleted - old_num_deleted
            if num_deleted > 0:
                account.log.append("`%s`: " % (folder,) + \
                                   ngettext("deleted %d message", "deleted %d messages", num_deleted) % (num_deleted,))

def do_fetch(cfg : Namespace, state : State, account : Account, srv : IMAP4, message_uids : _t.List[bytes]) -> None:
    fetch_num = cfg.fetch_number
    batch : _t.List[bytes] = []
    batch_total = 0
    while len(message_uids) > 0:
        if want_stop: raise KeyboardInterrupt()

        to_fetch, message_uids = message_uids[:fetch_num], message_uids[fetch_num:]
        to_fetch_set : _t.Set[bytes] = set(to_fetch)
        typ, data = srv.uid("FETCH", b",".join(to_fetch), "(RFC822.SIZE)") # type: ignore
        if typ != "OK":
            account.num_undelivered += len(to_fetch)
            state.num_errors += 1
            error(format_imap_error("FETCH", typ, data))
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
                fetch_check_untagged(cfg, state, attrs)
                continue

            new.append((uid, size))
            to_fetch_set.remove(uid)

        if len(to_fetch_set) > 0:
            account.num_undelivered += len(to_fetch)
            state.num_errors += 1
            error(format_imap_error("FETCH", "did not get enough elements"))
            continue

        while True:
            leftovers = []
            for uel in new:
                uid, size = uel
                if len(batch) < cfg.batch_number and batch_total + size < cfg.batch_size:
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

            do_fetch_batch(cfg, state, account, srv, batch, batch_total)
            batch = []
            batch_total = 0
            new = leftovers

    do_fetch_batch(cfg, state, account, srv, batch, batch_total)

def fetch_check_untagged(cfg : Namespace, state : State, attrs : _t.Dict[bytes, bytes]) -> None:
    try:
        flags = attrs[b"FLAGS"]
        if len(attrs) != 1:
            raise KeyError()
    except KeyError:
        sys.stderr.write("attrs dump: %s" % (repr(attrs),) + "\n")
        sys.stderr.flush()
        raise AccountFailure("another client is performing unknown conflicting actions in parallel with us, aborting `fetch`")

    # This is an untagged response generated by the server because
    # another client changed some flags.
    # Let's check they did not add or remove the flag we use for tracking state.
    if (cfg.mark == "seen" and b"\\Seen" in flags) or \
       (cfg.mark == "unseen" and b"\\Seen" not in flags) or \
       (cfg.mark == "flagged" and b"\\Flagged" in flags) or \
       (cfg.mark == "unflagged" and b"\\Flagged" not in flags):
        raise AccountFailure("another client is marking messages with potentially conflicting flags in parallel with us, aborting `fetch`")

def do_fetch_batch(cfg : Namespace, state : State, account : Account, srv : IMAP4, message_uids : _t.List[bytes], total_size : int) -> None:
    if want_stop: raise KeyboardInterrupt()

    if len(message_uids) == 0: return
    info(cfg, "... " + gettext("fetching a batch of %d messages (%d bytes)") % (len(message_uids), total_size))

    # because time.time() gives a float
    epoch_ms = time.time_ns() // 1000000

    joined = b",".join(message_uids)
    typ, data = srv.uid("FETCH", joined, "(BODY.PEEK[HEADER] BODY.PEEK[TEXT])") # type: ignore
    if typ != "OK":
        account.num_undelivered += len(message_uids)
        state.num_errors += 1
        error(format_imap_error("FETCH", typ, data))
        return

    if cfg.maildir is not None:
        internal_mda = True
        unsynced = []
        destdir = os.path.expanduser(cfg.maildir)
        try:
            os.makedirs(os.path.join(destdir, "tmp"), exist_ok=True)
            os.makedirs(os.path.join(destdir, "new"), exist_ok=True)
            os.makedirs(os.path.join(destdir, "cur"), exist_ok=True)
        except:
            raise CatastrophicFailure(gettext("failed to create `--maildir %s`"), destdir)

        sepoch_ms = str(epoch_ms)
        tmp_num = 0
    elif cfg.mda is not None:
        internal_mda = False
    else:
        assert False

    done_uids = []
    failed_uids = []
    while len(data) > 0:
        # have to do this whole thing beacause imaplib returns
        # multiple outputs as a flat list of partially-parsed chunks,
        # so we need the (xxx) detector below to make any sense of it
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
            fetch_check_untagged(cfg, state, attrs)
            continue

        if True:
            # strip \r like fetchmail does
            header = header.replace(b"\r\n", b"\n")
            body = body.replace(b"\r\n", b"\n")

        if internal_mda:
            # deliver to Maildir
            mho = _hashlib.sha256()
            mho.update(header)
            mho.update(body)
            msghash = mho.hexdigest()
            sflen = str(len(header) + len(body))

            try:
                tf : _t.Any
                tmp_path : str
                while True:
                    tmp_path = os.path.join(destdir, "tmp",
                                            f"IAP_{smypid}_{sepoch_ms}_{str(tmp_num)}.{myhostname},S={sflen}.part")
                    tmp_num += 1

                    try:
                        tf = open(tmp_path, "xb")
                    except FileExistsError:
                        continue
                    break

                try:
                    tf.write(header)
                    tf.write(body)
                    tf.flush()
                except Exception as exc:
                    try: tf.close()
                    except Exception: pass
                    try: os.unlink(tmp_path)
                    except Exception: pass
                    raise exc
            except Exception as exc:
                traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)
                failed_uids.append(uid)
            else:
                unsynced.append((tf, (uid, msghash, sflen, tmp_path)))
        else:
            # deliver via MDA
            flushed = False
            delivered = False
            with subprocess.Popen(cfg.mda, stdin=subprocess.PIPE, shell=True) as p:
                fd : _t.Any = p.stdin
                try:
                    fd.write(header)
                    fd.write(body)
                    fd.flush()
                    fd.close()
                except BrokenPipeError:
                    try: fd.close()
                    except Exception: pass
                except Exception as exc:
                    traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)
                    try: fd.close()
                    except Exception: pass
                else:
                    flushed = True

                retcode = p.wait()
                if retcode == 0:
                    delivered = flushed

            if delivered:
                done_uids.append(uid)
            else:
                failed_uids.append(uid)

    if internal_mda:
        # finish delivering to Maildir

        # fsync all messages to disk
        #
        # we delay `fsync`s till the end of the whole batch so that the target
        # filesystem could also batch disk writes, which could make a big
        # difference on an SSD
        synced = []
        for tf, el in unsynced:
            uid, msghash, sflen, tmp_path = el
            try:
                os.fsync(tf.fileno())
                tf.close()
            except Exception as exc:
                traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)
                try: tf.close()
                except Exception: pass
                try: os.unlink(tmp_path)
                except Exception: pass
                failed_uids.append(uid)
            else:
                synced.append(el)
        del unsynced

        # lock destination directory
        ddir = os.path.join(destdir, "new")
        try:
            dirfd = os.open(ddir, os.O_RDONLY | os.O_DIRECTORY)
            _fcntl.flock(dirfd, _fcntl.LOCK_EX)
        except Exception as exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)
            # cleanup
            for uid, _, _, tmp_path in synced:
                try: os.unlink(tmp_path)
                except Exception: pass
                failed_uids.append(uid)
            del synced
            error(gettext("failed to lock `--maildir %s`") % (destdir,))
        else:
            # rename files to destination
            for uid, msghash, sflen, tmp_path in synced:
                msg_num = 0
                while True:
                    msg_path = os.path.join(ddir,
                                            f"IAH_{msghash}_{str(msg_num)}.{myhostname},S={sflen}")
                    msg_num += 1

                    if os.path.exists(msg_path):
                        continue
                    break

                try:
                    os.rename(tmp_path, msg_path)
                except Exception as exc:
                    traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)
                    try: os.unlink(tmp_path)
                    except Exception: pass
                    failed_uids.append(uid)
                else:
                    done_uids.append(uid)
            del synced

            # ensure directory inode is synced to disk
            try:
                os.fsync(dirfd)
                _fcntl.flock(dirfd, _fcntl.LOCK_UN)
                os.close(dirfd)
            except Exception as exc:
                traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)
                failed_uids += done_uids
                done_uids = []
                error(gettext("failed to sync `--maildir %s`") % (destdir,))

    num_delivered = len(done_uids)
    num_undelivered = len(failed_uids)
    account.num_delivered += num_delivered
    account.num_undelivered += num_undelivered

    if internal_mda:
        how = "--maildir " + destdir
    else:
        how = "--mda " + cfg.mda

    if num_delivered > 0:
        info(cfg, "... " + ngettext("delivered %d message via `%s`", "delivered %d messages via `%s`", num_delivered) % (num_delivered, how))

    if num_undelivered > 0:
        state.num_errors += 1
        error(ngettext("failed to deliver %d message via `%s`", "failed to deliver %d messages via `%s`", num_undelivered) % (num_undelivered, how))
        if cfg.paranoid is not None:
            if num_delivered == 0:
                raise AccountFailure(gettext("failed to deliver any messages, aborting `fetch`"))
            elif cfg.paranoid:
                raise CatastrophicFailure(gettext("failed to deliver %d messages in paranoid mode"), num_undelivered)

    do_store(cfg, state, account, srv, cfg.mark, done_uids, False)

marking_as = "... " + gettext("marking a batch of %d messages as %s")

def do_store(cfg : Namespace, state : State, account : Account, srv : IMAP4,
             method : str, message_uids : _t.List[bytes], interruptable : bool = True) -> None:
    if method == "noop": return

    store_num = cfg.store_number
    while len(message_uids) > 0:
        if interruptable and want_stop: raise KeyboardInterrupt()

        to_store, message_uids = message_uids[:store_num], message_uids[store_num:]
        joined = b",".join(to_store)
        if method == "seen":
            info(cfg, marking_as % (len(to_store), "SEEN"))
            typ, data = srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Seen") # type: ignore
        elif method == "unseen":
            info(cfg, marking_as % (len(to_store), "UNSEEN"))
            typ, data = srv.uid("STORE", joined, "-FLAGS.SILENT", "\\Seen") # type: ignore
        elif method == "flagged":
            info(cfg, marking_as % (len(to_store), "FLAGGED"))
            typ, data = srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Flagged") # type: ignore
        elif method == "unflagged":
            info(cfg, marking_as % (len(to_store), "UNFLAGGED"))
            typ, data = srv.uid("STORE", joined, "-FLAGS.SILENT", "\\Flagged") # type: ignore
        elif method in ["delete", "delete-noexpunge"]:
            info(cfg, "... " + gettext("deleting a batch of %d messages") % (len(to_store),))
            typ, data = srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Deleted") # type: ignore
            if typ == "OK" and method == "delete":
                srv.expunge()
        elif method == "gmail-trash":
            info(cfg, "... " + gettext("moving a batch of %d messages to `[GMail]/Trash`") % (len(to_store),))
            typ, data = srv.uid("STORE", joined, "+X-GM-LABELS", "\\Trash") # type: ignore
        else:
            assert False

        if typ == "OK":
            num_messages = len(to_store)
            if method in ["delete", "delete-noexpunge"]:
                account.num_deleted += num_messages
            elif method == "gmail-trash":
                account.num_moved += num_messages
            else:
                account.num_marked += num_messages
        else:
            state.num_errors += 1
            error(format_imap_error("STORE", typ, data))

def add_examples(fmt : _t.Any) -> None:
    _ = gettext
    fmt.add_text("# " + _("Notes on usage"))

    fmt.add_text(_('Message search filters are connected by logical "AND"s so, e.g., `--from "github.com" --not-from "notifications@github.com"` will act on messages which have a `From:` header with `github.com` but without `notifications@github.com` as substrings.'))

    fmt.add_text(_("Note that `fetch` subcommand acts on `--unseen` while `delete` acts on `--seen` messages by default."))

    fmt.add_text("# " + _("Examples"))

    fmt.start_section(_("List all available IMAP folders and count how many messages they contain"))

    fmt.start_section(_("with the password taken from `pinentry`"))
    fmt.add_code(f'{__package__} count --host imap.example.com --user account@example.com --pass-pinentry')
    fmt.end_section()

    fmt.start_section(_("with the password taken from the first line of the given file"))
    fmt.add_code(f"""{__package__} count --host imap.example.com --user account@example.com \\
  --passfile /path/to/file/containing/account@example.com.password
""")
    fmt.end_section()

    fmt.start_section(_("with the password taken from the output of password-store utility"))
    fmt.add_code(f"""{__package__} count --host imap.example.com --user account@example.com \\
  --passcmd "pass show mail/account@example.com"
""")
    fmt.end_section()

    fmt.start_section(_("with two accounts on the same server"))
    fmt.add_code(f"""{__package__} count --porcelain \\
  --host imap.example.com \\
  --user account@example.com --passcmd "pass show mail/account@example.com" \\
  --user another@example.com --passcmd "pass show mail/another@example.com"
""")
    fmt.end_section()

    fmt.end_section()

    fmt.add_text(_("Now, assuming the following are set:"))
    fmt.add_code("""common=(--host imap.example.com --user account@example.com --passcmd "pass show mail/account@example.com")
common_mda=("${{common[@]}}" --mda maildrop)
gmail_common=(--host imap.gmail.com --user account@gmail.com --passcmd "pass show mail/account@gmail.com")
gmail_common_mda=("${{gmail_common[@]}}" --mda maildrop)
""")

    fmt.start_section(_("Count how many messages older than 7 days are in `[Gmail]/All Mail` folder"))
    fmt.add_code(f'{__package__} count "${{gmail_common[@]}}" --folder "[Gmail]/All Mail" --older-than 7')
    fmt.end_section()

    fmt.start_section(_(f"Mark all messages in `INBOX` as not `SEEN`, fetch all not `SEEN` messages marking them `SEEN` as you download them so that if the process gets interrupted you could continue from where you left off"))
    fmt.add_code(f"""# {_("setup: do once")}
{__package__} mark "${{common[@]}}" --folder INBOX unseen

# {_("repeatable part")}
{__package__} fetch "${{common_mda[@]}}" --folder INBOX
""")
    fmt.end_section()

    fmt.start_section(_(f"Similarly to the above, but use `FLAGGED` instead of `SEEN`. This allows to use this in parallel with another instance of `{__package__}` using the `SEEN` flag, e.g. if you want to backup to two different machines independently, or if you want to use `{__package__}` simultaneously in parallel with `fetchmail` or other similar tool"))
    fmt.add_code(f"""# {_("setup: do once")}
{__package__} mark "${{common[@]}}" --folder INBOX unflagged

# {_("repeatable part")}
{__package__} fetch "${{common_mda[@]}}" --folder INBOX --any-seen --unflagged

# {_("this will work as if nothing of the above was run")}
fetchmail

# {_(f"in this use case you should use both `--seen` and `--flagged` when expiring old messages to only delete messages fetched by both {__package__} and fetchmail")}
{__package__} delete "${{common[@]}}" --folder INBOX --older-than 7 --seen --flagged
""")
    fmt.end_section()

    fmt.start_section(_(f"Similarly to the above, but run `{__package__} fetch` as a daemon to download updates every hour"))
    fmt.add_code(f"""# {_("setup: do once")}
{__package__} mark "${{common[@]}}" --folder INBOX unseen

# {_("repeatable part")}
{__package__} fetch "${{common_mda[@]}}" --folder INBOX --every 3600
""")
    fmt.end_section()

    fmt.start_section(_("Fetch all messages from `INBOX` folder that were delivered in the last 7 days (the resulting date is rounded down to the start of the day by server time), but don't change any flags"))
    fmt.add_code(f'{__package__} fetch "${{common_mda[@]}}" --folder INBOX --any-seen --newer-than 7')
    fmt.end_section()

    fmt.start_section(_("Fetch all messages from `INBOX` folder that were delivered from the beginning of today (by server time), without changing any flags"))
    fmt.add_code(f'{__package__} fetch "${{common_mda[@]}}" --folder INBOX --any-seen --newer-than 0')
    fmt.end_section()

    fmt.start_section(_("Delete all `SEEN` messages older than 7 days from `INBOX` folder"))
    fmt.add_text("")
    fmt.add_text(_(f"Assuming you fetched and backed up all your messages already this allows you to keep as little as possible on the server, so that if your account gets cracked/hacked, you won't be as vulnerable."))
    fmt.add_code(f'{__package__} delete "${{common[@]}}" --folder INBOX --older-than 7')
    fmt.add_text(_("(`--seen` is implied by default)"))
    fmt.end_section()

    fmt.start_section(_("**DANGEROUS!** If you fetched and backed up all your messages already, you can skip `--older-than` and just delete all `SEEN` messages instead"))
    fmt.add_code(f'{__package__} delete "${{common[@]}}" --folder INBOX')
    fmt.add_text(_(f"Though, setting at least `--older-than 1`, to make sure you won't lose any data in case you forgot you are running another instance of `{__package__}` or another IMAP client that changes message flags (`{__package__}` will abort if it notices another client doing it, but better be safe than sorry), is highly recommended anyway."))
    fmt.end_section()

    fmt.start_section(_("Fetch everything GMail considers to be Spam for local filtering"))
    fmt.add_code(f"""# {_("setup: do once")}
mkdir -p ~/Mail/spam/{{new,cur,tmp}}

cat > ~/.mailfilter-spam << EOF
DEFAULT="\\$HOME/Mail/spam"
EOF

{__package__} mark "${{gmail_common[@]}}" --folder "[Gmail]/Spam" unseen

# {_("repeatable part")}
{__package__} fetch "${{gmail_common_mda[@]}}" --mda "maildrop ~/.mailfilter-spam" --folder "[Gmail]/Spam"
""")
    fmt.end_section()

    fmt.start_section(_("Fetch everything from all folders, except `INBOX`, `[Gmail]/Starred` (because in GMail there are included in `[Gmail]/All Mail`), and `[Gmail]/Trash`"))
    fmt.add_code(f"""{__package__} fetch "${{gmail_common_mda[@]}}" --all-folders \\
  --not-folder INBOX --not-folder "[Gmail]/Starred" --not-folder "[Gmail]/Trash"
""")
    fmt.add_text("The purpose of this is purely illustrative. In GMail all messages outside of `[Gmail]/Trash` and `[Gmail]/Spam` are included in `[Gmail]/All Mail` so you should probably just fetch that folder instead.")
    fmt.end_section()

    fmt.start_section(_("GMail-specific deletion mode: move (expire) old messages to `[Gmail]/Trash` and then delete them"))

    fmt.add_text("")
    fmt.add_text(_("In GMail, deleting messages from `INBOX` does not actually delete them, nor moves them to trash, just removes them from `INBOX` while keeping them available from `[Gmail]/All Mail`."))
    fmt.add_text(_("To work around this, this tool provides a GMail-specific `--method gmail-trash` that moves messages to `[Gmail]/Trash` in a GMail-specific way (this is not a repetition, it does require issuing special IMAP `STORE` commands to achieve this):"))
    fmt.add_code(f'{__package__} delete "${{gmail_common[@]}}" --folder "[Gmail]/All Mail" --older-than 7')
    fmt.add_text(_("(`--method gmail-trash` is implied by `--host imap.gmail.com` and `--folder` not being `[Gmail]/Trash`, `--seen` is still implied by default)"))

    fmt.add_text(_("Messages in `[Gmail]/Trash` will be automatically removed by GMail in 30 days, but you can also delete them immediately with:"))

    fmt.add_code(f'{__package__} delete "${{gmail_common[@]}}" --folder "[Gmail]/Trash" --any-seen --older-than 7')
    fmt.add_text(_("(`--method delete` is implied by `--host imap.gmail.com` but `--folder` being `[Gmail]/Trash`)"))
    fmt.end_section()

    fmt.start_section(_("Every hour, fetch messages from different folders using different MDA settings and then expire messages older than 7 days, all in a single pass (reusing the server connection between subcommands)"))
    fmt.add_code(f"""{__package__} for-each "${{gmail_common[@]}}" --every 3600 -- \\
  fetch --folder "[Gmail]/All Mail" --mda maildrop \\; \\
  fetch --folder "[Gmail]/Spam" --mda "maildrop ~/.mailfilter-spam" \\; \\
  delete --folder "[Gmail]/All Mail" --folder "[Gmail]/Spam" --folder "[Gmail]/Trash" \\
    --older-than 7
""")
    fmt.add_text(_("Note the `--` and `\\;` tokens, without them the above will fail to parse."))
    fmt.add_text(_("Also note that `delete` will use `--method gmail-trash` for `[Gmail]/All Mail` and `[Gmail]/Spam` and then use `--method delete` for `[Gmail]/Trash` even though they are specified together."))
    fmt.end_section()

class ArgumentParser(argparse.BetterArgumentParser):
    def error(self, message : str) -> _t.NoReturn:
        self.print_usage(sys.stderr)
        die(message, 2)

def make_argparser(real : bool = True) -> _t.Any:
    _ = gettext

    parser = ArgumentParser(
        prog=__package__,
        description=_("A handy Keep It Stupid Simple (KISS) Swiss-army-knife-like tool for fetching and performing batch operations on messages residing on IMAP servers.") + "\n" + \
                    _("Logins to a specified server, performs specified actions on all messages matching specified criteria in all specified folders, logs out."),
        additional_sections = [add_examples],
        allow_abbrev = False,
        add_version = True,
        add_help = False)
    parser.add_argument("-h", "--help", action="store_true", help=_("show this help message and exit"))
    parser.add_argument("--markdown", action="store_true", help=_("show help messages formatted in Markdown"))

    class EmitAccount(argparse.Action):
        def __init__(self, option_strings : str, dest : str, type : _t.Any = None, **kwargs : _t.Any) -> None:
            self.ptype = type
            super().__init__(option_strings, dest, type=str, **kwargs)

        def __call__(self, parser : _t.Any, cfg : Namespace, value : _t.Any, option_string : _t.Optional[str] = None) -> None:
            if cfg.host is None:
                die(_("`--host` is required"))

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
                die(_("`--user` is required"))

            user = cfg.user
            cfg.user = None

            allow_login = cfg.allow_login
            if cfg.socket == "plain":
                allow_login = allow_login and cfg.allow_plain

            if self.ptype == "pinentry":
                password = pinentry(host, user)
            elif self.ptype == "file":
                with open(value, "rb") as f:
                    password = f.readline().decode(defenc)
            elif self.ptype == "cmd":
                with subprocess.Popen(value, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True) as p:
                    p.stdin.close() # type: ignore
                    password = p.stdout.readline().decode(defenc) # type: ignore
                    retcode = p.wait()
                    if retcode != 0:
                        die(_("`--passcmd` (`%s`) failed with non-zero exit code %d") % (value, retcode))
            else:
                assert False

            if password[-1:] == "\n":
                password = password[:-1]
            if password[-1:] == "\r":
                password = password[:-1]

            cfg.accounts.append(Account(cfg.socket, host, port, user, password, allow_login, IMAP_base))

    def add_common(cmd : _t.Any) -> _t.Any:
        cmd.set_defaults(accounts = [])

        cmd.add_argument("-q", "--quieter", dest = "quiet", action="store_true", help=_("be less verbose"))

        agrp = cmd.add_argument_group(_("debugging"))
        agrp.add_argument("--very-dry-run", action="store_true", help=_("verbosely describe what the given command line would do and exit"))
        agrp.add_argument("--dry-run", action="store_true", help=_("perform a trial run without actually performing any changes"))
        agrp.add_argument("--debug", action="store_true", help=_("dump IMAP conversation to stderr"))

        agrp = cmd.add_argument_group(_("hooks"))
        agrp.add_argument("--notify-success", action="store_true", help=_(f"generate notification (via `notify-send`) describing changes on the server performed by `{__package__}`, if any, at the end of each program cycle; most useful if you run `{__package__}` in background with `--every` argument in a graphical environment"))
        agrp.add_argument("--success-cmd", metavar = "CMD", action = "append", type=str, default = [], help=_(f"shell command to run at the end of each program cycle that performed some changes on the server, i.e. a generalized version of `--notify-success`; the spawned process will receive the description of the performed changes via stdin; can be specified multiple times"))
        agrp.add_argument("--notify-failure", action="store_true", help=_(f"generate notification (via `notify-send`) describing recent failures, if any, at the end of each program cycle; most useful if you run `{__package__}` in background with `--every` argument in a graphical environment"))
        agrp.add_argument("--failure-cmd", metavar = "CMD", action = "append", type=str, default = [], help=_(f"shell command to run at the end of each program cycle that had some of its command fail, i.e. a generalized version of `--notify-failure`; the spawned process will receive the description of the failured via stdin; can be specified multiple times"))
        agrp.set_defaults(notify = False)

        agrp = cmd.add_argument_group(_("authentication settings"))
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--auth-allow-login", dest="allow_login", action="store_true", help=_("allow the use of IMAP `LOGIN` command (default)"))
        grp.add_argument("--auth-forbid-login", dest="allow_login", action="store_false", help=_("forbid the use of IMAP `LOGIN` command, fail if challenge-response authentication is not available"))
        grp.set_defaults(allow_login = True)

        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--auth-allow-plain", dest="allow_plain", action="store_true", help=_("allow passwords to be transmitted over the network in plain-text"))
        grp.add_argument("--auth-forbid-plain", dest="allow_plain", action="store_false", help=_("forbid passwords from being transmitted over the network in plain-text, plain-text authentication would still be possible over SSL if `--auth-allow-login` is set (default)"))
        grp.set_defaults(allow_plain = False)

        agrp = cmd.add_argument_group("server connection", description = _("can be specified multiple times"))
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--plain", dest="socket", action="store_const", const = "plain", help=_("connect via plain-text socket"))
        grp.add_argument("--ssl", dest="socket", action="store_const", const = "ssl", help=_("connect over SSL socket") + " " + _("(default)"))
        grp.add_argument("--starttls", dest="socket", action="store_const", const = "starttls", help=_("connect via plain-text socket, but then use STARTTLS command"))
        grp.set_defaults(socket = "ssl")

        agrp.add_argument("--host", type=str, help=_("IMAP server to connect to (required)"))
        agrp.add_argument("--port", type=int, help=_("port to use") + " " + _("(default: 143 for `--plain` and `--starttls`, 993 for `--ssl`)"))

        agrp = cmd.add_argument_group(_("authentication to the server"), description=_("either of `--pass-pinentry`, `--passfile`, or `--passcmd` are required; can be specified multiple times"))
        agrp.add_argument("--user", type=str, help=_("username on the server (required)"))

        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--pass-pinentry", nargs=0, action=EmitAccount, type="pinentry", help=_("read the password via `pinentry`"))
        grp.add_argument("--passfile", "--pass-file", action=EmitAccount, type="file", help=_("file containing the password on its first line"))
        grp.add_argument("--passcmd", "--pass-cmd", action=EmitAccount, type="cmd", help=_("shell command that returns the password as the first line of its stdout"))
        grp.set_defaults(password = None)

        agrp = cmd.add_argument_group(_("batching settings"), description=_("larger values improve performance but produce longer IMAP command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen"))
        agrp.add_argument("--store-number", metavar = "INT", type=int, default = 150, help=_("batch at most this many message UIDs in IMAP `STORE` requests (default: %(default)s)"))
        agrp.add_argument("--fetch-number", metavar = "INT", type=int, default = 150, help=_("batch at most this many message UIDs in IMAP `FETCH` metadata requests (default: %(default)s)"))
        agrp.add_argument("--batch-number", metavar = "INT", type=int, default = 150, help=_("batch at most this many message UIDs in IMAP `FETCH` data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: %(default)s)"))
        agrp.add_argument("--batch-size", metavar = "INT", type=int, default = 4 * 1024 * 1024, help=_(f"batch `FETCH` at most this many bytes of RFC822 messages at once; RFC822 messages larger than this will be fetched one by one (i.e. without batching); essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted while `{__package__}` is batching (default: %(default)s)"))

        agrp = cmd.add_argument_group("polling/daemon options")
        agrp.add_argument("--every", metavar = "SECONDS", type=int, help=_("repeat the command every `SECONDS` seconds if the whole cycle takes less than `SECONDS` seconds and `<cycle time>` seconds otherwise (with a minimum of `60` seconds either way)") + ";\n" + \
                                                                         _("i.e. it will do its best to repeat the command precisely every `SECONDS` seconds even if the command is `fetch` and fetching new messages and `--new-mail-cmd` take different time each cycle") + ";\n" + \
                                                                         _("this prevents the servers accessed earlier in the cycle from learning about the amount of new data fetched from the servers accessed later in the cycle"))
        agrp.add_argument("--every-add-random", metavar = "ADD", default = 60, type=int, help=_("sleep a random number of seconds in [0, ADD] range (uniform distribution) before each `--every` cycle (default: %(default)s)") + ";\n" + \
                                                                                             _("if you set it large enough to cover the longest single-server `fetch`, it will prevent any of the servers learning anything about the data on other servers") + ";\n" + \
                                                                                             _(f"if you run `{__package__}` on a machine that disconnects from the Internet when you go to sleep and you set it large enough, it will help in preventing the servers from collecting data about your sleep cycle"))
        return cmd

    def add_folders(cmd : _t.Any, all_by_default : _t.Optional[bool]) -> _t.Any:
        def_fall, def_freq = "", ""
        if all_by_default is None:
            def_freq = " " + _("(will be used as default for subcommands)")
        elif all_by_default:
            def_fall = " " + _("(default)")
        else:
            def_freq = " " + _("(required)")

        agrp = cmd.add_argument_group(_("folder search filters") + def_freq)

        egrp = agrp.add_mutually_exclusive_group(required = all_by_default == False)
        egrp.add_argument("--all-folders", action="store_true", default = all_by_default == True,
                          help=_("operate on all folders") + def_fall)
        egrp.add_argument("--folder", metavar = "NAME", dest="folders", action="append", type=str, default=[],
                          help=_("mail folders to include; can be specified multiple times"))

        agrp.add_argument("--not-folder", metavar = "NAME", dest="not_folders", action="append", type=str, default=[],
                          help=_("mail folders to exclude; can be specified multiple times"))
        return cmd

    def add_folders_sub(cmd : _t.Any) -> _t.Any:
        egrp = cmd.add_mutually_exclusive_group()
        egrp.add_argument("--all-folders", action="store_true", default = argparse.SUPPRESS)
        egrp.add_argument("--folder", metavar = "NAME", dest="folders", action="append", type=str, default=argparse.SUPPRESS)
        cmd.add_argument("--not-folder", metavar = "NAME", dest="not_folders", action="append", type=str, default=argparse.SUPPRESS)
        return cmd

    def add_common_filters(cmd : _t.Any) -> _t.Any:
        agrp = cmd.add_argument_group(_("message search filters"))
        agrp.add_argument("--older-than", metavar = "DAYS", action="append", default=[], type=int, help=_("operate on messages older than this many days, **the date will be rounded down to the start of the day; actual matching happens on the server, so all times are server time**; e.g. `--older-than 0` means older than the start of today by server time, `--older-than 1` means older than the start of yesterday, etc; can be specified multiple times, in which case the earliest (the most old) date on the list will be chosen"))
        agrp.add_argument("--newer-than", metavar = "DAYS", action="append", default=[], type=int, help=_("operate on messages newer than this many days, a negation of`--older-than`, so **everything from `--older-than` applies**; e.g., `--newer-than -1` will match files dated into the future, `--newer-than 0` will match files delivered from the beginning of today, etc; can be specified multiple times, in which case the latest (the least old) date on the list will be chosen"))

        agrp.add_argument("--older-than-timestamp-in", metavar = "PATH", action="append", default=[], type=str, help=_("operate on messages older than the timestamp (in seconds since UNIX Epoch) recorded on the first line of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above"))
        agrp.add_argument("--newer-than-timestamp-in", metavar = "PATH", action="append", default=[], type=str, help=_("operate on messages newer than the timestamp (in seconds since UNIX Epoch) recorded on the first line of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above"))

        agrp.add_argument("--older-than-mtime-of", metavar = "PATH", action="append", default=[], type=str, help=_("operate on messages older than `mtime` of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above"))
        agrp.add_argument("--newer-than-mtime-of", metavar = "PATH", action="append", default=[], type=str, help=_("operate on messages newer than `mtime` of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above"))

        agrp.add_argument("--from", dest="hfrom", metavar = "ADDRESS", action = "append", type=str, default = [], help=_("operate on messages that have this string as substring of their header's FROM field; can be specified multiple times"))
        agrp.add_argument("--not-from", dest="hnotfrom", metavar = "ADDRESS", action = "append", type=str, default = [], help=_("operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times"))
        return cmd

    def add_flag_filters(cmd : _t.Any, default : _t.Union[_t.Optional[bool], str]) -> _t.Any:
        def_mex = " " + _("(mutually exclusive)")
        def_str = " " + _("(default)")
        def_req = def_mex
        def_any, def_seen, def_unseen, def_flag = "", "", "", def_str
        if default is None:
            def_any = def_str
        elif default == True:
            def_seen = def_str
        elif default == False:
            def_unseen = def_str
        elif default == "depends":
            def_req = " " + _("(mutually exclusive, default: depends on other arguments)")
            def_flag = ""
        else:
            assert False

        agrp = cmd.add_argument_group(_("message IMAP `SEEN` flag filters") + def_req)

        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--any-seen", dest="seen", action="store_const", const = None, help=_("operate on both `SEEN` and not `SEEN` messages") + def_any)
        grp.add_argument("--seen", dest="seen", action="store_true", help=_("operate on messages marked as `SEEN`") + def_seen)
        grp.add_argument("--unseen", dest="seen", action="store_false", help=_("operate on messages not marked as `SEEN`") + def_unseen)
        grp.set_defaults(seen = default)

        agrp = cmd.add_argument_group(_("message IMAP `FLAGGED` flag filters") + def_req)
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--any-flagged", dest="flagged", action="store_const", const = None, help=_("operate on both `FLAGGED` and not `FLAGGED` messages") + def_flag)
        grp.add_argument("--flagged", dest="flagged", action="store_true", help=_("operate on messages marked as `FLAGGED`"))
        grp.add_argument("--unflagged", dest="flagged", action="store_false", help=_("operate on messages not marked as `FLAGGED`"))
        grp.set_defaults(flagged = None)
        return cmd

    def add_delivery(cmd : _t.Any) -> _t.Any:
        agrp = cmd.add_argument_group(_("delivery target (required, mutually exclusive)"))
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--maildir", metavar = "DIRECTORY", type=str,
                         help=_("Maildir to deliver the messages to;") + "\n" + \
                              _(f"with this specified `{__package__}` will simply drop raw RFC822 messages, one message per file, into `DIRECTORY/new` (creating it, `DIRECTORY/cur`, and `DIRECTORY/tmp` if any of those do not exists)"))
        grp.add_argument("--mda", dest="mda", metavar = "COMMAND", type=str,
                         help=_("shell command to use as an MDA to deliver the messages to;") + "\n" + \
                              _(f"with this specified `{__package__}` will spawn `COMMAND` via the shell and then feed raw RFC822 message into its `stdin`, the resulting process is then responsible for delivering the message to `mbox`, `Maildir`, etc;") + "\n" + \
                              _("`maildrop` from Courier Mail Server project is a good KISS default"))

        agrp = cmd.add_argument_group(_("delivery mode (mutually exclusive)"))
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--yolo", dest="paranoid", action="store_const", const = None, help=_(f"messages that fail to be delivered into the `--maildir` or by the `--mda` are left un`--mark`ed on the server but no other messages get affected, current `{__package__} fetch` continues as if nothing is amiss"))
        grp.add_argument("--careful", dest="paranoid", action="store_false", help=_(f"messages that fail to be delivered into the `--maildir` or by the `--mda` are left un`--mark`ed on the server but no other messages get affected, `{__package__}` aborts currently running `fetch` if zero messages from the current batch get delivered as that usually means that the target file system is out of space, read-only, or generates IO errors (default)"))
        grp.add_argument("--paranoid", dest="paranoid", action="store_true", help=_(f"`{__package__}` aborts the process immediately if any of the messages in the current batch fail to be delivered into the `--maildir` or by the `--mda`, the whole batch gets left un`--mark`ed on the server"))
        grp.set_defaults(paranoid = False)

        agrp = cmd.add_argument_group(_("hooks"))
        agrp.add_argument("--new-mail-cmd", metavar="CMD", action = "append", type=str, default = [], help=_("shell command to run at the end of each program cycle that had new messages successfully delivered into the `--maildir` or by the `--mda` of this `fetch` subcommand; can be specified multiple times"))
        return cmd

    def no_cmd(cfg : Namespace, state : State) -> None:
        parser.print_help(sys.stderr)
        sys.exit(2)
    parser.set_defaults(func=no_cmd)

    if not real:
        add_common(parser)
        add_common_filters(parser)

    subparsers = parser.add_subparsers(title="subcommands")

    cmd = subparsers.add_parser("list", help=_("list all available folders on the server, one per line"),
                                description = _("Login, perform IMAP `LIST` command to get all folders, print them one per line."))
    if real: add_common(cmd)
    cmd.set_defaults(command="list")
    cmd.set_defaults(func=cmd_list)

    cmd = subparsers.add_parser("count", help=_("count how many matching messages each specified folder has"),
                                description = _("Login, (optionally) perform IMAP `LIST` command to get all folders, perform IMAP `SEARCH` command with specified filters in each folder, print message counts for each folder one per line."))
    if real: add_common(cmd)
    add_folders(cmd, True)
    def add_count(cmd : _t.Any) -> _t.Any:
        cmd.set_defaults(command="count")
        if real: add_common_filters(cmd)
        add_flag_filters(cmd, None)
        cmd.add_argument("--porcelain", action="store_true", help=_("print in a machine-readable format"))
        return cmd
    add_count(cmd)
    cmd.set_defaults(func=cmd_action)

    cmd = subparsers.add_parser("mark", help=_("mark matching messages in specified folders in a specified way"),
                                description = _("Login, perform IMAP `SEARCH` command with specified filters for each folder, mark resulting messages in specified way by issuing IMAP `STORE` commands."))
    if real: add_common(cmd)
    add_folders(cmd, False)
    def add_mark(cmd : _t.Any) -> _t.Any:
        cmd.set_defaults(command="mark")
        if real: add_common_filters(cmd)
        add_flag_filters(cmd, "depends")
        agrp = cmd.add_argument_group("marking")
        sets_x_if = _("sets `%s` if no message flag filter is specified")
        agrp.add_argument("mark", choices=["seen", "unseen", "flagged", "unflagged"], help=_("mark how") + " " + _("(required)") + f""":
- `seen`: {_("add `SEEN` flag")}, {sets_x_if % ("--unseen",)}
- `unseen`: {_("remove `SEEN` flag")}, {sets_x_if % ("--seen",)}
- `flag`: {_("add `FLAGGED` flag")}, {sets_x_if % ("--unflagged",)}
- `unflag`: {_("remove `FLAGGED` flag")}, {sets_x_if % ("--flagged",)}
""")
        return cmd
    add_mark(cmd)
    cmd.set_defaults(func=cmd_action)

    cmd = subparsers.add_parser("fetch", help=_("fetch matching messages from specified folders, feed them to an MDA, and then mark them in a specified way if MDA succeeds"),
                                description = _("Login, perform IMAP `SEARCH` command with specified filters for each folder, fetch resulting messages in (configurable) batches, feed each batch of messages to an MDA, mark each message for which MDA succeeded in a specified way by issuing IMAP `STORE` commands."))
    if real: add_common(cmd)
    add_folders(cmd, True)
    def add_fetch(cmd : _t.Any) -> _t.Any:
        cmd.set_defaults(command="fetch")
        add_delivery(cmd)
        if real: add_common_filters(cmd)
        add_flag_filters(cmd, False)
        agrp = cmd.add_argument_group("marking")
        agrp.add_argument("--mark", choices=["auto", "noop", "seen", "unseen", "flagged", "unflagged"], default = "auto", help=_("after the message was fetched") + f""":
- `auto`: {_('`seen` when only `--unseen` is set (default), `flagged` when only `--unflagged` is set, `noop` otherwise')}
- `noop`: {_("do nothing")}
- `seen`: {_("add `SEEN` flag")}
- `unseen`: {_("remove `SEEN` flag")}
- `flagged`: {_("add `FLAGGED` flag")}
- `unflagged`: {_("remove `FLAGGED` flag")}
""")
        return cmd
    add_fetch(cmd)
    cmd.set_defaults(func=cmd_action)

    cmd = subparsers.add_parser("delete", help=_("delete matching messages from specified folders"),
                                description = _("Login, perform IMAP `SEARCH` command with specified filters for each folder, delete them from the server using a specified method."))
    if real: add_common(cmd)
    add_folders(cmd, False)
    def add_delete(cmd : _t.Any) -> _t.Any:
        cmd.set_defaults(command="delete")
        if real: add_common_filters(cmd)
        add_flag_filters(cmd, True)
        agrp = cmd.add_argument_group(_("deletion method"))
        agrp.add_argument("--method", choices=["auto", "delete", "delete-noexpunge", "gmail-trash"], default="auto", help=_("delete messages how") + f""":
- `auto`: {_('`gmail-trash` when `--host imap.gmail.com` and the current folder is not `[Gmail]/Trash`, `delete` otherwise')} {_("(default)")}
- `delete`: {_('mark messages as deleted and then use IMAP `EXPUNGE` command, i.e. this does what you would expect a "delete" command to do, works for most IMAP servers')}
- `delete-noexpunge`: {_('mark messages as deleted but skip issuing IMAP `EXPUNGE` command hoping the server does as RFC2060 says and auto-`EXPUNGE`s messages on IMAP `CLOSE`; this is much faster than `delete` but some servers (like GMail) fail to implement this properly')}
- `gmail-trash`: {_(f'move messages to `[Gmail]/Trash` in GMail-specific way instead of trying to delete them immediately (GMail ignores IMAP `Deleted` flag and `EXPUNGE` command outside of `[Gmail]/Trash`); you can then `{__package__} delete --folder "[Gmail]/Trash"` them after (which will default to `--method delete`), or you could just leave them there and GMail will delete them in 30 days')}
""")
        return cmd
    add_delete(cmd)
    cmd.set_defaults(func=cmd_action)

    def cmd_for_each(cfg : Namespace, state : State) -> None:
        # generate parser for our cfg
        fe_parser = argparse.BetterArgumentParser(prog = __package__ + " for-each", add_help = True)

        # we do this to force the user to specify `--folder` or such
        # for each command if the global one is not specified
        add_folders_here = add_folders_sub
        if not cfg.all_folders and len(cfg.folders) == 0:
            add_folders_here = lambda x: add_folders(x, False)

        fe_subparsers = fe_parser.add_subparsers(title="subcommands")
        add_count(fe_subparsers.add_parser("count"))
        add_folders_here(add_mark(fe_subparsers.add_parser("mark")))
        add_folders_here(add_fetch(fe_subparsers.add_parser("fetch")))
        add_folders_here(add_delete(fe_subparsers.add_parser("delete")))

        # set defaults from cfg
        fe_parser.set_defaults(**{name: value for name, value in cfg.__dict__.items() if name != "rest"})

        # split command line by ";" tokens
        commands = []
        acc = []
        for a in cfg.rest:
            if a != ";":
                acc.append(a)
            else:
                if len(acc) > 0:
                    commands.append(acc)
                    acc = []
        if len(acc) > 0:
            commands.append(acc)
        del acc

        # parse each command
        subcfgs = []
        for cargv in commands:
            subcfg = fe_parser.parse_args(cargv)
            subcfgs.append(subcfg)

        # run them
        cmd_multi_action(cfg, state, subcfgs)

    cmd = subparsers.add_parser("for-each", help=_("perform multiple other subcommands, sequentially, on a single server connection"),
                                description = _("""For each account: login, perform other subcommands given in `ARG`s, logout.

This is most useful for performing complex changes `--every` once in while in daemon mode.
Or if you want to set different `--folder`s for different subcommands but run them all at once.

Except for the simplest of cases, you must use `--` before `ARG`s so that any options specified in `ARG`s won't be picked up by `for-each`.
Run with `--very-dry-run` to see the interpretation of the given command line.

All generated hooks are deduplicated and run after all other subcommands are done.
E.g., if you have several `fetch --new-mail-cmd filter-my-mail` as subcommands of `for-each`, then `filter-my-mail` *will be run **once** after all other subcommands finish*.
"""))
    if real: add_common(cmd)
    add_folders(cmd, None)
    cmd.add_argument("rest", metavar="ARG", nargs="+", type=str, help=_("arguments, these will be split by `;` and parsed into other subcommands"))
    cmd.set_defaults(func=cmd_for_each)

    return parser

def main() -> None:
    _ = gettext

    parser = make_argparser()

    try:
        cfg = parser.parse_args(sys.argv[1:])
    except CatastrophicFailure as exc:
        error(str(exc))
        sys.exit(1)

    if cfg.help:
        if cfg.markdown:
            parser = make_argparser(False)
            parser.set_formatter_class(argparse.MarkdownBetterHelpFormatter)
            print(parser.format_help(1024))
        else:
            print(parser.format_help())
        sys.exit(0)

    state = State()

    handle_signals()

    try:
        cfg.func(cfg, state)
    except KeyboardInterrupt:
        state.num_errors += 1
        error(_("Interrupted!"))
    except CatastrophicFailure as exc:
        state.num_errors += 1
        notify_error(cfg, str(exc))
    except Exception as exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__, 100, sys.stderr)
        state.num_errors += 1
        notify_error(cfg, _("A bug!"))

    if state.num_errors > 0:
        error(ngettext("There was %d error!", "There were %d errors!", state.num_errors) % (state.num_errors,))
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
