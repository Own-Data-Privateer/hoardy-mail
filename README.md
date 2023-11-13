# What?

`imaparms` is a Keep It Stupid Simple (KISS) Swiss-army-knife-like tool for fetching and performing batch operations on messages residing on IMAP4 servers.
That is: login to a specified server, fetch or perform specified actions (count, flag/mark, delete, etc) on all messages matching specified criteria in all specified folders, logout.

This tool was inspired by [fetchmail](https://www.fetchmail.info/) and [IMAPExpire](https://gitlab.com/mikecardwell/IMAPExpire) and is basically a generalized combination of the two.

# Why?

I used to use and (usually privately, but sometimes not) patch both `fetchmail` and `IMAPExpire` for years before getting tired of it and deciding it would be simpler to just write my own thingy instead of trying to make `fetchmail` fetch mail at decent speeds and fix all the issues making it inconvenient and unsafe to run `IMAPExpire` immediately after `fetchmail` finishes fetching mail.

Which is to say, the main use case I made this for is as follows:

- you periodically fetch and backup/archive your mail to a local `Maildir` (or `mbox`) with this tool's `imaparms fetch` subcommand (which does what `fetchmail --softbounce --invisible --norewrite --mda MDA` does but >150x faster) or a similar tool (like [fdm](https://github.com/nicm/fdm)), then
- you backup your `Maildir` with `rsync`/`git`/`bup`/etc to make at least one other copy somewhere, and then, after your backup succeeds,
- you run this tool's `imaparms delete` subcommand to expire old already-fetched messages from the original mail server (I prefer to expire messages `--older-than` some number of intervals between backups, just to be safe, but if you do backups directly after the `fetch`, or you like to live dangerously, you could delete old messages immediately), so that
- when/if your account get cracked/hacked the attacker only gets your unfetched mail (+ configurable amount of yet to be removed messages), which is much better than them getting the whole last 20 years or whatever of your correspondence. (If your personal computer gets compromised enough, attackers will eventually get everything anyway, so deleting old mail from servers does not make things worse. But see some more thoughts on this below.)

Also, you can run `imaparms fetch` with `--unflagged` command line option instead of the implied `--unseen` option, which will make it use the `FLAGGED` IMAP flag instead of the `SEEN` IMAP flag to track state, allowing you to run it simultaneously with tools that use the `SEEN` flag, like `fetchmail`, and then simply delete duplicated files.
I.e. if you are really paranoid, you could use that feature to check files produced by `fetchmail` and `imaparms fetch` against each other, see below.

# Quickstart

## Installation

- Install with:
  ```
  pip install imaparms
  ```
  and run as
  ```
  imaparms --help
  ```
- Alternatively, install it via Nix
  ```
  nix-env -i -f ./default.nix
  ```
- Alternatively, run without installing:
  ```
  python3 -m imaparms.__main__ --help
  ```

## Backup all your email

`imaparms` is not intended as a **backup** utility, `imaparms` is intended as a better replacement for `fetchmail`+`IMAPExpire` combination, with `imaparms` you are supposed to backup your `Maildir` with some third-party tool instead.
If you want to keep a synchronized copy of your mail locally and on your mail server you should use [offlineimap](https://github.com/OfflineIMAP/offlineimap), [imapsync](https://github.com/imapsync/imapsync), or something similar instead.

`imaparms` can, however, be used for efficient local backups of your mail if you are willing to sacrifice either `SEEN` or `FLAGGED` IMAP flag to `imaparms` for it to use it to store its state on the server.
And using `imaparms` for backups is illustrative, so a couple of examples follow.

All examples on this page use `maildrop` MDA from [Courier Mail Server project](https://www.courier-mta.org/), which is the simplest commodity MDA with the simplest setup I know of.
But, of course, you can use anything else.
E.g., [fdm](https://github.com/nicm/fdm) can function as an MDA, and it is also pretty simple to setup.

### Backup inefficiently

The following will fetch all messages from all the folders on the server (without changing message flags on the server side) and feed them to `maildrop` which will just put them all into `~/Mail/backup` `Maildir`.

```
# setup: do once
mkdir -p ~/Mail/backup/{new,cur,tmp}

cat > ~/.mailfilter << EOF
DEFAULT="$HOME/Mail/backup"
EOF

# backup all your mail from GMail
imaparms fetch --host imap.gmail.com --user user@gmail.com --pass-pinentry --mda maildrop --all-folders --all
```

For GMail you will have to create and use application-specific password, which requires enabling 2FA, [see below for more info](#gmail).

Also, if you have a lot of mail, this will be very inefficient, as it will try to re-download everything again if it ever gets interrupted.

### Backup efficiently

To make the above efficient you have to sacrifice either `SEEN` or `FLAGGED` IMAP flags to allow `imaparms` to track which messages are yet to be fetched, i.e. either:

```
# mark all messages as UNSEEN
imaparms mark --host imap.gmail.com --user user@gmail.com --pass-pinentry --all-folders unseen

# fetch UNSEEN and mark as SEEN as you go
# this can be interrrupted and restarted and it will continue from where it left off
imaparms mark --host imap.gmail.com --user user@gmail.com --pass-pinentry --all-folders --unseen
```

or

```
# mark all messages as UNFLAGGED
imaparms mark --host imap.gmail.com --user user@gmail.com --pass-pinentry --all-folders unflagged

# similarly
imaparms mark --host imap.gmail.com --user user@gmail.com --pass-pinentry --all-folders --unflagged
```

This, of course, means that if you open or "mark as read" a message in GMail's web-mail UI while using `imaparms --unseen`, or flag (star) it there while using `imaparms --unflagged`, `imaparms` will ignore the message on the next `fetch`.

## Fetch, Backup, Expire

My preferred workflow described [above](#why) looks like this:

```
common=(--ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com")

# setup: do once
mkdir -p ~/Mail/INBOX/{new,cur,tmp}

cat > ~/.mailfilter << EOF
DEFAULT="$HOME/Mail/INBOX"
EOF

# fetch
imaparms fetch "${common[@]}" --mda maildrop --folder "INBOX" --unseen

# now you can index it or whatever
notmuch new

# backup
rsync -aHAXiv ~/Mail /disk/backup

# expire old mail from the server
imaparms delete "${common[@]}" --folder "INBOX" --seen --older-than 3
```

## Fetch, Backup, Expire: The Paranoid Version

The paranoid/double-backup workflow described [above](#why) that uses `fetchmail` in parallel can be implemented like this:

```
secondary_common=(--ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com")

# setup: do once
mkdir -p ~/Mail/INBOX.secondary/{new,cur,tmp}

cat > ~/.mailfilter-secondary << EOF
DEFAULT="$HOME/Mail/INBOX.secondary"
EOF

# ... prepare by unflagging all messages
imaparms mark "${secondary_common[@]}" --folder "INBOX" unflagged

# run fetchmail daemon as usual
fetchmail --mda maildrop -d 900

# fetch using the FLAGGED flag for tracking state
imaparms fetch "${secondary_common[@]}" --mda "maildrop ~/.mailfilter-secondary" --folder "INBOX" --unflagged

# deduplicate
jdupes -o time -O -rdN Mail/INBOX Mail/INBOX.secondary

# index
notmuch new

# backup
rsync -aHAXiv ~/Mail /disk/backup

# expire old messages fetched by both fetchmail and this
imaparms delete "${secondary_common[@]}" --folder "INBOX" --seen --flagged --older-than 3
```

## See also

See the [usage section](#usage) for explanation of used command line options.

See the [examples section](#examples) for more examples.

See [notmuch](https://notmuchmail.org/) for my preferred KISS mail indexer and Mail User Agent (MUA).
Of course, you can use anything else, e.g. Thunderbird, just configure it to use the local `Maildir` as the "mail account".
Or you could point your own local IMAP server to your `Maildir` and use any mail client that can use IMAP, but locally.

# Comparison to

## [fetchmail](https://www.fetchmail.info/)

`imaparms fetch`

- fetches your mail >150 times faster by default (`fetchmail` fetches and marks messages one-by-one, incurring huge network latency overheads, `imaparms fetch` does it in (configurable) batches);
- fetches messages out-of-order to try and maximize `messages/second` metric when it makes sense (i.e. it temporarily delays fetching of larger messages if many smaller ones can be fetched instead) so that you could efficiently index your mail in parallel with fetching;
- only does deliveries to [MDA/LDA](https://en.wikipedia.org/wiki/Message_delivery_agent) (similar to `fetchmail --mda` option), deliveries over SMTP are not and will never be supported (if you want this you can just use [msmtp](https://marlam.de/msmtp/) as your MDA);
- thus this tool is much simpler to use when fetching to a local `Maildir` as it needs no configuration to fetch messages as-is without modifying any headers, thus fetching the same messages twice will produce identical files (which is not true for `fetchmail`, `imaparms --mda MDA fetch` is roughly equivalent to `fetchmail --softbounce --invisible --norewrite --mda MDA`);
- probably will not work with most broken IMAP servers (`fetchmail` has lots of workarounds for server bugs, `imaparms fetch` does not);
- is written in Python instead of C;
- has other subcommands, not just `imaparms fetch`.

## [fdm](https://github.com/nicm/fdm)

[Better explanation of what fdm does](https://wiki.archlinux.org/title/fdm).

`imaparms fetch`

- uses server-side message flags to track state instead of keeping a local database of fetched UIDs;
- fetches messages out-of-order to try and maximize `messages/second` metric;
- does not do any filtering, offloads delivery to MDA/LDA;
- is written in Python instead of C;
- has other subcommands, not just `imaparms fetch`.

## [IMAPExpire](https://gitlab.com/mikecardwell/IMAPExpire)

`imaparms delete`

- allows all UNICODE characters except `\n` in passwords/passphrases (yes, including spaces, quotes, etc);
- provides a bunch of options controlling message selection and uses `--seen` option by default for destructive actions, so you won't accidentally delete any messages you have not yet fetched even if your fetcher got stuck/crashed;
- provides GMail-specific options;
- is written in Python instead of Perl and requires nothing but the basic Python install, no third-party libraries needed;
- has other subcommands, not just `imaparms delete`.

## [offlineimap](https://github.com/OfflineIMAP/offlineimap), [imapsync](https://github.com/imapsync/imapsync), and similar

- `imaparms fetch` does deliveries from an IMAP server to your MDA instead of trying to synchronize state between some combinations of IMAP servers and local Maildirs (i.e. for `imaparms fetch` your IMAP server is always the source, never a destination);
- `imaparms` has other subcommands, not just `imaparms fetch`.

# Some Fun and Relevant Facts

Note that [Snowden revelations](https://en.wikipedia.org/wiki/Global_surveillance_disclosures_(2013%E2%80%93present)) mean that Google and US Government store copies of all of your correspondence since 2001-2009 (it depends) even if you delete everything from all the servers.

And they wiretap basically all the traffic going though international Internet exchanges because they wiretap all underwater cables.
Simply because they can, apparently?
(If you think about it, there is absolutely no point to doing this if you are trying to achieve their stated signal-intelligence goals.
Governments and organized crime use one-time-pads since 1950s.
AES256 + 32 bytes of shared secret + some simple [steganography](https://en.wikipedia.org/wiki/Steganography) and even if the signal gets discovered, no quantum-computer will ever be able to break it, no research into [quantum-safe cryptography](https://en.wikipedia.org/wiki/Post-quantum_cryptography) needed.
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
Short-term and against random exploitations of your mail servers, this thing is perfect, IMHO.

# <span id="gmail"/>GMail: Some Fun and Relevant Facts

GMail docs say that IMAP and SMTP are "legacy protocols" and are "insecure".
Which, sure, they could be, if you reuse passwords.
But them implying that everything except their own web-mail UI is "insecure" is kinda funny given that they do use SMTP to transfer mail between servers and [signing in with Google prompts](https://web.archive.org/web/20230702050207/https://support.google.com/accounts/answer/7026266?co=GENIE.Platform%3DAndroid&hl=en) exists.
I.e. you can borrow someone's phone, unlock it (passcode? peek over their shoulder or just get some video surveillance footage of them typing it in public; fingerprint? they leave their fingerprints all over the device itself, dust with some flour, take a photo, apply some simple filters, 3D-print the result, this actually takes ~3 minutes to do if you know what you are doing), ask Google to authenticate via prompt.
Done, you can login to everything with no password needed.
And Google appears to give no way to disable Google prompts if your account has an attached Android device.
Though, you can make Google prompts ask for a password too, but that feature need special setup.
Meanwhile, "legacy" passwords are not secure, apparently?

So to use `imaparms` with GMail you will have to enable 2FA in your account settings and then add an application-specific password for IMAP access.
I.e., instead of generating a random password and giving it to Google (while storing it in a password manager that feeds it to `imaparms`), you ask Google to generate a random password for you and use that with `imaparms`.

To enable 2FA, even for very old accounts that never used anything phone or Android-related, for no rational reasons, GMail requires specifying a working phone number that can receive SMS.
Which you can then simply remove after you copied your OTP secret into an authentificator of your choice.
Sorry, why did you need the phone number, again?

Ah, well, Google now knows it and will be able track your movements by buying location data from your network operator.
Thank you very much.

In theory, as an alternative to application-specific passwords, you can setup OAuth2 and update tokens automatically with [mailctl](https://github.com/pdobsan/mailctl), but Google will still ask for your phone number to set it up, and OAuth2 renewal adds another point of failure without really adding any security if you store your passwords in a password manager and use `--passcmd` option described below to feed them into `imaparms`.

That is to say, I don't use OAuth2, which is why `imaparms` does not support OAuth2.

# Usage

## imaparms [--version] [-h] [--help-markdown] {list,count,mark,fetch,delete,expire} ...

A Keep It Stupid Simple (KISS) Swiss-army-knife-like tool for fetching and performing batch operations on messages residing on IMAP4 servers.
Logins to a specified server, performs specified actions on all messages matching specified criteria in all specified folders, logs out.

- optional arguments:
  - `--version`
  : show program's version number and exit
  - `-h, --help`
  : show this help message and exit
  - `--help-markdown`
  : show this help message formatted in Markdown and exit

- subcommands:
  - `{list,count,mark,fetch,delete,expire}`
    - `list`
    : list all available folders on the server, one per line
    - `count`
    : count how many matching messages each specified folder has (counts for all available folders by default)
    - `mark`
    : mark matching messages in specified folders in a specified way
    - `fetch`
    : fetch matching messages from specified folders, feed them to an MDA, and then mark them in a specified way if MDA succeeds
    - `delete (expire)`
    : delete matching messages from specified folders

### imaparms list [--debug] [--dry-run] [--plain | --ssl | --starttls] [--host HOST] [--port PORT] [--user USER] [--pass-pinentry | --passfile PASSFILE | --passcmd PASSCMD] [--store-number INT] [--fetch-number INT] [--batch-number INT] [--batch-size INT] [--every SECONDS] [--every-add-random ADD]

Login, perform IMAP `LIST` command to get all folders, print them one per line.

- debugging:
  - `--debug`
  : print IMAP conversation to stderr
  - `--dry-run`
  : don't perform any actions, only show what would be done

- server connection:
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

- server auth:
  either of `--passfile` or `--passcmd` are required

  - `--user USER`
  : username on the server (required)
  - `--pass-pinentry`
  : read the password via `pinentry`
  - `--passfile PASSFILE, --pass-file PASSFILE`
  : file containing the password on its first line
  - `--passcmd PASSCMD, --pass-cmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- batching settings:
  larger values improve performance but produce longer command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen

  - `--store-number INT`
  : batch at most this many message UIDs in IMAP `STORE` requests (default: 150)
  - `--fetch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` metadata requests (default: 150)
  - `--batch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: 150)
  - `--batch-size INT`
  : batch FETCH at most this many bytes of RFC822 messages at once; RFC822 messages larger than this will be fetched one by one (i.e. without batching); essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted while `imaparms` is batching (default: 4194304)

- polling/daemon options:
  - `--every SECONDS`
  : repeat the command every `SECONDS` seconds if the whole cycle takes less than `SECONDS` seconds and `<cycle time>` seconds otherwise (with a minimum of `60` seconds either way);
    i.e. it will do its best to repeat the command precisely every `SECONDS` seconds even if the command is `fetch` and fetching new messages and `--new-mail-cmd` take different time each cycle;
    this prevents the servers accessed earlier in the cycle from learning about the amount of new data fetched from the servers accessed later in the cycle
  - `--every-add-random ADD`
  : sleep a random number of seconds in [0, ADD] range (uniform distribution) before each `--every` cycle (default: 60);
    if you set in large enough to cover the longest single-server `fetch`, it will prevent any of the servers learning anything about the data on other servers;
    if you run `imaparms` on a machine that disconnects from the Internet when you go to sleep and you set it large enough, it will help in preventing the servers from collecting data about your sleep cycle

### imaparms count [--debug] [--dry-run] [--plain | --ssl | --starttls] [--host HOST] [--port PORT] [--user USER] [--pass-pinentry | --passfile PASSFILE | --passcmd PASSCMD] [--store-number INT] [--fetch-number INT] [--batch-number INT] [--batch-size INT] [--every SECONDS] [--every-add-random ADD] [--all-folders | --folder NAME] [--not-folder NAME] [--all | [--seen | --unseen |] [--flagged | --unflagged]] [--older-than DAYS] [--newer-than DAYS] [--older-than-timestamp-in PATH] [--newer-than-timestamp-in PATH] [--older-than-mtime-of PATH] [--newer-than-mtime-of PATH] [--from ADDRESS] [--not-from ADDRESS] [--porcelain]

Login, (optionally) perform IMAP `LIST` command to get all folders, perform IMAP `SEARCH` command with specified filters in each folder, print message counts for each folder one per line.

- optional arguments:
  - `--porcelain`
  : print in a machine-readable format

- debugging:
  - `--debug`
  : print IMAP conversation to stderr
  - `--dry-run`
  : don't perform any actions, only show what would be done

- server connection:
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

- server auth:
  either of `--passfile` or `--passcmd` are required

  - `--user USER`
  : username on the server (required)
  - `--pass-pinentry`
  : read the password via `pinentry`
  - `--passfile PASSFILE, --pass-file PASSFILE`
  : file containing the password on its first line
  - `--passcmd PASSCMD, --pass-cmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- batching settings:
  larger values improve performance but produce longer command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen

  - `--store-number INT`
  : batch at most this many message UIDs in IMAP `STORE` requests (default: 150)
  - `--fetch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` metadata requests (default: 150)
  - `--batch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: 150)
  - `--batch-size INT`
  : batch FETCH at most this many bytes of RFC822 messages at once; RFC822 messages larger than this will be fetched one by one (i.e. without batching); essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted while `imaparms` is batching (default: 4194304)

- polling/daemon options:
  - `--every SECONDS`
  : repeat the command every `SECONDS` seconds if the whole cycle takes less than `SECONDS` seconds and `<cycle time>` seconds otherwise (with a minimum of `60` seconds either way);
    i.e. it will do its best to repeat the command precisely every `SECONDS` seconds even if the command is `fetch` and fetching new messages and `--new-mail-cmd` take different time each cycle;
    this prevents the servers accessed earlier in the cycle from learning about the amount of new data fetched from the servers accessed later in the cycle
  - `--every-add-random ADD`
  : sleep a random number of seconds in [0, ADD] range (uniform distribution) before each `--every` cycle (default: 60);
    if you set in large enough to cover the longest single-server `fetch`, it will prevent any of the servers learning anything about the data on other servers;
    if you run `imaparms` on a machine that disconnects from the Internet when you go to sleep and you set it large enough, it will help in preventing the servers from collecting data about your sleep cycle

- folder search filters:
  - `--all-folders`
  : operate on all folders (default)
  - `--folder NAME`
  : mail folders to include; can be specified multiple times
  - `--not-folder NAME`
  : mail folders to exclude; can be specified multiple times

- message search filters:
  - `--older-than DAYS`
  : operate on messages older than this many days, **the date will be rounded down to the start of the day; actual matching happens on the server, so all times are server time**; e.g. `--older-than 0` means older than the start of today by server time, `--older-than 1` means older than the start of yesterday, etc
  - `--newer-than DAYS`
  : operate on messages newer than this many days, a negation of`--older-than`, so **everything from `--older-than` applies**; e.g., `--newer-than -1` will match files dated into the future, `--newer-than 0` will match files delivered from the beginning of today, etc
  - `--older-than-timestamp-in PATH`
  : operate on messages older than the timestamp (in seconds since UNIX Epoch) recorder on the first line of this PATH, **which will be rounded down to the start of the day** (can be specified multiple times)
  - `--newer-than-timestamp-in PATH`
  : operate on messages newer than the timestamp (in seconds since UNIX Epoch) recorder on the first line of this PATH, which will be rounded **up** to the start of **the next day** (can be specified multiple times)
  - `--older-than-mtime-of PATH`
  : operate on messages older than mtime of this PATH, **which will be rounded down to the start of the day** (can be specified multiple times)
  - `--newer-than-mtime-of PATH`
  : operate on messages newer than mtime of this PATH, which will be rounded **up** to the start of **the next day** (can be specified multiple times)
  - `--from ADDRESS`
  : operate on messages that have this string as substring of their header's FROM field; can be specified multiple times
  - `--not-from ADDRESS`
  : operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times

- message flag filters:
  - `--all`
  : operate on all messages (default)
  - `--seen`
  : operate on messages marked as `SEEN`
  - `--unseen`
  : operate on messages not marked as `SEEN`
  - `--flagged`
  : operate on messages marked as `FLAGGED`
  - `--unflagged`
  : operate on messages not marked as `FLAGGED`

### imaparms mark [--debug] [--dry-run] [--plain | --ssl | --starttls] [--host HOST] [--port PORT] [--user USER] [--pass-pinentry | --passfile PASSFILE | --passcmd PASSCMD] [--store-number INT] [--fetch-number INT] [--batch-number INT] [--batch-size INT] [--every SECONDS] [--every-add-random ADD] (--all-folders | --folder NAME) [--not-folder NAME] [--all | [--seen | --unseen |] [--flagged | --unflagged]] [--older-than DAYS] [--newer-than DAYS] [--older-than-timestamp-in PATH] [--newer-than-timestamp-in PATH] [--older-than-mtime-of PATH] [--newer-than-mtime-of PATH] [--from ADDRESS] [--not-from ADDRESS] {seen,unseen,flagged,unflagged}

Login, perform IMAP `SEARCH` command with specified filters for each folder, mark resulting messages in specified way by issuing IMAP `STORE` commands.

- debugging:
  - `--debug`
  : print IMAP conversation to stderr
  - `--dry-run`
  : don't perform any actions, only show what would be done

- server connection:
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

- server auth:
  either of `--passfile` or `--passcmd` are required

  - `--user USER`
  : username on the server (required)
  - `--pass-pinentry`
  : read the password via `pinentry`
  - `--passfile PASSFILE, --pass-file PASSFILE`
  : file containing the password on its first line
  - `--passcmd PASSCMD, --pass-cmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- batching settings:
  larger values improve performance but produce longer command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen

  - `--store-number INT`
  : batch at most this many message UIDs in IMAP `STORE` requests (default: 150)
  - `--fetch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` metadata requests (default: 150)
  - `--batch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: 150)
  - `--batch-size INT`
  : batch FETCH at most this many bytes of RFC822 messages at once; RFC822 messages larger than this will be fetched one by one (i.e. without batching); essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted while `imaparms` is batching (default: 4194304)

- polling/daemon options:
  - `--every SECONDS`
  : repeat the command every `SECONDS` seconds if the whole cycle takes less than `SECONDS` seconds and `<cycle time>` seconds otherwise (with a minimum of `60` seconds either way);
    i.e. it will do its best to repeat the command precisely every `SECONDS` seconds even if the command is `fetch` and fetching new messages and `--new-mail-cmd` take different time each cycle;
    this prevents the servers accessed earlier in the cycle from learning about the amount of new data fetched from the servers accessed later in the cycle
  - `--every-add-random ADD`
  : sleep a random number of seconds in [0, ADD] range (uniform distribution) before each `--every` cycle (default: 60);
    if you set in large enough to cover the longest single-server `fetch`, it will prevent any of the servers learning anything about the data on other servers;
    if you run `imaparms` on a machine that disconnects from the Internet when you go to sleep and you set it large enough, it will help in preventing the servers from collecting data about your sleep cycle

- folder search filters (required):
  - `--all-folders`
  : operate on all folders
  - `--folder NAME`
  : mail folders to include; can be specified multiple times
  - `--not-folder NAME`
  : mail folders to exclude; can be specified multiple times

- message search filters:
  - `--older-than DAYS`
  : operate on messages older than this many days, **the date will be rounded down to the start of the day; actual matching happens on the server, so all times are server time**; e.g. `--older-than 0` means older than the start of today by server time, `--older-than 1` means older than the start of yesterday, etc
  - `--newer-than DAYS`
  : operate on messages newer than this many days, a negation of`--older-than`, so **everything from `--older-than` applies**; e.g., `--newer-than -1` will match files dated into the future, `--newer-than 0` will match files delivered from the beginning of today, etc
  - `--older-than-timestamp-in PATH`
  : operate on messages older than the timestamp (in seconds since UNIX Epoch) recorder on the first line of this PATH, **which will be rounded down to the start of the day** (can be specified multiple times)
  - `--newer-than-timestamp-in PATH`
  : operate on messages newer than the timestamp (in seconds since UNIX Epoch) recorder on the first line of this PATH, which will be rounded **up** to the start of **the next day** (can be specified multiple times)
  - `--older-than-mtime-of PATH`
  : operate on messages older than mtime of this PATH, **which will be rounded down to the start of the day** (can be specified multiple times)
  - `--newer-than-mtime-of PATH`
  : operate on messages newer than mtime of this PATH, which will be rounded **up** to the start of **the next day** (can be specified multiple times)
  - `--from ADDRESS`
  : operate on messages that have this string as substring of their header's FROM field; can be specified multiple times
  - `--not-from ADDRESS`
  : operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times

- message flag filters (default: depends on other arguments):
  - `--all`
  : operate on all messages
  - `--seen`
  : operate on messages marked as `SEEN`
  - `--unseen`
  : operate on messages not marked as `SEEN`
  - `--flagged`
  : operate on messages marked as `FLAGGED`
  - `--unflagged`
  : operate on messages not marked as `FLAGGED`

- marking:
  - `{seen,unseen,flagged,unflagged}`
  : mark how (required):
    - `seen`: add `SEEN` flag, sets `--unseen` if no message search filter is specified
    - `unseen`: remove `SEEN` flag, sets `--seen` if no message search filter is specified
    - `flag`: add `FLAGGED` flag, sets `--unflagged` if no message search filter is specified
    - `unflag`: remove `FLAGGED` flag, sets `--flagged` if no message search filter is specified

### imaparms fetch [--debug] [--dry-run] [--plain | --ssl | --starttls] [--host HOST] [--port PORT] [--user USER] [--pass-pinentry | --passfile PASSFILE | --passcmd PASSCMD] [--store-number INT] [--fetch-number INT] [--batch-number INT] [--batch-size INT] [--every SECONDS] [--every-add-random ADD] --mda COMMAND [--new-mail-cmd NEW_MAIL_CMD] [--all-folders | --folder NAME] [--not-folder NAME] [--all | [--seen | --unseen |] [--flagged | --unflagged]] [--older-than DAYS] [--newer-than DAYS] [--older-than-timestamp-in PATH] [--newer-than-timestamp-in PATH] [--older-than-mtime-of PATH] [--newer-than-mtime-of PATH] [--from ADDRESS] [--not-from ADDRESS] [--mark {auto,noop,seen,unseen,flagged,unflagged}]

Login, perform IMAP `SEARCH` command with specified filters for each folder, fetch resulting messages in (configurable) batches, feed each batch of messages to an MDA, mark each message for which MDA succeded in a specified way by issuing IMAP `STORE` commands.

- debugging:
  - `--debug`
  : print IMAP conversation to stderr
  - `--dry-run`
  : don't perform any actions, only show what would be done

- server connection:
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

- server auth:
  either of `--passfile` or `--passcmd` are required

  - `--user USER`
  : username on the server (required)
  - `--pass-pinentry`
  : read the password via `pinentry`
  - `--passfile PASSFILE, --pass-file PASSFILE`
  : file containing the password on its first line
  - `--passcmd PASSCMD, --pass-cmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- batching settings:
  larger values improve performance but produce longer command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen

  - `--store-number INT`
  : batch at most this many message UIDs in IMAP `STORE` requests (default: 150)
  - `--fetch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` metadata requests (default: 150)
  - `--batch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: 150)
  - `--batch-size INT`
  : batch FETCH at most this many bytes of RFC822 messages at once; RFC822 messages larger than this will be fetched one by one (i.e. without batching); essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted while `imaparms` is batching (default: 4194304)

- polling/daemon options:
  - `--every SECONDS`
  : repeat the command every `SECONDS` seconds if the whole cycle takes less than `SECONDS` seconds and `<cycle time>` seconds otherwise (with a minimum of `60` seconds either way);
    i.e. it will do its best to repeat the command precisely every `SECONDS` seconds even if the command is `fetch` and fetching new messages and `--new-mail-cmd` take different time each cycle;
    this prevents the servers accessed earlier in the cycle from learning about the amount of new data fetched from the servers accessed later in the cycle
  - `--every-add-random ADD`
  : sleep a random number of seconds in [0, ADD] range (uniform distribution) before each `--every` cycle (default: 60);
    if you set in large enough to cover the longest single-server `fetch`, it will prevent any of the servers learning anything about the data on other servers;
    if you run `imaparms` on a machine that disconnects from the Internet when you go to sleep and you set it large enough, it will help in preventing the servers from collecting data about your sleep cycle

- delivery settings:
  - `--mda COMMAND`
  : shell command to use as an MDA to deliver the messages to (required for `fetch` subcommand)
    `imaparms` will spawn COMMAND via the shell and then feed raw RFC822 message into its `stdin`, the resulting process is then responsible for delivering the message to `mbox`, `Maildir`, etc.
    `maildrop` from Courier Mail Server project is a good KISS default.
  - `--new-mail-cmd NEW_MAIL_CMD`
  : shell command to run if any new messages were successfully delivered by the `--mda`

- folder search filters:
  - `--all-folders`
  : operate on all folders (default)
  - `--folder NAME`
  : mail folders to include; can be specified multiple times
  - `--not-folder NAME`
  : mail folders to exclude; can be specified multiple times

- message search filters:
  - `--older-than DAYS`
  : operate on messages older than this many days, **the date will be rounded down to the start of the day; actual matching happens on the server, so all times are server time**; e.g. `--older-than 0` means older than the start of today by server time, `--older-than 1` means older than the start of yesterday, etc
  - `--newer-than DAYS`
  : operate on messages newer than this many days, a negation of`--older-than`, so **everything from `--older-than` applies**; e.g., `--newer-than -1` will match files dated into the future, `--newer-than 0` will match files delivered from the beginning of today, etc
  - `--older-than-timestamp-in PATH`
  : operate on messages older than the timestamp (in seconds since UNIX Epoch) recorder on the first line of this PATH, **which will be rounded down to the start of the day** (can be specified multiple times)
  - `--newer-than-timestamp-in PATH`
  : operate on messages newer than the timestamp (in seconds since UNIX Epoch) recorder on the first line of this PATH, which will be rounded **up** to the start of **the next day** (can be specified multiple times)
  - `--older-than-mtime-of PATH`
  : operate on messages older than mtime of this PATH, **which will be rounded down to the start of the day** (can be specified multiple times)
  - `--newer-than-mtime-of PATH`
  : operate on messages newer than mtime of this PATH, which will be rounded **up** to the start of **the next day** (can be specified multiple times)
  - `--from ADDRESS`
  : operate on messages that have this string as substring of their header's FROM field; can be specified multiple times
  - `--not-from ADDRESS`
  : operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times

- message flag filters:
  - `--all`
  : operate on all messages
  - `--seen`
  : operate on messages marked as `SEEN`
  - `--unseen`
  : operate on messages not marked as `SEEN` (default)
  - `--flagged`
  : operate on messages marked as `FLAGGED`
  - `--unflagged`
  : operate on messages not marked as `FLAGGED`

- marking:
  - `--mark {auto,noop,seen,unseen,flagged,unflagged}`
  : after the message was fetched:
    - `auto`: `seen` when only `--unseen` is set (default), `flagged` when only `--unflagged` is set, `noop` otherwise
    - `noop`: do nothing
    - `seen`: add `SEEN` flag
    - `unseen`: remove `SEEN` flag
    - `flagged`: add `FLAGGED` flag
    - `unflagged`: remove `FLAGGED` flag

### imaparms delete [--debug] [--dry-run] [--plain | --ssl | --starttls] [--host HOST] [--port PORT] [--user USER] [--pass-pinentry | --passfile PASSFILE | --passcmd PASSCMD] [--store-number INT] [--fetch-number INT] [--batch-number INT] [--batch-size INT] [--every SECONDS] [--every-add-random ADD] (--all-folders | --folder NAME) [--not-folder NAME] [--all | [--seen | --unseen |] [--flagged | --unflagged]] [--older-than DAYS] [--newer-than DAYS] [--older-than-timestamp-in PATH] [--newer-than-timestamp-in PATH] [--older-than-mtime-of PATH] [--newer-than-mtime-of PATH] [--from ADDRESS] [--not-from ADDRESS] [--method {auto,delete,delete-noexpunge,gmail-trash}]

Login, perform IMAP `SEARCH` command with specified filters for each folder, delete them from the server using a specified method.

- optional arguments:
  - `--method {auto,delete,delete-noexpunge,gmail-trash}`
  : delete messages how:
    - `auto`: `gmail-trash` when `--host imap.gmail.com` and `--folder` is not (single) `[Gmail]/Trash`, `delete` otherwise (default)
    - `delete`: mark messages as deleted and then use IMAP `EXPUNGE` command, i.e. this does what you would expect a "delete" command to do, works for most IMAP servers
    - `delete-noexpunge`: mark messages as deleted but skip issuing IMAP `EXPUNGE` command hoping the server does as RFC2060 says and auto-`EXPUNGE`s messages on IMAP `CLOSE`; this is much faster than `delete` but some servers (like GMail) fail to implement this properly
    - `gmail-trash`: move messages to `[Gmail]/Trash` in GMail-specific way instead of trying to delete them immediately (GMail ignores IMAP `EXPUNGE` outside of `[Gmail]/Trash`, you can then `imaparms delete --method delete --folder "[Gmail]/Trash"` them after, or you could just leave them there and GMail will delete them in 30 days)

- debugging:
  - `--debug`
  : print IMAP conversation to stderr
  - `--dry-run`
  : don't perform any actions, only show what would be done

- server connection:
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

- server auth:
  either of `--passfile` or `--passcmd` are required

  - `--user USER`
  : username on the server (required)
  - `--pass-pinentry`
  : read the password via `pinentry`
  - `--passfile PASSFILE, --pass-file PASSFILE`
  : file containing the password on its first line
  - `--passcmd PASSCMD, --pass-cmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- batching settings:
  larger values improve performance but produce longer command lines (which some servers reject) and cause more stuff to be re-downloaded when networking issues happen

  - `--store-number INT`
  : batch at most this many message UIDs in IMAP `STORE` requests (default: 150)
  - `--fetch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` metadata requests (default: 150)
  - `--batch-number INT`
  : batch at most this many message UIDs in IMAP `FETCH` data requests; essentially, this controls the largest possible number of messages you will have to re-download if connection to the server gets interrupted (default: 150)
  - `--batch-size INT`
  : batch FETCH at most this many bytes of RFC822 messages at once; RFC822 messages larger than this will be fetched one by one (i.e. without batching); essentially, this controls the largest possible number of bytes you will have to re-download if connection to the server gets interrupted while `imaparms` is batching (default: 4194304)

- polling/daemon options:
  - `--every SECONDS`
  : repeat the command every `SECONDS` seconds if the whole cycle takes less than `SECONDS` seconds and `<cycle time>` seconds otherwise (with a minimum of `60` seconds either way);
    i.e. it will do its best to repeat the command precisely every `SECONDS` seconds even if the command is `fetch` and fetching new messages and `--new-mail-cmd` take different time each cycle;
    this prevents the servers accessed earlier in the cycle from learning about the amount of new data fetched from the servers accessed later in the cycle
  - `--every-add-random ADD`
  : sleep a random number of seconds in [0, ADD] range (uniform distribution) before each `--every` cycle (default: 60);
    if you set in large enough to cover the longest single-server `fetch`, it will prevent any of the servers learning anything about the data on other servers;
    if you run `imaparms` on a machine that disconnects from the Internet when you go to sleep and you set it large enough, it will help in preventing the servers from collecting data about your sleep cycle

- folder search filters (required):
  - `--all-folders`
  : operate on all folders
  - `--folder NAME`
  : mail folders to include; can be specified multiple times
  - `--not-folder NAME`
  : mail folders to exclude; can be specified multiple times

- message search filters:
  - `--older-than DAYS`
  : operate on messages older than this many days, **the date will be rounded down to the start of the day; actual matching happens on the server, so all times are server time**; e.g. `--older-than 0` means older than the start of today by server time, `--older-than 1` means older than the start of yesterday, etc
  - `--newer-than DAYS`
  : operate on messages newer than this many days, a negation of`--older-than`, so **everything from `--older-than` applies**; e.g., `--newer-than -1` will match files dated into the future, `--newer-than 0` will match files delivered from the beginning of today, etc
  - `--older-than-timestamp-in PATH`
  : operate on messages older than the timestamp (in seconds since UNIX Epoch) recorder on the first line of this PATH, **which will be rounded down to the start of the day** (can be specified multiple times)
  - `--newer-than-timestamp-in PATH`
  : operate on messages newer than the timestamp (in seconds since UNIX Epoch) recorder on the first line of this PATH, which will be rounded **up** to the start of **the next day** (can be specified multiple times)
  - `--older-than-mtime-of PATH`
  : operate on messages older than mtime of this PATH, **which will be rounded down to the start of the day** (can be specified multiple times)
  - `--newer-than-mtime-of PATH`
  : operate on messages newer than mtime of this PATH, which will be rounded **up** to the start of **the next day** (can be specified multiple times)
  - `--from ADDRESS`
  : operate on messages that have this string as substring of their header's FROM field; can be specified multiple times
  - `--not-from ADDRESS`
  : operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times

- message flag filters:
  - `--all`
  : operate on all messages
  - `--seen`
  : operate on messages marked as `SEEN` (default)
  - `--unseen`
  : operate on messages not marked as `SEEN`
  - `--flagged`
  : operate on messages marked as `FLAGGED`
  - `--unflagged`
  : operate on messages not marked as `FLAGGED`

## Notes on usage

Message search filters are connected by logical "AND"s so, e.g., `--from "github.com" --not-from "notifications@github.com"` will act on messages which have a `From:` header with `github.com` but without `notifications@github.com` as substrings.

Note that `fetch` and `delete` subcommands act on `--seen` messages by default.

Specifying `--folder` multiple times will perform the specified action on all specified folders.

## Examples

- List all available IMAP folders and count how many messages they contain:

  - with the password taken from `pinentry`:
    ```
    imaparms count --ssl --host imap.example.com --user myself@example.com --pass-pinentry
    ```

  - with the password taken from the first line of the given file:
    ```
    imaparms count --ssl --host imap.example.com --user myself@example.com --passfile /path/to/file/containing/myself@example.com.password
    ```

  - with the password taken from the output of password-store util:
    ```
    imaparms count --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com"
    ```

  - with two accounts on the same server:
    ```
    imaparms count --porcelain \
             --ssl --host imap.example.com \
             --user myself@example.com --passcmd "pass show mail/myself@example.com" \
             --user another@example.com --passcmd "pass show mail/another@example.com"

    ```

Now, assuming the following are set:

```
common=(--ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com")
common_mda=("${{common[@]}}" --mda maildrop)
gmail_common=(--ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com")
gmail_common_mda=("${{gmail_common[@]}}" --mda maildrop)

```

- Count how many messages older than 7 days are in `[Gmail]/All Mail` folder:
  ```
  imaparms count "${gmail_common[@]}" --folder "[Gmail]/All Mail" --older-than 7
  ```

- Mark all messages in `INBOX` as not `SEEN`, fetch all not `SEEN` messages marking them `SEEN` as you download them so that if the process gets interrupted you could continue from where you left off:
  ```
  # setup: do once
  imaparms mark "${common[@]}" --folder "INBOX" unseen

  # repeatable part
  imaparms fetch "${common_mda[@]}" --folder "INBOX"

  ```

- Similarly to the above, but run `imaparms fetch` as a daemon to download updates every hour:
  ```
  # setup: do once
  imaparms mark "${common[@]}" --folder "INBOX" unseen

  # repeatable part
  imaparms fetch "${common_mda[@]}" --folder "INBOX" --every 3600

  ```

- Fetch all messages from `INBOX` folder that were delivered in the last 7 days (the resulting date is rounded down to the start of the day by server time), but don't change any flags:
  ```
  imaparms fetch "${common_mda[@]}" --folder "INBOX" --all --newer-than 7
  ```

- Fetch all messages from `INBOX` folder that were delivered from the beginning of today (by server time):
  ```
  imaparms fetch "${common_mda[@]}" --folder "INBOX" --all --newer-than 0
  ```

- Delete all `SEEN` messages older than 7 days from `INBOX` folder:

  Assuming you fetched and backed up all your messages already this allows you to keep as little as possible on the server, so that if your account gets cracked/hacked, you won't be as vulnerable.

  ```
  imaparms delete "${common[@]}" --folder "INBOX" --older-than 7
  ```

  (`--seen` is implied by default)

- **DANGEROUS!** If you fetched and backed up all your messages already, you can skip `--older-than` and just delete all `SEEN` messages instead:
  ```
  imaparms delete "${common[@]}" --folder "INBOX"
  ```

  Though, setting at least `--older-than 1`, to make sure you won't lose any data in case you forgot you are running another instance of `imaparms` or another IMAP client that changes message flags (`imaparms` will abort if it notices another client doing it, but better be safe than sorry), is highly recommended anyway.

- Similarly to the above, but use `FLAGGED` instead of `SEEN`. This allows to use this in parallel with another instance of `imaparms` using the `SEEN` flag, e.g. if you want to backup to two different machines independently, or if you want to use `imaparms` simultaneously in parallel with `fetchmail` or other similar tool:
  ```
  # setup: do once
  imaparms mark "${common[@]}" --folder "INBOX" unflagged

  # repeatable part
  imaparms fetch "${common_mda[@]}" --folder "INBOX" --unflagged

  # this will work as if nothing of the above was run
  fetchmail

  # in this use case you should use both `--seen` and `--flagged` when expiring old messages to only delete messages fetched by both imaparms and fetchmail
  imaparms delete "${common[@]}" --folder "INBOX" --older-than 7 --seen --flagged

  ```

- Fetch everything GMail considers to be Spam for local filtering:
  ```
  # setup: do once
  mkdir -p ~/Mail/spam/{new,cur,tmp}

  cat > ~/.mailfilter-spam << EOF
  DEFAULT="$HOME/Mail/spam"
  EOF

  imaparms mark "${gmail_common[@]}" --folder "[Gmail]/Spam" unseen

  # repeatable part
  imaparms fetch "${gmail_common_mda[@]}" --mda "maildrop ~/.mailfilter-spam" --folder "[Gmail]/Spam"

  ```

- Fetch everything from all folders, except `INBOX` and `[Gmail]/Trash` (because messages in GMail `INBOX` are included `[Gmail]/All Mail`):
  ```
  imaparms fetch "${gmail_common_mda[@]}" --all-folders --not-folder "INBOX" --not-folder "[Gmail]/Trash"
  ```

- GMail-specific deletion mode: move (expire) old messages to `[Gmail]/Trash` and then delete them:

  In GMail, deleting messages from `INBOX` does not actually delete them, nor moves them to trash, just removes them from `INBOX` while keeping them available from `[Gmail]/All Mail`.

  To work around this, this tool provides a GMail-specific `--method gmail-trash` that moves messages to `[Gmail]/Trash` in a GMail-specific way (this is not a repetition, it does require issuing special IMAP `STORE` commands to achieve this):

  ```
  imaparms delete "${gmail_common[@]}" --folder "[Gmail]/All Mail" --older-than 7
  ```

  (`--method gmail-trash` is implied by `--host imap.gmail.com` and `--folder` not being `[Gmail]/Trash`, `--seen` is still implied by default)

  Messages in `[Gmail]/Trash` will be automatically removed by GMail in 30 days, but you can also delete them immediately with:

  ```
  imaparms delete "${gmail_common[@]}" --folder "[Gmail]/Trash" --all --older-than 7
  ```

  (`--method delete` is implied by `--host imap.gmail.com` but `--folder` being `[Gmail]/Trash`)

