# Table of Contents
<details><summary>(Click me to see it.)</summary>
<ul>
<li><a href="#what-is-hoardy-mail" id="toc-what-is-hoardy-mail">What is <code>hoardy-mail</code>?</a></li>
<li><a href="#who-hoardy-mail-is-for" id="toc-who-hoardy-mail-is-for">Who <code>hoardy-mail</code> is for?</a></li>
<li><a href="#why-make-a-replacement-for-fetchmailgetmail" id="toc-why-make-a-replacement-for-fetchmailgetmail">Why make a replacement for <code>fetchmail</code>/<code>getmail</code>?</a></li>
<li><a href="#highlights" id="toc-highlights">Highlights</a></li>
<li><a href="#quickstart" id="toc-quickstart">Quickstart</a>
<ul>
<li><a href="#pre-installation" id="toc-pre-installation">Pre-installation</a></li>
<li><a href="#installation" id="toc-installation">Installation</a></li>
<li><a href="#check-that-it-works" id="toc-check-that-it-works">Check that it works</a></li>
</ul></li>
<li><a href="#recipes" id="toc-recipes">Recipes</a>
<ul>
<li><a href="#how-to-backup-all-your-mail-from-gmail-yahoo-hotmail-yandex-etc" id="toc-how-to-backup-all-your-mail-from-gmail-yahoo-hotmail-yandex-etc">How to: backup all your mail from GMail, Yahoo, Hotmail, Yandex, etc</a></li>
<li><a href="#how-to-fetch-all-your-emails-from-gmail-yahoo-hotmail-yandex-etc" id="toc-how-to-fetch-all-your-emails-from-gmail-yahoo-hotmail-yandex-etc">How to: fetch all your emails from GMail, Yahoo, Hotmail, Yandex, etc</a></li>
<li><a href="#how-to-efficiently-incrementally-backup-all-your-mail-from-gmail-yahoo-hotmail-yandex-etc" id="toc-how-to-efficiently-incrementally-backup-all-your-mail-from-gmail-yahoo-hotmail-yandex-etc">How to: efficiently incrementally backup all your mail from GMail, Yahoo, Hotmail, Yandex, etc</a></li>
<li><a href="#how-to-efficiently-incrementally-backup-millions-andor-decades-of-messages-from-gmail-yahoo-hotmail-yandex-etc" id="toc-how-to-efficiently-incrementally-backup-millions-andor-decades-of-messages-from-gmail-yahoo-hotmail-yandex-etc">How to: efficiently incrementally backup millions and/or decades of messages from GMail, Yahoo, Hotmail, Yandex, etc</a></li>
<li><a href="#what-do-i-do-with-the-resulting-maildir" id="toc-what-do-i-do-with-the-resulting-maildir">What do I do with the resulting Maildir?</a></li>
<li><a href="#can-i-use-an-mdalda-to-deliver-messages" id="toc-can-i-use-an-mdalda-to-deliver-messages">Can I use an MDA/LDA to deliver messages?</a></li>
<li><a href="#how-to-implement-fetch-backup-expire-workflow" id="toc-how-to-implement-fetch-backup-expire-workflow"><span id="workflow"/>How to: implement “fetch + backup + expire” workflow</a></li>
<li><a href="#how-to-run-hoardy-mail-in-parallel-with-fetchmail-or-similar" id="toc-how-to-run-hoardy-mail-in-parallel-with-fetchmail-or-similar">How to: run <code>hoardy-mail</code> in parallel with <code>fetchmail</code> or similar</a></li>
<li><a href="#see-also" id="toc-see-also">See also</a></li>
</ul></li>
<li><a href="#why-would-you-even-want-to-use-any-of-this-isnt-gmail-good-enough" id="toc-why-would-you-even-want-to-use-any-of-this-isnt-gmail-good-enough"><span id="why-not-gmail"/>Why would you even want to use any of this, isn’t GMail good enough?</a></li>
<li><a href="#googles-security-theater" id="toc-googles-security-theater"><span id="gmail-is-evil"/>Google’s security theater</a></li>
<li><a href="#your-emails-will-eventually-get-stolen-anyway" id="toc-your-emails-will-eventually-get-stolen-anyway"><span id="stolen-anyway"/>Your emails will eventually get stolen anyway</a></li>
<li><a href="#alternatives" id="toc-alternatives">Alternatives</a>
<ul>
<li><a href="#fetchmail-and-getmail" id="toc-fetchmail-and-getmail">fetchmail and getmail</a></li>
<li><a href="#fdm" id="toc-fdm">fdm</a></li>
<li><a href="#imapexpire" id="toc-imapexpire">IMAPExpire</a></li>
<li><a href="#offlineimap-imapsync-and-similar" id="toc-offlineimap-imapsync-and-similar">offlineimap, imapsync, and similar</a></li>
</ul></li>
<li><a href="#meta" id="toc-meta">Meta</a>
<ul>
<li><a href="#changelog" id="toc-changelog">Changelog?</a></li>
<li><a href="#todo" id="toc-todo">TODO?</a></li>
<li><a href="#license" id="toc-license">License</a></li>
<li><a href="#contributing" id="toc-contributing">Contributing</a></li>
</ul></li>
<li><a href="#usage" id="toc-usage">Usage</a>
<ul>
<li><a href="#hoardy-mail" id="toc-hoardy-mail">hoardy-mail</a>
<ul>
<li><a href="#hoardy-mail-list" id="toc-hoardy-mail-list">hoardy-mail list</a></li>
<li><a href="#hoardy-mail-count" id="toc-hoardy-mail-count">hoardy-mail count</a></li>
<li><a href="#hoardy-mail-mark" id="toc-hoardy-mail-mark">hoardy-mail mark</a></li>
<li><a href="#hoardy-mail-fetch" id="toc-hoardy-mail-fetch">hoardy-mail fetch</a></li>
<li><a href="#hoardy-mail-delete" id="toc-hoardy-mail-delete">hoardy-mail delete</a></li>
<li><a href="#hoardy-mail-for-each" id="toc-hoardy-mail-for-each">hoardy-mail for-each</a></li>
</ul></li>
<li><a href="#notes-on-usage" id="toc-notes-on-usage">Notes on usage</a></li>
<li><a href="#examples" id="toc-examples">Examples</a></li>
</ul></li>
</ul>
</details>

# What is `hoardy-mail`?

`hoardy-mail` is a tool that can help you quickly fetch your email from remote IMAP servers to a local file system (150x faster and using 150x less disk writes than [fetchmail](https://www.fetchmail.info/)/[getmail](https://github.com/getmail6/getmail6)), programmatically change flags on messages on IMAP servers (e.g. mark all messages newer than a day old in some folder as unread), delete or expire old messages from IMAP servers, and do other similar things.
It can also perform several of those operations using the same IMAP connection, sequentially, allowing for complex updates.

More formally, `hoardy-mail` is a utility that can fetch and/or perform various batch operations on messages residing on specified IMAP servers.
I.e., the overall algorithms `hoardy-mail` implements looks like this:

- for each given account on each given server:
  - login,
  - for each given folder, message filter, and action (fetch, count, flag/mark, delete, etc):
    - `SELECT` the folder,
    - `SEARCH` for messages matching the filter, and then
    - perform the action on all of them,
  - logout;
- print a short message listing all performed changes and/or encountered issues (and, optionally, generate a desktop notification for it);
- if running with `--every N` (and, optionally, `--every-add-random ADD`):
  - sleep for `N + random(0, ADD)` seconds,
  - go to the beginning;
- end.

In other words, [in comparison to other things](#alternatives), `hoardy-mail` is a powerful yet fairly simple (Keep It Stupid Simple, KISS) replacement for a combination of [fetchmail](https://www.fetchmail.info/)/[getmail](https://github.com/getmail6/getmail6) and [IMAPExpire](https://gitlab.com/mikecardwell/IMAPExpire), with some additional features, and written in pure Python.

`hoardy-mail` was previously knows as `imaparms`.

# Who `hoardy-mail` is for?

If you

- fetch all your mail into a [Maildir](https://en.wikipedia.org/wiki/Maildir) with [fetchmail](https://www.fetchmail.info/), [getmail](https://github.com/getmail6/getmail6), or similar,
- backup your index and tags/labels database with a generic file synchronization tool like [syncthing](https://syncthing.net/), [bup](https://bup.github.io/), [rsync](https://rsync.samba.org/), [git](https://git-scm.com/), or similar,
- and then, eventually, delete the old backed up mail from the original server,

then, effectively, you are using IMAP as a mail delivery protocol, not like a mail access protocol it was designed to be.

In which case you might ask yourself, wouldn't it be nice if there was a tool that could help you automate fetching of new messages and deletion of already backed up old messages from IMAP servers in such a way that **any of your own systems crashing or losing hard drives at any point in time would not lose any of your mail**?

`hoardy-mail` is a replacement for `fetchmail`/`getmail` that does this (and more, but mainly this).

# Why make a replacement for `fetchmail`/`getmail`?

Originally, I made `hoardy-mail` to get a **safe combination** of [fetchmail](https://www.fetchmail.info/) and [IMAPExpire](https://gitlab.com/mikecardwell/IMAPExpire).
The main problem there is that `fetchmail` fetches yet-*unfetched* mail, while `IMAPExpire` expires *old* mail.
When `fetchmail` gets stuck or crashes it is entirely possible for `IMAPExpire` to delete some old yet-unfetched messages.
(And replacing `fetchmail` with [getmail](https://github.com/getmail6/getmail6) will not help.)

I used to patch `fetchmail` and `IMAPExpire` to help with this, but then I decided it would be simpler to just write my own thingy instead of trying to make `fetchmail` fetch mail at decent speeds and fix all the issues making it unsafe and inconvenient to run `IMAPExpire` immediately after `fetchmail` finishes fetching mail.

After I implemented `--older-than-mtime-of`, `--older-than-timestamp-in`, etc (to automate the above in a very nice manner), `--maildir` (which tortures my SSD 150x times less than `fetchmail` does), `--every-add-random` (which improves my privacy quite a bit) options I can no longer go back.

# Highlights

[![](https://oxij.org/asset/demo/software/hoardy-mail/imaparms-v2.5.png)](https://oxij.org/asset/demo/software/hoardy-mail/imaparms-v2.5.webm)

Click the above image to see the full terminal recording video of `hoardy-mail` invocation that also runs `new-mail-hook` indexing new mail with [notmuch](https://notmuchmail.org/) ([see workflow example below](#workflow)), followed by a full-text search in Emacs UI of `notmuch`.
(`hoardy-mail` was named `imaparms` at the point the recording was made. The account data was edited out and replaced by fake GMail accounts in post-processing.)

It was recorded on a 2013-era laptop (Thinkpad X230 with Intel Core i5-3230M CPU @ 2.60GHz upgraded with 16GB RAM and Samsung 870 EVO SSD), my `notmuch` database contains ~4 millions messages, and the whole search takes only 0.25 seconds in person (but about 2 seconds in the video because rendering an [asciinema](https://github.com/asciinema/asciinema) file to gif and then compressing it into webm adds extra time between frames, so it looks much more laggy than it actually is at the end there).

`hoardy-mail` seems to be one of the fastest, if not the fastest, IMAP fetchers there is.
By default, it fetches mail more than 150 times faster and using 150 less disk writes than [fetchmail](https://www.fetchmail.info/) (and [getmail](https://github.com/getmail6/getmail6)) while keeping to all the usual "only mark/delete messages on the server after they are `fsync`ed to disk" guarantees.

If your IMAP server supports long enough command lines, your system can do SSL and your hard drive can flush data fast enough, then you can saturate a gigabit Ethernet link with `hoardy-mail`.

Also, `hoardy-mail` will not lose any of your mail regardless of network connections failing unexpectedly, your IMAP server generating errors at unexpected times, other simultaneous IMAP clients making incompatible changes that could lead to future data loss, your disk failing while `hoardy-mail` tries to `fsync` your data, you calling `hoardy-mail` with wrong command line arguments, ...
In short, `hoardy-mail` is very careful about things.

Also, `hoardy-mail` has a nice CLI UI and it can also generate desktop notifications (via `notify-send`) about things breaking or just happening.

Also, since bootstrapping into a setup similar to the one described above requires querying into actual IMAP folder names and mass changes to flags on IMAP server-side, `hoardy-mail` provides subcommands for that too.

See the "subcommands" subsection of the [usage section](#usage) for the list available of subcommands and explanations of what they do.

# Quickstart

## Pre-installation

- Install `Python 3`:

  - On a Windows system: [Download Python installer from the official website](https://www.python.org/downloads/windows/), run it, **set `Add python.exe to PATH` checkbox**, then `Install` (the default options are fine).
  - On a conventional POSIX system like most GNU/Linux distros and MacOS X: Install `python3` via your package manager. Realistically, it probably is installed already.

## Installation

- On a Windows system:

  Open `cmd.exe` (press `Windows+R`, enter `cmd.exe`, press `Enter`), install this with
  ```bash
  python -m pip install hoardy-mail
  ```
  and run as
  ```bash
  python -m hoardy_mail --help
  ```

- On a POSIX system or on a Windows system with Python's `/Scripts` added to `PATH`:

  Open a terminal/`cmd.exe`, install this with
  ```bash
  pip install hoardy-mail
  ```
  and run as
  ```bash
  hoardy-mail --help
  ```

- Alternatively, for light development (without development tools, for those see `nix-shell` below):

  Open a terminal/`cmd.exe`, `cd` into this directory, then install with
  ```bash
  python -m pip install -e .
  # or
  pip install -e .
  ```
  and run as:
  ```bash
  python -m hoardy_mail --help
  # or
  hoardy-mail --help
  ```

- Alternatively, on a system with [Nix package manager](https://nixos.org/nix/)

  ```bash
  nix-env -i -f ./default.nix
  hoardy-mail --help
  ```

- Alternatively, to replicate my development environment:

  ```bash
  nix-shell ./default.nix --arg developer true
  ```

## Check that it works

```bash
hoardy-mail count --host imap.gmail.com --user account@gmail.com --pass-pinentry
```

# Recipes

`hoardy-mail` is designed to be used as a IMAP-server-to-local-Maildir [Mail Delivery Agent](https://en.wikipedia.org/wiki/Message_delivery_agent) (MDA) that makes the IMAP server in question store as little mail as possible while preventing data loss.

Which is to say, the main use case `hoardy-mail` is made for is as follows:

- you `touch ~/.last-mail-backup.new` or some such,
- you fetch your mail to a local Maildir with `hoardy-mail fetch` subcommand (which does what `fetchmail --softbounce --invisible --norewrite --mda MDA` does but much faster), then
- backup your Maildir with `syncthing`/`bup`/`rsync`/`git`/etc to make at least one other copy somewhere, and then,
- after your backup succeeds, you do `mv ~/.last-mail-backup.new ~/.last-mail-backup` or some such,
- you then run `hoardy-mail delete --older-than-mtime-of ~/.last-mail-backup --older-than 3` or some such to expire old already-fetched and backed up messages from the server (I prefer to expire messages `--older-than` some number of intervals between backups, just to be safe, but if you do backups directly after the `fetch`, or you like to live dangerously, you could delete old messages immediately),
- you can then do `hoardy-mail for-each` to run both `fetch` and `delete` on the same connection, and run the backup process asynchronously, and it will still work as expected,
- when/if your account get cracked/hacked the attacker only gets your unfetched mail (+ configurable amount of yet to be removed messages), which is much better than them getting the whole last 20 years or whatever of your correspondence. (If your personal computer gets compromised enough, attackers will eventually get everything anyway, so deleting old mail from servers does not make things worse. But see some [more thoughts on this below](#stolen-anyway).)

This section starts with simple example invocations of `hoardy-mail`, builds up to the above use case, and then shows how to do even more advanced things.

## How to: backup all your mail from GMail, Yahoo, Hotmail, Yandex, etc

`hoardy-mail` is not *intended* as an *IMAP mirroring tool*, it is intended to be used as a *Mail Delivery Agent with automatic expiration of old server-side mail*, i.e. a better replacement for `fetchmail`+`IMAPExpire` combination.
If you want to keep a synchronized copy of your mail locally and on your mail server without sacrificing any flags, you should use [offlineimap](https://github.com/OfflineIMAP/offlineimap), [imapsync](https://github.com/imapsync/imapsync), or something similar instead.

However, `hoardy-mail` can be used for efficient incremental backups of IMAP server data if you are willing to sacrifice either of `SEEN` or `FLAGGED` ("starred") IMAP flags for it.
Also, making email backups with `hoardy-mail` is pretty simple, [useful](#why-not-gmail), and illustrative, so a couple of examples follow.

## How to: fetch all your emails from GMail, Yahoo, Hotmail, Yandex, etc

The following will fetch all messages from all the folders on the server (without changing message flags on the server side) and just put them all into `~/Mail/backup` Maildir (creating it if it does not exists).

```bash
# backup all your mail from GMail
hoardy-mail fetch --host imap.gmail.com --user account@gmail.com --pass-pinentry \
  --maildir ~/Mail/backup --all-folders --any-seen
```

For GMail you will have to create and use application-specific password, which requires enabling 2FA, [see below for more info](#gmail-is-evil).

Also, if you have a lot of mail, this will be very inefficient, as it will try to re-download everything again if it ever gets interrupted.

## How to: efficiently incrementally backup all your mail from GMail, Yahoo, Hotmail, Yandex, etc

To make the above efficient you have to sacrifice either `SEEN` or `FLAGGED` IMAP flags to allow `hoardy-mail` to track which messages are yet to be fetched, i.e. either:

```bash
# mark all messages as UNSEEN
hoardy-mail mark --host imap.gmail.com --user account@gmail.com --pass-pinentry \
  --folder "[Gmail]/All Mail" unseen

# fetch UNSEEN and mark as SEEN as you go
# this can be interrrupted and restarted and it will continue from where it left off
hoardy-mail fetch --host imap.gmail.com --user account@gmail.com --pass-pinentry \
  --maildir ~/Mail/backup --folder "[Gmail]/All Mail" --unseen
```

or

```bash
# mark all messages as UNFLAGGED
hoardy-mail mark --host imap.gmail.com --user account@gmail.com --pass-pinentry \
  --folder "[Gmail]/All Mail" unflagged

# similarly
hoardy-mail fetch --host imap.gmail.com --user account@gmail.com --pass-pinentry \
  --maildir ~/Mail/backup --folder "[Gmail]/All Mail" --any-seen --unflagged
```

This, of course, means that if you open or "mark as read" a message in GMail's web-mail UI while using `--unseen`, or mark it as flagged ("star") it there while using `--unflagged`, `hoardy-mail` will ignore the message on the next `fetch`.

## How to: efficiently incrementally backup millions and/or decades of messages from GMail, Yahoo, Hotmail, Yandex, etc

In cases where you want to fetch *millions* of messages spanning *decades*, you'll probably want invoke `hoardy-mail fetch` multiple times with progressively smaller ` --older-than` arguments so that IMAP `SEARCH` command responses will be smaller to re-fetch if the process gets interrupted, i.e.:

```bash
# mark all messages as UNSEEN
hoardy-mail mark --host imap.gmail.com --user account@gmail.com --pass-pinentry \
  --folder "[Gmail]/All Mail" unseen

for n in 10 5 3 2 1; do
    echo "fetching mail older than $n years..."
    hoardy-mail fetch --host imap.gmail.com --user account@gmail.com --pass-pinentry \
      --maildir ~/Mail/backup --folder "[Gmail]/All Mail" --unseen \
      --older-than $((365*n))
done
```

## What do I do with the resulting Maildir?

You feed it into [sup](https://sup-heliotrope.github.io/), [notmuch](https://notmuchmail.org/), or similar, as discussed [this section](#why-not-gmail), and it gives you a GMail-like UI with full-text search and tagging, but with faster search, with no cloud storage involvement, and it works while you are offline.

Or you just repeat this mirroring on a schedule so that [when/if GMail decides to take your mail hostage](#why-not-gmail) you will be prepared to switch.

## Can I use an MDA/LDA to deliver messages?

Yes, just replace `--maildir DIRECTORY` with `--mda MDA`.
For instance, for `maildrop` Mail Delivery Agent (also knows as Local Delivery Agent, LDA, as it is an MDA that gets used to deliver messages to same machine) from [Courier Mail Server project](https://www.courier-mta.org/) --- which is a commodity MDA/LDA with the simplest setup, that I know of --- the simplest `hoardy-mail fetch` invocation looks like this:

```bash
### setup: do once
mkdir -p ~/Mail/backup/{new,cur,tmp}

cat > ~/.mailfilter << EOF
DEFAULT="\$HOME/Mail/backup"
EOF

# backup all your mail from GMail
hoardy-mail fetch --host imap.gmail.com --user account@gmail.com --pass-pinentry \
  --mda maildrop --all-folders --any-seen
```

Of course, you can use any other MDA/LDA you want, e.g.:

- [fdm](https://github.com/nicm/fdm) can function as an LDA and it is also pretty simple to setup;

- deliveries to an SMTP server can be done by using [msmtp](https://marlam.de/msmtp/).

## <span id="workflow"/>How to: implement "fetch + backup + expire" workflow

The intended workflow described [above](#recipes) looks like this (note that this uses `--older-than-timestamp-in` instead of `--older-than-mtime-of`, since this is a bit safer):

```bash
### setup: do once
echo 0 > ~/.rsync-last-mail-backup-timestamp

cat > ~/bin/new-mail-hook << EOF
#!/bin/sh -e
# index new mail
notmuch new

# auto-tagging rules go here

# backup
backup_start=\$(date +%s)
if rsync -aHAX ~/Mail /disk/backup ; then
    echo "\$backup_start" > ~/.rsync-last-mail-backup-timestamp
fi
EOF
chmod +x ~/bin/new-mail-hook

# optionally, if needed
# hoardy-mail mark ... --folder "[Gmail]/All Mail" unseen
```

```bash
### repeatable part

# every hour, fetch new and expire old mail from two GMail accounts,
# generate new desktop notifications with `notify-send` if some of the commands fail
hoardy-mail for-each --every 3600 --notify-failure \
    --host imap.gmail.com \
      --user account@gmail.com --passcmd "pass show mail/account@gmail.com" \
      --user another@gmail.com --passcmd "pass show mail/another@gmail.com" \
  -- \
    fetch --folder "[Gmail]/All Mail" --maildir ~/Mail/INBOX --new-mail-cmd new-mail-hook \; \
    fetch --folder "[Gmail]/Spam" --maildir ~/Mail/spam  \; \
    delete --folder "[Gmail]/All Mail" --folder "[Gmail]/Spam" --folder "[Gmail]/Trash" \
      --older-than-timestamp-in ~/.rsync-last-mail-backup-timestamp \
      --older-than 7

# note how new spam does not invoke `new-mail-hook`
```

You can check your command lines by running with `--very-dry-run` option, for the command above it prints:

```
# every 3600 seconds, for each of
... user account@gmail.com on host imap.gmail.com port 993 (SSL)
... user another@gmail.com on host imap.gmail.com port 993 (SSL)
# do
... in '[Gmail]/All Mail': search (UNSEEN), perform fetch, mark them as SEEN
... in '[Gmail]/Spam': search (UNSEEN), perform fetch, mark them as SEEN
... in '[Gmail]/All Mail', '[Gmail]/Spam', '[Gmail]/Trash': search (SEEN BEFORE 1-Jan-1970) {dynamic}, perform delete
```

Personally, I have a separate script `exec`-invoking `hoardy-mail` (see the terminal recording above) for each mail service I use, my window manager spawns a terminal window with `tmux attach -t subs` on startup while I have the following at the end of my `~/.tmux.conf`:

```
# create new session named "subs" with the first window named "shell"
new-session -s subs -n shell
# set remain-on-exit for all windows in this session by default
set-option  -t subs -g remain-on-exit on
# add new windows running hoardy-mail instances
new-window -t :2 -n mail mail-mine
new-window -t :3 -n gmail mail-gmail
# ... and so on
```

This way, if I need to fetch mail from one of the services immediately (e.g. for 2FA tokens sent via email) I just navigate to the respective `tmux` window and hit `Ctrl+C` there.

## How to: run `hoardy-mail` in parallel with `fetchmail` or similar

You can run `hoardy-mail fetch` with `--any-seen --unflagged` command line options instead of the implied `--unseen --any-flagged` options, which will make it use the `FLAGGED` IMAP flag instead of the `SEEN` IMAP flag to track state, allowing you to run it simultaneously with tools that use the `SEEN` flag, like `fetchmail`, `getmail`, or just another instance of `hoardy-mail` (using the other flag).

I.e. you can use it to run two instances of `hoardy-mail` on two separate machines and only expire old mail from the server after it was successfully backed up onto both machines.
Or, if you are really paranoid, you can this feature to check files produced by `fetchmail` and `hoardy-mail fetch` against each other and then simply delete duplicated files.

Running in parallel with `fetchmail` using `maildrop` MDA for both `fetchmail` and `hoardy-mail` can be implemented like this:

```bash
### setup: do once
echo 0 > ~/.rsync-last-mail-backup-timestamp

mkdir -p ~/Mail/INBOX/{new,cur,tmp}
mkdir -p ~/Mail/spam/{new,cur,tmp}
mkdir -p ~/Mail/INBOX.secondary/{new,cur,tmp}

cat > ~/.mailfilter << EOF
DEFAULT="\$HOME/Mail/INBOX"
EOF

cat > ~/.mailfilter-spam << EOF
DEFAULT="\$HOME/Mail/spam"
EOF

cat > ~/.mailfilter-secondary << EOF
DEFAULT="\$HOME/Mail/INBOX.secondary"
EOF

cat > ~/bin/new-mail-hook-dedup << EOF
#!/bin/sh -e
# deduplicate
jdupes -o time -O -rdN ~/Mail/INBOX ~/Mail/INBOX.secondary

# continue as usual
exec ~/bin/new-mail-hook
EOF
chmod +x ~/bin/new-mail-hook-dedup

secondary_common=(--host imap.gmail.com \
  --user account@gmail.com --passcmd "pass show mail/account@gmail.com" \
  --user another@gmail.com --passcmd "pass show mail/another@gmail.com")

# prepare by unflagging all messages
hoardy-mail mark "${secondary_common[@]}" --folder "INBOX" unflagged
```

```bash
### repeatable part
# run fetchmail daemon as usual, fetching new mail into the secondary maildir every hour
fetchmail --mda "maildrop ~/.mailfilter-secondary" -d 3600

# every 15 minutes
# - fetch new mail using FLAGGED flag for tracking state from "[Gmail]/All Mail",
# - fetch new mail using SEEN flag for tracking state from "[Gmail]/Spam",
# - expire old backed up messages marked both SEEN (by fetchmail) and FLAGGED (by hoardy-mail) from "[Gmail]/All Mail",
# - expire old backed up messages marked as SEEN (by hoardy-mail) from "[Gmail]/Spam",
# - clean any messages older than 7 days (regardless of their flags) from "[Gmail]/Trash".
# - generate new desktop notifications with `notify-send` if some of the commands fail
hoardy-mail for-each --every 900 --notify-failure \
    "${secondary_common[@]}" \
  -- \
    fetch --folder "[Gmail]/All Mail" --mda maildrop --new-mail-cmd new-mail-hook --any-seen --unflagged \; \
    fetch --folder "[Gmail]/Spam" --mda "maildrop ~/.mailfilter-spam" \; \
    delete --seen --flagged --folder "[Gmail]/All Mail" \
      --older-than-timestamp-in ~/.rsync-last-mail-backup-timestamp \
      --older-than 7 \; \
    delete "[Gmail]/Spam" \
      --older-than-timestamp-in ~/.rsync-last-mail-backup-timestamp \
      --older-than 7 \; \
    delete --any-seen --any-flagged --folder "[Gmail]/Trash" \
      --older-than 7

# note how new spam does not invoke `new-mail-hook`
```

## See also

See the [usage section](#usage) for explanation of used command line options.

See the [examples section](#examples) for more examples.

# <span id="why-not-gmail"/>Why would you even want to use any of this, isn't GMail good enough?

Remember the time when YouTube and Facebook showed you only the posts of people you were subscribed to?
After they locked your in by becoming a monopoly by providing fairly good social networking services for free for years (selling under cost is textbook monopolistic behaviour) they started showing "promoted" posts (i.e. advertisements) in your feed so that they could provide cheap and very effective advertisement services for companies at your expense.
Then, when advertisers were locked in, they started fleecing them too.

Now your subscriptions are just one of the inputs to their *algorithms that are designed to make you waste as much time as possible* on their platforms (*while keeping you satisfied or addicted just enough so that you wouldn't just leave*), and advertisers' ad postings are just inputs to their algorithms that are designed to waste as much of the advertiser's money as possible (being just effective enough to make them spend more).

(The process which Cory Doctorow calls "Enshittification".)

Remember the time when most people run their own mail servers or had their employers run them and you yourself got to decide which messages should go to `INBOX` and which should be marked as spam?
Today, Google provides email services for free, and so >70% of all e-mails originate from or get delivered to Google servers (GMail, GMail on custom domains, corporate GMail).
Now it's Google who decides which messages you get to see and which vanish into the void without a trace.

Which, as a recipient, is highly annoying if you frequently get useful mail that GMail marks as spam or just drops (happens all the time to me).
And, as a sender, is highly annoying when you need to send lots of mail.
Just go look up "Gmail Email Limits" (on a search engine other than Google).
It's a rabbit hole with lots of ad-hoc rules on just how much mail you can send before GMail decides to just drop your messages, yes, *drop*, not mark as spam, not reject, **they will drop your mail and tell neither the sender nor the recipient anything at all**.

Moreover, they are now working towards making their `INBOX` into an *algorithmically generated feed with "important" messages being shown first*.
It's easy to see where this is going.

Luckily, [while Google is working hard to discourage you from using and/or make open mail protocols unusable](#gmail-is-evil), IMAP is still #1 protocol for accessing and managing mail, and setting up your own mail server gets easier every year, so they can't just stop supporting it just yet (but they are doing their best).

But, objectively, GMail --- when it works --- is a very nice [Mail User Agent](https://en.wikipedia.org/wiki/Mail_user_agent) (aka MUA, aka email client, aka mail app) with an integrated full-text search engine and a labeling system.

Meanwhile, other modern MUAs like [Thunderbird](https://www.thunderbird.net/), [Sylpheed](https://sylpheed.sraoss.jp/en/), or [K-9 Mail](https://k9mail.app/) are designed to be IMAP and SMTP clients *first*, full-text search and tagging/labeling systems *second* (if at all).
Which is to say, they suck at searching and tagging mail.
Especially, since doing those things over IMAP is annoyingly slow, especially when your IMAP server is GMail which very much does not want you to use IMAP (after all, with a MUA working over IMAP, it's the MUA that decides how to sort and display your `INBOX`, not Google, and they hate they can't turn the order of messages in your `INBOX` into something they can sell).

However, there exists a bunch of MUAs that can do full-text mail search and tagging so well and so blazingly fast that they leave GMail in the dust (from a technical standpoint, given an index, full-text search >10x faster than GMail on a single-core of 2012-era laptop with an SSD is pretty easy to archive, simply because your SSD is much closer to you than GMail's servers).

Examples of such awesome MUAs that I'm aware of, in the order from simplest to hardest to setup:

- [sup](https://sup-heliotrope.github.io/) ([also this](https://github.com/sup-heliotrope/sup)) as both MUA and mail indexer,
- [alot](https://github.com/pazz/alot) as MUA + [notmuch](https://notmuchmail.org/) as mail indexer,
- Emacs UI of [notmuch](https://notmuchmail.org/) as MUA + [notmuch](https://notmuchmail.org/) as mail indexer,
- [mutt](https://en.wikipedia.org/wiki/Mutt_(e-mail_client)) as MUA + [notmuch](https://notmuchmail.org/) as mail indexer.

However, to use these awesome MUAs you need to download your mail and save it in [Maildir format](https://en.wikipedia.org/wiki/Maildir) on your hard disk first.

Which is where `hoardy-mail` and similar tools like [fetchmail](https://www.fetchmail.info/), [getmail](https://github.com/getmail6/getmail6), [offlineimap](https://github.com/OfflineIMAP/offlineimap), [imapsync](https://github.com/imapsync/imapsync), and etc come in.

Also, if GMail suddenly decides to take your mail hostage by locking you into their web-mail and disabling IMAP access, [which seems more and more plausible every year](#gmail-is-evil), having a local copy of most of your mail will make it much easier to switch away.
(Seems unrealistic to you?
This actually happened to me with one of the email providers I used before (not GMail, *not yet*).
They basically tried to force me to go through a KYC procedure to allow me to continue using IMAP, but because I had local backups, I just switched all the services that referenced that email address to something else and simply stopped using their service.
Are you sure Google wouldn't do this?)

See ["The Homely Mutt" by Steve Losh](https://stevelosh.com/blog/2012/10/the-homely-mutt/) for a long in-detail explanation on how this setup in general is supposed to work.
It describes a setup specifically tailored for `mutt` + `notmuch` + `offlineimap` + `msmtp` and the actual configs there are somewhat outdated (it was written in 2012) and much more complex than what you would need with, e.g. `sup` + `hoardy-mail` + `msmtp`, but it gives a good overview of the idea in general.
Functionally, `hoardy-mail` takes place `offlineimap` in that article.

Personally, I use `notmuch` with Emacs, which requires almost no setup if you have a well-configured Emacs already (and effectively infinite amounts of setup otherwise).

Also, see ["Sup" article on ArchWiki](https://wiki.archlinux.org/title/Sup) for how to setup `sup`.

(Also, in theory, [Thunderbird](https://www.thunderbird.net/) also supports operation over Maildir, but that feature is so buggy it's apparently disabled by default at the moment.)

# <span id="gmail-is-evil"/>Google's security theater

GMail docs say that IMAP and SMTP are "legacy protocols" and are "insecure".
Which, sure, they could be, if you reuse passwords.
But them implying that everything except their own web-mail UI is "insecure" is kinda funny given that they do use SMTP to transfer mail between servers and [signing in with Google prompts](https://web.archive.org/web/20230702050207/https://support.google.com/accounts/answer/7026266?co=GENIE.Platform%3DAndroid&hl=en) exists.
I.e. you can borrow someone's phone, unlock it (passcode? peek over their shoulder or just get some video surveillance footage of them typing it in public; fingerprint? they leave their fingerprints all over the device itself, dust with some flour, take a photo, apply some simple filters, 3D-print the result, this actually takes ~3 minutes to do if you know what you are doing), ask Google to authenticate via prompt.
Done, you can login into everything with no password needed.
And Google appears to give no way to disable Google prompts if your account has an attached Android device.
Though, you can make Google prompts ask for a password too, but that feature needs special setup.
Meanwhile, "legacy" passwords are not secure, apparently?

So to use `hoardy-mail` with GMail you will have to enable 2FA in your account settings and then add an application-specific password for IMAP access.
I.e., instead of generating a random password and giving it to Google (while storing it in a password manager that feeds it to `hoardy-mail`), you ask Google to generate a random password for you and use that with `hoardy-mail`.

To enable 2FA, even for very old accounts that never used anything phone or Android-related, for no rational reasons, GMail requires specifying a working phone number that can receive SMS.
Which you can then simply remove after you copied your OTP secret into an authenticator of your choice.
Sorry, why did you need the phone number, again?

Ah, well, Google now knows it and will be able track your movements by buying location data from your network operator.
Thank you very much.

In theory, as an alternative to application-specific passwords, you can setup OAuth2 and update tokens automatically with [mailctl](https://github.com/pdobsan/mailctl), but Google will still ask for your phone number to set it up, and OAuth2 renewal adds another point of failure without really adding any security if you store your passwords in a password manager and use `--passcmd` option described below to feed them into `hoardy-mail`.

That is to say, I don't use OAuth2, which is why `hoardy-mail` does not support OAuth2.

# <span id="stolen-anyway"/>Your emails will eventually get stolen anyway

Note that [Snowden revelations](https://en.wikipedia.org/wiki/Global_surveillance_disclosures_(2013%E2%80%93present)) mean that Google and US Government store copies of all of your correspondence since 2007-2009 (it depends on your mail provider) even if you delete everything from all the servers.

And they wiretap basically all the traffic going though international Internet exchanges because they wiretap all underwater cables.
Simply because they can, apparently?
(If you think about it, there is absolutely no point to doing this if you are trying to achieve their stated signal-intelligence goals.
Governments and organized crime use one-time-pads since 1950s.
AES256 + 32 bytes of shared secret (+ 8 bytes of plain-text session key + 4 bytes of plain-text IV) + some simple [steganography](https://en.wikipedia.org/wiki/Steganography) and even if the signal gets discovered, no quantum-computer will ever be able to break it, no research into [quantum-safe cryptography](https://en.wikipedia.org/wiki/Post-quantum_cryptography) needed.
So, clearly, this data collection only works against private citizens and civil society which have no ways to distribute symmetric keys and thus have to use public-key cryptography.)

Globally, >70% of all e-mails originate from or get delivered to Google servers (GMail, GMail on custom domains, corporate GMail).

Most e-mails never gets E2E-encrypted at all, `(100 - epsilon)`% (so, basically, 100%) of all e-mails sent over the Internet never get encrypted with quantum-safe cryptography in-transit.

So, eventually, US Government will get plain-text for almost everything you ever sent (unless you are a government official, work for well-organized crime syndicate, or you and all your friends are really paranoid).

Which means that, eventually, all that mail will get stolen.

So, in the best case scenario, a simple relatively benign blackmail-everyone-you-can-to-get-as-much-money-as-possible AI will be able organize a personal WikiLeaks-style breach, for every single person on planet Earth.
No input from nefarious humans interested in exploiting *personally you* required.
After all, you are not that interesting, so you have nothing to fear, nothing to hide, and you certainly did not write any still-embarrassing e-mails when you were 16 years old and did not send any nudes of yourself or anyone else to anyone (including any doctors, during the pandemic) ever.

It would be glorious, wouldn't it?

(Seriously, abstractly speaking, I'm kinda interested in civilization-wide legal and cultural effects of *every embarrassing, even slightly illegal and/or hypocritical thing every person ever did* relentlessly programmatically exploited as blackmail or worse.
Non-abstractly speaking, why exactly do governments spend public money to make this possible?
After all, hoarding of exploitable material that made a disaster after being stolen worked so well with [EternalBlue](https://en.wikipedia.org/wiki/EternalBlue), and that thing was a fixable bug, which leaked blackmail is not.)

That is to say, as a long-term defense measure, this tool is probably useless.
All your mail will get leaked eventually, regardless.
Against random exploitations of your mail servers `hoardy-mail` is perfect.

Also, `hoardy-mail` is a very nice fast mail fetcher, regardless of all of this.

# Alternatives

## [fetchmail](https://www.fetchmail.info/) and [getmail](https://github.com/getmail6/getmail6)

`hoardy-mail fetch`

- fetches your mail more than 150 times faster by default (both `fetchmail` and `getmail` fetch and mark messages one-by-one, incurring huge network latency overheads, `hoardy-mail fetch` does it in (configurable) batches);
- generates ~150 times less disk writes (`hoardy-mail fetch --maildir` `fsync`s messages to disk in (configurable) batches) improving performance and longevity of your SSD;
- fetches messages out-of-order to try and maximize `messages/second` metric when it makes sense (i.e. it temporarily delays fetching of larger messages if many smaller ones can be fetched instead) so that you could efficiently index your mail in parallel with fetching;
- only does deliveries to a local Maildir (with `hoardy-mail fetch --maildir` option) or [MDA/LDA](https://en.wikipedia.org/wiki/Message_delivery_agent) (with `hoardy-mail fetch --mda` option, which does the same thing as `fetchmail --mda` and `getmail`'s `MDA_external` options), deliveries over SMTP are not and will never be supported (if you want this you can just use [msmtp](https://marlam.de/msmtp/) with `hoardy-mail fetch --mda`); thus, `hoardy-mail`
- is much simpler to use when fetching to a local Maildir as it needs no configuration to fetch messages as-is without modifying any headers, thus fetching the same messages twice will produce identical files (which is not true for `fetchmail`, `hoardy-mail fetch --mda MDA` is roughly equivalent to `fetchmail --softbounce --invisible --norewrite --mda MDA`);
- probably will not work with most broken IMAP servers (`fetchmail` has lots of workarounds for server bugs, `hoardy-mail fetch` does not);
- is written in Python (like `getmail`) instead of C (like `fetchmail`);
- has other subcommands, not just `hoardy-mail fetch`.

## [fdm](https://github.com/nicm/fdm)

[A better explanation of what fdm does](https://wiki.archlinux.org/title/fdm).

`hoardy-mail fetch`

- uses server-side message flags to track state instead of keeping a local database of fetched UIDs;
- fetches messages out-of-order to try and maximize `messages/second` metric;
- generates ~150 times less disk writes;
- does not do any filtering, offloads that to MDA/LDA;
- is written in Python instead of C;
- has other subcommands, not just `hoardy-mail fetch`.

## [IMAPExpire](https://gitlab.com/mikecardwell/IMAPExpire)

`hoardy-mail delete`

- allows all UNICODE characters except `\n` in passwords/passphrases (yes, including spaces, quotes, etc);
- provides a bunch of options controlling message selection and uses `--seen` option by default for destructive actions, so you won't accidentally delete any messages you have not yet fetched even if your fetcher got stuck/crashed;
- provides GMail-specific options;
- is written in Python instead of Perl and requires nothing but the basic Python install, no third-party libraries needed;
- has other subcommands, not just `hoardy-mail delete`.

## [offlineimap](https://github.com/OfflineIMAP/offlineimap), [imapsync](https://github.com/imapsync/imapsync), and similar

- `hoardy-mail fetch` does deliveries from an IMAP server to your Maildir/MDA/LDA instead of trying to synchronize state between some combinations of IMAP servers and local Maildirs (i.e. for `hoardy-mail fetch` your IMAP server is always the source, never the destination), which might seem like a lack of a feature at first, but
  - `hoardy-mail` lacking two-way sync also prevents you from screwing up your `hoardy-mail` invocation options or restarting the program at an inopportune time and losing all your mail on the server on the next sync as a result (like you can with `offlineimap`),
  - i.e., with `hoardy-mail` you won't ever lose any messages on the server if you never run `hoardy-mail delete`, and if you do run `hoardy-mail delete`, `hoardy-mail`'s defaults try their best to prevent you from deleting any mail you probably did not mean to delete;
- consequently, `hoardy-mail` is much simpler to use as the complexity of its configuration is proportional to the complexity of your usage;
- `hoardy-mail fetch` generates ~150 times less disk writes;
- `hoardy-mail` has other subcommands, not just `hoardy-mail fetch`.

# Meta

## Changelog?

See [`CHANGELOG.md`](./CHANGELOG.md).

## TODO?

See the [bottom of `CHANGELOG.md`](./CHANGELOG.md#todo).

## License

[GPLv3](./LICENSE.txt)+, some small library parts are MIT.

## Contributing

Contributions are accepted both via GitHub issues and PRs, and via pure email.
In the latter case I expect to see patches formatted with `git-format-patch`.

If you want to perform a major change and you want it to be accepted upstream here, you should probably write me an email or open an issue on GitHub first.

# Usage

## hoardy-mail

A handy Swiss-army-knife-like utility for fetching and performing batch operations on messages residing on IMAP servers.
I.e., for each specified IMAP server: login, perform specified actions on all messages matching specified criteria in all specified folders, log out.

- options:
  - `--version`
  : show program's version number and exit
  - `-h, --help`
  : show this help message and exit
  - `--markdown`
  : show help messages formatted in Markdown
  - `-q, --quieter`
  : be less verbose

- debugging:
  - `--very-dry-run`
  : verbosely describe what the given command line would do and exit
  - `--dry-run`
  : perform a trial run without actually performing any changes
  - `--debug`
  : dump IMAP conversation to stderr

- hooks:
  - `--notify-success`
  : generate notifications (via `notify-send`) describing server-side changes, if any, at the end of each program cycle; most useful if you run `hoardy-mail` in background with `--every` argument in a graphical environment
  - `--success-cmd CMD`
  : shell command to run at the end of each program cycle that performed some changes on the server, i.e. a generalized version of `--notify-success`; the spawned process will receive the description of the performed changes via stdin; can be specified multiple times
  - `--notify-failure`
  : generate notifications (via `notify-send`) describing recent failures, if any, at the end of each program cycle; most useful if you run `hoardy-mail` in background with `--every` argument in a graphical environment
  - `--failure-cmd CMD`
  : shell command to run at the end of each program cycle that had some of its command fail, i.e. a generalized version of `--notify-failure`; the spawned process will receive the description of the failured via stdin; can be specified multiple times

- authentication settings:
  - `--auth-allow-login`
  : allow the use of IMAP `LOGIN` command (default)
  - `--auth-forbid-login`
  : forbid the use of IMAP `LOGIN` command, fail if challenge-response authentication is not available
  - `--auth-allow-plain`
  : allow passwords to be transmitted over the network in plain-text
  - `--auth-forbid-plain`
  : forbid passwords from being transmitted over the network in plain-text, plain-text authentication would still be possible over SSL if `--auth-allow-login` is set (default)

- server connection:
  can be specified multiple times

  - `--plain`
  : connect via plain-text socket
  - `--ssl`
  : connect over SSL socket (default)
  - `--starttls`
  : connect via plain-text socket, but then use STARTTLS command
  - `--host HOST`
  : IMAP server to connect to (required)
  - `--port PORT`
  : port to use (default: 143 for `--plain` and `--starttls`, 993 for `--ssl`)
  - `--timeout TIMEOUT`
  : socket timeout, in seconds (default: 60)

- authentication to the server:
  either of `--pass-pinentry`, `--passfile`, or `--passcmd` are required; can be specified multiple times

  - `--user USER`
  : username on the server (required)
  - `--pass-pinentry`
  : read the password via `pinentry`
  - `--passfile PASSFILE, --pass-file PASSFILE`
  : file containing the password on its first line
  - `--passcmd PASSCMD, --pass-cmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- batching settings:
  larger values improve performance but produce longer IMAP command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen

  - `--store-number INT`
  : batch at most this many message UIDs in IMAP `STORE` requests (default: 150)
  - `--fetch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` metadata requests (default: 150)
  - `--batch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: 150)
  - `--batch-size INT`
  : batch `FETCH` at most this many bytes of RFC822 messages at once; RFC822 messages larger than this will be fetched one by one (i.e. without batching); essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted while `hoardy-mail` is batching (default: 4194304)

- polling/daemon options:
  - `--every INTERVAL`
  : repeat the command every `INTERVAL` seconds;
    `hoardy-mail` will do its best to repeat the command precisely every `INTERVAL` seconds even if the command involes `fetch`ing of new messages and `--new-mail-cmd` invocations take different time each cycle; if program cycle takes more than `INTERVAL` seconds or `INTERVAL < 60` then `hoardy-mail` would sleep for `60` seconds either way,
    this prevents the servers accessed earlier in the cycle from learning about the amount of new data fetched from the servers accessed later in the cycle
  - `--every-add-random ADD`
  : sleep a random number of seconds in [0, ADD] range (uniform distribution) before each `--every` cycle, including the very first one (default: 60);
    if you set it large enough to cover the longest single-server `fetch`, it will prevent any of the servers learning anything about the data on other servers;
    if you run `hoardy-mail` on a machine that disconnects from the Internet when you go to sleep and you set it large enough, it will help in preventing the servers from collecting data about your sleep cycle

- message search filters:
  - `--older-than DAYS`
  : operate on messages older than this many days, **the date will be rounded down to the start of the day; actual matching happens on the server, so all times are server time**; e.g. `--older-than 0` means older than the start of today by server time, `--older-than 1` means older than the start of yesterday, etc; can be specified multiple times, in which case the earliest (the most old) date on the list will be chosen
  - `--newer-than DAYS`
  : operate on messages newer than this many days, a negation of`--older-than`, so **everything from `--older-than` applies**; e.g., `--newer-than -1` will match files dated into the future, `--newer-than 0` will match files delivered from the beginning of today, etc; can be specified multiple times, in which case the latest (the least old) date on the list will be chosen
  - `--older-than-timestamp-in PATH`
  : operate on messages older than the timestamp (in seconds since UNIX Epoch) recorded on the first line of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above
  - `--newer-than-timestamp-in PATH`
  : operate on messages newer than the timestamp (in seconds since UNIX Epoch) recorded on the first line of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above
  - `--older-than-mtime-of PATH`
  : operate on messages older than `mtime` of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above
  - `--newer-than-mtime-of PATH`
  : operate on messages newer than `mtime` of this PATH, rounded as described above; can be specified multiple times, in which case it will processed as described above
  - `--from ADDRESS`
  : operate on messages that have this string as substring of their header's FROM field; can be specified multiple times
  - `--not-from ADDRESS`
  : operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times

- subcommands:
  - `{list,count,mark,fetch,delete,for-each}`
    - `list`
    : list all available folders on the server, one per line
    - `count`
    : count how many matching messages each specified folder has
    - `mark`
    : mark matching messages in specified folders in a specified way
    - `fetch`
    : fetch matching messages from specified folders, put them into a Maildir or feed them to a MDA/LDA, and then mark them in a specified way if it succeeds
    - `delete`
    : delete matching messages from specified folders
    - `for-each`
    : perform multiple other subcommands, sequentially, on a single server connection

### hoardy-mail list

Login, perform IMAP `LIST` command to get all folders, print them one per line.

- options:
  - `--porcelain`
  : print in a machine-readable format (the default at the moment)

### hoardy-mail count

Login, (optionally) perform IMAP `LIST` command to get all folders, perform IMAP `SEARCH` command with specified filters in each folder, print message counts for each folder one per line.

- options:
  - `--porcelain`
  : print in a machine-readable format

- folder search filters:
  - `--all-folders`
  : operate on all folders (default)
  - `--folder NAME`
  : mail folders to include; can be specified multiple times
  - `--not-folder NAME`
  : mail folders to exclude; can be specified multiple times

- message IMAP `SEEN` flag filters (mutually exclusive):
  - `--any-seen`
  : operate on both `SEEN` and not `SEEN` messages (default)
  - `--seen`
  : operate on messages marked as `SEEN`
  - `--unseen`
  : operate on messages not marked as `SEEN`

- message IMAP `FLAGGED` flag filters (mutually exclusive):
  - `--any-flagged`
  : operate on both `FLAGGED` and not `FLAGGED` messages (default)
  - `--flagged`
  : operate on messages marked as `FLAGGED`
  - `--unflagged`
  : operate on messages not marked as `FLAGGED`

### hoardy-mail mark

Login, perform IMAP `SEARCH` command with specified filters for each folder, mark resulting messages in specified way by issuing IMAP `STORE` commands.

- folder search filters (required):
  - `--all-folders`
  : operate on all folders
  - `--folder NAME`
  : mail folders to include; can be specified multiple times
  - `--not-folder NAME`
  : mail folders to exclude; can be specified multiple times

- message IMAP `SEEN` flag filters (mutually exclusive, default: depends on other arguments):
  - `--any-seen`
  : operate on both `SEEN` and not `SEEN` messages
  - `--seen`
  : operate on messages marked as `SEEN`
  - `--unseen`
  : operate on messages not marked as `SEEN`

- message IMAP `FLAGGED` flag filters (mutually exclusive, default: depends on other arguments):
  - `--any-flagged`
  : operate on both `FLAGGED` and not `FLAGGED` messages
  - `--flagged`
  : operate on messages marked as `FLAGGED`
  - `--unflagged`
  : operate on messages not marked as `FLAGGED`

- marking:
  - `{seen,unseen,flagged,unflagged}`
  : mark how (required):
    - `seen`: add `SEEN` flag, sets `--unseen` if no message flag filter is specified
    - `unseen`: remove `SEEN` flag, sets `--seen` if no message flag filter is specified
    - `flag`: add `FLAGGED` flag, sets `--unflagged` if no message flag filter is specified
    - `unflag`: remove `FLAGGED` flag, sets `--flagged` if no message flag filter is specified

### hoardy-mail fetch

Login, perform IMAP `SEARCH` command with specified filters for each folder, fetch resulting messages in (configurable) batches, put each batch of message into the specified Maildir and `fsync` them to disk or feed them to the specified MDA/LDA, and, if and only if all of the above succeeds, mark each message in the batch on the server in a specified way by issuing IMAP `STORE` commands.

- folder search filters:
  - `--all-folders`
  : operate on all folders (default)
  - `--folder NAME`
  : mail folders to include; can be specified multiple times
  - `--not-folder NAME`
  : mail folders to exclude; can be specified multiple times

- delivery target (required, mutually exclusive):
  - `--maildir DIRECTORY`
  : Maildir to deliver the messages to;
    with this specified `hoardy-mail` will simply drop raw RFC822 messages, one message per file, into `DIRECTORY/new` (creating it, `DIRECTORY/cur`, and `DIRECTORY/tmp` if any of those do not exists)
  - `--mda COMMAND`
  : shell command to use as an MDA to deliver the messages to;
    with this specified `hoardy-mail` will spawn `COMMAND` via the shell and then feed raw RFC822 message into its `stdin`, the resulting process is then responsible for delivering the message to Maildir, mbox, etc;
    `maildrop` from Courier Mail Server project is a good KISS default

- delivery mode (mutually exclusive):
  - `--yolo`
  : messages that fail to be delivered into the `--maildir` or by the `--mda` are left un`--mark`ed on the server but no other messages get affected and currently running `hoardy-mail fetch` continues as if nothing is amiss
  - `--careful`
  : messages that fail to be delivered into the `--maildir` or by the `--mda` are left un`--mark`ed on the server, no other messages get affected, but `hoardy-mail` aborts currently running `fetch` and all the following commands of the `for-each` (if any) if zero messages from the current batch got successfully delivered --- as that usually means that the target file system is out of space, read-only, or generates IO errors (default)
  - `--paranoid`
  : `hoardy-mail` aborts the process immediately if any of the messages in the current batch fail to be delivered into the `--maildir` or by the `--mda`, the whole batch gets left un`--mark`ed on the server

- hooks:
  - `--new-mail-cmd CMD`
  : shell command to run at the end of each program cycle that had new messages successfully delivered into the `--maildir` or by the `--mda` of this `fetch` subcommand; can be specified multiple times

- message IMAP `SEEN` flag filters (mutually exclusive):
  - `--any-seen`
  : operate on both `SEEN` and not `SEEN` messages
  - `--seen`
  : operate on messages marked as `SEEN`
  - `--unseen`
  : operate on messages not marked as `SEEN` (default)

- message IMAP `FLAGGED` flag filters (mutually exclusive):
  - `--any-flagged`
  : operate on both `FLAGGED` and not `FLAGGED` messages (default)
  - `--flagged`
  : operate on messages marked as `FLAGGED`
  - `--unflagged`
  : operate on messages not marked as `FLAGGED`

- marking:
  - `--mark {auto,noop,seen,unseen,flagged,unflagged}`
  : after the message was fetched:
    - `auto`: `seen` when only `--unseen` is set (which it is by default), `flagged` when only `--unflagged` is set, `noop` otherwise (default)
    - `noop`: do nothing
    - `seen`: add `SEEN` flag
    - `unseen`: remove `SEEN` flag
    - `flagged`: add `FLAGGED` flag
    - `unflagged`: remove `FLAGGED` flag

### hoardy-mail delete

Login, perform IMAP `SEARCH` command with specified filters for each folder, delete them from the server using a specified method.

- folder search filters (required):
  - `--all-folders`
  : operate on all folders
  - `--folder NAME`
  : mail folders to include; can be specified multiple times
  - `--not-folder NAME`
  : mail folders to exclude; can be specified multiple times

- message IMAP `SEEN` flag filters (mutually exclusive):
  - `--any-seen`
  : operate on both `SEEN` and not `SEEN` messages
  - `--seen`
  : operate on messages marked as `SEEN` (default)
  - `--unseen`
  : operate on messages not marked as `SEEN`

- message IMAP `FLAGGED` flag filters (mutually exclusive):
  - `--any-flagged`
  : operate on both `FLAGGED` and not `FLAGGED` messages (default)
  - `--flagged`
  : operate on messages marked as `FLAGGED`
  - `--unflagged`
  : operate on messages not marked as `FLAGGED`

- deletion method:
  - `--method {auto,delete,delete-noexpunge,gmail-trash}`
  : delete messages how:
    - `auto`: `gmail-trash` when `--host imap.gmail.com` and the current folder is not `[Gmail]/Trash`, `delete` otherwise (default)
    - `delete`: mark messages as deleted and then use IMAP `EXPUNGE` command, i.e. this does what you would expect a "delete" command to do, works for most IMAP servers
    - `delete-noexpunge`: mark messages as deleted but skip issuing IMAP `EXPUNGE` command hoping the server does as RFC2060 says and auto-`EXPUNGE`s messages on IMAP `CLOSE`; this is much faster than `delete` but some servers (like GMail) fail to implement this properly
    - `gmail-trash`: move messages to `[Gmail]/Trash` in GMail-specific way instead of trying to delete them immediately (GMail ignores IMAP `Deleted` flag and `EXPUNGE` command outside of `[Gmail]/Trash`); you can then `hoardy-mail delete --folder "[Gmail]/Trash"` them after (which will default to `--method delete`), or you could just leave them there and GMail will delete them in 30 days

### hoardy-mail for-each

For each account: login, perform other subcommands given in `ARG`s, logout.

This is most useful for performing complex changes `--every` once in while in daemon mode.
Or if you want to set different `--folder`s for different subcommands but run them all at once.

Except for the simplest of cases, you must use `--` before `ARG`s so that any options specified in `ARG`s won't be picked up by `for-each`.
Run with `--very-dry-run` to see the interpretation of the given command line.

All generated hooks are deduplicated and run after all other subcommands are done.
E.g., if you have several `fetch --new-mail-cmd filter-my-mail` as subcommands of `for-each`, then `filter-my-mail` *will be run **once** after all other subcommands finish*.

- positional arguments:
  - `ARG`
  : arguments, these will be split by `;` and parsed into other subcommands

- folder search filters (will be used as default for subcommands):
  - `--all-folders`
  : operate on all folders
  - `--folder NAME`
  : mail folders to include; can be specified multiple times
  - `--not-folder NAME`
  : mail folders to exclude; can be specified multiple times

## Notes on usage

- When specifying account-related settings `--user` and `--pass*` options should be always specified last.

  Internally, new account definition gets emitted when a new `--pass*` option finishes processing.

  All server connection and authentication options except `--user` and `--pass*` get reused between successively defined accounts, unless overwritten with a new value before the next `--pass*` option.

- Message search filters are connected by logical "AND"s so, e.g., `--from "github.com" --not-from "notifications@github.com"` will act on messages which have a `From:` header with `github.com` but without `notifications@github.com` as substrings.

- `fetch` subcommand acts on `--unseen` messages by default.

- `delete` subcommand acts on `--seen` messages by default.

- Under `for-each`, after any command that produced errors (e.g. a `fetch` that failed to deliver at least one message because `--maildir` or `--mda` failed to do their job), any successive `delete` commands will be automatically skipped.

  In theory, in the case of `--maildir` or `--mda` failing to deliver some messages `hoardy-mail` need not do this as those messages will be left unmarked on the server, but in combination with the default `--careful` delivery option (which see) this behaviour could still be helpful in preventing data loss in the event where the target filesystem starts generating random IO errors (e.g. if you HDD/SSD just failed).

  In general, this behaviour exists to prevent `delete` from accidentally deleting something important when folder hierarchy on the IMAP server changes to be incompatible with in-use `hoardy-mail` options. For instance, say you are trying to `fetch` from a folder that was recently renamed and then try to `delete` from `--all-folders`. The behaviour described above will prevent this from happening.

## Examples

- List all available IMAP folders and count how many messages they contain:

  - with the password taken from `pinentry`:
    ```
    hoardy-mail count --host imap.example.com --user account@example.com --pass-pinentry
    ```

  - with the password taken from the first line of the given file:
    ```
    hoardy-mail count --host imap.example.com --user account@example.com \
      --passfile /path/to/file/containing/account@example.com.password
    ```

  - with the password taken from the output of password-store utility:
    ```
    hoardy-mail count --host imap.example.com --user account@example.com \
      --passcmd "pass show mail/account@example.com"
    ```

  - with two accounts on the same server:
    ```
    hoardy-mail count --porcelain \
      --host imap.example.com \
      --user account@example.com --passcmd "pass show mail/account@example.com" \
      --user another@example.com --passcmd "pass show mail/another@example.com"
    ```

Now, assuming the following are set:

```
common=(--host imap.example.com --user account@example.com --passcmd "pass show mail/account@example.com")
common_mda=("${{common[@]}}" --mda maildrop)
gmail_common=(--host imap.gmail.com --user account@gmail.com --passcmd "pass show mail/account@gmail.com")
gmail_common_mda=("${{gmail_common[@]}}" --mda maildrop)
```

- Count how many messages older than 7 days are in `[Gmail]/All Mail` folder:
  ```
  hoardy-mail count "${gmail_common[@]}" --folder "[Gmail]/All Mail" --older-than 7
  ```

- Mark all messages in `INBOX` as not `SEEN`, fetch all not `SEEN` messages marking them `SEEN` as you download them so that if the process gets interrupted you could continue from where you left off:
  ```
  # setup: do once
  hoardy-mail mark "${common[@]}" --folder INBOX unseen

  # repeatable part
  hoardy-mail fetch "${common_mda[@]}" --folder INBOX
  ```

- Similarly to the above, but use `FLAGGED` instead of `SEEN`. This allows to use this in parallel with another instance of `hoardy-mail` using the `SEEN` flag, e.g. if you want to backup to two different machines independently, or if you want to use `hoardy-mail` simultaneously in parallel with `fetchmail` or other similar tool:
  ```
  # setup: do once
  hoardy-mail mark "${common[@]}" --folder INBOX unflagged

  # repeatable part
  hoardy-mail fetch "${common_mda[@]}" --folder INBOX --any-seen --unflagged

  # this will work as if nothing of the above was run
  fetchmail

  # in this use case you should use both `--seen` and `--flagged` when expiring old messages
  # so that it would only delete messages fetched by both hoardy-mail and fetchmail
  hoardy-mail delete "${common[@]}" --folder INBOX --older-than 7 --seen --flagged
  ```

- Similarly to the above, but run `hoardy-mail fetch` as a daemon to download updates every hour:
  ```
  # setup: do once
  hoardy-mail mark "${common[@]}" --folder INBOX unseen

  # repeatable part
  hoardy-mail fetch "${common_mda[@]}" --folder INBOX --every 3600
  ```

- Fetch all messages from `INBOX` folder that were delivered in the last 7 days (the resulting date is rounded down to the start of the day by server time), but don't change any flags:
  ```
  hoardy-mail fetch "${common_mda[@]}" --folder INBOX --any-seen --newer-than 7
  ```

- Fetch all messages from `INBOX` folder that were delivered from the beginning of today (by server time), without changing any flags:
  ```
  hoardy-mail fetch "${common_mda[@]}" --folder INBOX --any-seen --newer-than 0
  ```

- Delete all `SEEN` messages older than 7 days from `INBOX` folder:

  Assuming you fetched and backed up all your messages already this allows you to keep as little as possible on the server, so that if your account gets cracked/hacked, you won't be as vulnerable.

  ```
  hoardy-mail delete "${common[@]}" --folder INBOX --older-than 7
  ```

  (`--seen` is implied by default)

- **DANGEROUS!** If you fetched and backed up all your messages already, you can skip `--older-than` and just delete all `SEEN` messages instead:
  ```
  hoardy-mail delete "${common[@]}" --folder INBOX
  ```

  Though, setting at least `--older-than 1`, to make sure you won't lose any data in case you forgot you are running another instance of `hoardy-mail` or another IMAP client that changes message flags is highly recommended.

- Fetch everything GMail considers to be Spam for local filtering:
  ```
  # setup: do once
  mkdir -p ~/Mail/spam/{new,cur,tmp}

  cat > ~/.mailfilter-spam << EOF
  DEFAULT="\$HOME/Mail/spam"
  EOF

  hoardy-mail mark "${gmail_common[@]}" --folder "[Gmail]/Spam" unseen

  # repeatable part
  hoardy-mail fetch "${gmail_common_mda[@]}" --mda "maildrop ~/.mailfilter-spam" --folder "[Gmail]/Spam"
  ```

- Fetch everything from all folders, except for `INBOX`, `[Gmail]/Starred` (because in GMail these two are included in `[Gmail]/All Mail`), and `[Gmail]/Trash` (for illustrative purposes):
  ```
  hoardy-mail fetch "${gmail_common_mda[@]}" --all-folders \
    --not-folder INBOX --not-folder "[Gmail]/Starred" --not-folder "[Gmail]/Trash"
  ```

  Note that, in GMail, all messages except for those in `[Gmail]/Trash` and `[Gmail]/Spam` are included in `[Gmail]/All Mail`. So, if you want to fetch everything, you should probably just fetch from those three folders instead:

  ```
  hoardy-mail fetch "${gmail_common_mda[@]}" \
    --folder "[Gmail]/All Mail" --folder "[Gmail]/Trash" --folder "[Gmail]/Spam"
  ```

- GMail-specific deletion mode: move (expire) old messages to `[Gmail]/Trash` and then delete them:

  In GMail, deleting messages from `INBOX` does not actually delete them, nor moves them to trash, just removes them from `INBOX` while keeping them available from `[Gmail]/All Mail`.

  To work around this, this tool provides a GMail-specific `--method gmail-trash` that moves messages to `[Gmail]/Trash` in a GMail-specific way (this is not a repetition, it does require issuing special IMAP `STORE` commands to achieve this):

  ```
  hoardy-mail delete "${gmail_common[@]}" --folder "[Gmail]/All Mail" --older-than 7
  ```

  (`--method gmail-trash` is implied by `--host imap.gmail.com` and `--folder` not being `[Gmail]/Trash`, `--seen` is still implied by default)

  Messages in `[Gmail]/Trash` will be automatically removed by GMail in 30 days, but you can also delete them immediately with:

  ```
  hoardy-mail delete "${gmail_common[@]}" --folder "[Gmail]/Trash" --any-seen --older-than 7
  ```

  (`--method delete` is implied by `--host imap.gmail.com` but `--folder` being `[Gmail]/Trash`)

- Every hour, fetch messages from different folders using different MDA settings and then expire messages older than 7 days, all in a single pass (reusing the server connection between subcommands):
  ```
  hoardy-mail for-each "${gmail_common[@]}" --every 3600 -- \
    fetch --folder "[Gmail]/All Mail" --mda maildrop \; \
    fetch --folder "[Gmail]/Spam" --mda "maildrop ~/.mailfilter-spam" \; \
    delete --folder "[Gmail]/All Mail" --folder "[Gmail]/Spam" --folder "[Gmail]/Trash" \
      --older-than 7
  ```

  Note the `--` and `\;` tokens, without them the above will fail to parse.

  Also note that `delete` will use `--method gmail-trash` for `[Gmail]/All Mail` and `[Gmail]/Spam` and then use `--method delete` for `[Gmail]/Trash` even though they are specified together.

  Also, when running in parallel with another IMAP client that changes IMAP flags, `hoardy-mail for-each` will notice the other client doing it while `fetch`ing and will skip all following `delete`s of that `--every` cycle to prevent data loss.

