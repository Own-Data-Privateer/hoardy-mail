#!/usr/bin/env python3
#
# This file is a part of `hoardy-mail` project.
#
# Copyright (c) 2023-2024 Jan Malakhovski <oxij@oxij.org>
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

"""`main()`."""

import dataclasses as _dc
import decimal
import fcntl as _fcntl
import hashlib as _hashlib
import os
import random
import signal as _signal
import socket as _socket
import ssl
import subprocess
import sys as _sys
import time
import typing as _t

from imaplib import IMAP4, IMAP4_SSL
from gettext import gettext, ngettext

from kisstdlib import *
from kisstdlib import argparse_ext as argparse
from kisstdlib.argparse_ext import Namespace
from kisstdlib.getpass_ext import getpass_pinentry

__prog__ = "hoardy-mail"
defenc = _sys.getdefaultencoding()
myhostname = _socket.gethostname()
smypid = str(os.getpid())


def imap_parse_data(  # pylint: disable=dangerous-default-value
    data: bytes,
    literals: _t.List[bytes] = [],
    top_level: bool = True,
) -> _t.Tuple[_t.Any, bytes]:
    "Parse IMAP response string into a tree of strings."
    acc: _t.List[bytes] = []
    res = b""
    i = 0
    state = False
    while i < len(data):
        c = data[i : i + 1]
        # print(c)
        if state is False:
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
                res, data = imap_parse_data(data[i + 1 :], literals, False)
                acc.append(res)
                res = b""
                i = 0
                if len(data) == 0:
                    return acc, b""
                if data[i : i + 1] not in [b" ", b")"]:
                    raise ValueError("expecting space or end parens")
            elif c == b")":
                acc.append(res)
                return acc, data[i + 1 :]
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
                if data[i : i + 1] not in [b" ", b")"]:
                    raise ValueError("expecting space or end parens")
            else:
                if not isinstance(res, bytes):
                    raise ValueError("unexpected char")
                res += c
        elif state is True:
            if c == b'"':
                state = False
            elif c == b"\\":
                i += 1
                if i >= len(data):
                    raise ValueError("unfinished escape sequence")
                res += data[i : i + 1]
            else:
                res += c
        i += 1
    if res != b"":
        if state or not top_level:
            raise ValueError("unfinished quote or parens")
        acc.append(res)
    return acc, b""


def imap_parse(  # pylint: disable=dangerous-default-value
    line: bytes, literals: _t.List[bytes] = []
) -> _t.Any:
    res, rest = imap_parse_data(line, literals)
    if rest != b"":
        raise ValueError("unexpected tail", rest)
    return res


def imap_parse_attrs(data: _t.List[bytes]) -> _t.Dict[bytes, bytes]:
    if len(data) % 2 != 0:
        raise ValueError("data array of non-even length")

    res = {}
    for i in range(0, len(data), 2):
        name = data[i].upper()
        value = data[i + 1]
        res[name] = value
    return res


def test_imap_parse() -> None:
    assert imap_parse(b"(1 2 3)") == [[b"1", b"2", b"3"]]
    assert imap_parse(b"(0 1) (1 2 3)") == [[b"0", b"1"], [b"1", b"2", b"3"]]
    assert imap_parse(b"(0 1) ((1 2 3))") == [[b"0", b"1"], [[b"1", b"2", b"3"]]]
    assert imap_parse(b"(0 1) ((1 2 3) )") == [[b"0", b"1"], [[b"1", b"2", b"3"], b""]]
    assert imap_parse(b'(\\Trash \\Nya) "." "All Mail"') == [
        [b"\\Trash", b"\\Nya"],
        b".",
        b"All Mail",
    ]
    assert imap_parse(b'(\\Trash \\Nya) "." "All\\"Mail"') == [
        [b"\\Trash", b"\\Nya"],
        b".",
        b'All"Mail',
    ]
    assert imap_parse(b'1 2 3 4 "\\\\Nya" 5 6 7') == [
        b"1",
        b"2",
        b"3",
        b"4",
        b"\\Nya",
        b"5",
        b"6",
        b"7",
    ]
    assert imap_parse(b'(1 2 3) 4 "\\\\Nya" 5 6 7') == [
        [b"1", b"2", b"3"],
        b"4",
        b"\\Nya",
        b"5",
        b"6",
        b"7",
    ]
    assert imap_parse(b"1 (UID 123 RFC822.SIZE 128)") == [
        b"1",
        [b"UID", b"123", b"RFC822.SIZE", b"128"],
    ]
    val = imap_parse(b"UID 123 BODY[HEADER] {128}", [b"128bytesofdata"])
    assert val == [b"UID", b"123", b"BODY[HEADER]", b"128bytesofdata"]
    assert imap_parse(b"1 (UID 123 BODY[HEADER] {128})", [b"128bytesofdata"]) == [b"1", val]
    assert imap_parse_attrs(val) == {
        b"UID": b"123",
        b"BODY[HEADER]": b"128bytesofdata",
    }


def imap_quote(arg: str) -> str:
    arg = arg[:]
    arg = arg.replace("\\", "\\\\")
    arg = arg.replace('"', '\\"')
    return '"' + arg + '"'


imap_months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]  # fmt: skip


def imap_date(date: time.struct_time) -> str:
    return f"{str(date.tm_mday)}-{imap_months[date.tm_mon-1]}-{str(date.tm_year)}"


def make_search_filter(cfg: Namespace, now: int) -> _t.Tuple[str, bool]:
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
        filters.append(f"FROM {imap_quote(f)}")

    for f in cfg.hnotfrom:
        filters.append(f"NOT FROM {imap_quote(f)}")

    def read_timestamp(path: str) -> int:
        with open(path, "rb") as f:
            try:
                data = f.readline().decode(defenc).strip()
                # converting via Decimal to preserve all 9 digits after the dot
                return int(decimal.Decimal(data) * 10**9)
            except Exception as exc:
                raise Failure(
                    "failed to decode a timestamp from the first line of %s", path
                ) from exc

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

    return "(" + " ".join(filters) + ")", dynamic


def ignored_exception(exc: BaseException) -> None:
    warning(gettext("Ignored exception: %s"), str(exc), exc_info=exc)


def uncaught_exception(exc: BaseException) -> None:
    warning(gettext("Uncaught exception: %s"), str(exc), exc_info=exc)


def run_hook(hook: str) -> None:
    try:
        with subprocess.Popen(hook, shell=True) as _p:
            # __exit__ will do everything we need
            pass
    except Exception as exc:
        ignored_exception(exc)


def run_hook_stdin(hook: str, data: bytes) -> None:
    try:
        with subprocess.Popen(hook, stdin=subprocess.PIPE, shell=True) as p:
            fd: _t.Any = p.stdin
            fd.write(data)
            fd.flush()
            fd.close()
    except Exception as exc:
        ignored_exception(exc)


def notify_send(typ: str, title: str, body: str) -> None:
    try:
        with subprocess.Popen(
            ["notify-send", "-a", "hoardy-mail", "-i", typ, "--", title, body]
        ) as _p:
            pass
    except Exception as exc:
        ignored_exception(exc)


def notify_success(cfg: Namespace, title: str, body: str) -> None:
    if cfg.notify_success:
        notify_send("info", title, body)

    for cmd in cfg.success_cmd:
        run_hook_stdin(cmd, title.encode(defenc) + b"\n" + body.encode(defenc) + b"\n")


def notify_failure(cfg: Namespace, title: str, body: str) -> None:
    if cfg.notify_failure:
        notify_send("error", title, body)

    for cmd in cfg.failure_cmd:
        run_hook_stdin(cmd, title.encode(defenc) + b"\n" + body.encode(defenc) + b"\n")


class AccountFailure(Failure):
    pass


class AccountSoftFailure(AccountFailure):
    pass


class FolderFailure(AccountFailure):
    pass


def format_imap_error(command: str, typ: str, data: _t.Any = None) -> _t.Any:
    if data is None:
        return gettext("IMAP %s command failed: %s") % (command, typ)
    return gettext("IMAP %s command failed: %s %s") % (command, typ, repr(data))


def imap_exc(exc: _t.Any, command: str, typ: str, data: _t.Any) -> _t.Any:
    return exc(format_imap_error(command, typ, data))


def imap_check(exc: _t.Any, command: str, v: _t.Tuple[str, _t.Any]) -> _t.Any:
    typ, data = v
    if typ != "OK":
        raise imap_exc(exc, command, typ, data)
    return data


@_dc.dataclass
class Account:
    socket: str
    timeout: int
    host: str
    port: int
    user: str
    password: str
    allow_login: bool
    IMAP_base: type

    num_delivered: int = _dc.field(default=0)
    num_undelivered: int = _dc.field(default=0)
    num_marked: int = _dc.field(default=0)
    num_trashed: int = _dc.field(default=0)
    num_deleted: int = _dc.field(default=0)
    changes: _t.List[str] = _dc.field(default_factory=list)
    errors: _t.List[str] = _dc.field(default_factory=list)

    def reset(self) -> None:
        self.num_delivered = 0
        self.num_undelivered = 0
        self.num_marked = 0
        self.num_trashed = 0
        self.num_deleted = 0
        self.changes = []
        self.errors = []


def account_error(account: Account, pattern: str, *args: _t.Any, exc_info: bool = False) -> None:
    message = pattern % args
    account.errors.append(message)
    error("%s", message, exc_info=exc_info)


def account_conflict(account: Account, attrs: _t.Dict[bytes, bytes]) -> None:
    account_error(
        account,
        gettext(
            "another IMAP client is performing potentially conflicting actions in parallel with us: %s"
        ),
        repr(attrs),
    )
    # we simply print this error and continue because `delete` command will do
    # nothing if `account.errors` is not empty


def connect(account: Account, debugging: bool) -> _t.Any:
    if debugging:

        class IMAP(account.IMAP_base):  # type: ignore
            def send(self, data: bytes) -> int:
                stderr.write(b"C: " + data)
                stderr.flush()
                return super().send(data)  # type: ignore

            def read(self, size: int) -> bytes:
                res = super().read(size)
                stderr.write(b"S: " + res)
                stderr.flush()
                return res  # type: ignore

            def readline(self) -> bytes:
                res = super().readline()
                stderr.write(b"S: " + res)
                stderr.flush()
                return res  # type: ignore

    else:
        IMAP = account.IMAP_base  # type: ignore

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True
    ssl_context.load_default_certs()

    _socket.setdefaulttimeout(account.timeout)

    try:
        if account.socket == "ssl":
            srv = IMAP(account.host, account.port, ssl_context=ssl_context)
        else:
            srv = IMAP(account.host, account.port)
            if account.socket == "starttls":
                srv.starttls(ssl_context)
    except Exception as exc:
        raise AccountFailure(
            "failed to connect to host %s port %s: %s",
            account.host,
            account.port,
            repr(exc),
        ) from exc

    return srv


@_dc.dataclass
class State:
    pending_hooks: _t.List[str] = _dc.field(default_factory=list)


def for_each_account_poll(cfg: Namespace, state: State, *args: _t.Any) -> None:
    if cfg.every is None:
        for_each_account(cfg, state, *args)
        return

    fmt = "[%Y-%m-%d %H:%M:%S]"
    every = cfg.every

    def do_sleep(ttime: str) -> None:
        raise_delayed_signals()

        printf(
            "# "
            + gettext(
                "sleeping until %s, send SIGUSR1 to PID %s or hit ^C to start immediately, hit ^C twice to abort"
            ),
            ttime,
            smypid,
        )

        try:
            soft_sleep(to_sleep, verbose="")
        except SignalInterrupt as exc:
            if exc.signum != _signal.SIGINT:
                raise

        printf(
            gettext("starting in a little bit, last chance to abort..."),
            end="",
            color=ANSIColor.YELLOW,
        )

        with yes_signals():
            for i in range(3, 0, -1):
                stdout.write_str(f" {i}...", color=ANSIColor.YELLOW)
                stdout.flush()
                sleep(1)
            stdout.write_str_ln("")
            stdout.flush()

    to_sleep = random.randint(0, cfg.every_add_random)
    if to_sleep > 0:
        now = time.time()
        ttime = time.strftime(fmt, time.localtime(now + to_sleep))
        do_sleep(ttime)

    while True:
        now = time.time()
        repeat_at = now + every
        ftime = time.strftime(fmt, time.localtime(now))
        if not cfg.quiet:
            printf("# " + gettext("poll: starting at %s"), ftime)

        for_each_account(cfg, state, *args)

        now = time.time()
        ntime = time.strftime(fmt, time.localtime(now))

        if not cfg.quiet:
            printf("# " + gettext("poll: finished at %s"), ntime)

        to_sleep = max(60, repeat_at - now + random.randint(0, cfg.every_add_random))
        ttime = time.strftime(fmt, time.localtime(now + to_sleep))
        do_sleep(ttime)


def for_each_account(
    cfg: Namespace, state: State, func: _t.Callable[..., None], *args: _t.Any
) -> None:
    num_delivered = 0
    num_marked = 0
    num_trashed = 0
    num_deleted = 0
    num_undelivered = 0
    num_errors = 0
    changes = []
    errors = []

    account: Account
    for account in cfg.accounts:
        raise_delayed_signals()

        account.reset()

        try:
            srv = connect(account, cfg.debugging)

            do_logout = True
            try:
                data = imap_check(AccountFailure, "CAPABILITY", srv.capability())
                try:
                    capabilities = data[0].decode("ascii").split(" ")
                    if "IMAP4rev1" not in capabilities:
                        raise ValueError()
                except (UnicodeDecodeError, KeyError, ValueError) as exc:
                    raise AccountFailure(
                        "host %s port %s does not speak IMAP4rev1, your IMAP server appears to be too old",
                        cfg.host,
                        cfg.port,
                    ) from exc

                # print(capabilities)

                method: str
                if "AUTH=CRAM-MD5" in capabilities:

                    def do_cram_md5(challenge: bytes) -> str:
                        import hmac

                        pwd = account.password.encode("utf-8")  # pylint: disable=cell-var-from-loop
                        return (
                            imap_quote(account.user)  # pylint: disable=cell-var-from-loop
                            + " "
                            + hmac.HMAC(pwd, challenge, "md5").hexdigest()
                        )

                    method = "AUTHENTICATE CRAM-MD5"
                    typ, data = srv.authenticate("CRAM-MD5", do_cram_md5)
                elif account.allow_login:
                    method = "LOGIN PLAIN"
                    typ, data = srv._simple_command(  # pylint: disable=protected-access
                        "LOGIN", imap_quote(account.user), imap_quote(account.password)
                    )
                else:
                    raise AccountFailure(
                        "authentication with plain-text credentials is disabled, set both `--auth-allow-login` and `--auth-allow-plain` if you really want to do this"
                    )

                if typ != "OK":
                    raise AccountFailure(
                        "failed to login (%s) as %s to host %s port %d: %s",
                        method,
                        account.user,
                        account.host,
                        account.port,
                        repr(data),
                    )
                srv.state = "AUTH"  # pylint: disable=attribute-defined-outside-init

                printf(
                    "# " + gettext("logged in (%s) as %s to host %s port %d (%s)"),
                    method,
                    account.user,
                    account.host,
                    account.port,
                    account.socket.upper(),
                )

                func(cfg, state, account, srv, *args)
            except AccountSoftFailure as exc:
                account_error(account, "%s", exc.get_message(gettext))
            except BaseException:
                do_logout = False
                raise
            finally:
                if do_logout:
                    try:
                        srv.logout()
                    except Exception:
                        pass
                else:
                    srv.shutdown()
                srv = None
        except AccountFailure as exc:
            account_error(account, "%s", exc.get_message(gettext))
        except IMAP4.abort as exc:
            account_error(account, "%s", "imaplib: " + str(exc))
        except OSError as exc:
            account_error(
                account,
                gettext("unexpected failure while working with host %s port %s: %s"),
                account.host,
                account.port,
                str(exc),
                exc_info=True,
            )
        finally:
            num_delivered += account.num_delivered
            num_marked += account.num_marked
            num_trashed += account.num_trashed
            num_deleted += account.num_deleted
            num_undelivered += account.num_undelivered
            num_errors += len(account.errors)
            if len(account.changes) > 0:
                changes.append(
                    gettext("%s on %s:") % (account.user, account.host)
                    + "\n- "
                    + "\n- ".join(account.changes)
                )
            if len(account.errors) > 0:
                errors.append(
                    gettext("%s on %s:") % (account.user, account.host)
                    + "\n- "
                    + "\n- ".join(account.errors)
                )

    if len(state.pending_hooks) > 0:
        for hook in state.pending_hooks:
            printf("# " + gettext("running `%s`"), hook)
            run_hook(hook)
        state.pending_hooks = []

    good = []
    if num_delivered > 0:
        good.append(
            ngettext("fetched %d new message", "fetched %d new messages", num_delivered)
            % (num_delivered,)
        )
    if num_marked > 0:
        good.append(ngettext("marked %d message", "marked %d messages", num_marked) % (num_marked,))
    if num_trashed > 0:
        good.append(
            ngettext("trashed %d message", "trashed %d messages", num_trashed) % (num_trashed,)
        )
    if num_deleted > 0:
        good.append(
            ngettext("deleted %d message", "deleted %d messages", num_deleted) % (num_deleted,)
        )

    bad = []
    if num_undelivered > 0:
        bad.append(
            ngettext(
                "failed to fetch %d message",
                "failed to fetch %d messages",
                num_undelivered,
            )
            % (num_undelivered,)
        )
    if num_errors > 0:
        bad.append(
            ngettext("produced %d new error", "produced %d new errors", num_errors) % (num_errors,)
        )

    if len(good) > 0:
        good_actions = gettext(", ").join(good)
        if not cfg.quiet:
            printf("# " + gettext("poll: %s"), good_actions)
        notify_success(cfg, good_actions, "\n".join(changes))

    if len(bad) > 0:
        bad_actions = gettext(", ").join(bad)
        printf_err("# " + gettext("poll: %s"), bad_actions, color=ANSIColor.RED)
        notify_failure(cfg, bad_actions, "\n".join(errors))


def check_cmd(cfg: Namespace) -> None:
    if len(cfg.accounts) == 0:
        raise CatastrophicFailure(
            "no accounts are specified, need at least one `--host`, `--user`, and either of `--passfile` or `--passcmd`"
        )

    if cfg.command == "fetch" and cfg.maildir is None and cfg.mda is None:
        raise CatastrophicFailure(
            "no delivery method is specified, either `--maildir` or `--mda` is required"
        )


def cmd_list(cfg: Namespace, state: State) -> None:
    check_cmd(cfg)

    if cfg.very_dry_run:
        _sys.exit(1)

    for_each_account_poll(cfg, state, do_list)


def do_list(_cfg: Namespace, _state: State, _account: Account, srv: IMAP4) -> None:
    folders = get_folders(srv)
    for e in folders:
        print(e)


def get_folders(srv: IMAP4) -> _t.List[str]:
    res = []
    data = imap_check(AccountFailure, "LIST", srv.list())
    for el in data:
        tags, _, arg = imap_parse(el)  # pylint: disable=unbalanced-tuple-unpacking
        if b"\\Noselect" in tags:
            continue
        res.append(arg.decode("utf-8"))
    return res


def print_prelude(cfg: Namespace) -> None:
    if cfg.quiet:
        return

    _ = gettext
    if cfg.every is not None:
        printf("# " + _("every %d seconds, for each of"), cfg.every)
    else:
        printf("# " + _("for each of"))
    for acc in cfg.accounts:
        printf(
            "... " + _("user %s on host %s port %d (%s)"),
            acc.user,
            acc.host,
            acc.port,
            acc.socket.upper(),
        )
    printf("# " + _("do"))


def prepare_cmd(cfg: Namespace, now: int) -> str:
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
            if cfg.seen is False and cfg.flagged is None:
                cfg.mark = "seen"
            elif cfg.seen is None and cfg.flagged is False:
                cfg.mark = "flagged"
            else:
                cfg.mark = "noop"

    if len(cfg.folders) != 0:
        cfg.all_folders = False

    if cfg.all_folders:
        place = gettext("in all folders")
    else:
        place = gettext("in %s") % (gettext(", ").join(map(repr, cfg.folders)),)

    if cfg.not_folders:
        place += " " + gettext("excluding %s") % (gettext(", ").join(map(repr, cfg.not_folders)),)

    search_filter, dynamic = make_search_filter(cfg, now)
    sf = search_filter
    if cfg.every is not None and dynamic:
        sf += " " + gettext("{dynamic}")

    if "mark" in cfg:
        what = gettext(f"search %s, perform {cfg.command}, mark them as %s") % (
            sf,
            cfg.mark.upper(),
        )
    else:
        what = gettext(f"search %s, perform {cfg.command}") % (sf,)

    if not cfg.quiet:
        printf("... %s: %s", place, what)

    return search_filter


def cmd_action(cfg: Namespace, state: State) -> None:
    check_cmd(cfg)
    print_prelude(cfg)
    now = time.time_ns()
    cfg.search_filter = prepare_cmd(cfg, now)

    if cfg.very_dry_run:
        _sys.exit(1)

    for_each_account_poll(cfg, state, for_each_folder_multi, [cfg])


def cmd_multi_action(common_cfg: Namespace, state: State, subcfgs: _t.List[Namespace]) -> None:
    print_prelude(common_cfg)
    now = time.time_ns()
    for subcfg in subcfgs:
        subcfg.search_filter = prepare_cmd(subcfg, now)

    if common_cfg.very_dry_run:
        _sys.exit(1)

    for_each_account_poll(common_cfg, state, for_each_folder_multi, subcfgs)


def for_each_folder_multi(
    common_cfg: Namespace, state: State, account: Account, srv: IMAP4, subcfgs: _t.List[Namespace]
) -> None:
    if common_cfg.every is not None:
        now = time.time_ns()
        for subcfg in subcfgs:
            subcfg.search_filter, _ = make_search_filter(subcfg, now)

    for subcfg in subcfgs:
        for_each_folder_(subcfg, state, account, srv, do_folder_action, subcfg.command)


def for_each_folder_(
    cfg: Namespace,
    state: State,
    account: Account,
    srv: IMAP4,
    func: _t.Callable[..., None],
    *args: _t.Any,
) -> None:
    if cfg.all_folders:
        folders = get_folders(srv)
    else:
        folders = cfg.folders

    for folder in filter(lambda f: f not in cfg.not_folders, folders):
        raise_delayed_signals()

        typ, data = srv.select(imap_quote(folder))
        if typ != "OK":
            account_error(account, "%s", format_imap_error("SELECT", typ, data))
            continue

        try:
            func(cfg, state, account, srv, folder, *args)
        except FolderFailure as exc:
            account_error(account, "%s", exc.get_message(gettext))

        srv.close()


def do_folder_action(
    cfg: Namespace, state: State, account: Account, srv: IMAP4, folder: str, command: str
) -> None:

    typ, data = srv.uid("SEARCH", cfg.search_filter)
    if typ != "OK":
        raise imap_exc(FolderFailure, "SEARCH", typ, data)

    result: _t.Optional[bytes] = data[0]
    if result is None:
        raise imap_exc(FolderFailure, "SEARCH", typ, data)
    if result == b"":
        message_uids = []
    else:
        message_uids = result.split(b" ")
    num_messages = len(message_uids)

    if command == "count":
        if cfg.porcelain:
            print(f"{num_messages} {folder}")
        else:
            printf(
                ngettext(
                    "folder `%s` has %d message matching %s",
                    "folder `%s` has %d messages matching %s",
                    num_messages,
                ),
                folder,
                num_messages,
                cfg.search_filter,
            )
        return

    act: str
    actargs: _t.Any
    method = None
    if command == "mark":
        act = "marking as %s %d messages matching %s from folder `%s`"
        actargs = (cfg.mark.upper(), num_messages, cfg.search_filter, folder)
    elif command == "fetch":
        act = "fetching %d messages matching %s from folder `%s`"
        actargs = (num_messages, cfg.search_filter, folder)
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
            actargs = (num_messages, cfg.search_filter, folder)
        elif method == "gmail-trash":
            act = "moving %d messages matching %s from folder `%s` to `[GMail]/Trash`"
            actargs = (num_messages, cfg.search_filter, folder)
        else:
            assert False
    else:
        assert False

    if cfg.dry_run:
        printf(gettext("dry-run: ") + gettext("not " + act), *actargs)
        return
    if command == "delete" and len(account.errors) > 0:
        account_error(
            account,
            gettext("one of the previous commands reported issues: ") + gettext("not " + act),
            *actargs,
        )
        return

    printf(gettext(act), *actargs)

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
                account.changes.append(
                    f"`{folder}`: "
                    + ngettext("marked %d message", "marked %d messages", num_marked)
                    % (num_marked,)
                )
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
                    msg = ngettext(
                        "fetched and marked %d message",
                        "fetched and marked %d messages",
                        num_delivered,
                    ) % (num_delivered,)
                else:
                    msg = ngettext(
                        "fetched %d but marked %d message",
                        "fetched %d but marked %d messages",
                        max(num_delivered, num_marked),
                    ) % (num_delivered, num_marked)
                account.changes.append(f"`{folder}`: {msg}")

                for hook in cfg.new_mail_cmd:
                    if hook not in state.pending_hooks:
                        state.pending_hooks.append(hook)
    elif command == "delete":
        assert method is not None
        old_num_trashed = account.num_trashed
        old_num_deleted = account.num_deleted
        try:
            do_store(cfg, state, account, srv, method, message_uids)
        finally:
            num_trashed = account.num_trashed - old_num_trashed
            if num_trashed > 0:
                account.changes.append(
                    f"`{folder}`: "
                    + ngettext("trashed %d message", "trashed %d messages", num_trashed)
                    % (num_trashed,)
                )
            num_deleted = account.num_deleted - old_num_deleted
            if num_deleted > 0:
                account.changes.append(
                    f"`{folder}`: "
                    + ngettext("deleted %d message", "deleted %d messages", num_deleted)
                    % (num_deleted,)
                )


def do_fetch(
    cfg: Namespace, state: State, account: Account, srv: IMAP4, message_uids: _t.List[bytes]
) -> None:
    fetch_num = cfg.fetch_number
    batch: _t.List[bytes] = []
    batch_total = 0
    while len(message_uids) > 0:
        raise_delayed_signals()

        to_fetch, message_uids = message_uids[:fetch_num], message_uids[fetch_num:]
        to_fetch_set: _t.Set[bytes] = set(to_fetch)
        typ, data = srv.uid("FETCH", b",".join(to_fetch), "(RFC822.SIZE)")  # type: ignore
        if typ != "OK":
            account.num_undelivered += len(to_fetch)
            account_error(account, "%s", format_imap_error("FETCH", typ, data))
            continue

        new = []
        for el in data:
            _, attrs_ = imap_parse(el)  # pylint: disable=unbalanced-tuple-unpacking
            attrs = imap_parse_attrs(attrs_)
            # print(attrs)

            try:
                uid = attrs[b"UID"]
                size = int(attrs[b"RFC822.SIZE"])
            except KeyError:
                account_conflict(account, attrs)
                continue

            new.append((uid, size))
            to_fetch_set.remove(uid)

        if len(to_fetch_set) > 0:
            account.num_undelivered += len(to_fetch)
            account_error(
                account,
                "%s",
                format_imap_error("FETCH", "the result does not have all requested messages"),
            )
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


def do_fetch_batch(
    cfg: Namespace,
    state: State,
    account: Account,
    srv: IMAP4,
    message_uids: _t.List[bytes],
    total_size: int,
) -> None:
    raise_delayed_signals()

    if len(message_uids) == 0:
        return
    if not cfg.quiet:
        printf(
            "... " + gettext("fetching a batch of %d messages (%d bytes)"),
            len(message_uids),
            total_size,
        )

    # because time.time() gives a float
    epoch_ms = time.time_ns() // 1000000

    joined = b",".join(message_uids)
    typ, data = srv.uid("FETCH", joined, "(BODY.PEEK[HEADER] BODY.PEEK[TEXT])")  # type: ignore
    if typ != "OK":
        account.num_undelivered += len(message_uids)
        account_error(account, "%s", format_imap_error("FETCH", typ, data))
        return

    if cfg.maildir is not None:
        internal_mda = True
        unsynced = []
        destdir = os.path.expanduser(cfg.maildir)
        try:
            os.makedirs(os.path.join(destdir, "tmp"), exist_ok=True)
            os.makedirs(os.path.join(destdir, "new"), exist_ok=True)
            os.makedirs(os.path.join(destdir, "cur"), exist_ok=True)
        except Exception as exc:
            raise CatastrophicFailure(gettext("failed to create `--maildir %s`"), destdir) from exc

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
        _, attrs_ = imap_parse(line, literals)  # pylint: disable=unbalanced-tuple-unpacking
        attrs = imap_parse_attrs(attrs_)
        # print(attrs)

        try:
            uid = attrs[b"UID"]
            header = attrs[b"BODY[HEADER]"]
            body = attrs[b"BODY[TEXT]"]
        except KeyError:
            account_conflict(account, attrs)
            continue

        if True:  # pylint: disable=using-constant-test
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
                tf: _t.Any
                tmp_path: str
                while True:
                    tmp_path = os.path.join(
                        destdir,
                        "tmp",
                        f"IAP_{smypid}_{sepoch_ms}_{str(tmp_num)}.{myhostname},S={sflen}.part",
                    )
                    tmp_num += 1

                    try:
                        tf = open(tmp_path, "xb")  # pylint: disable=consider-using-with
                    except FileExistsError:
                        continue
                    break

                try:
                    tf.write(header)
                    tf.write(body)
                    tf.flush()
                except Exception:
                    try:
                        tf.close()
                    except Exception:
                        pass
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                    raise
            except Exception as exc:
                failed_uids.append(uid)
                uncaught_exception(exc)
            else:
                unsynced.append((tf, (uid, msghash, sflen, tmp_path)))
        else:
            # deliver via MDA
            flushed = False
            delivered = False
            with subprocess.Popen(cfg.mda, stdin=subprocess.PIPE, shell=True) as p:
                fd: _t.Any = p.stdin
                try:
                    fd.write(header)
                    fd.write(body)
                    fd.flush()
                    fd.close()
                except BrokenPipeError:
                    try:
                        fd.close()
                    except Exception:
                        pass
                except Exception as exc:
                    try:
                        fd.close()
                    except Exception:
                        pass
                    uncaught_exception(exc)
                else:
                    flushed = True

                retcode = p.wait()
                if retcode != 0:
                    warning(gettext("`--mda %s` finished with exit code `%d`"), cfg.mda, retcode)
                elif not flushed:
                    warning(gettext("failed to `flush` to `stdin` of `--mda %s`"), cfg.mda)
                else:
                    delivered = True

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
                failed_uids.append(uid)
                try:
                    tf.close()
                except Exception:
                    pass
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                uncaught_exception(exc)
            else:
                synced.append(el)
        del unsynced

        # lock destination directory
        ddir = os.path.join(destdir, "new")
        try:
            dirfd = os.open(ddir, os.O_RDONLY | os.O_DIRECTORY)
            _fcntl.flock(dirfd, _fcntl.LOCK_EX)
        except Exception as exc:
            # cleanup
            for uid, _, _, tmp_path in synced:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                failed_uids.append(uid)
            del synced
            account_error(
                account,
                gettext("failed to lock `--maildir %s`: %s"),
                destdir,
                str(exc),
                exc_info=True,
            )
        else:
            # rename files to destination
            for uid, msghash, sflen, tmp_path in synced:
                msg_num = 0
                while True:
                    msg_path = os.path.join(
                        ddir, f"IAH_{msghash}_{str(msg_num)}.{myhostname},S={sflen}"
                    )
                    msg_num += 1

                    if os.path.exists(msg_path):
                        continue
                    break

                try:
                    os.rename(tmp_path, msg_path)
                except Exception as exc:
                    failed_uids.append(uid)
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                    uncaught_exception(exc)
                else:
                    done_uids.append(uid)
            del synced

            # ensure directory inode is synced to disk
            try:
                os.fsync(dirfd)
                _fcntl.flock(dirfd, _fcntl.LOCK_UN)
                os.close(dirfd)
            except Exception as exc:
                failed_uids += done_uids
                done_uids = []
                account_error(
                    account,
                    gettext("failed to sync `--maildir %s`: %s"),
                    destdir,
                    str(exc),
                    exc_info=True,
                )

    num_delivered = len(done_uids)
    num_undelivered = len(failed_uids)
    account.num_delivered += num_delivered
    account.num_undelivered += num_undelivered

    if internal_mda:
        how = "--maildir " + destdir
    else:
        how = "--mda " + cfg.mda

    if num_delivered > 0 and not cfg.quiet:
        printf(
            "... "
            + ngettext(
                "delivered %d message via `%s`", "delivered %d messages via `%s`", num_delivered
            ),
            num_delivered,
            how,
        )

    if num_undelivered > 0:
        account_error(
            account,
            ngettext(
                "failed to deliver %d message via `%s`",
                "failed to deliver %d messages via `%s`",
                num_undelivered,
            ),
            num_undelivered,
            how,
        )
        if cfg.paranoid is not None:
            if num_delivered == 0:
                raise AccountSoftFailure(
                    "failed to deliver any messages, aborting this `fetch` and any following commands"
                )
            if cfg.paranoid:
                raise CatastrophicFailure(
                    "failed to deliver %d messages in paranoid mode", num_undelivered
                )

    do_store(cfg, state, account, srv, cfg.mark, done_uids, False)


marking_as_msg = "... " + gettext("marking a batch of %d messages as %s")
delete_msg = "... " + gettext("deleting a batch of %d messages")
gmail_trash_msg = "... " + gettext("moving a batch of %d messages to `[GMail]/Trash`")


def do_store(
    cfg: Namespace,
    _state: State,
    account: Account,
    srv: IMAP4,
    method: str,
    message_uids: _t.List[bytes],
    interruptable: bool = True,
) -> None:
    if method == "noop":
        return

    store_num = cfg.store_number
    while len(message_uids) > 0:
        if interruptable:
            raise_delayed_signals()

        to_store, message_uids = message_uids[:store_num], message_uids[store_num:]
        joined = b",".join(to_store)

        if not cfg.quiet:
            if method in ("delete", "delete-noexpunge"):
                printf(delete_msg, len(to_store))
            elif method == "gmail-trash":
                printf(gmail_trash_msg, len(to_store))
            else:
                printf(marking_as_msg, len(to_store), method.upper())

        if method == "seen":
            typ, data = srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Seen")  # type: ignore
        elif method == "unseen":
            typ, data = srv.uid("STORE", joined, "-FLAGS.SILENT", "\\Seen")  # type: ignore
        elif method == "flagged":
            typ, data = srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Flagged")  # type: ignore
        elif method == "unflagged":
            typ, data = srv.uid("STORE", joined, "-FLAGS.SILENT", "\\Flagged")  # type: ignore
        elif method in ("delete", "delete-noexpunge"):
            typ, data = srv.uid("STORE", joined, "+FLAGS.SILENT", "\\Deleted")  # type: ignore
            if typ == "OK" and method == "delete":
                srv.expunge()
        elif method == "gmail-trash":
            typ, data = srv.uid("STORE", joined, "+X-GM-LABELS", "\\Trash")  # type: ignore
        else:
            assert False

        if typ == "OK":
            num_messages = len(to_store)
            if method in ("delete", "delete-noexpunge"):
                account.num_deleted += num_messages
            elif method == "gmail-trash":
                account.num_trashed += num_messages
            else:
                account.num_marked += num_messages
        else:
            account_error(account, "%s", format_imap_error("STORE", typ, data))


def add_examples(fmt: _t.Any) -> None:
    _ = gettext

    # fmt: off
    fmt.add_text("# " + _("Notes on usage"))

    fmt.add_text(_("- When specifying account-related settings `--user` and `--pass*` options should be always specified last."))
    fmt.add_text(_("  Internally, new account definition gets emitted when a new `--pass*` option finishes processing."))
    fmt.add_text(_("  All server connection and authentication options except `--user` and `--pass*` get reused between successively defined accounts, unless overwritten with a new value before the next `--pass*` option."))
    fmt.add_text(_('- Message search filters are connected by logical "AND"s so, e.g., `--from "github.com" --not-from "notifications@github.com"` will act on messages which have a `From:` header with `github.com` but without `notifications@github.com` as substrings.'))
    fmt.add_text(_("- `fetch` subcommand acts on `--unseen` messages by default."))
    fmt.add_text(_("- `delete` subcommand acts on `--seen` messages by default."))
    fmt.add_text(_("- Under `for-each`, after any command that produced errors (e.g. a `fetch` that failed to deliver at least one message because `--maildir` or `--mda` failed to do their job), any successive `delete` commands will be automatically skipped."))
    fmt.add_text(_(f"  In theory, in the case of `--maildir` or `--mda` failing to deliver some messages `{__prog__}` need not do this as those messages will be left unmarked on the server, but in combination with the default `--careful` delivery option (which see) this behaviour could still be helpful in preventing data loss in the event where the target filesystem starts generating random IO errors (e.g. if you HDD/SSD just failed)."))
    fmt.add_text(_(f"  In general, this behaviour exists to prevent `delete` from accidentally deleting something important when folder hierarchy on the IMAP server changes to be incompatible with in-use `{__prog__}` options. For instance, say you are trying to `fetch` from a folder that was recently renamed and then try to `delete` from `--all-folders`. The behaviour described above will prevent this from happening."))

    fmt.add_text("# " + _("Examples"))

    fmt.start_section(_("List all available IMAP folders and count how many messages they contain"))

    fmt.start_section(_("with the password taken from `pinentry`"))
    fmt.add_code(f'{__prog__} count --host imap.example.com --user account@example.com --pass-pinentry')
    fmt.end_section()

    fmt.start_section(_("with the password taken from the first line of the given file"))
    fmt.add_code(f"""{__prog__} count --host imap.example.com --user account@example.com \\
  --passfile /path/to/file/containing/account@example.com.password
""")
    fmt.end_section()

    fmt.start_section(_("with the password taken from the output of password-store utility"))
    fmt.add_code(f"""{__prog__} count --host imap.example.com --user account@example.com \\
  --passcmd "pass show mail/account@example.com"
""")
    fmt.end_section()

    fmt.start_section(_("with two accounts on the same server"))
    fmt.add_code(f"""{__prog__} count --porcelain \\
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
    fmt.add_code(f'{__prog__} count "${{gmail_common[@]}}" --folder "[Gmail]/All Mail" --older-than 7')
    fmt.end_section()

    fmt.start_section(_("Mark all messages in `INBOX` as not `SEEN`, fetch all not `SEEN` messages marking them `SEEN` as you download them so that if the process gets interrupted you could continue from where you left off"))
    fmt.add_code(f"""# {_("setup: do once")}
{__prog__} mark "${{common[@]}}" --folder INBOX unseen

# {_("repeatable part")}
{__prog__} fetch "${{common_mda[@]}}" --folder INBOX
""")
    fmt.end_section()

    fmt.start_section(_(f"Similarly to the above, but use `FLAGGED` instead of `SEEN`. This allows to use this in parallel with another instance of `{__prog__}` using the `SEEN` flag, e.g. if you want to backup to two different machines independently, or if you want to use `{__prog__}` simultaneously in parallel with `fetchmail` or other similar tool"))
    fmt.add_code(f"""# {_("setup: do once")}
{__prog__} mark "${{common[@]}}" --folder INBOX unflagged

# {_("repeatable part")}
{__prog__} fetch "${{common_mda[@]}}" --folder INBOX --any-seen --unflagged

# {_("this will work as if nothing of the above was run")}
fetchmail

# {_("in this use case you should use both `--seen` and `--flagged` when expiring old messages")}
# {_(f"so that it would only delete messages fetched by both {__prog__} and fetchmail")}
{__prog__} delete "${{common[@]}}" --folder INBOX --older-than 7 --seen --flagged
""")
    fmt.end_section()

    fmt.start_section(_(f"Similarly to the above, but run `{__prog__} fetch` as a daemon to download updates every hour"))
    fmt.add_code(f"""# {_("setup: do once")}
{__prog__} mark "${{common[@]}}" --folder INBOX unseen

# {_("repeatable part")}
{__prog__} fetch "${{common_mda[@]}}" --folder INBOX --every 3600
""")
    fmt.end_section()

    fmt.start_section(_("Fetch all messages from `INBOX` folder that were delivered in the last 7 days (the resulting date is rounded down to the start of the day by server time), but don't change any flags"))
    fmt.add_code(f'{__prog__} fetch "${{common_mda[@]}}" --folder INBOX --any-seen --newer-than 7')
    fmt.end_section()

    fmt.start_section(_("Fetch all messages from `INBOX` folder that were delivered from the beginning of today (by server time), without changing any flags"))
    fmt.add_code(f'{__prog__} fetch "${{common_mda[@]}}" --folder INBOX --any-seen --newer-than 0')
    fmt.end_section()

    fmt.start_section(_("Delete all `SEEN` messages older than 7 days from `INBOX` folder"))
    fmt.add_text("")
    fmt.add_text(_("Assuming you fetched and backed up all your messages already this allows you to keep as little as possible on the server, so that if your account gets cracked/hacked, you won't be as vulnerable."))
    fmt.add_code(f'{__prog__} delete "${{common[@]}}" --folder INBOX --older-than 7')
    fmt.add_text(_("(`--seen` is implied by default)"))
    fmt.end_section()

    fmt.start_section(_("**DANGEROUS!** If you fetched and backed up all your messages already, you can skip `--older-than` and just delete all `SEEN` messages instead"))
    fmt.add_code(f'{__prog__} delete "${{common[@]}}" --folder INBOX')
    fmt.add_text(_(f"Though, setting at least `--older-than 1`, to make sure you won't lose any data in case you forgot you are running another instance of `{__prog__}` or another IMAP client that changes message flags is highly recommended."))
    fmt.end_section()

    fmt.start_section(_("Fetch everything GMail considers to be Spam for local filtering"))
    fmt.add_code(f"""# {_("setup: do once")}
mkdir -p ~/Mail/spam/{{new,cur,tmp}}

cat > ~/.mailfilter-spam << EOF
DEFAULT="\\$HOME/Mail/spam"
EOF

{__prog__} mark "${{gmail_common[@]}}" --folder "[Gmail]/Spam" unseen

# {_("repeatable part")}
{__prog__} fetch "${{gmail_common_mda[@]}}" --mda "maildrop ~/.mailfilter-spam" --folder "[Gmail]/Spam"
""")
    fmt.end_section()

    fmt.start_section(_("Fetch everything from all folders, except for `INBOX`, `[Gmail]/Starred` (because in GMail these two are included in `[Gmail]/All Mail`), and `[Gmail]/Trash` (for illustrative purposes)"))
    fmt.add_code(f"""{__prog__} fetch "${{gmail_common_mda[@]}}" --all-folders \\
  --not-folder INBOX --not-folder "[Gmail]/Starred" --not-folder "[Gmail]/Trash"
""")
    fmt.add_text("Note that, in GMail, all messages except for those in `[Gmail]/Trash` and `[Gmail]/Spam` are included in `[Gmail]/All Mail`. So, if you want to fetch everything, you should probably just fetch from those three folders instead:")
    fmt.add_code(f"""{__prog__} fetch "${{gmail_common_mda[@]}}" \\
  --folder "[Gmail]/All Mail" --folder "[Gmail]/Trash" --folder "[Gmail]/Spam"
""")
    fmt.end_section()

    fmt.start_section(_("GMail-specific deletion mode: move (expire) old messages to `[Gmail]/Trash` and then delete them"))

    fmt.add_text("")
    fmt.add_text(_("In GMail, deleting messages from `INBOX` does not actually delete them, nor moves them to trash, just removes them from `INBOX` while keeping them available from `[Gmail]/All Mail`."))
    fmt.add_text(_("To work around this, this tool provides a GMail-specific `--method gmail-trash` that moves messages to `[Gmail]/Trash` in a GMail-specific way (this is not a repetition, it does require issuing special IMAP `STORE` commands to achieve this):"))
    fmt.add_code(f'{__prog__} delete "${{gmail_common[@]}}" --folder "[Gmail]/All Mail" --older-than 7')
    fmt.add_text(_("(`--method gmail-trash` is implied by `--host imap.gmail.com` and `--folder` not being `[Gmail]/Trash`, `--seen` is still implied by default)"))

    fmt.add_text(_("Messages in `[Gmail]/Trash` will be automatically removed by GMail in 30 days, but you can also delete them immediately with:"))

    fmt.add_code(f'{__prog__} delete "${{gmail_common[@]}}" --folder "[Gmail]/Trash" --any-seen --older-than 7')
    fmt.add_text(_("(`--method delete` is implied by `--host imap.gmail.com` but `--folder` being `[Gmail]/Trash`)"))
    fmt.end_section()

    fmt.start_section(_("Every hour, fetch messages from different folders using different MDA settings and then expire messages older than 7 days, all in a single pass (reusing the server connection between subcommands)"))
    fmt.add_code(f"""{__prog__} for-each "${{gmail_common[@]}}" --every 3600 -- \\
  fetch --folder "[Gmail]/All Mail" --mda maildrop \\; \\
  fetch --folder "[Gmail]/Spam" --mda "maildrop ~/.mailfilter-spam" \\; \\
  delete --folder "[Gmail]/All Mail" --folder "[Gmail]/Spam" --folder "[Gmail]/Trash" \\
    --older-than 7
""")
    fmt.add_text(_("Note the `--` and `\\;` tokens, without them the above will fail to parse."))
    fmt.add_text(_("Also note that `delete` will use `--method gmail-trash` for `[Gmail]/All Mail` and `[Gmail]/Spam` and then use `--method delete` for `[Gmail]/Trash` even though they are specified together."))
    fmt.add_text(_(f"Also, when running in parallel with another IMAP client that changes IMAP flags, `{__prog__} for-each` will notice the other client doing it while `fetch`ing and will skip all following `delete`s of that `--every` cycle to prevent data loss."))
    fmt.end_section()
    # fmt: on


def make_argparser(real: bool) -> _t.Any:
    _ = gettext

    parser = argparse.BetterArgumentParser(
        prog=__prog__,
        description=_(
            "A handy Swiss-army-knife-like utility for fetching and performing batch operations on messages residing on IMAP servers."
        )
        + "\n"
        + _(
            "I.e., for each specified IMAP server: login, perform specified actions on all messages matching specified criteria in all specified folders, log out."
        ),
        additional_sections=[add_examples],
        add_version=True,
    )

    class EmitAccount(argparse.Action):
        def __init__(
            self,
            option_strings: str,
            dest: str,
            type: _t.Any = None,  # pylint: disable=redefined-builtin
            **kwargs: _t.Any,
        ) -> None:
            self.ptype = type
            super().__init__(option_strings, dest, type=str, **kwargs)

        def __call__(
            self,
            parser: _t.Any,
            cfg: Namespace,
            value: _t.Any,
            option_string: _t.Optional[str] = None,
        ) -> None:
            if cfg.host is None:
                raise CatastrophicFailure("`--host` is required")

            host: str = cfg.host

            IMAP_base: type
            if cfg.socket in ["plain", "starttls"]:
                port = 143
                IMAP_base = IMAP4
            elif cfg.socket == "ssl":
                port = 993
                IMAP_base = IMAP4_SSL

            if cfg.port is not None:
                port = cfg.port

            if cfg.user is None:
                raise CatastrophicFailure("`--user` is required")

            user = cfg.user
            cfg.user = None

            allow_login = cfg.allow_login
            if cfg.socket == "plain":
                allow_login = allow_login and cfg.allow_plain

            if self.ptype == "pinentry":
                password = getpass_pinentry(
                    _("Please enter the passphrase for user %s on host %s") % (user, host),
                    _("Passphrase:"),
                    defenc,
                )
            elif self.ptype == "file":
                with open(value, "rb") as f:
                    password = f.readline().decode(defenc)
            elif self.ptype == "cmd":
                with subprocess.Popen(
                    value, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True
                ) as p:
                    p.stdin.close()  # type: ignore
                    password = p.stdout.readline().decode(defenc)  # type: ignore
                    retcode = p.wait()
                    if retcode != 0:
                        raise CatastrophicFailure(
                            "`--passcmd` (`%s`) failed with non-zero exit code %d", value, retcode
                        )
            else:
                assert False

            if password[-1:] == "\n":
                password = password[:-1]
            if password[-1:] == "\r":
                password = password[:-1]

            cfg.accounts.append(
                Account(cfg.socket, cfg.timeout, host, port, user, password, allow_login, IMAP_base)
            )

    # fmt: off
    def add_common(cmd: _t.Any) -> _t.Any:
        cmd.set_defaults(accounts=[])

        cmd.add_argument("-q", "--quieter", dest="quiet", action="store_true",
            help=_("be less verbose")
        )

        agrp = cmd.add_argument_group(_("debugging"))
        agrp.add_argument("--very-dry-run", action="store_true",
            help=_("verbosely describe what the given command line would do and exit"),
        )
        agrp.add_argument("--dry-run", action="store_true",
            help=_("perform a trial run without actually performing any changes"),
        )
        agrp.add_argument("--debug", dest="debugging", action="store_true",
            help=_("dump IMAP conversation to stderr")
        )

        agrp = cmd.add_argument_group(_("hooks"))
        agrp.add_argument("--notify-success", action="store_true",
            help=_(f"generate notifications (via `notify-send`) describing server-side changes, if any, at the end of each program cycle; most useful if you run `{__prog__}` in background with `--every` argument in a graphical environment"),
        )
        agrp.add_argument("--success-cmd", metavar="CMD", action="append", type=str, default=[],
            help=_("shell command to run at the end of each program cycle that performed some changes on the server, i.e. a generalized version of `--notify-success`; the spawned process will receive the description of the performed changes via stdin; can be specified multiple times"),
        )
        agrp.add_argument("--notify-failure", action="store_true",
            help=_(f"generate notifications (via `notify-send`) describing recent failures, if any, at the end of each program cycle; most useful if you run `{__prog__}` in background with `--every` argument in a graphical environment"),
        )
        agrp.add_argument("--failure-cmd", metavar="CMD", action="append", type=str, default=[],
            help=_("shell command to run at the end of each program cycle that had some of its command fail, i.e. a generalized version of `--notify-failure`; the spawned process will receive the description of the failured via stdin; can be specified multiple times"),
        )
        agrp.set_defaults(notify=False)

        agrp = cmd.add_argument_group(_("authentication settings"))
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--auth-allow-login", dest="allow_login", action="store_true",
            help=_("allow the use of IMAP `LOGIN` command (default)"),
        )
        grp.add_argument("--auth-forbid-login", dest="allow_login", action="store_false",
            help=_("forbid the use of IMAP `LOGIN` command, fail if challenge-response authentication is not available"),
        )
        grp.set_defaults(allow_login=True)

        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--auth-allow-plain", dest="allow_plain", action="store_true",
            help=_("allow passwords to be transmitted over the network in plain-text"),
        )
        grp.add_argument("--auth-forbid-plain", dest="allow_plain", action="store_false",
            help=_("forbid passwords from being transmitted over the network in plain-text, plain-text authentication would still be possible over SSL if `--auth-allow-login` is set (default)"),
        )
        grp.set_defaults(allow_plain=False)

        agrp = cmd.add_argument_group("server connection",
            description=_("can be specified multiple times")
        )
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--plain", dest="socket", action="store_const", const="plain",
            help=_("connect via plain-text socket"),
        )
        grp.add_argument("--ssl", dest="socket", action="store_const", const="ssl",
            help=_("connect over SSL socket") + " " + _("(default)"),
        )
        grp.add_argument("--starttls", dest="socket", action="store_const", const="starttls",
            help=_("connect via plain-text socket, but then use STARTTLS command"),
        )
        grp.set_defaults(socket="ssl")

        agrp.add_argument("--host", type=str, help=_("IMAP server to connect to (required)"))
        agrp.add_argument("--port", type=int,
            help=_("port to use")
            + " "
            + _("(default: 143 for `--plain` and `--starttls`, 993 for `--ssl`)"),
        )

        agrp.add_argument("--timeout", type=int, default=60,
            help=_("socket timeout, in seconds (default: %(default)s)"),
        )

        agrp = cmd.add_argument_group(_("authentication to the server"),
            description=_("either of `--pass-pinentry`, `--passfile`, or `--passcmd` are required; can be specified multiple times"),
        )
        agrp.add_argument("--user", type=str, help=_("username on the server (required)"))

        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--pass-pinentry", nargs=0, action=EmitAccount, type="pinentry",
            help=_("read the password via `pinentry`"),
        )
        grp.add_argument("--passfile", "--pass-file", action=EmitAccount, type="file",
            help=_("file containing the password on its first line"),
        )
        grp.add_argument("--passcmd", "--pass-cmd", action=EmitAccount, type="cmd",
            help=_("shell command that returns the password as the first line of its stdout"),
        )
        grp.set_defaults(password=None)

        agrp = cmd.add_argument_group(_("batching settings"),
            description=_("larger values improve performance but produce longer IMAP command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen"),
        )
        agrp.add_argument("--store-number", metavar="INT", type=int, default=150,
            help=_("batch at most this many message UIDs in IMAP `STORE` requests (default: %(default)s)"),
        )
        agrp.add_argument("--fetch-number", metavar="INT", type=int, default=150,
            help=_("batch at most this many message UIDs in IMAP `FETCH` metadata requests (default: %(default)s)"),
        )
        agrp.add_argument("--batch-number", metavar="INT", type=int, default=150,
            help=_("batch at most this many message UIDs in IMAP `FETCH` data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: %(default)s)"),
        )
        agrp.add_argument("--batch-size", metavar="INT", type=int, default=4 * 1024 * 1024,
            help=_(f"batch `FETCH` at most this many bytes of RFC822 messages at once; RFC822 messages larger than this will be fetched one by one (i.e. without batching); essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted while `{__prog__}` is batching (default: %(default)s)"),
        )

        agrp = cmd.add_argument_group("polling/daemon options")
        agrp.add_argument("--every", metavar="INTERVAL", type=int,
            help=_("repeat the command every `INTERVAL` seconds")
            + ";\n"
            + _(f"`{__prog__}` will do its best to repeat the command precisely every `INTERVAL` seconds even if the command involes `fetch`ing of new messages and `--new-mail-cmd` invocations take different time each cycle; if program cycle takes more than `INTERVAL` seconds or `INTERVAL < 60` then `{__prog__}` would sleep for `60` seconds either way")
            + ",\n"
            + _("this prevents the servers accessed earlier in the cycle from learning about the amount of new data fetched from the servers accessed later in the cycle"),
        )
        agrp.add_argument("--every-add-random", metavar="ADD", default=60, type=int,
            help=_("sleep a random number of seconds in [0, ADD] range (uniform distribution) before each `--every` cycle, including the very first one (default: %(default)s)")
            + ";\n"
            + _("if you set it large enough to cover the longest single-server `fetch`, it will prevent any of the servers learning anything about the data on other servers")
            + ";\n"
            + _(f"if you run `{__prog__}` on a machine that disconnects from the Internet when you go to sleep and you set it large enough, it will help in preventing the servers from collecting data about your sleep cycle"),
        )

        return cmd

    def add_folders(cmd: _t.Any, all_by_default: _t.Optional[bool]) -> _t.Any:
        def_fall, def_freq = "", ""
        if all_by_default is None:
            def_freq = " " + _("(will be used as default for subcommands)")
        elif all_by_default:
            def_fall = " " + _("(default)")
        else:
            def_freq = " " + _("(required)")

        agrp = cmd.add_argument_group(_("folder search filters") + def_freq)

        egrp = agrp.add_mutually_exclusive_group(required=all_by_default is False)
        egrp.add_argument("--all-folders", action="store_true", default=all_by_default is True,
            help=_("operate on all folders") + def_fall,
        )
        egrp.add_argument("--folder", metavar="NAME", dest="folders", action="append", type=str, default=[],
            help=_("mail folders to include; can be specified multiple times"),
        )

        agrp.add_argument("--not-folder", metavar="NAME", dest="not_folders", action="append", type=str, default=[],
            help=_("mail folders to exclude; can be specified multiple times"),
        )

        return cmd

    def add_folders_sub(cmd: _t.Any) -> _t.Any:
        egrp = cmd.add_mutually_exclusive_group()
        egrp.add_argument("--all-folders", action="store_true", default=argparse.SUPPRESS)
        egrp.add_argument("--folder", metavar="NAME", dest="folders", action="append", type=str, default=argparse.SUPPRESS)
        cmd.add_argument("--not-folder", metavar="NAME", dest="not_folders", action="append", type=str, default=argparse.SUPPRESS)
        return cmd

    def add_common_filters(cmd: _t.Any) -> _t.Any:
        agrp = cmd.add_argument_group(_("message search filters"))
        agrp.add_argument("--older-than", metavar="DAYS", action="append", default=[], type=int,
            help=_("operate on messages older than this many days, **the date will be rounded down to the start of the day; actual matching happens on the server, so all times are server time**; e.g. `--older-than 0` means older than the start of today by server time, `--older-than 1` means older than the start of yesterday, etc; can be specified multiple times, in which case the earliest (the most old) date on the list will be chosen"),
        )
        agrp.add_argument("--newer-than", metavar="DAYS", action="append", default=[], type=int,
            help=_("operate on messages newer than this many days, a negation of`--older-than`, so **everything from `--older-than` applies**; e.g., `--newer-than -1` will match files dated into the future, `--newer-than 0` will match files delivered from the beginning of today, etc; can be specified multiple times, in which case the latest (the least old) date on the list will be chosen"),
        )

        agrp.add_argument("--older-than-timestamp-in", metavar="PATH", action="append", default=[], type=str,
            help=_("operate on messages older than the timestamp (in seconds since UNIX Epoch) recorded on the first line of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above"),
        )
        agrp.add_argument("--newer-than-timestamp-in", metavar="PATH", action="append", default=[], type=str,
            help=_("operate on messages newer than the timestamp (in seconds since UNIX Epoch) recorded on the first line of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above"),
        )

        agrp.add_argument("--older-than-mtime-of", metavar="PATH", action="append", default=[], type=str,
            help=_("operate on messages older than `mtime` of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above"),
        )
        agrp.add_argument("--newer-than-mtime-of", metavar="PATH", action="append", default=[], type=str,
            help=_("operate on messages newer than `mtime` of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above"),
        )

        agrp.add_argument("--from", dest="hfrom", metavar="ADDRESS", action="append", type=str, default=[],
            help=_("operate on messages that have this string as substring of their header's FROM field; can be specified multiple times"),
        )
        agrp.add_argument("--not-from", dest="hnotfrom", metavar="ADDRESS", action="append", type=str, default=[],
            help=_("operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times"),
        )

        return cmd

    def add_flag_filters(cmd: _t.Any, default: _t.Union[_t.Optional[bool], str]) -> _t.Any:
        def_mex = " " + _("(mutually exclusive)")
        def_str = " " + _("(default)")
        def_req = def_mex
        def_any, def_seen, def_unseen, def_flag = "", "", "", def_str
        if default is None:
            def_any = def_str
        elif default is True:
            def_seen = def_str
        elif default is False:
            def_unseen = def_str
        elif default == "depends":
            def_req = " " + _("(mutually exclusive, default: depends on other arguments)")
            def_flag = ""
        else:
            assert False

        agrp = cmd.add_argument_group(_("message IMAP `SEEN` flag filters") + def_req)

        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--any-seen", dest="seen", action="store_const", const=None,
            help=_("operate on both `SEEN` and not `SEEN` messages") + def_any,
        )
        grp.add_argument("--seen", dest="seen", action="store_true",
            help=_("operate on messages marked as `SEEN`") + def_seen,
        )
        grp.add_argument("--unseen", dest="seen", action="store_false",
            help=_("operate on messages not marked as `SEEN`") + def_unseen,
        )
        grp.set_defaults(seen=default)

        agrp = cmd.add_argument_group(_("message IMAP `FLAGGED` flag filters") + def_req)
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--any-flagged", dest="flagged", action="store_const", const=None,
            help=_("operate on both `FLAGGED` and not `FLAGGED` messages") + def_flag,
        )
        grp.add_argument("--flagged", dest="flagged", action="store_true",
            help=_("operate on messages marked as `FLAGGED`"),
        )
        grp.add_argument("--unflagged", dest="flagged", action="store_false",
            help=_("operate on messages not marked as `FLAGGED`"),
        )
        grp.set_defaults(flagged=None)

        return cmd

    def add_delivery(cmd: _t.Any) -> _t.Any:
        agrp = cmd.add_argument_group(_("delivery target (required, mutually exclusive)"))
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--maildir", metavar="DIRECTORY", type=str,
            help=_("Maildir to deliver the messages to;")
            + "\n"
            + _(f"with this specified `{__prog__}` will simply drop raw RFC822 messages, one message per file, into `DIRECTORY/new` (creating it, `DIRECTORY/cur`, and `DIRECTORY/tmp` if any of those do not exists)"),
        )
        grp.add_argument("--mda", dest="mda", metavar="COMMAND", type=str,
            help=_("shell command to use as an MDA to deliver the messages to;")
            + "\n"
            + _(f"with this specified `{__prog__}` will spawn `COMMAND` via the shell and then feed raw RFC822 message into its `stdin`, the resulting process is then responsible for delivering the message to Maildir, mbox, etc;")
            + "\n"
            + _("`maildrop` from Courier Mail Server project is a good KISS default"),
        )

        agrp = cmd.add_argument_group(_("delivery mode (mutually exclusive)"))
        grp = agrp.add_mutually_exclusive_group()
        grp.add_argument("--yolo", dest="paranoid", action="store_const", const=None,
            help=_(f"messages that fail to be delivered into the `--maildir` or by the `--mda` are left un`--mark`ed on the server but no other messages get affected and currently running `{__prog__} fetch` continues as if nothing is amiss"),
        )
        grp.add_argument("--careful", dest="paranoid", action="store_false",
            help=_(f"messages that fail to be delivered into the `--maildir` or by the `--mda` are left un`--mark`ed on the server, no other messages get affected, but `{__prog__}` aborts currently running `fetch` and all the following commands of the `for-each` (if any) if zero messages from the current batch got successfully delivered --- as that usually means that the target file system is out of space, read-only, or generates IO errors (default)"),
        )
        grp.add_argument("--paranoid", dest="paranoid", action="store_true",
            help=_(f"`{__prog__}` aborts the process immediately if any of the messages in the current batch fail to be delivered into the `--maildir` or by the `--mda`, the whole batch gets left un`--mark`ed on the server"),
        )
        grp.set_defaults(paranoid=False)

        agrp = cmd.add_argument_group(_("hooks"))
        agrp.add_argument("--new-mail-cmd", metavar="CMD", action="append", type=str, default=[],
            help=_("shell command to run at the end of each program cycle that had new messages successfully delivered into the `--maildir` or by the `--mda` of this `fetch` subcommand; can be specified multiple times"),
        )

        return cmd

    def no_cmd(_cfg: Namespace, _state: State) -> None:
        parser.print_help(stderr)  # type: ignore
        die(_("no subcommand specified"), code=2)

    parser.set_defaults(func=no_cmd)

    if not real:
        add_common(parser)
        add_common_filters(parser)

    subparsers = parser.add_subparsers(title="subcommands")

    cmd = subparsers.add_parser(
        "list",
        help=_("list all available folders on the server, one per line"),
        description=_("Login, perform IMAP `LIST` command to get all folders, print them one per line."),
    )
    if real:
        add_common(cmd)
    cmd.add_argument(
        "--porcelain",
        action="store_true",
        help=_("print in a machine-readable format (the default at the moment)"),
    )
    cmd.set_defaults(command="list")
    cmd.set_defaults(func=cmd_list)

    cmd = subparsers.add_parser("count",
        help=_("count how many matching messages each specified folder has"),
        description=_("Login, (optionally) perform IMAP `LIST` command to get all folders, perform IMAP `SEARCH` command with specified filters in each folder, print message counts for each folder one per line."),
    )
    if real:
        add_common(cmd)
    add_folders(cmd, True)

    def add_count(cmd: _t.Any) -> _t.Any:
        cmd.set_defaults(command="count")
        if real:
            add_common_filters(cmd)
        add_flag_filters(cmd, None)
        cmd.add_argument("--porcelain", action="store_true",
            help=_("print in a machine-readable format")
        )
        return cmd

    add_count(cmd)
    cmd.set_defaults(func=cmd_action)

    cmd = subparsers.add_parser("mark",
        help=_("mark matching messages in specified folders in a specified way"),
        description=_("Login, perform IMAP `SEARCH` command with specified filters for each folder, mark resulting messages in specified way by issuing IMAP `STORE` commands."),
    )
    if real:
        add_common(cmd)
    add_folders(cmd, False)

    def add_mark(cmd: _t.Any) -> _t.Any:
        cmd.set_defaults(command="mark")
        if real:
            add_common_filters(cmd)
        add_flag_filters(cmd, "depends")
        agrp = cmd.add_argument_group("marking")
        sets_x_if = _("sets `%s` if no message flag filter is specified")
        agrp.add_argument("mark", choices=["seen", "unseen", "flagged", "unflagged"],
            help=_("mark how")
            + " "
            + _("(required)")
            + f""":
- `seen`: {_("add `SEEN` flag")}, {sets_x_if % ("--unseen",)}
- `unseen`: {_("remove `SEEN` flag")}, {sets_x_if % ("--seen",)}
- `flag`: {_("add `FLAGGED` flag")}, {sets_x_if % ("--unflagged",)}
- `unflag`: {_("remove `FLAGGED` flag")}, {sets_x_if % ("--flagged",)}
""",
        )
        return cmd

    add_mark(cmd)
    cmd.set_defaults(func=cmd_action)

    cmd = subparsers.add_parser("fetch",
        help=_("fetch matching messages from specified folders, put them into a Maildir or feed them to a MDA/LDA, and then mark them in a specified way if it succeeds"),
        description=_("Login, perform IMAP `SEARCH` command with specified filters for each folder, fetch resulting messages in (configurable) batches, put each batch of message into the specified Maildir and `fsync` them to disk or feed them to the specified MDA/LDA, and, if and only if all of the above succeeds, mark each message in the batch on the server in a specified way by issuing IMAP `STORE` commands."),
    )
    if real:
        add_common(cmd)
    add_folders(cmd, True)

    def add_fetch(cmd: _t.Any) -> _t.Any:
        cmd.set_defaults(command="fetch")
        add_delivery(cmd)
        if real:
            add_common_filters(cmd)
        add_flag_filters(cmd, False)
        agrp = cmd.add_argument_group("marking")
        agrp.add_argument("--mark", choices=["auto", "noop", "seen", "unseen", "flagged", "unflagged"], default="auto",
            help=_("after the message was fetched")
            + f""":
- `auto`: {_('`seen` when only `--unseen` is set (which it is by default), `flagged` when only `--unflagged` is set, `noop` otherwise (default)')}
- `noop`: {_("do nothing")}
- `seen`: {_("add `SEEN` flag")}
- `unseen`: {_("remove `SEEN` flag")}
- `flagged`: {_("add `FLAGGED` flag")}
- `unflagged`: {_("remove `FLAGGED` flag")}
""",
        )
        return cmd

    add_fetch(cmd)
    cmd.set_defaults(func=cmd_action)

    cmd = subparsers.add_parser("delete",
        help=_("delete matching messages from specified folders"),
        description=_("Login, perform IMAP `SEARCH` command with specified filters for each folder, delete them from the server using a specified method."),
    )
    if real:
        add_common(cmd)
    add_folders(cmd, False)

    def add_delete(cmd: _t.Any) -> _t.Any:
        cmd.set_defaults(command="delete")
        if real:
            add_common_filters(cmd)
        add_flag_filters(cmd, True)
        agrp = cmd.add_argument_group(_("deletion method"))
        agrp.add_argument("--method", choices=["auto", "delete", "delete-noexpunge", "gmail-trash"], default="auto",
            help=_("delete messages how")
            + f""":
- `auto`: {_('`gmail-trash` when `--host imap.gmail.com` and the current folder is not `[Gmail]/Trash`, `delete` otherwise')} {_("(default)")}
- `delete`: {_('mark messages as deleted and then use IMAP `EXPUNGE` command, i.e. this does what you would expect a "delete" command to do, works for most IMAP servers')}
- `delete-noexpunge`: {_('mark messages as deleted but skip issuing IMAP `EXPUNGE` command hoping the server does as RFC2060 says and auto-`EXPUNGE`s messages on IMAP `CLOSE`; this is much faster than `delete` but some servers (like GMail) fail to implement this properly')}
- `gmail-trash`: {_(f'move messages to `[Gmail]/Trash` in GMail-specific way instead of trying to delete them immediately (GMail ignores IMAP `Deleted` flag and `EXPUNGE` command outside of `[Gmail]/Trash`); you can then `{__prog__} delete --folder "[Gmail]/Trash"` them after (which will default to `--method delete`), or you could just leave them there and GMail will delete them in 30 days')}
""",
        )
        return cmd

    add_delete(cmd)
    cmd.set_defaults(func=cmd_action)

    def cmd_for_each(cfg: Namespace, state: State) -> None:
        # generate parser for our cfg
        fe_parser = argparse.BetterArgumentParser(prog=__prog__ + " for-each")

        # we do this to force the user to specify `--folder` or such
        # for each command if the global one is not specified
        add_folders_here: _t.Callable[[_t.Any], _t.Any] = add_folders_sub
        if not cfg.all_folders and len(cfg.folders) == 0:
            add_folders_here = lambda x: add_folders(x, False)  # pylint: disable=unnecessary-lambda-assignment

        fe_subparsers = fe_parser.add_subparsers(title="subcommands")
        add_count(fe_subparsers.add_parser("count"))
        add_folders_here(add_mark(fe_subparsers.add_parser("mark")))
        add_folders_here(add_fetch(fe_subparsers.add_parser("fetch")))
        add_folders_here(add_delete(fe_subparsers.add_parser("delete")))

        # set defaults from cfg
        fe_parser.set_defaults(
            **{name: value for name, value in cfg.__dict__.items() if name != "rest"}
        )

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

    cmd = subparsers.add_parser("for-each",
        help=_("perform multiple other subcommands, sequentially, on a single server connection"),
        description=_("""For each account: login, perform other subcommands given in `ARG`s, logout.

This is most useful for performing complex changes `--every` once in while in daemon mode.
Or if you want to set different `--folder`s for different subcommands but run them all at once.

Except for the simplest of cases, you must use `--` before `ARG`s so that any options specified in `ARG`s won't be picked up by `for-each`.
Run with `--very-dry-run` to see the interpretation of the given command line.

All generated hooks are deduplicated and run after all other subcommands are done.
E.g., if you have several `fetch --new-mail-cmd filter-my-mail` as subcommands of `for-each`, then `filter-my-mail` *will be run **once** after all other subcommands finish*.
"""),
    )
    if real:
        add_common(cmd)
    add_folders(cmd, None)
    cmd.add_argument("rest", metavar="ARG", nargs="+", type=str,
        help=_("arguments, these will be split by `;` and parsed into other subcommands"),
    )
    cmd.set_defaults(func=cmd_for_each)
    # fmt: on

    return parser


def main() -> None:
    setup_result = setup_kisstdlib(__prog__, signals=["SIGTERM", "SIGINT", "SIGBREAK", "SIGUSR1"])
    run_kisstdlib_main(
        setup_result,
        argparse.make_argparser_and_run,
        make_argparser,
        lambda cargs: cargs.func(cargs, State()),
    )


if __name__ == "__main__":
    main()
