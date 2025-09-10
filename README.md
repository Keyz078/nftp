# nftp - Nextcloud SFTP-like CLI

`nftp` is a simple interactive CLI tool for Nextcloud, providing FTP/SFTP-like commands for file management.

---

## Features

* Login to Nextcloud and save session for faster next login.
* Interactive SFTP-like prompt (`nftp:<current_path>`).
* Navigate Nextcloud directories (`cd`, `pwd`, `ls`).
* Upload (`put`) and download (`get`) single files.
* Create and delete folders (`mkdir`, `rmdir`).
* Delete files or folders (`rm`) with confirmation.
* Local commands: `lls`, `lpwd`, `lcd`.
* Built-in help menu (`help`) for all commands.
* Supports filenames and paths with spaces.

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Keyz078/nftp.git
cd nftp
```

2. Make the script executable:

```bash
chmod +x nftp
```

3. Run:

```bash
./nftp
```

> Requires Bash shell environment.

---

## Usage

### SFTP-like Prompt

Once started, you will see:

```
nftp:/>
```

### Remote Commands

| Command            | Description                                   |
| ------------------ | --------------------------------------------- |
| `ls`               | List files and folders in current remote path |
| `pwd`              | Show current remote path                      |
| `cd <dir>`         | Change remote directory                       |
| `get <file>`       | Download remote file to local machine         |
| `put <local_file>` | Upload local file to current remote directory |
| `mkdir <folder>`   | Create remote folder                          |
| `rm <file/folder>` | Delete remote file/folder (confirmation)      |
| `rmdir <folder>`   | Delete empty remote folder (confirmation)     |
| `help`             | Show help menu                                |
| `exit`             | Exit CLI                                      |

### Local Commands

| Command     | Description                               |
| ----------- | ----------------------------------------- |
| `lls`       | List files and folders in local directory |
| `lpwd`      | Show current local directory              |
| `lcd <dir>` | Change local directory                    |

---

### Examples

#### Navigate and download a file

```bash
nftp:/Documents> cd Reports
nftp:/Documents/Reports> ls
report1.pdf
nftp:/Documents/Reports> get report1.pdf
```

#### Upload a local file

```bash
nftp:/Documents> put ~/Downloads/file.txt
```

#### Create a new folder and upload

```bash
nftp:/Documents> mkdir NewFolder
nftp:/Documents> cd NewFolder
nftp:/Documents/NewFolder> put ~/Downloads/file.txt
```

---

## Notes

* Only **one file at a time** can be uploaded or downloaded.
* Directories are suffixed with `/` when listed (`Reports/`).
* Session is saved in `~/.nextcloud_session` for faster login next time.
* Supports spaces in filenames and paths.
* Use `help` to see all commands.

---

## License

MIT License
