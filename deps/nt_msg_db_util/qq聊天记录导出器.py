import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "QQ 聊天记录完整导出器"


def format_time(value):
    value = float(value or 0)
    if value > 10_000_000_000:
        value /= 1000
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def message_text(text, content):
    if text:
        return str(text)
    if not content:
        return ""
    try:
        value = json.loads(content)
        if isinstance(value, dict) and value.get("text"):
            return str(value["text"])
        return json.dumps(value, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return str(content)


def export_chat(db_path, peer_uid, self_uid, out_dir, report):
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        """
        SELECT timestamp, sender_uid, sender_qq, text, content
        FROM c2c_messages WHERE peer_uid = ? ORDER BY timestamp, msg_id
        """,
        (peer_uid,),
    ).fetchall()
    conn.close()
    txt_lines, html_items = [], []
    for i, (timestamp, sender_uid, sender_qq, text, content) in enumerate(rows, 1):
        when = format_time(timestamp)
        who = "我" if self_uid and sender_uid == self_uid else str(sender_qq or sender_uid or "对方")
        body = message_text(text, content)
        txt_lines.append(f"[{when}] {who}\n{body}\n")
        html_items.append(
            "<article class='message'>"
            f"<div class='meta'>{html.escape(when)} · {html.escape(who)}</div>"
            f"<div class='body'>{html.escape(body).replace(chr(10), '<br>')}</div></article>"
        )
        if i % 5000 == 0:
            report(f"正在写出聊天记录：{i:,} / {len(rows):,}")
    txt_path, html_path = out_dir / "chat.txt", out_dir / "chat.html"
    txt_path.write_text("\n".join(txt_lines), encoding="utf-8")
    document = """<!doctype html><meta charset="utf-8"><title>QQ 聊天记录</title>
<style>body{max-width:960px;margin:2rem auto;padding:0 1rem;font:15px/1.6 system-ui,sans-serif;color:#222}.message{border-bottom:1px solid #eee;padding:.8rem 0}.meta{color:#777;font-size:13px}.body{overflow-wrap:anywhere}</style><main>
""" + "\n".join(html_items) + "\n</main>\n"
    html_path.write_text(document, encoding="utf-8")
    return len(rows), txt_path, html_path


class Exporter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1160x820")
        self.minsize(980, 700)
        icon_candidates = []
        if getattr(sys, "frozen", False):
            icon_candidates.append(Path(sys.executable).resolve().parent / "qq聊天记录导出器.ico")
        icon_candidates.append(Path(__file__).resolve().parent.parent.parent.parent / "工具" / "qq聊天记录导出器.ico")
        for icon_path in icon_candidates:
            if icon_path.exists():
                try:
                    self.iconbitmap(default=str(icon_path))
                    break
                except tk.TclError:
                    pass
        self.db_var = tk.StringVar()
        self.qq_exe_var = tk.StringVar()
        self.wrapper_var = tk.StringVar()
        self.self_uid_var = tk.StringVar()
        self.work_var = tk.StringVar(value=str(Path.cwd() / "qq导出结果"))
        self.out_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="先选择原始 nt_msg.db，然后点击“完整处理”")
        self.contacts = []
        self._build_ui()
        self.search_var.trace_add("write", lambda *_: self._refresh_contacts())
        self._autofill_paths()

    def _repo_paths(self):
        here = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        candidates = [
            here.parent / "qqcli-rs" / "deps",
            Path("E:/qq聊天记录/qqcli-rs/deps"),
            Path.cwd() / "qqcli-rs/deps",
        ]
        return next((p for p in candidates if (p / "nt_msg_db_util" / "1.decrypt.py").exists()), None)

    def _uv_command(self):
        """优先使用发布包自带的 uv，避免依赖用户自行配置 PATH。"""
        if getattr(sys, "frozen", False):
            bundled_uv = Path(sys.executable).resolve().parent / "uv.exe"
            if bundled_uv.exists():
                return str(bundled_uv)
        return shutil.which("uv") or "uv"

    def _autofill_paths(self):
        qq_candidates = [Path("D:/QQ/QQ.exe"), Path("C:/Program Files/Tencent/QQ/QQ.exe")]
        qq_exe = next((p for p in qq_candidates if p.exists()), None)
        if qq_exe:
            self.qq_exe_var.set(str(qq_exe))
            version_root = qq_exe.parent / "versions"
            wrappers = list(version_root.glob("*/resources/app/wrapper.node")) if version_root.exists() else []
            if wrappers:
                self.wrapper_var.set(str(max(wrappers, key=lambda p: p.stat().st_mtime)))
        db_candidates = [
            Path("D:/qqfile/Tencent Files/2827352235/nt_qq/nt_db/nt_msg.db"),
            Path("E:/qq聊天记录/手机导入-20261018/nt_msg.db"),
        ]
        db = next((p for p in db_candidates if p.exists() and p.stat().st_size), None)
        if db:
            self.db_var.set(str(db))

    def _build_ui(self):
        colors = {
            "bg": "#111318", "surface": "#191C23", "surface2": "#222631",
            "border": "#303644", "text": "#F5F7FB", "muted": "#A8AFBF",
            "accent": "#9B6CFF", "accent_active": "#B48CFF", "success": "#45D483",
        }
        self._colors = colors
        self.configure(bg=colors["bg"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("App.TFrame", background=colors["bg"])
        style.configure("Card.TLabelframe", background=colors["surface"], foreground=colors["text"], bordercolor=colors["border"], relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=colors["surface"], foreground=colors["accent_active"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("App.TLabel", background=colors["bg"], foreground=colors["text"], font=("Microsoft YaHei UI", 10))
        style.configure("Muted.TLabel", background=colors["bg"], foreground=colors["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Card.TLabel", background=colors["surface"], foreground=colors["text"], font=("Microsoft YaHei UI", 10))
        style.configure("CardMuted.TLabel", background=colors["surface"], foreground=colors["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Title.TLabel", background=colors["bg"], foreground=colors["text"], font=("Microsoft YaHei UI", 22, "bold"))
        style.configure("Subtitle.TLabel", background=colors["bg"], foreground=colors["muted"], font=("Microsoft YaHei UI", 10))
        style.configure("TEntry", fieldbackground=colors["surface2"], foreground=colors["text"], insertcolor=colors["text"], borderwidth=0, lightcolor=colors["surface2"], darkcolor=colors["surface2"], padding=(10, 7))
        style.configure("Input.TEntry", fieldbackground=colors["surface2"], foreground=colors["text"], insertcolor=colors["text"], borderwidth=0, lightcolor=colors["surface2"], darkcolor=colors["surface2"], padding=(10, 7))
        style.configure("TButton", background=colors["surface2"], foreground=colors["text"], borderwidth=0, lightcolor=colors["surface2"], darkcolor=colors["surface2"], focuscolor=colors["surface2"], padding=(12, 7), font=("Microsoft YaHei UI", 9))
        style.map("TButton", background=[("active", colors["border"]), ("pressed", colors["border"])], bordercolor=[("focus", colors["surface2"])])
        style.configure("Pick.TButton", background=colors["surface2"], foreground=colors["accent_active"], borderwidth=0, lightcolor=colors["surface2"], darkcolor=colors["surface2"], focuscolor=colors["surface2"], padding=(12, 7), font=("Microsoft YaHei UI", 9, "bold"))
        style.map("Pick.TButton", background=[("active", colors["border"]), ("pressed", colors["border"])])
        style.configure("Accent.TButton", background=colors["accent"], foreground="#FFFFFF", borderwidth=0, lightcolor=colors["accent"], darkcolor=colors["accent"], focuscolor=colors["accent"], padding=(16, 8), font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", colors["accent_active"]), ("pressed", colors["accent_active"])])
        style.configure("Treeview", background=colors["surface2"], fieldbackground=colors["surface2"], foreground=colors["text"], bordercolor=colors["border"], rowheight=29, font=("Microsoft YaHei UI", 9))
        style.configure("Treeview.Heading", background=colors["border"], foreground=colors["text"], relief="flat", padding=7, font=("Microsoft YaHei UI", 9, "bold"))
        style.map("Treeview", background=[("selected", colors["accent"])], foreground=[("selected", "#FFFFFF")])
        style.configure("Dark.Vertical.TScrollbar", background=colors["border"], troughcolor=colors["surface"], bordercolor=colors["surface"], arrowcolor=colors["muted"], relief="flat", borderwidth=0, arrowsize=10, width=10)
        style.map("Dark.Vertical.TScrollbar", background=[("active", colors["accent"]), ("pressed", colors["accent_active"])], arrowcolor=[("active", colors["text"])])

        root = ttk.Frame(self, padding=(24, 20, 24, 14), style="App.TFrame")
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        header = ttk.Frame(root, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.columnconfigure(1, weight=1)
        mark = tk.Canvas(header, width=48, height=48, bg=colors["bg"], highlightthickness=0)
        mark.create_oval(4, 4, 44, 44, fill=colors["accent"], outline="")
        mark.create_text(24, 24, text="QQ", fill="#FFFFFF", font=("Segoe UI", 10, "bold"))
        mark.grid(row=0, column=0, rowspan=2, padx=(0, 13))
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(header, text="把本地 QQ NT 数据库整理成可保存、可检索的聊天记录", style="Subtitle.TLabel").grid(row=1, column=1, sticky="w", pady=(3, 0))
        self.status_badge = ttk.Label(header, text="准备就绪", style="Muted.TLabel")
        self.status_badge.grid(row=0, column=2, rowspan=2, sticky="e")

        source = ttk.LabelFrame(root, text=" ① 数据源与 QQ 环境 ", padding=14, style="Card.TLabelframe")
        source.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        source.columnconfigure(1, weight=1)
        fields = [("原始数据库", self.db_var, "选择", self.choose_db), ("QQ.exe", self.qq_exe_var, "选择", self.choose_qq), ("wrapper.node", self.wrapper_var, "选择", self.choose_wrapper), ("处理目录", self.work_var, "选择", self.choose_work)]
        for row, (label, var, button, command) in enumerate(fields):
            ttk.Label(source, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=5, padx=(0, 12))
            shell = tk.Frame(source, bg=colors["surface2"], highlightbackground=colors["border"], highlightcolor=colors["accent"], highlightthickness=1, bd=0)
            shell.grid(row=row, column=1, columnspan=2, sticky="ew", pady=5)
            shell.columnconfigure(0, weight=1)
            ttk.Entry(shell, textvariable=var, style="Input.TEntry").grid(row=0, column=0, sticky="ew")
            ttk.Button(shell, text=button, command=command, style="Pick.TButton").grid(row=0, column=1, sticky="ns", padx=(0, 2), pady=2)

        process = ttk.Frame(root, style="App.TFrame")
        process.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(process, text="扫描 nt_msg.db", command=self.scan_db).pack(side="left")
        ttk.Button(process, text="完整处理：解密并整理", command=self.start_pipeline, style="Accent.TButton").pack(side="left", padx=10)
        ttk.Label(process, text="密钥只在内存中使用，不会写入文件", style="Muted.TLabel").pack(side="left")
        ttk.Button(process, text="加载已整理数据库", command=self.load_db).pack(side="right")
        ttk.Label(process, text="自己的 UID", style="Muted.TLabel").pack(side="right", padx=(0, 8))
        ttk.Entry(process, textvariable=self.self_uid_var, width=25).pack(side="right", padx=(0, 10))

        pane = ttk.PanedWindow(root, orient="vertical")
        pane.grid(row=3, column=0, sticky="nsew")
        top = ttk.Frame(pane, style="App.TFrame"); top.columnconfigure(0, weight=1); top.rowconfigure(1, weight=1)
        bar = ttk.Frame(top, style="App.TFrame"); bar.grid(row=0, column=0, sticky="ew", pady=(0, 7)); bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="② 选择会话", style="App.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(bar, textvariable=self.search_var).grid(row=0, column=1, sticky="ew", padx=(18, 0))
        columns = ("peer_uid", "peer_qq", "count", "first", "last")
        self.tree = ttk.Treeview(top, columns=columns, show="headings", selectmode="browse")
        names = {"peer_uid":"好友 UID", "peer_qq":"QQ 号", "count":"消息数", "first":"最早时间", "last":"最近时间"}
        widths = {"peer_uid":300, "peer_qq":130, "count":90, "first":170, "last":170}
        for col in columns:
            self.tree.heading(col, text=names[col]); self.tree.column(col, width=widths[col], anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(top, orient="vertical", command=self.tree.yview, style="Dark.Vertical.TScrollbar"); scroll.grid(row=1, column=1, sticky="ns", padx=(7, 0))
        self.tree.configure(yscrollcommand=scroll.set); self.tree.bind("<<TreeviewSelect>>", self._select_contact)
        pane.add(top, weight=4)
        bottom = ttk.Frame(pane, style="App.TFrame"); bottom.columnconfigure(0, weight=1); bottom.rowconfigure(0, weight=1)
        self.log = tk.Text(bottom, height=7, state="disabled", wrap="word", bg=colors["surface"], fg=colors["muted"], insertbackground=colors["text"], relief="flat", borderwidth=0, padx=12, pady=10, font=("Consolas", 9))
        self.log.grid(row=0, column=0, sticky="nsew")
        pane.add(bottom, weight=1)

        footer = ttk.Frame(root, style="App.TFrame"); footer.grid(row=4, column=0, sticky="ew", pady=(12, 0)); footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="选择导出目录", command=self.choose_out).grid(row=0, column=1, padx=8)
        ttk.Button(footer, text="导出选中会话", command=self.export_selected, style="Accent.TButton").grid(row=0, column=2)
        ttk.Label(footer, text="个人联系方式  QQ：2827352235", style="Muted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(12, 0))

    def log_line(self, text):
        def write():
            self.log.configure(state="normal"); self.log.insert("end", str(text) + "\n"); self.log.see("end"); self.log.configure(state="disabled")
        self.after(0, write)

    def choose_db(self):
        path = filedialog.askopenfilename(title="选择原始 nt_msg.db", filetypes=[("QQ 数据库", "nt_msg.db"), ("所有文件", "*.*")])
        if path: self.db_var.set(path)

    def choose_qq(self):
        path = filedialog.askopenfilename(title="选择 QQ.exe", filetypes=[("QQ 程序", "QQ.exe"), ("程序", "*.exe")])
        if path: self.qq_exe_var.set(path)

    def choose_wrapper(self):
        path = filedialog.askopenfilename(title="选择 wrapper.node", filetypes=[("wrapper.node", "wrapper.node"), ("所有文件", "*.*")])
        if path: self.wrapper_var.set(path)

    def choose_work(self):
        path = filedialog.askdirectory(title="选择处理目录")
        if path: self.work_var.set(path)

    def choose_out(self):
        path = filedialog.askdirectory(title="选择导出目录")
        if path: self.out_var.set(path)

    def scan_db(self):
        root = filedialog.askdirectory(title="选择要搜索的 QQ 数据目录")
        if not root: return
        self.status_var.set("正在搜索 nt_msg.db……")
        found = []
        for base, _, files in os.walk(root):
            if "nt_msg.db" in files:
                path = Path(base) / "nt_msg.db"
                if path.stat().st_size: found.append(path)
        if not found:
            messagebox.showinfo("扫描结果", "没有找到非空 nt_msg.db")
            self.status_var.set("未找到数据库")
            return
        found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        self.db_var.set(str(found[0]))
        self.log_line("找到数据库：" + "\n".join(str(p) for p in found))
        self.status_var.set(f"找到 {len(found)} 个数据库，已选择最新文件")

    def _ps_quote(self, value):
        return "'" + str(value).replace("'", "''") + "'"

    def extract_key(self):
        deps = self._repo_paths()
        if not deps: raise RuntimeError("找不到 qq-win-db-key 和 nt_msg_db_util 项目")
        script_path = deps / "qq-win-db-key/scripts/windows/ntqq/windows_ntqq_get_key.ps1"
        if not script_path.exists(): raise RuntimeError("找不到 Windows NTQQ 密钥提取脚本")
        qq_exe, wrapper = Path(self.qq_exe_var.get()), Path(self.wrapper_var.get())
        if not qq_exe.exists() or not wrapper.exists(): raise RuntimeError("QQ.exe 或 wrapper.node 路径无效")
        workspace = deps.parent.parent
        rel = lambda path: os.path.relpath(str(path), str(workspace))
        helper = deps / "qq-win-db-key/extract_key_gui.ps1"
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", rel(helper),
             "-ScriptPath", rel(script_path), "-QQExePath", str(qq_exe), "-WrapperNodePath", str(wrapper)],
            cwd=str(workspace), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
        )
        key = result.stdout.strip()
        if not re.fullmatch(r"[\x20-\x7e]{16}", key):
            raise RuntimeError("密钥提取失败：" + (result.stderr.strip() or "请确认 QQ 正在运行并已登录，且 wrapper.node 与 QQ 版本一致"))
        return key

    def start_pipeline(self):
        source = Path(self.db_var.get().strip())
        if not source.exists() or source.stat().st_size == 0:
            messagebox.showwarning("提示", "请先选择有效的 nt_msg.db")
            return
        work = Path(self.work_var.get().strip())
        self.status_var.set("正在完整处理，请稍候……")
        self.log_line("开始完整流程：复制数据库 → 提取 key → 解密 → 整理消息")
        threading.Thread(target=self._pipeline_worker, args=(source, work), daemon=True).start()

    def _pipeline_worker(self, source, work):
        try:
            deps = self._repo_paths()
            if not deps: raise RuntimeError("找不到 nt_msg_db_util 项目")
            util = deps / "nt_msg_db_util"
            work.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, work / "nt_msg.db")
            self.log_line(f"已复制原始数据库：{source.stat().st_size:,} bytes")
            key = self.extract_key()
            self.log_line("密钥提取成功（内容不会显示或写入文件）")
            env = os.environ.copy(); env["NTQQ_DB_KEY"] = key; env["PYTHONUTF8"] = "1"; env["PYTHONIOENCODING"] = "utf-8"; env["UV_CACHE_DIR"] = str(work / "uv-cache")
            for script in ("1.decrypt.py", "3.export.py"):
                args = [self._uv_command(), "run", "--project", str(util), "python", str(util / script)]
                if script == "3.export.py": args += ["--src", "nt_msg_plain.db", "--dst", "nt_msg_export.db", "--batch", "5000"]
                self.log_line("运行 " + script)
                proc = subprocess.run(args, cwd=work, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
                if proc.stdout: self.log_line(proc.stdout[-4000:])
                if proc.returncode: raise RuntimeError(script + " 执行失败：" + (proc.stderr[-2000:] or proc.stdout[-2000:]))
            db = work / "nt_msg_export.db"
            self.after(0, lambda: self.db_var.set(str(db)))
            self.after(0, self.load_db)
            self.after(0, lambda: self.status_var.set("完整处理完成，请选择好友后导出"))
            self.log_line("完成：" + str(db))
        except Exception as exc:
            self.log_line("失败：" + str(exc))
            self.after(0, lambda: self.status_var.set("完整处理失败"))
            self.after(0, lambda: messagebox.showerror("处理失败", str(exc)))

    def load_db(self):
        path = Path(self.db_var.get().strip())
        if not path.exists(): return
        try:
            conn = sqlite3.connect(str(path))
            self.contacts = conn.execute("SELECT peer_uid, COALESCE(MAX(peer_qq), ''), COUNT(*), MIN(timestamp), MAX(timestamp) FROM c2c_messages GROUP BY peer_uid ORDER BY MAX(timestamp) DESC").fetchall()
            conn.close(); self._refresh_contacts()
            if not self.out_var.get(): self.out_var.set(str(path.parent / "导出"))
            self.status_var.set(f"已加载 {len(self.contacts):,} 个私聊会话")
        except Exception as exc: messagebox.showerror("读取失败", str(exc))

    def _refresh_contacts(self):
        if not hasattr(self, "tree"): return
        keyword = self.search_var.get().strip().lower()
        for item in self.tree.get_children(): self.tree.delete(item)
        for peer_uid, peer_qq, count, first, last in self.contacts:
            if keyword and keyword not in str(peer_uid).lower() and keyword not in str(peer_qq).lower(): continue
            self.tree.insert("", "end", values=(peer_uid, peer_qq, f"{count:,}", format_time(first), format_time(last)))

    def _select_contact(self, _event=None):
        selected = self.tree.selection()
        if selected: self.status_var.set("已选择：" + self.tree.item(selected[0], "values")[0])

    def export_selected(self):
        selected = self.tree.selection()
        if not selected: messagebox.showwarning("提示", "请先选择一个好友会话"); return
        db_path = Path(self.db_var.get().strip()); out = Path(self.out_var.get().strip()) if self.out_var.get().strip() else db_path.parent / "导出"
        peer_uid = self.tree.item(selected[0], "values")[0]; self.status_var.set("正在导出……")
        def worker():
            try:
                count, txt, html_path = export_chat(db_path, peer_uid, self.self_uid_var.get().strip(), out, self.log_line)
                self.after(0, lambda: self.status_var.set(f"导出完成：{count:,} 条消息"))
                self.after(0, lambda: messagebox.showinfo("导出完成", f"共导出 {count:,} 条消息。\n\nTXT：{txt}\nHTML：{html_path}"))
            except Exception as exc:
                self.after(0, lambda: self.status_var.set("导出失败")); self.after(0, lambda: messagebox.showerror("导出失败", str(exc)))
        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    Exporter().mainloop()
