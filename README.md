# nftp - Nextcloud SFTP-like WEBDAV CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

`nftp` is a simple interactive WEBDAV CLI tool for Nextcloud, providing SFTP-like commands for file management.

---

## Features

* Login to Nextcloud and save session for faster next login.
* Interactive SFTP-like prompt (`nftp:<current_path>`).
* Navigate Nextcloud directories (`cd`, `pwd`, `ls`).
* Upload (`put`) and download (`get`) multiple files (Recursive not supported).
* Create and delete directories (`mkdir`, `rmdir`).
* Copy and move items (`cp`, `mv`).
* Delete files or directories (`rm`, `rmdir`) with confirmation.
* Local commands: `lls`, `lpwd`, `lcd`.
* Built-in help menu (`help`) for all commands.
* Supports filenames and paths with spaces.

---

## Installation

### python method
1. Clone the repository:

```bash
git clone https://github.com/Keyz078/nftp.git
cd nftp
pip3 install -r requirements.txt
python3 nftp.py
```

### Binary method

1. Download binary
```bash
# for amd64
wget https://github.com/Keyz078/nftp/releases/download/v0.1.1/nftp-amd64.tar.gz

# for arm64
wget https://github.com/Keyz078/nftp/releases/download/v0.1.1/nftp-arm64.tar.gz
```
2. Extract and make the script executable:

```bash
tar xzvf nftp-{arch}.tar.gz
chmod +x nftp-{arch}
sudo mv nft-{arch} /usr/local/bin/nftp
```

3. Run:

```bash
nftp
```

---

## Usage

### SFTP-like Prompt

Once started, you will see:

```
nftp:/>
```

### Remote Commands

| Command                                        | Description                                                     |
|------------------------------------------------|-----------------------------------------------------------------|
| `ls [-l] [-h] [-lh]`                           | List files and directories in current remote path               |
| `pwd`                                          | Show current remote path                                        |
| `cd <dir>`                                     | Change remote directory                                         |
| `get <file1> <file2> ...`                      | Download multiple remote file to local                          |
| `put <local_file1> <local_file2> ... <target>` | Upload multiple local files (last args can be directory target) |
| `cp <src> <src> ... <target> [-i] [-r]`        | Copy items on server                                            |
| `mv <src> <src> ... <target> [-i]`             | Move items on server                                            |
| `mkdir <directories>`                          | Create remote directories                                       |
| `rm <file/directories>` [-f]                   | Delete remote file/directories recursively (confirmation)       |
| `rmdir <directories>`                          | Delete empty remote directories (confirmation)                  |
| `help`                                         | Show help menu                                                  |
| `exit`                                         | Exit CLI                                                        |
| `logout`                                       | Logout from the server (clear session)                          |

### Local Commands

| Command     | Description                               |
| ----------- | ----------------------------------------- |
| `lls`       | List files and directories in local directory |
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

* Directories are suffixed with `/` when listed (`Reports/`).
* Session is saved in `~/.nextcloud_session` for faster login next time.
* Supports spaces in filenames and paths.
* Use `help` to see all commands.

---

## License

[MIT License](./LICENSE)
