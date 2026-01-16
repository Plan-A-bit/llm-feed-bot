#!/usr/bin/env python3
import sys
import os
import time
import json
import subprocess
import sqlite3
import re
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QTabWidget, QMessageBox, QLabel, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import requests
from bs4 import BeautifulSoup

# Use user-writable directory (XDG compliant)
DATA_ROOT = Path.home() / ".local" / "share" / "llmfeed"
DATA_ROOT.mkdir(parents=True, exist_ok=True)
(LLM_URL := "http://127.0.0.1:8080/completion")

class WebWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    def __init__(self, urls):
        super().__init__()
        self.urls = urls
        self._running = True
    def run(self):
        for url in self.urls:
            if not self._running:
                break
            self.progress.emit(f"[→] Fetching {url}")
            try:
                r = requests.get(url, timeout=10, headers={"User-Agent": "LLMFeedBot"})
                if r.status_code == 200:
                    content_type = r.headers.get('content-type', '').lower()
                    if 'text/plain' in content_type or url.endswith('.txt'):
                        text = r.text
                    else:
                        soup = BeautifulSoup(r.text, "html.parser")
                        text = soup.get_text()
                    name = "".join(c if c.isalnum() or c in "._-" else "_" for c in url[-50:])
                    (DATA_ROOT / f"{name}.txt").write_text(text, encoding="utf-8")
                    self.progress.emit(f"[✓] Saved {name}.txt")
                else:
                    self.progress.emit(f"[✗] HTTP {r.status_code}")
            except Exception as e:
                self.progress.emit(f"[✗] Error: {str(e)}")
            time.sleep(1)
        self.finished.emit()
    def stop(self):
        self._running = False

class PresetWorker(QThread):
    done = pyqtSignal(str)
    def __init__(self, fetch_func):
        super().__init__()
        self.fetch_func = fetch_func
        self._running = True
    def run(self):
        if not self._running:
            return
        try:
            self.fetch_func()
            self.done.emit("[✓] Done")
        except Exception as e:
            self.done.emit(f"[✗] Failed: {str(e)}")
    def stop(self):
        self._running = False

def fetch_gutenberg():
    r = requests.get("https://www.gutenberg.org/files/1342/1342-0.txt", timeout=10)
    if r.status_code == 200:
        (DATA_ROOT / "gutenberg_pride_prejudice.txt").write_text(r.text, encoding="utf-8")

def fetch_rfcs():
    for i in [1, 10, 100, 1000]:
        r = requests.get(f"https://www.rfc-editor.org/rfc/rfc{i}.txt", timeout=8)
        if r.status_code == 200:
            (DATA_ROOT / f"rfc{i}.txt").write_text(r.text, encoding="utf-8")

def fetch_manpages():
    pages = ["bash", "ssh", "systemd"]
    for p in pages:
        r = requests.get(f"https://man7.org/linux/man-pages/man1/{p}.html", timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            pre = soup.find("pre")
            if pre:
                (DATA_ROOT / f"{p}_man.txt").write_text(pre.get_text(), encoding="utf-8")

def fetch_gpg():
    r = requests.get("https://keys.openpgp.org/vks/v1/by-fingerprint/886D5E5E3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F", timeout=10)
    if r.status_code == 200 and "-----BEGIN PGP PUBLIC KEY BLOCK-----" in r.text:
        (DATA_ROOT / "sample_key.asc").write_text(r.text, encoding="utf-8")

def fetch_all_coding_man():
    out_dir = DATA_ROOT / "man"
    out_dir.mkdir(exist_ok=True)
    paths = os.environ.get("PATH", "").split(":")
    commands = set()
    for path in paths:
        if os.path.isdir(path):
            for item in os.listdir(path):
                full_path = os.path.join(path, item)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    commands.add(item)
    common = {"python3", "gcc", "gdb", "make", "git", "curl", "wget", "jq", "vim", "nano", "tmux", "screen", "rsync", "ssh", "scp", "openssl", "nmcli", "ip", "ss", "tcpdump", "htop", "iotop", "lsof", "strace", "journalctl", "dnf", "rpm", "podman", "buildah", "skopeo"}
    commands.update(common)
    saved = 0
    for cmd in sorted(commands):
        out_path = out_dir / f"{cmd}.txt"
        if out_path.exists():
            continue
        try:
            result = subprocess.run(['man', '-w', cmd], capture_output=True, text=True, timeout=3)
            if result.returncode == 0 and result.stdout.strip():
                man_text = subprocess.run(['man', cmd], capture_output=True, text=True, timeout=5).stdout
                clean_text = subprocess.run(['col', '-b'], input=man_text, capture_output=True, text=True).stdout
                if clean_text.strip():
                    out_path.write_text(clean_text, encoding="utf-8")
                    saved += 1
        except:
            continue

# ✅ MODIFIED: Only process files modified in last 5 minutes
class SummarizeWorker(QThread):
    done = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self._running = True
    def run(self):
        if not self._running:
            return
        now = time.time()
        cutoff = now - 300  # 5 minutes
        for txt in DATA_ROOT.glob("*.txt"):
            if not txt.is_file():
                continue
            mtime = txt.stat().st_mtime
            if mtime < cutoff:
                continue  # Skip old files
            try:
                content = txt.read_text(encoding="utf-8", errors="ignore")[:4000]
                payload = {"prompt": f"Summarize concisely:\n{content}\nSummary:", "n_predict": 200}
                r = requests.post(LLM_URL, json=payload, timeout=30)
                summary = r.json().get("content", "").strip()
                (DATA_ROOT / f"{txt.stem}_summary.txt").write_text(summary, encoding="utf-8")
            except: pass
        self.done.emit("[✓] Summaries saved")
    def stop(self):
        self._running = False

# ✅ MODIFIED: Only process files modified in last 5 minutes
class ClassifyWorker(QThread):
    done = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self._running = True
    def run(self):
        if not self._running:
            return
        now = time.time()
        cutoff = now - 300  # 5 minutes
        categories = ["security", "networking", "crypto"]
        for txt in DATA_ROOT.glob("*.txt"):
            if not txt.is_file():
                continue
            mtime = txt.stat().st_mtime
            if mtime < cutoff:
                continue  # Skip old files
            try:
                content = txt.read_text(encoding="utf-8", errors="ignore")[:2000]
                prompt = f"Classify into one of: {', '.join(categories)}. Text: {content}\nCategory:"
                r = requests.post(LLM_URL, json={"prompt": prompt, "n_predict": 10}, timeout=20)
                cat = r.json().get("content", "").strip().lower()
                if cat not in categories: cat = "other"
                (DATA_ROOT / f"{txt.stem}_classified_{cat}.txt").write_text(content, encoding="utf-8")
            except: pass
        self.done.emit("[✓] Files classified")
    def stop(self):
        self._running = False

class ExtractCodeWorker(QThread):
    done = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self._running = True
    def run(self):
        if not self._running:
            return
        code_block = re.compile(r"```(?:\w+)?\s*(.*?)```", re.DOTALL)
        for txt in DATA_ROOT.glob("*.txt"):
            text = txt.read_text(encoding="utf-8", errors="ignore")
            snippets = code_block.findall(text)
            if snippets:
                out = DATA_ROOT / f"{txt.stem}_code.sh"
                out.write_text("\n\n".join(snippets), encoding="utf-8")
        self.done.emit("[✓] Code snippets extracted")
    def stop(self):
        self._running = False

class IndexWorker(QThread):
    done = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self._running = True
    def run(self):
        if not self._running:
            return
        db = sqlite3.connect(DATA_ROOT / "index.db")
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(path, content)")
        db.execute("DELETE FROM docs")
        for txt in DATA_ROOT.glob("*.txt"):
            content = txt.read_text(encoding="utf-8", errors="ignore")
            db.execute("INSERT INTO docs VALUES (?, ?)", (str(txt), content))
        db.commit()
        db.close()
        self.done.emit("[✓] Searchable index built")
    def stop(self):
        self._running = False

class CheatSheetWorker(QThread):
    done = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self._running = True
    def run(self):
        if not self._running:
            return
        man_pages = ["dnf", "systemd"]
        for cmd in man_pages:
            try:
                help_text = subprocess.run([cmd, "--help"], capture_output=True, text=True, timeout=5).stdout
                prompt = f"Create a concise cheat sheet for '{cmd}' from this help:\n{help_text[:2000]}"
                payload = {"prompt": prompt, "n_predict": 300}
                r = requests.post(LLM_URL, json=payload, timeout=30)
                sheet = r.json().get("content", "").strip()
                (DATA_ROOT / f"{cmd}_cheatsheet.txt").write_text(sheet, encoding="utf-8")
            except: pass
        self.done.emit("[✓] Cheat sheets generated")
    def stop(self):
        self._running = False

class AskLLMWorker(QThread):
    answer_ready = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.file_path = None
        self.question = None
        self._run_query = False

    def set_query(self, file_path, question):
        self.file_path = file_path
        self.question = question
        self._run_query = True

    def run(self):
        if not self._run_query:
            return
        try:
            content = Path(self.file_path).read_text(encoding="utf-8", errors="ignore")[:2000]
            prompt = f"Context:\n{content}\n\nQuestion: {self.question}\nAnswer:"
            payload = {"prompt": prompt, "n_predict": 400}
            r = requests.post("http://127.0.0.1:8080/completion", json=payload)
            ans = r.json().get("content", "").strip()
            self.answer_ready.emit(ans)
        except Exception as e:
            self.answer_ready.emit(f"[✗] Error: {str(e)}")

class LLMBotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM Feed Bot")
        self.resize(1000, 700)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QTabWidget::pane { border: 0; }
            QTabBar::tab { background: #2a2a2a; color: #4ade80; padding: 10px; }
            QTabBar::tab:selected { background: #ff0000; color: white; }
            QPushButton { background: #333; color: #4ade80; padding: 8px; border: 1px solid #555; }
            QLineEdit { background: #0d0d0d; color: #4ade80; padding: 5px; }
            QTextEdit { background: #0d0d0d; color: #4ade80; font-family: monospace; }
            QComboBox { background: #0d0d0d; color: #4ade80; padding: 5px; }
        """)
        font = QFont("Monospace", 11)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)

        central = QWidget()
        layout = QVBoxLayout()

        toolbar = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste URL...")
        self.confirm_btn = QPushButton("✅ Add URL")
        self.scrape_btn = QPushButton("🔍 Scrape URLs")
        self.confirm_btn.clicked.connect(self.add_url)
        self.scrape_btn.clicked.connect(self.start_web_fetch)
        toolbar.addWidget(self.url_input)
        toolbar.addWidget(self.confirm_btn)
        toolbar.addWidget(self.scrape_btn)
        layout.addLayout(toolbar)

        self.tabs = QTabWidget()

        welcome_tab = QWidget()
        welcome_layout = QVBoxLayout()
        welcome_text = QTextEdit()
        welcome_text.setReadOnly(True)
        welcome_text.setPlainText(
            "✨ Welcome to LLM Feed Bot ✨\n\n"
            "This tool builds a private, offline knowledge base for your local LLM.\n\n"
            "TABS:\n"
            "• 🌐 Custom URL — Add any webpage or .txt URL (HTML auto-converted to clean text)\n"
            "• 📚 Gutenberg — Fetch public domain books\n"
            "• 📜 RFCs — Get internet standards (RFCs)\n"
            "• 📘 Man Pages — Download Linux command docs\n"
            "  → Includes “Fetch Core Man” (bash, ssh, systemd)\n"
            "  → NEW: “📥 Fetch All Coding Man” gets man pages for ALL CLI tools on your system\n"
            "• 🔐 GPG Keys — Retrieve public keys\n"
            "• 📝 Summarize — Auto-summarize .txt files *(requires LLM server)*\n"
            "• 💻 Extract Code — Pull executable snippets *(requires LLM server)*\n"
            "• 🔍 Build Index — Create full-text search DB *(requires LLM server)*\n"
            "•  cheatsheet — Generate CLI references *(requires LLM server)*\n"
            "• 🗂️ Classify — Auto-tag files by topic *(requires LLM server)*\n"
            "• ❓ Ask LLM — Query any .txt file with your local LLM *(requires LLM server)*\n\n"
            "All data stays on your machine. No telemetry. No cloud.\n\n"
            "⚠️ LLM SERVER REQUIRED FOR AI FEATURES:\n"
            "Start your LLM server at http://127.0.0.1:8080 before using AI tabs.\n\n"
            "💡 IMPORTANT: Operations like Summarize, Classify, etc. ONLY affect files\n"
            "modified in the last 5 minutes — to avoid reprocessing old data,\n"
            "reduce RAM usage, and prevent cache overload."
        )
        welcome_layout.addWidget(welcome_text)
        welcome_tab.setLayout(welcome_layout)
        self.tabs.addTab(welcome_tab, "🎉 Welcome")

        custom_tab = QWidget()
        custom_layout = QVBoxLayout()

        top_row = QHBoxLayout()
        top_left = QLabel("🤖")
        top_left.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        top_left.setStyleSheet("color: #4ade80; font-size: 24px;")
        top_right = QLabel("⚙️")
        top_right.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        top_right.setStyleSheet("color: #4ade80; font-size: 24px;")
        top_row.addWidget(top_left)
        top_row.addStretch()
        top_row.addWidget(top_right)

        self.custom_log = QTextEdit()
        self.custom_log.setReadOnly(True)
        self.custom_log.setMinimumHeight(300)

        bottom_row = QHBoxLayout()
        bottom_left = QLabel("🧠")
        bottom_left.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        bottom_left.setStyleSheet("color: #4ade80; font-size: 24px;")
        bottom_right = QLabel("⚡")
        bottom_right.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        bottom_right.setStyleSheet("color: #4ade80; font-size: 24px;")
        bottom_row.addWidget(bottom_left)
        bottom_row.addStretch()
        bottom_row.addWidget(bottom_right)

        custom_layout.addLayout(top_row)
        custom_layout.addWidget(self.custom_log)
        custom_layout.addLayout(bottom_row)
        custom_tab.setLayout(custom_layout)
        self.tabs.addTab(custom_tab, "🌐 Custom URL")

        self.create_preset_tab("📚 Gutenberg", "Fetch Book", fetch_gutenberg)
        self.create_preset_tab("📜 RFCs", "Fetch RFCs", fetch_rfcs)

        man_tab = QWidget()
        man_layout = QVBoxLayout()
        btn_core = QPushButton("Fetch Core Man (bash, ssh, systemd)")
        btn_all = QPushButton("📥 Fetch All Coding Man")
        log = QTextEdit()
        log.setReadOnly(True)

        def run_core():
            btn_core.setEnabled(False)
            w = PresetWorker(fetch_manpages)
            w.done.connect(lambda m: self.update_log(log, m, btn_core))
            w.start()
            setattr(self, 'worker_man_core', w)

        def run_all():
            btn_all.setEnabled(False)
            w = PresetWorker(fetch_all_coding_man)
            w.done.connect(lambda m: self.update_log(log, m, btn_all))
            w.start()
            setattr(self, 'worker_man_all', w)

        btn_core.clicked.connect(run_core)
        btn_all.clicked.connect(run_all)
        man_layout.addWidget(btn_core)
        man_layout.addWidget(btn_all)
        man_layout.addWidget(log)
        man_tab.setLayout(man_layout)
        self.tabs.addTab(man_tab, "📘 Man Pages")

        self.create_preset_tab("🔐 GPG Keys", "Fetch Key", fetch_gpg)
        self.create_worker_tab("📝 Summarize", "Run Summarization", SummarizeWorker)
        self.create_worker_tab("💻 Extract Code", "Extract Snippets", ExtractCodeWorker)
        self.create_worker_tab("🔍 Build Index", "Create Search Index", IndexWorker)
        self.create_worker_tab(" cheatsheet", "Generate Cheat Sheets", CheatSheetWorker)
        self.create_worker_tab("🗂️ Classify", "Auto-Classify", ClassifyWorker)

        ask_tab = QWidget()
        ask_layout = QVBoxLayout()
        self.file_combo = QComboBox()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Type your question and press Enter...")
        self.ask_output = QTextEdit()
        self.ask_output.setReadOnly(True)
        self.ask_output.setMaximumHeight(300)
        self.ask_output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.ask_output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.prompt_input.returnPressed.connect(self.send_ask_query)
        ask_layout.addWidget(QLabel("Select context file:"))
        ask_layout.addWidget(self.file_combo)
        ask_layout.addWidget(QLabel("Your question:"))
        ask_layout.addWidget(self.prompt_input)
        ask_layout.addWidget(self.ask_output)
        ask_tab.setLayout(ask_layout)
        self.tabs.addTab(ask_tab, "❓ Ask LLM")
        self.update_file_list()

        layout.addWidget(self.tabs)
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.worker = None
        self.urls = []
        self.ask_worker = AskLLMWorker()
        self.ask_worker.answer_ready.connect(self.handle_ask_answer)

    def update_file_list(self):
        self.file_combo.clear()
        paths_to_scan = [Path.home(), DATA_ROOT]
        seen = set()
        for root in paths_to_scan:
            for f in root.rglob("*.txt"):
                if f.is_file():
                    try:
                        if str(f).startswith(str(Path.home())):
                            display = f.relative_to(Path.home())
                            full_path = f
                        else:
                            display = f.relative_to(DATA_ROOT)
                            full_path = f
                        key = str(full_path.resolve())
                        if key not in seen:
                            seen.add(key)
                            self.file_combo.addItem(str(display), str(full_path))
                    except Exception:
                        continue

    def create_preset_tab(self, name, btn_text, func):
        widget = QWidget()
        layout = QVBoxLayout()
        btn = QPushButton(btn_text)
        log = QTextEdit()
        log.setReadOnly(True)
        def run():
            btn.setEnabled(False)
            w = PresetWorker(func)
            w.done.connect(lambda m: self.update_log(log, m, btn))
            w.start()
            setattr(self, f"worker_{name}", w)
        btn.clicked.connect(run)
        layout.addWidget(btn)
        layout.addWidget(log)
        widget.setLayout(layout)
        self.tabs.addTab(widget, name)

    def create_worker_tab(self, name, btn_text, WorkerClass):
        widget = QWidget()
        layout = QVBoxLayout()
        btn = QPushButton(btn_text)
        log = QTextEdit()
        log.setReadOnly(True)
        def run():
            btn.setEnabled(False)
            w = WorkerClass()
            w.done.connect(lambda m: self.update_log(log, m, btn))
            w.start()
            setattr(self, f"worker_{name}", w)
        btn.clicked.connect(run)
        layout.addWidget(btn)
        layout.addWidget(log)
        widget.setLayout(layout)
        self.tabs.addTab(widget, name)

    def update_log(self, log, msg, btn):
        log.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        btn.setEnabled(True)

    def add_url(self):
        url = self.url_input.text().strip()
        if url:
            self.urls.append(url)
            self.custom_log.append(f"[+] Added: {url}")
            self.url_input.clear()

    def start_web_fetch(self):
        if not self.urls:
            QMessageBox.warning(self, "No URLs", "Add at least one URL first.")
            return
        self.worker = WebWorker(self.urls)
        self.worker.progress.connect(lambda m: self.custom_log.append(m))
        self.worker.finished.connect(lambda: self.custom_log.append("[✓] Custom fetch done"))
        self.worker.finished.connect(lambda: self.urls.clear())
        self.worker.start()

    def send_ask_query(self):
        if self.file_combo.count() == 0:
            self.ask_output.append("[!] No .txt files found.")
            return
        question = self.prompt_input.text().strip()
        if not question:
            self.ask_output.append("[!] Please enter a question.")
            return
        file_path = self.file_combo.currentData()
        self.ask_output.append(f"\n[You] {question}")
        self.prompt_input.clear()
        self.ask_worker.set_query(file_path, question)
        self.ask_worker.start()

    def handle_ask_answer(self, answer):
        self.ask_output.append(f"[LLM] {answer}\n")
        self.ask_output.verticalScrollBar().setValue(self.ask_output.verticalScrollBar().maximum())

    def closeEvent(self, event):
        workers = []
        for attr in dir(self):
            obj = getattr(self, attr)
            if isinstance(obj, QThread) and attr.startswith('worker_'):
                workers.append(obj)
        if hasattr(self, 'worker') and self.worker:
            workers.append(self.worker)
        if hasattr(self, 'ask_worker') and self.ask_worker.isRunning():
            workers.append(self.ask_worker)
        for w in workers:
            w.stop()
            w.wait(2000)
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    dark_palette = app.palette()
    dark_palette.setColor(app.palette().ColorRole.Window, Qt.GlobalColor.black)
    dark_palette.setColor(app.palette().ColorRole.WindowText, Qt.GlobalColor.green)
    app.setPalette(dark_palette)
    window = LLMBotGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
