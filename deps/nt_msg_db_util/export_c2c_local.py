import argparse
import html
import json
import sqlite3
from datetime import datetime
from pathlib import Path


def message_text(text: str | None, content: str | None) -> str:
    if text:
        return text
    if not content:
        return ""
    try:
        value = json.loads(content)
        if isinstance(value, dict):
            if value.get("text"):
                return str(value["text"])
            return json.dumps(value, ensure_ascii=False)
    except json.JSONDecodeError:
        pass
    return content


def main() -> None:
    parser = argparse.ArgumentParser(description="Export one C2C conversation locally.")
    parser.add_argument("--db", default="nt_msg_export.db")
    parser.add_argument("--peer-uid", required=True)
    parser.add_argument("--self-uid", default="")
    parser.add_argument("--out-dir", default="exported_c2c")
    args = parser.parse_args()

    db_path = Path(args.db)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT timestamp, sender_uid, sender_qq, text, content
        FROM c2c_messages
        WHERE peer_uid = ?
        ORDER BY timestamp, msg_id
        """,
        (args.peer_uid,),
    ).fetchall()
    conn.close()

    txt_lines = []
    html_items = []
    for timestamp, sender_uid, sender_qq, text, content in rows:
        when = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        who = "我" if args.self_uid and sender_uid == args.self_uid else str(sender_qq or sender_uid)
        body = message_text(text, content)
        txt_lines.append(f"[{when}] {who}\n{body}\n")
        html_items.append(
            "<article class='message'>"
            f"<div class='meta'>{html.escape(when)} · {html.escape(who)}</div>"
            f"<div class='body'>{html.escape(body).replace(chr(10), '<br>')}</div>"
            "</article>"
        )

    (out_dir / "chat.txt").write_text("\n".join(txt_lines), encoding="utf-8")
    document = """<!doctype html>
<meta charset="utf-8">
<title>QQ C2C Chat Export</title>
<style>
body { max-width: 920px; margin: 2rem auto; font: 15px/1.6 system-ui, sans-serif; color: #222; }
.message { border-bottom: 1px solid #eee; padding: .8rem 0; }
.meta { color: #777; font-size: 13px; }
.body { white-space: normal; overflow-wrap: anywhere; }
</style>
<main>
""" + "\n".join(html_items) + "\n</main>\n"
    (out_dir / "chat.html").write_text(document, encoding="utf-8")
    print(f"exported={len(rows)}")
    print(f"txt={out_dir / 'chat.txt'}")
    print(f"html={out_dir / 'chat.html'}")


if __name__ == "__main__":
    main()
