#!/usr/bin/env python3

import argparse
import imaplib
import os
import ssl
import subprocess
import sys
import time

def main():
    epilog = """
examples:

- GMail with a password taken from password-store util:

$ pyimapexpire --dry-run --age 7 --ssl --host imap.gmail.com --user myself@gmail.com --passcmd pass show mail/myself@gmail.com

- GMail with a password taken from a file:

$ pyimapexpire --dry-run --age 7 --ssl --host imap.gmail.com --user myself@gmail.com --passfile /path/to/file/containing/myself@gmail.com.password
"""

    parser = argparse.ArgumentParser(prog="pyimapexpire", description="Login to an IMAP4 server and remove all messages older than a given number of days.", epilog=epilog, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version="%(prog)s 1.0")
    parser.add_argument("--debug", action="store_true", help="print IMAP conversation to stderr")
    parser.add_argument("--dry-run", action="store_true", help="don't actually delete anything")
    parser.add_argument("--age", type=int, required = True, help="delete mail older than this many days")
    parser.add_argument("--folder", action="append", type=str, default=[], help="mail folders to delete mail from. Can be specified multiple times, default: INBOX")
    grp = parser.add_mutually_exclusive_group(required = True)
    grp.add_argument("--plain", action="store_true", help="connect via plain-text socket")
    grp.add_argument("--ssl", action="store_true", help="connect over SSL socket")
    grp.add_argument("--starttls", action="store_true", help="connect via plain-text socket, but then use STARTTLS command")
    parser.add_argument("--host", type=str, required=True, help="IMAP server to connect to")
    parser.add_argument("--port", type=int, help="port to use, default: 143 for --plain and --starttls, 993 for --ssl")
    parser.add_argument("--user", type=str, required = True, help="username on the server")
    grp = parser.add_mutually_exclusive_group(required = True)
    grp.add_argument("--passfile", action="store_true", help="password will be read from the first line of the file supplied in the first positional argument")
    grp.add_argument("--passcmd", action="store_true", help="password will be read from the first line of the output of the command supplied by the positional arguments (the command will be run with exec(2), not via the shell)")
    parser.add_argument("rest", metavar="ARGS", nargs="+", type=str, help="positional arguments to use in --passfile or --passcmd")
    args = parser.parse_args(sys.argv[1:])

    if len(args.folder) == 0:
        args.folder = ["INBOX"]

    if args.passfile:
        with open(args.rest[0], "rb") as f:
            password = str(f.readline(), "utf-8")
    elif args.passcmd:
        with subprocess.Popen(args.rest, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None) as p:
            p.stdin.close()
            password = str(p.stdout.readline(), "utf-8")
            retcode = p.wait()
            if retcode != 0:
                raise SystemError("failed to execute passcmd")

    if password[-1:] == "\n":
        password = password[:-1]

    if args.plain or args.starttls:
        port = 143
        IMAP_base = imaplib.IMAP4
    elif args.ssl:
        port = 993
        IMAP_base = imaplib.IMAP4_SSL

    IMAP = IMAP_base
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

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.check_hostname = True
    ssl_context.load_default_certs()

    #sys.exit(1)

    if args.ssl:
        srv = IMAP(args.host, port, ssl_context = ssl_context)
    else:
        srv = IMAP(args.host, port)
        if args.starttls:
            srv.starttls(ssl_context)

    epoch = int(time.time())
    now = time.gmtime(epoch - 3 * 86400)
    month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    search_date = f"{str(now.tm_mday)}-{month[now.tm_mon-1]}-{str(now.tm_year)}"

    srv.login(args.user, password)
    print(f"logged in as {args.user} to {args.host}")

    had_errors = False
    for folder in args.folder:
        typ, data = srv.select(folder)
        if typ != "OK":
            sys.stderr.write("SELECT command failed: " + str(data[0], "utf-8") + "\n")
            had_errors = True
            continue

        typ, data = srv.uid("SEARCH", f"(BEFORE {search_date})")
        if typ != "OK":
            sys.stderr.write("SEARCH command failed: " + str(data[0], "utf-8") + "\n")
            had_errors = True
            continue

        result = str(data[0], "utf-8")
        if result == "":
            # nothing to do
            print(f"no matching messages in {folder}")
            continue

        message_uids = result.split(" ")
        if args.dry_run:
            print(f"would delete {len(message_uids)} messages from {folder}")
        else:
            print(f"deleting {len(message_uids)} messages from {folder}")

        while len(message_uids) > 0:
            to_delete = message_uids[:100]
            message_uids = message_uids[100:]
            if args.dry_run:
                print("would delete", ",".join(to_delete))
            else:
                srv.uid("STORE", ",".join(to_delete), "+FLAGS.SILENT", "\\Deleted")
                srv.expunge()

        srv.close()

    srv.logout()

    if had_errors:
        sys.exit(1)

if __name__ == '__main__':
    main()
