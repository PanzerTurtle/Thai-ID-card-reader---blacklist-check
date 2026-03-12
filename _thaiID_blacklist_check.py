# Blacklist checker for Thai National ID Card Reader
# by Athipbadee Taweesup

import sys
import time
import csv
import unicodedata

from smartcard.System import readers
from smartcard.util import toHexString
from smartcard.Exceptions import NoCardException


# Blacklist loading
TITLES = [
    "นาย", "นาง", "นางสาว", "เด็กชาย", "เด็กหญิง", "ด.ช.", "ด.ญ.",
    "mr.", "mrs.", "ms.", "miss", "dr.", "prof.",
]

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = " ".join(text.split()).strip()
    text_lower = text.lower()
    for title in TITLES:
        if text_lower.startswith(title):
            text = text[len(title):].strip()
            break
    return text.lower()


def load_blacklist(csv_path: str):
    id_blacklist   = {}
    name_blacklist = set()

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            cid  = row[0].strip()
            name = normalize(row[1])
            if not name:
                continue
            if cid == "-":
                name_blacklist.add(name)
            else:
                id_blacklist[cid] = name
                name_blacklist.add(name)  # also index by name for ID rows

    return id_blacklist, name_blacklist


# Blacklist check
def check_blacklist(card_data: dict, id_blacklist: dict, name_blacklist: list):
    cid    = card_data.get("CID", "").strip()
    nameTH = normalize(card_data.get("TH Fullname", ""))
    nameEN = normalize(card_data.get("EN Fullname", ""))

    # ID check
    if cid and cid in id_blacklist:
        return True, f"พบเลขบัตรเหมื่อนกัน → {cid}  ({id_blacklist[cid]})"

    # Name check
    for name in [nameTH, nameEN]:
        if name and name in name_blacklist:
            return True, f"พบชื่อ-นามสกุลเหมื่อนกัน → {name}"

    return False, ""


# APDU command bytes  
APDU_SELECT = [0x00, 0xA4, 0x04, 0x00, 0x08, 0xA0, 0x00, 0x00, 0x00, 0x54, 0x48, 0x00, 0x01]
FIELD = [
    ("CID",             [0x80, 0xB0, 0x00, 0x04, 0x02, 0x00, 0x0D]),
    ("TH Fullname",     [0x80, 0xB0, 0x00, 0x11, 0x02, 0x00, 0x64]),
    ("EN Fullname",     [0x80, 0xB0, 0x00, 0x75, 0x02, 0x00, 0x64]),
    ("Date of Birth",   [0x80, 0xB0, 0x00, 0xD9, 0x02, 0x00, 0x08]),
    ("Gender",          [0x80, 0xB0, 0x00, 0xE1, 0x02, 0x00, 0x01]),
    ("Card Issuer",     [0x80, 0xB0, 0x00, 0xF6, 0x02, 0x00, 0x64]),
    ("Issue Date",      [0x80, 0xB0, 0x01, 0x67, 0x02, 0x00, 0x08]),
    ("Expire Date",     [0x80, 0xB0, 0x01, 0x6F, 0x02, 0x00, 0x08]),
    ("Address",         [0x80, 0xB0, 0x15, 0x79, 0x02, 0x00, 0x64]),
]


# Card reading
def transmit_APDU(conn, apdu):
    data, sw1, sw2 = conn.transmit(apdu)
    if sw1 == 0x61:
        data, sw1, sw2 = conn.transmit([0x00, 0xC0, 0x00, 0x00, sw2])
    return data, sw1, sw2


def thai2unicode(data):
    return bytes(data).decode("tis-620", errors="replace").replace("#", " ").strip()


def read_card(reader_list):
    card_data = {}
    try:
        with reader_list[0].createConnection() as connection:
            connection.connect()
            data, sw1, sw2 = transmit_APDU(connection, APDU_SELECT)
            if sw1 != 0x90:
                print("Applet selection failed")
                return card_data
            for (label, cmd) in FIELD:
                data, sw1, sw2 = transmit_APDU(connection, cmd)
                if sw1 == 0x90 and data:
                    value = thai2unicode(data)
                    if label == "Gender":
                        value = {"1": "ชาย", "2": "หญิง"}.get(value, value)
                    card_data[label] = value
    except NoCardException:
        pass
    return card_data


# Terminal display
SEPARATOR = "=" * 50
def print_card(card_data: dict):
    print(SEPARATOR)
    for label, value in card_data.items():
        print(f"  {label:15}: {value}")


def print_result(is_blacklisted: bool, reason: str):
    print(SEPARATOR)
    if is_blacklisted:
        print("BLACKLISTED")
        print(f" : {reason}")
    else:
        print("CLEAR — not on blacklist")
    print(SEPARATOR)


if __name__ == "__main__":
    csv_path = "blacklist.csv"

    print(f"Loading blacklist from: {csv_path}")
    id_bl, name_bl = load_blacklist(csv_path)
    print(f"  {len(id_bl)} entries with ID  |  {len(name_bl)} entries name-only")
    print("Waiting for card...\n")
    print(SEPARATOR)

    reader_list = readers()
    last_cid = None
    while True:
        if not reader_list: # check for reader dynamically
            print("No card reader detected.")
            time.sleep(1)
            continue
        try:
            card_data = read_card(reader_list)
            if card_data:
                cid = card_data.get("CID", "")
                if cid != last_cid: # new card
                    last_cid = cid
                    print_card(card_data)
                    is_bl, reason = check_blacklist(card_data, id_bl, name_bl)
                    print_result(is_bl, reason)
            else:
                last_cid = None
        except Exception as e:
            last_cid = None
        time.sleep(1)
