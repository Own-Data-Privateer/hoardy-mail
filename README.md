# What?

A Keep It Stupid Simple (KISS) Swiss army knife tool for interacting with IMAP4 servers: login to a specified server, perform specified actions on messages in specified folders matching specified criteria.

The main use case I made this for is as follows:

- you periodically fetch and backup your mail somehow (e.g. with `fetchmail` and `rsync`/`git`/`bup`) and then,
- after your backup succeeds, you run this tool and remove old (older than zero or more intervals between backups) already-fetched messages from your mail servers,
- so that when/if your account get cracked/hacked you are not as exposed.

After all, nefarious actors getting all of your unfetched + zero or more days of your fetched mail is much better than them getting the whole last 20 years or whatever of your correspondence.
(And if your personal computer gets compromised enough, attackers will eventually get everything anyway, so deleting old mail from servers does not make things worse.)

This tool was inspired by [IMAPExpire](https://gitlab.com/mikecardwell/IMAPExpire) which I used and (privately) patched bugs out of for years before getting tired of it and deciding it would be simpler to just write my own thingy.
Unlike IMAPExpire this

- is written in Python instead of Perl and requires nothing but the basic Python install, no third-party libraries needed;
- allows all UNICODE characters except `\n` in passwords/passphrases (yes, including spaces, quotes, etc),
- provides `--seen` option and uses it by default for destructive actions, so you won't accidentally delete any messages you have not yet fetched;
- provides GMail-specific options.

You can even run this tool without installing it like this:
```
python3 -m imaparms.__main__ --help
```

# Some Fun and Relevant Facts

Note that [Snowden revelations](https://en.wikipedia.org/wiki/Global_surveillance_disclosures_(2013%E2%80%93present)) mean that Google and US Government store copies of all of your correspondence since 2001-2009 (it depends) even if you delete everything from all the servers.

And they wiretap basically all the traffic going though international Internet exchanges because they wiretap all underwater cables.
Simply because they can, apparently?

(Which is a bit creepy, if you ask me.
If you think about it, there is absolutely no point to doing this if you are trying to achieve the stated signal-intelligence goals.
Governments and organized crime use one-time-pads since 1950s.
AES256 + 32 bytes of shared secret + some simple [steganography](https://en.wikipedia.org/wiki/Steganography) and even if the signal gets discovered, no quantum-computer will ever be able to break it, no research into [quantum-safe cryptography](https://en.wikipedia.org/wiki/Post-quantum_cryptography) needed.
So, clearly, this data collection only works against private citizens and civil society which have no ways to distribute symmetric keys and thus have to use public-key cryptography.)

Globally, >70% of all e-mails originate from or get delivered to Google servers (GMail, GMail on custom domains, corporate GMail).

Most e-mails never gets E2E-encrypted at all, `(100 - epsilon)`% (so, basically, 100%) of all e-mails sent over the Internet never get encrypted with quantum-safe cryptography in-transit.

So, eventually, US Government will get plain-text for almost everything you ever sent (unless you are a government official, work for well-organized crime syndicate, or you and all your friends are really paranoid).
Which means that, unless they come to their senses there and shred all that data, eventually, all that mail will get stolen.

So, in the best case scenario, a simple relatively benign blackmail-everyone-you-can-to-get-as-much-money-as-possible AI will be able organize a personal WikiLeaks-style breach, for every single person on planet Earth.
No input from nefarious humans interested in exploiting *personally you* required.
After all, you are not that interesting, so you have nothing to fear, nothing to hide, and you certainly did not write any still-embarrassing e-mails when you were 16 years old and did not send any nudes of yourself or anyone else to anyone (including any doctors, during the pandemic) ever.

It would be glorious!
Wouldn't it?

(Seriously, abstractly speaking, I'm kinda interested in civilization-wide legal and cultural effects of *every embarrassing, even slightly illegal and/or hypocritical thing every person ever did* relentlessly programmatically exploited as blackmail or worse.
Non-abstractly speaking, the fact that governments spend public money to make this possible creeps me out.
After all, hoarding of exploitable material worked so well with [EternalBlue](https://en.wikipedia.org/wiki/EternalBlue), and that thing was a fixable bug, which leaked blackmail is not.)

That is to say, as a long-term defense measure, this tool is probably useless.
All your mail will get leaked eventually, regardless.
Short-term and against random exploitations of your mail servers, this thing is perfect, IMHO.

# GMail: Some Fun and Relevant Facts

GMail considers IMAP/SMTP to be "insecure", so to use it you will have to enable 2FA in your account settings and then add an application-specific password for IMAP/SMTP access.

(Which is kinda funny, given that [signing in with Google prompts](https://web.archive.org/web/20230702050207/https://support.google.com/accounts/answer/7026266?co=GENIE.Platform%3DAndroid&hl=en) exists.
I.e. you can borrow their phone, unlock it (passcode? peek over their shoulder or just get some video surveillance footage of them typing it in public; fingerprint? they leave their fingerprints all over the device itself, dust with some flour, take a photo, apply some simple filters, 3D-print the result, this actually takes ~3 minutes to do if you know what you are doing), ask Google to authenticate via prompt.
Done, you can login to everything with no password needed.
And Google appears to give no way to disable Google prompts if your account has an attached Android device.
Though, you can make Google prompts ask for a password too, but that feature need special setup.
Meanwhile, "legacy" passwords are not secure, apparently?)

Then, to enable 2FA, even for very old accounts that never used anything phone or Android-related, for no rational reasons, GMail requires specifying a working phone number that can receive SMS.
Which you can then simply remove after you copied your OTP secret into an authentificator of your choice.

Sorry, why did you need the phone number, again?
Ah, well, Google now knows it and will be able track your movements by buying location data from your network operator.
Thank you very much.

# Usage

## imaparms [--version] [-h] [--help-markdown] {count,delete} ...

Login to an IMAP4 server and perform actions on messages in specified folders matching specified criteria.

- optional arguments:
  - `--version`
  : show program's version number and exit
  - `-h, --help`
  : show this help message and exit
  - `--help-markdown`
  : show this help message formatted in Markdown and exit

- subcommands:
  - `{count,delete}`
    - `count`
    : count how many matching messages specified folders (or all of them, by default) contain
    - `delete`
    : delete matching messages from specified folders

### imaparms count [--debug] (--plain | --ssl | --starttls) --host HOST [--port PORT] --user USER (--passfile PASSFILE | --passcmd PASSCMD) [--folder FOLDERS] [--all | --seen | --unseen] [--older-than DAYS] [--newer-than DAYS] [--from ADDRESS] [--not-from ADDRESS]

- optional arguments:
  - `--folder FOLDERS`
  : mail folders to operane on; can be specified multiple times; default: all available mail folders

- debugging:
  - `--debug`
  : print IMAP conversation to stderr

- server connection:
  - `--plain`
  : connect via plain-text socket
  - `--ssl`
  : connect over SSL socket
  - `--starttls`
  : connect via plain-text socket, but then use STARTTLS command
  - `--host HOST`
  : IMAP server to connect to
  - `--port PORT`
  : port to use; default: 143 for `--plain` and `--starttls`, 993 for `--ssl`
  - `--user USER`
  : username on the server
  - `--passfile PASSFILE`
  : file containing the password
  - `--passcmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- message search filters:
  - `--all`
  : operate on all messages (default)
  - `--seen`
  : operate on messages marked as seen
  - `--unseen`
  : operate on messages not marked as seen
  - `--older-than DAYS`
  : operate on messages older than this many days
  - `--newer-than DAYS`
  : operate on messages not older than this many days
  - `--from ADDRESS`
  : operate on messages that have this string as substring of their header's FROM field; can be specified multiple times
  - `--not-from ADDRESS`
  : operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times

### imaparms delete [--debug] [--dry-run] (--plain | --ssl | --starttls) --host HOST [--port PORT] --user USER (--passfile PASSFILE | --passcmd PASSCMD) [--method {auto,delete,delete-noexpunge,gmail-trash}] --folder FOLDERS [--all | --seen | --unseen] [--older-than DAYS] [--newer-than DAYS] [--from ADDRESS] [--not-from ADDRESS]

- optional arguments:
  - `--method {auto,delete,delete-noexpunge,gmail-trash}`
  : delete messages how:
    - `auto`: `gmail-trash` when `--host imap.gmail.com` and `--folder` is not (single) `[Gmail]/Trash`, `delete` otherwise (default)
    - `delete`: mark messages with `\Deleted` flag and then use IMAP `EXPUNGE` command, i.e. this does what you would expect a "delete" command to do, works for most IMAP servers
    - `delete-noexpunge`: mark messages with `\Deleted` flag but skip issuing IMAP `EXPUNGE` command hoping the server does as RFC2060 says and auto-`EXPUNGE`s messages on IMAP `CLOSE`; this is much faster than `delete` but some servers (like GMail) fail to implement this properly
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
  : connect over SSL socket
  - `--starttls`
  : connect via plain-text socket, but then use STARTTLS command
  - `--host HOST`
  : IMAP server to connect to
  - `--port PORT`
  : port to use; default: 143 for `--plain` and `--starttls`, 993 for `--ssl`
  - `--user USER`
  : username on the server
  - `--passfile PASSFILE`
  : file containing the password
  - `--passcmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- required arguments:
  - `--folder FOLDERS`
  : mail folders to operate on; can be specified multiple times

- message search filters:
  - `--all`
  : operate on all messages
  - `--seen`
  : operate on messages marked as seen (default)
  - `--unseen`
  : operate on messages not marked as seen
  - `--older-than DAYS`
  : operate on messages older than this many days
  - `--newer-than DAYS`
  : operate on messages not older than this many days
  - `--from ADDRESS`
  : operate on messages that have this string as substring of their header's FROM field; can be specified multiple times
  - `--not-from ADDRESS`
  : operate on messages that don't have this string as substring of their header's FROM field; can be specified multiple times

## Notes on usage

Specifying `--folder` multiple times will perform the specified action on all specified folders.

Message search filters are connected by logical "AND"s so `--from "github.com" --not-from "notifications@github.com"` will act on messages from "github.com" but not from "notifications@github.com".

Also note that destructive actions act on `--seen` messages by default.

## Examples

- List all available IMAP folders and count how many messages they contain:

  - with the password taken from the first line of the given file:
    ```
    imaparms count --ssl --host imap.example.com --user myself@example.com --passfile /path/to/file/containing/myself@example.com.password
    ```

  - with the password taken from the output of password-store util:
    ```
    imaparms count --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com"
    ```

- Delete all seen messages older than 7 days from `INBOX` folder:

  Assuming you fetched and backed up all your messages already this allows you to keep as little as possible on the server, so that if your account gets hacked, you won't be as vulnerable.

  ```
  imaparms delete --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX" --older-than 7
  ```

  Note that the above only removes `--seen` messages by default.

- **DANGEROUS!** If you fetched and backed up all your messages already, you can skip `--older-than` and just delete all `--seen` messages instead:
  ```
  imaparms delete --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX"
  ```

  Though, setting at least `--older-than 1` in case you forgot you had another fetcher running in parallel and you want to be sure you won't lose any data in case something breaks, is highly recommended anyway.

- Count how many messages older than 7 days are in `[Gmail]/Trash` folder:
  ```
  imaparms count --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --older-than 7
  ```

- GMail-specific deletion mode: move (expire) old messages from `[Gmail]/All Mail` to `[Gmail]/Trash`:

  Unfortunately, in GMail, deleting messages from `INBOX` does not actually delete them, nor moves them to trash, just removes them from `INBOX` while keeping them available from `[Gmail]/All Mail`.

  To work around this, this tool provides a GMail-specific deletion method that moves messages to `[Gmail]/Trash` in a GMail-specific way (this is not a repetition, it does require issuing special STORE commands to achieve this).

  You will probably want to run it over `[Gmail]/All Mail` folder (again, after you fetched everything from there) instead of `INBOX`:

  ```
  imaparms delete --method gmail-trash --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/All Mail" --older-than 7
  ```

  which is equivalent to simply

  ```
  imaparms delete --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/All Mail" --older-than 7
  ```

  since `--method gmail-trash` is the default when `--host imap.gmail.com` and `--folder` is not `[Gmail]/Trash`

  Also, note that the above only moves `--seen` messages by default.

  Messages in `[Gmail]/Trash` will be automatically removed by GMail in 30 days, but you can also delete them immediately with

  ```
  imaparms delete --method delete --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --all --older-than 7
  ```

  which is equivalent to simply

  ```
  imaparms delete --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --all --older-than 7
  ```

