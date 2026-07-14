# ota_update.py

import urequests
import os
import machine
import time
import gc

# -----------------------------
# GitHub OTA settings
# -----------------------------

GITHUB_USER = "CLOW-94"
GITHUB_REPO = "RemoteSensor"
GITHUB_BRANCH = "main"

VERSION_FILE = "version.txt"

# Files that are allowed to update from GitHub
OTA_FILES = [
    "boot.py",
    "main.py",
    "ota_update.py",
    "BMP280.py",
    "veml7700.py"

]

BASE_URL = "https://raw.githubusercontent.com/{}/{}/{}/".format(
    GITHUB_USER,
    GITHUB_REPO,
    GITHUB_BRANCH
)


# -----------------------------
# Local version functions
# -----------------------------

def get_local_version():
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except:
        return "0.0.0"


def save_local_version(version):
    with open(VERSION_FILE, "w") as f:
        f.write(version)


# -----------------------------
# GitHub download functions
# -----------------------------

def download_text(url):
    print("Downloading:", url)

    response = urequests.get(url)

    if response.status_code != 200:
        response.close()
        raise Exception("HTTP error: {}".format(response.status_code))

    text = response.text
    response.close()
    return text


def get_remote_version():
    url = BASE_URL + VERSION_FILE
    return download_text(url).strip()


def download_file(filename):
    url = BASE_URL + filename
    new_filename = filename + ".new"

    print("Downloading file:", filename)

    response = urequests.get(url)

    if response.status_code != 200:
        response.close()
        raise Exception("Failed to download {} HTTP {}".format(filename, response.status_code))

    with open(new_filename, "w") as f:
        while True:
            chunk = response.raw.read(256)
            if not chunk:
                break

            if isinstance(chunk, bytes):
                chunk = chunk.decode()

            f.write(chunk)

    response.close()
    gc.collect()

    return new_filename


# -----------------------------
# File replace function
# -----------------------------

def replace_file(filename):
    new_filename = filename + ".new"
    backup_filename = filename + ".bak"

    # Remove old backup if it exists
    try:
        os.remove(backup_filename)
    except:
        pass

    # Backup current file
    try:
        os.rename(filename, backup_filename)
    except:
        pass

    # Move new file into place
    os.rename(new_filename, filename)

    print("Updated:", filename)


# -----------------------------
# Main OTA check
# -----------------------------

def check_for_updates():
    print("Checking for OTA update...")

    local_version = get_local_version()
    print("Local version:", local_version)

    try:
        remote_version = get_remote_version()
        print("Remote version:", remote_version)

        if remote_version == local_version:
            print("No OTA update needed")
            return False

        print("OTA update available")

        # Download all files first
        for filename in OTA_FILES:
            download_file(filename)

        # Replace files only after all downloads succeed
        for filename in OTA_FILES:
            replace_file(filename)

        save_local_version(remote_version)

        print("OTA update complete")
        print("Rebooting in 3 seconds...")
        time.sleep(3)
        machine.reset()

    except Exception as e:
        print("OTA update failed:", e)

        # Clean up incomplete .new files
        for filename in OTA_FILES:
            try:
                os.remove(filename + ".new")
            except:
                pass

        return False

