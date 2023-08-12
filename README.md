# What?

A tool that logins to an IMAP4 server and performs actions on messages in specified folders matching specified criteria.

Inspired by <https://gitlab.com/mikecardwell/IMAPExpire>, but this

- is written in Python instead of Perl;
- requires nothing but the basic Python install, no third-party libraries needed;
- provides `--seen` option, so you won't accidentally delete any messages you have not yet fetched;
- provides GMail-specific commands.

# Usage

## imaparms [--version] [-h] [--help-markdown] {count,delete,gmail-trash} ...

Login to an IMAP4 server and perform actions on messages in specified folders matching specified criteria.

- optional arguments:
  - `--version`
  : show program's version number and exit
  - `-h, --help`
  : show this help message and exit
  - `--help-markdown`
  : show this help message formatted in Markdown and exit

- subcommands:
  - `{count,delete,gmail-trash}`
    - `count`
    : count how many matching messages specified folders (or all of them, by default) contain
    - `delete`
    : delete (and expunge) matching messages from all specified folders
    - `gmail-trash`
    : GMail-specific: move matching messages to GMail's Trash folder from all specified folders

### imaparms count [--debug] [--dry-run] (--plain | --ssl | --starttls) --host HOST [--port PORT] --user USER (--passfile PASSFILE | --passcmd PASSCMD) [--folder FOLDERS] [--all | --seen | --unseen] [--older-than DAYS] [--newer-than DAYS] [--from HFROM]

- optional arguments:
  - `--folder FOLDERS`
  : mail folders to operane on; can be specified multiple times; default: all available mail folders

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
  : port to use; default: 143 for --plain and --starttls, 993 for --ssl
  - `--user USER`
  : username on the server
  - `--passfile PASSFILE`
  : file containing the password
  - `--passcmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- message search filters:
  - `--all`
  : operate on all messages; the default
  - `--seen`
  : operate on messages marked as seen
  - `--unseen`
  : operate on messages not marked as seen
  - `--older-than DAYS`
  : operate on messages older than this many days
  - `--newer-than DAYS`
  : operate on messages not older than this many days
  - `--from HFROM`
  : operate on messages that have this string as substring of their header's FROM field

### imaparms delete [--debug] [--dry-run] (--plain | --ssl | --starttls) --host HOST [--port PORT] --user USER (--passfile PASSFILE | --passcmd PASSCMD) --folder FOLDERS [--all | --seen | --unseen] [--older-than DAYS] [--newer-than DAYS] [--from HFROM]

- optional arguments:
  - `--folder FOLDERS`
  : mail folders to operate on; can be specified multiple times; required

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
  : port to use; default: 143 for --plain and --starttls, 993 for --ssl
  - `--user USER`
  : username on the server
  - `--passfile PASSFILE`
  : file containing the password
  - `--passcmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- message search filters:
  - `--all`
  : operate on all messages
  - `--seen`
  : operate on messages marked as seen; the default
  - `--unseen`
  : operate on messages not marked as seen
  - `--older-than DAYS`
  : operate on messages older than this many days
  - `--newer-than DAYS`
  : operate on messages not older than this many days
  - `--from HFROM`
  : operate on messages that have this string as substring of their header's FROM field

### imaparms gmail-trash [--debug] [--dry-run] (--plain | --ssl | --starttls) --host HOST [--port PORT] --user USER (--passfile PASSFILE | --passcmd PASSCMD) --folder FOLDERS [--all | --seen | --unseen] [--older-than DAYS] [--newer-than DAYS] [--from HFROM]

- optional arguments:
  - `--folder FOLDERS`
  : mail folders to operate on; can be specified multiple times; required

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
  : port to use; default: 143 for --plain and --starttls, 993 for --ssl
  - `--user USER`
  : username on the server
  - `--passfile PASSFILE`
  : file containing the password
  - `--passcmd PASSCMD`
  : shell command that returns the password as the first line of its stdout

- message search filters:
  - `--all`
  : operate on all messages
  - `--seen`
  : operate on messages marked as seen; the default
  - `--unseen`
  : operate on messages not marked as seen
  - `--older-than DAYS`
  : operate on messages older than this many days
  - `--newer-than DAYS`
  : operate on messages not older than this many days
  - `--from HFROM`
  : operate on messages that have this string as substring of their header's FROM field

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

- Delete seen messages older than 7 days from "INBOX" folder:

  Assuming you fetched and backed up all your messages already this allows you to keep as little as possible on the server, so that if your account gets hacked, you won't be as vulnerable.

  ```
  imaparms delete --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX" --older-than 7
  ```

  (note that this only deletes `--seen` messages by default)

- Count how many messages older than 7 days are in "[Gmail]/Trash" folder:
  ```
  imaparms count --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --older-than 7
  ```

- GMail-specific mode: move old messages from "[Gmail]/All Mail" to Trash:

  Unfortunately, in GMail, deleting messages from "INBOX" does not actually delete them, nor moves them to "Trash", just removes them from "INBOX", so this tool provides a GMail-specific command that moves messages to "Trash" on GMail:

  ```
  imaparms gmail-trash --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/All Mail" --older-than 7
  ```

  (note that this only moves `--seen` messages by default)

  after which you can now delete them (and other matching messages in Trash) with

  ```
  imaparms delete --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --all --older-than 7
  ```

## Notes

GMail considers IMAP/SMTP to be "insecure", so to use it you will have to enable 2FA in your account settings and then add an application-specific password for IMAP/SMTP access. Enabling 2FA requires a phone number, which you can then replace by an OTP authentificator of your choice (but Google will now know your phone number and will track your movements by buying location data from your network operator).

