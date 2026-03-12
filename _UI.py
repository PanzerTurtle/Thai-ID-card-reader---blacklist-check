# ThaiID Blacklist Check — Tkinter UI
# by Athipbadee Taweesup

import time
import threading
import tkinter as tk
from tkinter import filedialog

from _thaiID_blacklist_check import *


# ── Colour palette ───────────────────────────────────────────────────────────
BG          = "#1a1a2e"
PANEL       = "#16213e"
ACCENT      = "#e94560"
TEXT        = "#eaeaea"
SUBTEXT     = "#8892a4"
BTN_BG      = "#0f3460"
BTN_HOVER   = "#e94560"
CLEAR_BG    = "#0d3b2e"
CLEAR_FG    = "#4ade80"
HIT_BG      = "#3b0d0d"
HIT_FG      = "#f87171"
IDLE_BG     = PANEL
IDLE_FG     = SUBTEXT


# ── Reusable styled button ───────────────────────────────────────────────────
class FlatButton(tk.Label):
    def __init__(self, parent, text, command, **kw):
        super().__init__(
            parent,
            text=text,
            bg=BTN_BG, fg=TEXT,
            font=("Courier New", 11, "bold"),
            padx=20, pady=10,
            cursor="hand2",
            **kw
        )
        self._cmd = command
        self.bind("<Enter>",    lambda e: self.config(bg=BTN_HOVER))
        self.bind("<Leave>",    lambda e: self.config(bg=BTN_BG))
        self.bind("<Button-1>", lambda e: self._cmd())


# ══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ThaiID Blacklist Check - v1.0 by Athipbadee Taweesup")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("620x480")

        self.id_bl          = {}
        self.name_bl        = []
        self.last_cid       = None
        self._poll_thread   = None
        self._running       = False
        self._manual_active = False

        self._build_upload_page()

    # ── Page 1: CSV upload ──────────────────────────────────────────────────
    def _build_upload_page(self):
        self._clear_window()
        self.geometry("620x340")

        frame = tk.Frame(self, bg=BG)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(frame, text="ThaiID Blacklist Check", bg=BG, fg=TEXT, font=("Courier New", 20, "bold")).pack(pady=(0, 4))
        tk.Label(frame, text="ระบบตรวจสอบรายชื่อบัญชีดำ", bg=BG, fg=SUBTEXT, font=("Courier New", 10)).pack(pady=(0, 36))
        tk.Label(frame, text="อัพโหลดไฟล์ blacklist.csv", bg=BG, fg=SUBTEXT, font=("Courier New", 10)).pack(pady=(0, 14))
        FlatButton(frame, "Upload Blacklist CSV", command=self._pick_csv).pack()

        self._upload_error = tk.Label(frame, text="", bg=BG, fg=ACCENT, font=("Courier New", 9))
        self._upload_error.pack(pady=(12, 0))

    def _pick_csv(self):
        path = filedialog.askopenfilename(
            title="Select Blacklist CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return

        if not path.lower().endswith(".csv"):
            self._upload_error.config(
                text="Wrong file type — please select a .csv file")
            return

        try:
            id_bl, name_bl = load_blacklist(path)
        except Exception as e:
            self._upload_error.config(
                text=f"Failed to load file: {e}")
            return

        self.id_bl   = id_bl
        self.name_bl = name_bl
        self._build_main_page()

    # ── Page 2: Main scanner UI ─────────────────────────────────────────────
    def _build_main_page(self):
        self._stop_polling()
        self._clear_window()
        self.geometry("620x600")

        # ── Top bar ──────────────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=PANEL, pady=12)
        topbar.pack(fill="x")

        tk.Label(topbar, text="ThaiID Blacklist Check",
                 bg=PANEL, fg=TEXT,
                 font=("Courier New", 16, "bold")).pack(side="left", padx=20)

        FlatButton(topbar, "↺  Change CSV",
                   command=self._reupload).pack(side="right", padx=20)

        # ── Manual search bar ─────────────────────────────────────────────
        search_frame = tk.Frame(self, bg=BG)
        search_frame.pack(fill="x", padx=20, pady=(14, 0))

        tk.Label(search_frame, text="ค้นหา", bg=BG, fg=SUBTEXT, font=("Courier New", 9)).pack(anchor="w", pady=(0, 4))

        input_row = tk.Frame(search_frame, bg=BG)
        input_row.pack(fill="x")

        self._search_var = tk.StringVar()
        self._search_entry = tk.Entry(
            input_row,
            textvariable=self._search_var,
            bg=PANEL, fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Courier New", 11),
            highlightbackground="#2a2a4a",
            highlightthickness=1,
        )
        self._search_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self._search_entry.bind("<Return>", lambda e: self._manual_search())

        FlatButton(input_row, "ค้นหา", command=self._manual_search).pack(side="left")

        # ── Status badge ──────────────────────────────────────────────────
        self._status_frame = tk.Frame(self, bg=IDLE_BG, highlightbackground="#2a2a4a", highlightthickness=1)
        self._status_frame.pack(fill="x", padx=20, pady=(14, 0))

        self._status_label = tk.Label(
            self._status_frame,
            text="กรุณาเสียบบัตร...",
            bg=IDLE_BG, fg=IDLE_FG,
            font=("Courier New", 13, "bold"),
            pady=14
        )
        self._status_label.pack()

        # ── Card info display ─────────────────────────────────────────────
        info_outer = tk.Frame(self, bg=PANEL, highlightbackground="#2a2a4a", highlightthickness=1)
        info_outer.pack(fill="both", expand=True, padx=20, pady=12)

        self._info_text = tk.Text(
            info_outer,
            bg=PANEL, fg=TEXT,
            font=("Courier New", 10),
            relief="flat",
            state="disabled",
            padx=14, pady=12,
            spacing1=3,
            cursor="arrow",
            selectbackground=PANEL,
            insertbackground=PANEL,
            wrap="word"
        )
        self._info_text.pack(fill="both", expand=True)

        self._info_text.tag_config("label",  foreground=SUBTEXT)
        self._info_text.tag_config("value",  foreground=TEXT)
        self._info_text.tag_config("reason", foreground=ACCENT)
        self._info_text.tag_config("idle",   foreground=SUBTEXT)

        self._set_idle_info()
        self._start_polling()

    # ── Manual search ────────────────────────────────────────────────────────
    def _manual_search(self):
        query = self._search_var.get().strip()
        if not query:
            return

        if query.isdigit():
            card_data = {"CID": query, "TH Fullname": "", "EN Fullname": ""}
        else:
            card_data = {"CID": "", "TH Fullname": query, "EN Fullname": query}

        is_bl, reason = check_blacklist(card_data, self.id_bl, self.name_bl)
        self._manual_active = True
        self._show_search_result(query, is_bl, reason)

    def _show_search_result(self, query, is_bl, reason):
        segs = [
            ("label", "ค้นหา       : "),
            ("value",  f"{query}\n"),
            ("label", "วิธีค้นหา   : "),
            ("value",  f"{'เลขประจำตัว' if query.isdigit() else 'ชื่อ-นามสกุล'}\n"),
        ]
        if is_bl:
            segs.append(("label",  "\nผลลัพธ์     : "))
            segs.append(("reason", f"{reason}\n"))

        self._write_info(segs)

        if is_bl:
            self._status_frame.config(bg=HIT_BG)
            self._status_label.config(text="พบบุคคลต้องห้าม!", bg=HIT_BG, fg=HIT_FG)
        else:
            self._status_frame.config(bg=CLEAR_BG)
            self._status_label.config(
                text="ผ่าน ไม่พบบุคคลต้องห้าม", bg=CLEAR_BG, fg=CLEAR_FG)

    # ── Display helpers ──────────────────────────────────────────────────────
    def _set_idle_info(self):
        self._write_info([("idle", "กรูณาเสียบบัตร...\n")])

    def _write_info(self, tagged_segments):
        t = self._info_text
        t.config(state="normal")
        t.delete("1.0", "end")
        for tag, text in tagged_segments:
            t.insert("end", text, tag)
        t.config(state="disabled")

    def _show_card(self, card_data, is_bl, reason):
        self._manual_active = False
        LABELS = [
            ("CID",           "เลขประจำตัวประชาชน"),
            ("TH Fullname",   "ชื่อ (TH)"),
            ("EN Fullname",   "ชื่อ (EN)"),
            ("Date of Birth", "วันเกิด"),
            ("Gender",        "เพศ"),
            ("Issue Date",    "วันออกบัตร"),
            ("Expire Date",   "วันบัตรหมดอายุ"),
            ("Address",       "ที่อยู่"),
        ]
        segs = []
        for key, display in LABELS:
            if key in card_data:
                segs.append(("label", f"{display}: "))
                segs.append(("value", f"{card_data[key]}\n"))

        if is_bl:
            segs.append(("label",  "\nผลลัพธ์  : "))
            segs.append(("reason", f"{reason}\n"))

        self._write_info(segs)

        if is_bl:
            self._status_frame.config(bg=HIT_BG)
            self._status_label.config(text="พบบุคคลต้องห้าม!", bg=HIT_BG, fg=HIT_FG)
        else:
            self._status_frame.config(bg=CLEAR_BG)
            self._status_label.config(
                text="ผ่าน ไม่พบบุคคลต้องห้าม", bg=CLEAR_BG, fg=CLEAR_FG)

    def _set_no_reader(self):
        if self._manual_active:
            return
        self._status_frame.config(bg=IDLE_BG)
        self._status_label.config(
            text="ไม่พบเครื่องอ่านบัตร",
            bg=IDLE_BG, fg=IDLE_FG)
        self._write_info([("idle", "ไม่พบเครื่องอ่านบัตร\n")])

    def _reset_display(self):
        if self._manual_active:
            return
        self._status_frame.config(bg=IDLE_BG)
        self._status_label.config(
            text="กรุณาเสียบบัตร...",
            bg=IDLE_BG, fg=IDLE_FG)
        self._set_idle_info()

    # ── Card polling (background thread) ────────────────────────────────────
    def _start_polling(self):
        self._running = True
        self.last_cid = None
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _stop_polling(self):
        self._running = False

    def _poll_loop(self):
        _had_reader = False
        while self._running:
            reader_list = readers()
            if not reader_list:
                if _had_reader:
                    _had_reader = False
                self.after(0, self._set_no_reader)
                time.sleep(1)
                continue
            if not _had_reader:
                _had_reader = True
                if not self._manual_active:
                    self.after(0, self._reset_display)
            try:
                card_data = read_card(reader_list)
                if card_data:
                    cid = card_data.get("CID", "")
                    if cid != self.last_cid:
                        self.last_cid = cid
                        is_bl, reason = check_blacklist(
                            card_data, self.id_bl, self.name_bl)
                        self.after(0, self._show_card, card_data, is_bl, reason)
                else:
                    if self.last_cid is not None:
                        self.last_cid = None
                        self.after(0, self._reset_display)
            except Exception:
                if self.last_cid is not None:
                    self.last_cid = None
                    self.after(0, self._reset_display)
            time.sleep(1)

    # ── Navigation ───────────────────────────────────────────────────────────
    def _reupload(self):
        self._stop_polling()
        self._build_upload_page()

    def _clear_window(self):
        for w in self.winfo_children():
            w.destroy()

    def on_close(self):
        self._running = False
        self.destroy()


def main_UI():
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main_UI()
    