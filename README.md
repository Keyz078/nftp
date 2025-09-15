# nftp - Nextcloud SFTP-like WEBDAV CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

`nftp` is a simple interactive WEBDAV CLI tool for Nextcloud, providing SFTP-like commands for file management.

---

## Features

* Login to Nextcloud and save session for faster next login.
* Interactive SFTP-like prompt (`nftp:<current_path>`).
* Navigate Nextcloud directories (`cd`, `pwd`, `ls`).
* Upload (`put`) and download (`get`) multiple files.
* Create and delete folders (`mkdir`, `rmdir`).
* Delete files or folders (`rm`) with confirmation.
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
wget https://github.com/Keyz078/nftp/releases/download/v0.1.0/nftp-amd64.tar.gz

# for arm64
wget https://github.com/Keyz078/nftp/releases/download/v0.1.0/nftp-arm64.tar.gz
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

| Command            | Description                                   |
| ------------------ | --------------------------------------------- |
| `ls`               | List files and folders in current remote path |
| `pwd`              | Show current remote path                      |
| `cd <dir>`         | Change remote directory                       |
| `get <file1> <file2>`       | Download multiple remote file to local machine         |
| `put <local_file>` | Upload multiple local file to current remote directory |
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

* Directories are suffixed with `/` when listed (`Reports/`).
* Session is saved in `~/.nextcloud_session` for faster login next time.
* Supports spaces in filenames and paths.
* Use `help` to see all commands.

---

## License

[MIT License](./LICENSE)
