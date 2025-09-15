#!/usr/bin/env python3
import os
import sys
import base64
import requests
import urllib3
import readline
import shutil
import shlex
import re
import xml.etree.ElementTree as ET
import subprocess
from email.utils import parsedate_to_datetime
from getpass import getpass
from tqdm import tqdm
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SESSION_FILE = os.path.expanduser("~/.nextcloud_session")
CURRENT_PATH = "/"
URL = ""
CREDS = ""
USERNAME = ""
BASE_URL = ""

NS = {"d": "DAV:"}  # XML namespace

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
  rm    <target1> <target2> ...                     - Delete file/directory (confirmation)
  rmdir <dir1> <dir2>...                            - Delete empty directory (confirmation)
  clear                                             - Clean the screen
  help                                              - Show this help
  exit                                              - Exit CLI
""")

def join_path(base, part):
    if base == "/":
        return "/" + part
    else:
        return base.rstrip("/") + "/" + part

def encode_creds(username, password):
    return base64.b64encode(f"{username}:{password}".encode()).decode()

def encode_path(path):
    return quote(path, safe="/")

def expand_nc_path(path):
    if path == "~" or path == ".":
        return "/"
    elif path.startswith("~/"):
        return "/" + path[2:]
    elif path.startswith("/"):
        return path
    else:
        return join_path(CURRENT_PATH, path)

def ask_yes_no(prompt):
    while True:
        ans = input(f"{prompt} (Y/n): ").strip().lower()
        if ans == "y":
            return True
        elif ans == "n":
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

def file_stream(source, total=0, mode="read", desc=""):
    chunk_size = 8192
    if mode == "read":
        with tqdm(
            total=total, unit="B", unit_scale=True, unit_divisor=1024, desc=desc
        ) as bar:
            for chunk in source.iter_content(chunk_size=chunk_size):
                if chunk:
                    bar.update(len(chunk))
                    yield chunk
    elif mode == "write":
        with open(source, "rb") as f, tqdm(
            total=total, unit="B", unit_scale=True, unit_divisor=1024, desc=desc
        ) as bar:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                bar.update(len(chunk))
                yield chunk

def nextcloud_request(method, path, data=None):
    headers = {"Authorization": f"Basic {CREDS}"}
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
        print(f"HTTP Error: {e.response.status_code} - {e.response.reason}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
        return None

def login():
    try:
        global URL, CREDS, USERNAME, BASE_URL
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
            USERNAME = input("Username: ").strip()
            PASSWORD = getpass("Password: ").strip()
            CREDS = encode_creds(USERNAME, PASSWORD)
        else:
            USERNAME = base64.b64decode(CREDS).decode().split(":")[0]

        BASE_URL = f"{URL}/remote.php/dav/files/{USERNAME}"
        response = nextcloud_request("PROPFIND", "/")
        if response and response.status_code in [200, 207]:
            print("Login successful!")
            if not os.path.exists(SESSION_FILE):
                if ask_yes_no("Save session for next time?"):
                    save_session()
                    print(f"Session saved to {SESSION_FILE}")
        elif response and response.status_code == 401:
            print("Login failed: Invalid username or password. Old session cleared.")
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            sys.exit(1)
        else:
            print("Connection failed: URL not found or server unreachable. Old session cleared.")
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            sys.exit(1)
    except (EOFError, KeyboardInterrupt):
        print("\nLogin cancelled.")
        sys.exit(1)

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

def ls_command(args):
    global CURRENT_PATH
    long_format = False
    human_readable = False
    paths = []

    for a in args:
        if a.startswith("-"):
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

    def list_path(target):
        if target != "/":
            target = target.rstrip("/")
        response = nextcloud_request("PROPFIND", f"{target}/")

        if not response or response.status_code not in [200, 207]:
            return

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            print("Failed to parse server response.")
            return

        items = []
        for resp in root.findall("d:response", NS):
            href = resp.find("d:href", NS).text
            name = os.path.basename(href.rstrip("/"))
            name = requests.utils.unquote(name)

            if not name or name == USERNAME or name == os.path.basename(target):
                continue

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

            items.append({
                "name": name,
                "is_dir": is_dir,
                "size": size,
                "lastmod": lastmod
            })

        if not items:
            print("Directory is empty.")
            return

        def fmt_size(num):
            if not human_readable:
                return str(num)
            for unit in ["B", "K", "M", "G", "T"]:
                if num < 1024.0:
                    return f"{num:3.1f}{unit}"
                num /= 1024.0
            return f"{num:.1f}P"

        if long_format:
            items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            sizes_str = [fmt_size(item["size"]) for item in items]
            max_width = max(len(s) for s in sizes_str)

            for item, size_str in zip(items, sizes_str):
                ftype = "d" if item["is_dir"] else "-"
                size_str = size_str.rjust(max_width)
                date_str = item["lastmod"] if item["lastmod"] else "-"
                label = item["name"] + ("/" if item["is_dir"] else "")
                print(f"{ftype} {size_str} {date_str} {label}")
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

def cd_command(args):
    global CURRENT_PATH
    target = expand_nc_path(args[0]) if args else "/"
    new_path = os.path.normpath(target)
    if new_path != "/":
        new_path = new_path.rstrip("/")

    response = nextcloud_request("PROPFIND", f"{new_path}/")
    if not response or response.status_code not in [200, 207]:
        print(f"cd: {target}: No such file or directory")
        return

    items = re.findall(r"<d:href>(.*?)</d:href>", response.text)
    if len(items) == 1:
        href = items[0]
        if not href.endswith("/"):
            print(f"cd: {target}: Not a directory")
            return

    CURRENT_PATH = new_path

def get_command(args):
    for file in args:
        file_path = expand_nc_path(file)
        response = nextcloud_request("PROPFIND", file_path)
        if not response:
            print(f"Error: '{file}' not found.")
            continue

        try:
            root = ET.fromstring(response.text)
            hrefs = [resp.find("d:href", NS).text for resp in root.findall("d:response", NS)]
            if any(h.endswith("/") for h in hrefs):
                print(f"Error: '{file}' is a directory.")
                continue
        except ET.ParseError:
            print("Failed to parse server response.")
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

def put_command(args):
    for local_file in args:
        if not os.path.isfile(local_file):
            print(f"Error: '{local_file}' is not a regular file or does not exist.")
            continue

        filename = os.path.basename(local_file)
        upload_path = expand_nc_path(filename)
        total = os.path.getsize(local_file)

        print(f"Uploading '{local_file}' to '{CURRENT_PATH}' on server...")

        put_response = nextcloud_request(
            "PUT",
            upload_path,
            data=file_stream(local_file, total=total, mode="write", desc=filename)
        )

        if put_response:
            print(f"Upload successful: '{local_file}'")
        else:
            print(f"Upload failed: '{local_file}'")

def mkdir_command(args):
    for folder in args:
        path = expand_nc_path(folder)
        response = nextcloud_request("MKCOL", path)
        if response:
            print(f"Folder '{folder}' created.")

def rm_command(args):
    for target in args:
        path = expand_nc_path(target)
        response = nextcloud_request("PROPFIND", path)
        if not response:
            print(f"Error: '{target}' not found.")
            continue

        if not ask_yes_no(f"Are you sure to delete '{target}'?"):
            print("Cancelled.")
            continue

        response = nextcloud_request("DELETE", path)
        if response:
            print(f"'{target}' deleted.")

def rmdir_command(args):
    for target in args:
        path = expand_nc_path(target)
        response = nextcloud_request("PROPFIND", f"{path}/")
        if not response or response.status_code not in [200, 207]:
            print(f"Error: '{target}' not found or is not a directory.")
            continue

        items = re.findall(r"<d:href>(.*?)</d:href>", response.text)
        if len(items) == 1:
            href = items[0]
            if not href.endswith("/"):
                print(f"rmdir: {target}: Not a directory")
                return

        try:
            root = ET.fromstring(response.text)
            items = root.findall("d:response", NS)
            if len(items) > 1:
                print(f"Error: '{target}' is not empty.")
                continue
        except ET.ParseError:
            print("Failed to parse server response.")
            continue

        if not ask_yes_no(f"Are you sure to delete folder '{target}'?"):
            print("Cancelled.")
            continue

        response = nextcloud_request("DELETE", path)
        if response:
            print(f"Folder '{target}' deleted.")

def main():
    login()
    commands = {
        "ls": ls_command,
        "pwd": lambda args: print(CURRENT_PATH),
        "cd": cd_command,
        "get": get_command,
        "put": put_command,
        "mkdir": mkdir_command,
        "rm": rm_command,
        "rmdir": rmdir_command,
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
                print("Invalid command. Type 'help' for commands.")
        except KeyboardInterrupt:
            print()
        except EOFError:
            sys.exit("\nGoodbye!")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
