# What?

A tool that logins to an IMAP4 server and performs actions on messages in specified folders matching specified criteria.

Inspired by <https://gitlab.com/mikecardwell/IMAPExpire>, but this

- is written in Python instead of Perl;
- requires nothing but the basic Python install, no third-party libraries needed;
- provides `--seen` option, so you won't accidentally delete any messages you have not yet fetched;
- provides GMail-specific commands.

# How to use?

Run `imaparms --help` for full documentation.

# Notes

GMail considers IMAP/SMTP to be "insecure", so to use it you will have to enable 2FA in your account settings and then add an application-specific password for IMAP/SMTP access. Enabling 2FA requires a phone number, which you can then replace by an OTP authentificator of your choice (but Google will now know your phone number and will track your movements by buying location data from your network operator).

# Examples

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
  imaparms delete --ssl --host imap.example.com --user myself@example.com --passcmd "pass show mail/myself@example.com" --folder "INBOX" --seen --older-than 7
  ```

- Count how many messages older than 7 days are in "[Gmail]/Trash" folder:
  ```
  imaparms count --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --older-than 7
  ```

- GMail-specific mode: move old messages from "[Gmail]/All Mail" to Trash:

  Unfortunately, in GMail, deleting messages from "INBOX" does not actually delete them, nor moves them to "Trash", just removes them from "INBOX", so this tool provides a GMail-specific command that moves messages to "Trash" on GMail:

  ```
  imaparms gmail-trash --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/All Mail" --seen --older-than 7
  ```

  after which you can now delete them (and other matching messages in Trash) with

  ```
  imaparms delete --ssl --host imap.gmail.com --user myself@gmail.com --passcmd "pass show mail/myself@gmail.com" --folder "[Gmail]/Trash" --older-than 7
  ```
