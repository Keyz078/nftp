#!/usr/bin/env python3
import os
import sys
import base64
import requests
import urllib3
import readline
import shutil
import shlex
import xml.etree.ElementTree as ET
import argparse
from email.utils import parsedate_to_datetime
from getpass import getpass
from tqdm import tqdm
from urllib.parse import quote, urlparse
import posixpath
import subprocess

VERSION = "dev"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SESSION_FILE = os.path.expanduser("~/.nextcloud_session")
CURRENT_PATH = "/"
URL = ""
CREDS = ""
USERNAME = ""
BASE_URL = ""
NS = {"d": "DAV:"}  # XML namespace

# ----------------- UTILITIES -----------------
def show_help():
    print("""
===== Nextcloud WebDAV CLI Help =====
Available Commands:
  ls    [-l] [-h] [-lh]                             - List files and directories in the current Nextcloud path
  pwd                                               - Show current Nextcloud directory
  cd    <dir>                                       - Change directory
  lls                                               - List files and directories in local
  lpwd                                              - Show current local directory
  lcd   <dir>                                       - Change local directory
  get   <file1> <file2> ...                         - Download file to local machine
  put   <local_file1> <local_file2>...              - Upload local file to current Nextcloud directory
  mkdir <directory>                                 - Create a directory
  rm    <target1> <target2> ... [-f]                - Delete file/directory (confirmation)
  rmdir <dir1> <dir2>...                            - Delete empty directory (confirmation)
  cp    <src1> <src2> ... <target>  [-i] [-r]       - Copy items on server (interactive)
  mv    <src1> <src2> ... <target>  [-i]            - Move items on server (interactive)
  logout                                            - Logout from the server (clear session)
  clear                                             - Clean the screen
  help                                              - Show this help
  exit                                              - Exit CLI
""")

# ----------------- PATH UTILITIES -----------------
def encode_creds(username, password):
    return base64.b64encode(f"{username}:{password}".encode()).decode()

def encode_path(path):
    return quote(path, safe="/")

def expand_nc_path(path):
    if path == "~":
        return "/"
    elif path.startswith("~/"):
        return posixpath.join("/", path[2:])
    elif path.startswith("~"):
        return posixpath.join("/", path[1:])
    elif path.startswith("/"):
        return posixpath.normpath(path)
    elif path == ".":
        return CURRENT_PATH
    else:
        return posixpath.normpath(posixpath.join(CURRENT_PATH, path))


def ask_yes_no(prompt):
    while True:
        ans = input(f"{prompt} (Y/n): ").strip().lower()
        if ans in ["y", "yes", ""]:
            return True
        elif ans in ["n", "no"]:
            return False

def load_session():
    global URL, CREDS
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE) as f:
            for line in f:
                if line.startswith("URL="):
                    URL = line.strip().split("=", 1)[1].strip('"')
                elif line.startswith("CREDS="):
                    CREDS = line.strip().split("=", 1)[1].strip('"')

def save_session():
    with open(SESSION_FILE, "w") as f:
        f.write(f'URL="{URL}"\n')
        f.write(f'CREDS="{CREDS}"\n')
    os.chmod(SESSION_FILE, 0o600)

# ----------------- FILE STREAM -----------------
def file_stream(source, total=0, mode="read", desc=""):
    chunk_size = 8192
    if mode == "read":
        with tqdm(total=total, unit="B", unit_scale=True, unit_divisor=1024, desc=desc) as bar:
            for chunk in source.iter_content(chunk_size=chunk_size):
                if chunk:
                    bar.update(len(chunk))
                    yield chunk
    elif mode == "write":
        with open(source, "rb") as f, tqdm(total=total, unit="B", unit_scale=True, unit_divisor=1024, desc=desc) as bar:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                bar.update(len(chunk))
                yield chunk

# ----------------- WEBDAV REQUEST -----------------
def nextcloud_request(method, path, data=None, destination=None, suppress=None):
    headers = {"Authorization": f"Basic {CREDS}"}
    if destination:
        headers["Destination"] = f"{BASE_URL}{encode_path(destination)}"
        headers["Overwrite"] = "T"
    encoded_path = encode_path(path)
    url = f"{BASE_URL}{encoded_path}"
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            data=data,
            verify=False,
            timeout=30,
            stream=True if method == "GET" else False
        )
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        if not (suppress and e.response.status_code in (suppress if isinstance(suppress, (list, set, tuple)) else [suppress])):
            print(f"HTTP Error: {e.response.status_code} - {e.response.reason}")
        return e.response
    except requests.exceptions.SSLError:
        print(f"SSL Error: Is the server running on http?")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
        return None

# ----------------- PROPFIND & PARSING UTILITIES -----------------
def propfind_path(path, suppress=None):
    response = nextcloud_request("PROPFIND", path, suppress=suppress)
    if not response or response.status_code not in [200, 207]:
        return None
    try:
        root = ET.fromstring(response.text)
        return root
    except ET.ParseError:
        print(f"Failed to parse server response for '{path}'")
        return None

def is_directory(path):
    root = propfind_path(f"{path.rstrip('/')}/", suppress=404)
    if root is None:
        return False
    hrefs = [elem.text for elem in root.findall("d:response/d:href", NS)]
    # If only one href and it does not end with '/', it's a file
    if len(hrefs) == 1 and not hrefs[0].endswith("/"):
        return False
    return True

def get_item_info(resp):
    href = resp.find("d:href", NS).text
    name = os.path.basename(href.rstrip("/"))
    name = requests.utils.unquote(name)
    is_dir = href.endswith("/")
    size_elem = resp.find(".//d:getcontentlength", NS)
    size = int(size_elem.text) if size_elem is not None and size_elem.text else 0
    lastmod = None
    lastmod_elem = resp.find(".//d:getlastmodified", NS)
    if lastmod_elem is not None and lastmod_elem.text:
        try:
            dt = parsedate_to_datetime(lastmod_elem.text)
            lastmod = dt.astimezone().strftime("%Y-%m-%d %H:%M")
        except Exception:
            lastmod = lastmod_elem.text
    return {
        "name": name,
        "is_dir": is_dir,
        "size": size,
        "lastmod": lastmod
    }

# ----------------- LOGIN -----------------
def validate_url(url):
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)

def login():
    global URL, CREDS, USERNAME, BASE_URL
    try:
        load_session()
        if CREDS:
            USERNAME = base64.b64decode(CREDS).decode().split(":")[0]
            print(f"Saved session found for: {URL} as {USERNAME}")
            if not ask_yes_no("Continue this session?"):
                os.remove(SESSION_FILE)
                URL = ""
                CREDS = ""
                print("Session cleared. Please login again.")

        if not URL:
            URL = input("Enter Nextcloud URL (http/https): ").strip()
            if not validate_url(URL):
                print("Invalid URL. Must start with http:// or https://")
                sys.exit(1)
            USERNAME = input("Username: ").strip()
            PASSWORD = getpass("Password: ").strip()
            CREDS = encode_creds(USERNAME, PASSWORD)
        else:
            USERNAME = base64.b64decode(CREDS).decode().split(":")[0]

        BASE_URL = f"{URL}/remote.php/dav/files/{USERNAME}"

        response = nextcloud_request("PROPFIND", "/")
        if response is None:
            print("Connection failed: Could not reach server or invalid URL.")
            sys.exit(1)
        elif response.status_code in [200, 207]:
            if not os.path.exists(SESSION_FILE) and ask_yes_no("Save session for next time?"):
                save_session()
                print(f"Session saved to {SESSION_FILE}")
        elif response.status_code == 401:
            print("Login failed: Invalid username or password. Old session cleared.")
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            sys.exit(1)
        else:
            print(f"Connection failed: HTTP {response.status_code}")
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            sys.exit(1)

    except (EOFError, KeyboardInterrupt):
        print("\nLogin cancelled.")
        sys.exit(1)

# ----------------- Logout -----------------
def logout():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
        print("Session cleared.")
        sys.exit("Logged out")
    else:
        print("No session to clear.")

# ----------------- LOCAL COMMANDS -----------------
def local_ls(args):
    try:
        subprocess.run(["ls"] + args)
    except FileNotFoundError:
        print("Error: 'ls' command not found.")
    except Exception as e:
        print(f"Error running local command: {e}")

def local_cd(args):
    try:
        os.chdir(" ".join(args))
    except FileNotFoundError:
        print(f"No such directory: {' '.join(args)}")
    except Exception as e:
        print(f"Error changing directory: {e}")

# ----------------- SERVER COMMANDS -----------------

# ----------------- LS COMMAND -----------------
def ls_command(args):
    global CURRENT_PATH

    long_format = False
    human_readable = False
    paths = []

    for a in args:
        if a.startswith("-") and len(a) > 1:
            for ch in a[1:]:
                if ch == "l":
                    long_format = True
                elif ch == "h":
                    human_readable = True
                else:
                    print(f"Unknown flag: -{ch}")
                    print("Usage: ls [-l] [-h] [path...]")
                    return
        else:
            paths.append(a)

    if not paths:
        paths = [CURRENT_PATH]

    def fmt_size(num):
        if not human_readable:
            return str(num)
        for unit in ["B", "K", "M", "G", "T"]:
            if num < 1024.0:
                return f"{num:3.1f}{unit}"
            num /= 1024.0
        return f"{num:.1f}P"

    def print_item(item):
        if long_format:
            ftype = "d" if item["is_dir"] else "-"
            size_str = fmt_size(item["size"]).rjust(8)
            date_str = item["lastmod"] if item["lastmod"] else "-"
            label = item["name"] + ("/" if item["is_dir"] else "")
            print(f"{ftype} {size_str} {date_str} {label}")
        else:
            label = item["name"] + ("/" if item["is_dir"] else "")
            print(label)

    def list_path(target):
        target = target.rstrip("/") if target != "/" else "/"

        root = propfind_path(target, suppress=404)
        if root is None:
            print(f"ls: cannot access '{target}': No such file or directory")
            return

        responses = root.findall("d:response", NS)
        if not responses:
            print(f"ls: cannot access '{target}': No such file or directory")
            return

        target_resp = responses[0]
        href = target_resp.find("d:href", NS).text
        is_dir = href.endswith("/")

        if not is_dir:
            item = get_item_info(target_resp)
            print_item(item)
            return

        items = []
        for resp in responses[1:]:
            item = get_item_info(resp)
            # Skip current user folder or folder itself
            if not item["name"] or item["name"] == USERNAME or item["name"] == os.path.basename(target):
                continue
            items.append(item)

        if not items:
            print("Directory is empty.")
            return

        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        if long_format:
            for item in items:
                print_item(item)
        else:
            combined = [item["name"] + ("/" if item["is_dir"] else "") for item in items]
            term_width = shutil.get_terminal_size((80, 20)).columns
            max_len = max(len(item) for item in combined) + 2
            cols = max(1, term_width // max_len)
            rows = (len(combined) + cols - 1) // cols
            for r in range(rows):
                for c in range(cols):
                    idx = c * rows + r
                    if idx < len(combined):
                        print(combined[idx].ljust(max_len), end="")
                print()

    for p in paths:
        target = expand_nc_path(p)
        if len(paths) > 1:
            print(f"\n{p}:")
        list_path(target)

# ----------------- CP/MV COMMAND -----------------
def handle_copy_move(args, operation="COPY"):
    interactive = False
    recursive = False
    non_flag_args = []
    usage_message=f"Usage: {'cp' if operation == 'COPY' else 'mv'} {'[-r] [-i]' if operation == 'COPY' else '[-i]'} <source1> <source2> ... <target>"
    for a in args:
        if a.startswith("-") and len(a) > 1:
            for ch in a[1:]:
                if ch == "i":
                    interactive = True
                elif ch == "r" and operation == "COPY":
                    recursive = True
                else:
                    print(f"Unknown flag: -{ch}")
                    print(usage_message)
                    return
        else:
            non_flag_args.append(a)

    if len(non_flag_args) < 2:
        print(usage_message)
        return

    target = expand_nc_path(non_flag_args[-1])
    sources = non_flag_args[:-1]

    target_is_dir = is_directory(target)

    if len(sources) > 1 and not target_is_dir:
        print(f"{'cp' if operation == 'COPY' else 'mv'}: target '{target}' is not a directory")
        return

    for src in sources:
        src_path = expand_nc_path(src)
        root = propfind_path(src_path, suppress=404)
        if root is None:
            print(f"{'cp' if operation == 'COPY' else 'mv'}: '{src}' no such file or directory.")
            continue

        hrefs = [resp.find("d:href", NS).text for resp in root.findall("d:response", NS)]
        is_dir = any(h.endswith("/") for h in hrefs)

        if operation == "COPY" and is_dir and not recursive:
            print(f"cp: {src_path} is a directory, use -r to copy recursively")
            continue

        dst_path = posixpath.normpath(
            f"{target.rstrip('/')}/{posixpath.basename(src_path)}"
        ) if target_is_dir else target

        if posixpath.normpath(src_path) == posixpath.normpath(dst_path):
            print(f"{operation.lower()}: '{src}' and '{dst_path}' are the same file")
            continue

        if interactive:
            check_exists_root = propfind_path(dst_path, suppress=404)
            if check_exists_root is not None:
                if not ask_yes_no(f"Overwrite '{dst_path}'?"):
                    print("Skipped.")
                    continue

        resp = nextcloud_request(operation, src_path, destination=dst_path)
        if resp:
            print(f"{'Copied' if operation == 'COPY' else 'Moved'} '{src}' to '{dst_path}'. (status {resp.status_code})")
        else:
            print(f"Error: Failed to {'cp' if operation == 'COPY' else 'mv'} '{src}' to '{dst_path}'.")

cp_command = lambda args: handle_copy_move(args, operation="COPY")
mv_command = lambda args: handle_copy_move(args, operation="MOVE")

# ----------------- GET COMMAND -----------------
def get_command(args):
    for file in args:
        file_path = expand_nc_path(file)
        root = propfind_path(file_path)
        if root is None:
            print(f"Error: '{file}' not found.")
            continue

        hrefs = [resp.find("d:href", NS).text for resp in root.findall("d:response", NS)]
        if any(h.endswith("/") for h in hrefs):
            print(f"Error: '{file}' is a directory.")
            continue

        get_response = nextcloud_request("GET", file_path)
        if not get_response:
            continue

        local_filename = os.path.basename(file)
        print(f"Downloading '{file}'...")
        total = int(get_response.headers.get("content-length", 0))
        try:
            with open(local_filename, "wb") as f:
                for chunk in file_stream(get_response, total=total, mode="read", desc=local_filename):
                    f.write(chunk)
            print(f"Download successful: '{local_filename}'")
        except Exception as e:
            print(f"Error during file write: {e}")
            if os.path.exists(local_filename):
                os.remove(local_filename)

# ----------------- PUT COMMAND -----------------
def put_command(args):
    if not args:
        print("Usage: put <local_file1> <local_file2> ... [target_directory]")
        return

    possible_target = expand_nc_path(args[-1])
    target_is_dir = is_directory(possible_target)

    if target_is_dir:
        local_files = args[:-1]
        target_dir = possible_target
    else:
        local_files = args
        target_dir = CURRENT_PATH

    if not local_files:
        print("No local files specified to upload.")
        return

    for local_file in local_files:
        if not os.path.isfile(local_file):
            print(f"Error: '{local_file}' is not a regular file or does not exist.")
            continue

        filename = os.path.basename(local_file)
        upload_path = posixpath.join(target_dir.rstrip('/'), filename)
        total = os.path.getsize(local_file)

        print(f"Uploading '{local_file}' to '{target_dir}' on server...")

        put_response = nextcloud_request(
            "PUT",
            upload_path,
            data=file_stream(local_file, total=total, mode="write", desc=filename)
        )

        if put_response:
            print(f"Upload successful: '{local_file}'")
        else:
            print(f"Upload failed: '{local_file}'")

# ----------------- MKDIR COMMAND -----------------
def mkdir_command(args):
    parents = False
    folders = []

    for a in args:
        if a.startswith("-") and len(a) > 1:
            for ch in a[1:]:
                if ch == "p":
                    parents = True
                else:
                    print(f"Unknown flag: -{ch}")
                    print("Usage: mkdir [-p] <directory1> <directory2> ...")
                    return
        else:
            folders.append(a)

    if not folders:
        print("Usage: mkdir [-p] <directory1> <directory2> ...")
        return

    for folder in folders:
        path = expand_nc_path(folder)
        if parents:
            parts = path.strip("/").split("/")
            current = ""
            for part in parts:
                current = f"{current}/{part}" if current else f"/{part}"
                resp = nextcloud_request("MKCOL", current, suppress=405)
                if resp or resp.status_code in (201, 405):
                    pass
                else:
                    print(f"Failed to create '{current}' (status {resp.status_code if resp else 'no response'})")
                    break
            else:
                print(f"Folder '{folder}' created (with parents).")
        else:
            resp = nextcloud_request("MKCOL", path, suppress=405)
            if resp and resp.status_code == 201:
                print(f"Folder '{folder}' created.")
            elif resp and resp.status_code == 405:
                print(f"Folder '{folder}' already exists.")
            else:
                print(f"Failed to create '{folder}' (status {resp.status_code if resp else 'no response'})")

# ----------------- RM/RMDIR COMMAND -----------------
def rm_command(args):
    force = False
    targets = []

    for a in args:
        if a.startswith("-") and len(a) > 1:
            for ch in a[1:]:
                if ch == "f":
                    force = True
                else:
                    print(f"rm: Unknown flag: -{ch}")
                    return
        else:
            targets.append(a)

    for target in targets:
        path = expand_nc_path(target)
        root = propfind_path(path, suppress=404)
        if root is None:
            print(f"rm: '{target}' no such file or directory.")
            continue

        if not force and not ask_yes_no(f"Are you sure to delete '{target}'?"):
            print("Cancelled.")
            continue

        response = nextcloud_request("DELETE", path)
        if response:
            print(f"'{target}' deleted.")

def rmdir_command(args):
    for target in args:
        path = expand_nc_path(target)
        root = propfind_path(f"{path}/", suppress=404)
        if root is None:
            print(f"rmdir: '{target}' no such file or directory.")
            continue

        hrefs = [elem.text for elem in root.findall(".//d:href", NS)]

        if len(hrefs) == 1 and not hrefs[0].endswith("/"):
            print(f"rmdir: {target}: Not a directory")
            continue

        responses = root.findall("d:response", NS)
        if len(responses) > 1:
            print(f"rmdir: '{target}' is not empty.")
            continue

        response = nextcloud_request("DELETE", path)
        if response:
            print(f"Folder '{target}' deleted.")

# ----------------- CD COMMAND -----------------
def cd_command(args):
    global CURRENT_PATH

    target = expand_nc_path(args[0]) if args else "/"
    target = posixpath.normpath(target)
    
    if not is_directory(target):
        print(f"cd: {target}: No such file or directory or not a directory")
        return

    CURRENT_PATH = target.rstrip("/") if target != "/" else "/"

# ----------------- MAIN LOOP -----------------
def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("-v", "--version", action="store_true", help="Show version")
    args, unknown = parser.parse_known_args()

    if args.version:
        print(f"nftp version: {VERSION}")
        return

    invalid_flags = [a for a in unknown if a.startswith("-")]
    if invalid_flags:
        print(f"Error: invalid option(s) {invalid_flags}, non-interactive mode not supported (currently on development).")
        return

    login()
    commands = {
        "logout": lambda args: logout(),
        "ls": ls_command,
        "pwd": lambda args: print(CURRENT_PATH),
        "cd": cd_command,
        "get": get_command,
        "put": put_command,
        "mkdir": mkdir_command,
        "rm": rm_command,
        "rmdir": rmdir_command,
        "cp": cp_command,
        "mv": mv_command,
        "lls": local_ls,
        "lpwd": lambda args: print(os.getcwd()),
        "lcd": local_cd,
        "clear": lambda args: os.system("clear"),
        "help": lambda args: show_help(),
        "exit": lambda args: sys.exit("Goodbye!"),
    }
    while True:
        try:
            line = input(f"nftp:{CURRENT_PATH}> ").strip()
            if not line:
                continue
            parts = shlex.split(line)
            cmd = parts[0]
            args = parts[1:]
            if cmd in commands:
                commands[cmd](args)
            else:
                print("Invalid command. Type 'help' for commands")
        except (KeyboardInterrupt):
            print()
        except (EOFError):
            print("\nExiting...")
            sys.exit(0)


if __name__ == "__main__":
    main()