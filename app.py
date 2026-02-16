from flask import Flask, request
import json
import os
from datetime import datetime

app = Flask(__name__)

FILE_NAME = "bookings.json"

TEAM = ["พี่เน็ต", "พี่เอฟ", "พี่ชุ", "พี่ปาล์ม", "อื่นๆ"]

STATUS_BOOKED = "BOOKED"
STATUS_CHECKED_IN = "CHECKED_IN"
STATUS_CHECKED_OUT = "CHECKED_OUT"


def load_bookings():
    if not os.path.exists(FILE_NAME):
        return []
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bookings(bookings):
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)


def to_dt(date_str, time_str):
    return datetime.fromisoformat(f"{date_str}T{time_str}")


def is_conflict(existing, new_b):
    if existing.get("date") != new_b.get("date"):
        return False

    ex_start = to_dt(existing["date"], existing["start"])
    ex_end = to_dt(existing["date"], existing["end"])
    new_start = to_dt(new_b["date"], new_b["start"])
    new_end = to_dt(new_b["date"], new_b["end"])

    return (new_start < ex_end) and (new_end > ex_start)


def migrate_old_bookings(bookings):
    changed = False
    next_id = 1

    existing_ids = [b.get("id") for b in bookings if isinstance(b.get("id"), int)]
    if existing_ids:
        next_id = max(existing_ids) + 1

    for b in bookings:
        if "id" not in b:
            b["id"] = next_id
            next_id += 1
            changed = True
        if "status" not in b:
            b["status"] = STATUS_BOOKED
            changed = True

    return bookings, changed


def get_active_booking(bookings):
    actives = [b for b in bookings if b.get("status") == STATUS_CHECKED_IN]
    actives.sort(key=lambda x: (x.get("date", ""), x.get("start", "")))
    return actives[0] if actives else None


def new_id(bookings):
    return max([b.get("id", 0) for b in bookings] + [0]) + 1


@app.route("/", methods=["GET", "POST"])
def home():
    bookings = load_bookings()
    bookings, changed = migrate_old_bookings(bookings)
    if changed:
        save_bookings(bookings)

    msg = ""
    msg_color = "#1e8e3e"  # green-ish

    selected_date = request.args.get("date", "").strip()
    today = datetime.now().date().isoformat()
    if not selected_date:
        selected_date = today

    active = get_active_booking(bookings)

    # ===== Handle POST =====
    if request.method == "POST":
        action = request.form.get("action", "add")

        if action == "delete":
            bid = int(request.form.get("id", "0"))
            before = len(bookings)
            bookings = [b for b in bookings if b.get("id") != bid]
            save_bookings(bookings)
            msg = "🗑️ ลบรายการแล้ว" if len(bookings) < before else "ไม่พบรายการที่ต้องการลบ"

        elif action == "checkin":
            bid = int(request.form.get("id", "0"))
            active = get_active_booking(bookings)

            if active and active.get("id") != bid:
                msg = f"❌ มีคนใช้อยู่แล้ว: {active.get('name')} ({active.get('start')}-{active.get('end')})"
                msg_color = "#d93025"
            else:
                updated = False
                for b in bookings:
                    if b.get("id") == bid:
                        b["status"] = STATUS_CHECKED_IN
                        updated = True
                        break
                save_bookings(bookings)
                msg = "✅ Check-in แล้ว" if updated else "ไม่พบรายการที่ต้องการอัปเดต"

        elif action == "checkout":
            bid = int(request.form.get("id", "0"))
            updated = False
            for b in bookings:
                if b.get("id") == bid:
                    b["status"] = STATUS_CHECKED_OUT
                    updated = True
                    break
            save_bookings(bookings)
            msg = "✅ Check-out แล้ว" if updated else "ไม่พบรายการที่ต้องการอัปเดต"

        else:
            # add booking
            person = request.form.get("person", "").strip()
            other_name = request.form.get("other_name", "").strip()
            name = other_name if person == "อื่นๆ" else person

            date = request.form.get("date", "").strip()
            start = request.form.get("start", "").strip()
            end = request.form.get("end", "").strip()
            purpose = request.form.get("purpose", "").strip()

            if name == "" or date == "" or start == "" or end == "":
                msg = "กรุณากรอกให้ครบ: ชื่อ, วันที่, เวลาเริ่ม, เวลาเลิก"
                msg_color = "#d93025"
            else:
                try:
                    start_dt = to_dt(date, start)
                    end_dt = to_dt(date, end)
                except Exception:
                    msg = "รูปแบบวันที่/เวลาไม่ถูกต้อง"
                    msg_color = "#d93025"
                else:
                    if end_dt <= start_dt:
                        msg = "เวลาเลิกต้องมากกว่าเวลาเริ่ม"
                        msg_color = "#d93025"
                    else:
                        new_booking = {
                            "id": new_id(bookings),
                            "name": name,
                            "purpose": purpose,
                            "date": date,
                            "start": start,
                            "end": end,
                            "status": STATUS_BOOKED,
                        }

                        conflict = any(is_conflict(b, new_booking) for b in bookings)
                        if conflict:
                            msg = "❌ เวลานี้ชนกับรายการที่มีอยู่แล้ว กรุณาเลือกเวลาใหม่"
                            msg_color = "#d93025"
                        else:
                            bookings.append(new_booking)
                            bookings.sort(key=lambda x: (x.get("date", ""), x.get("start", "")))
                            save_bookings(bookings)
                            msg = "✅ จองสำเร็จแล้ว"
                            msg_color = "#1e8e3e"
                            selected_date = date

    # refresh active after changes
    active = get_active_booking(bookings)

    # dropdown options
    options = "".join([f'<option value="{p}">{p}</option>' for p in TEAM])

    # daily list
    day_list = [b for b in bookings if b.get("date") == selected_date]
    day_list.sort(key=lambda x: x.get("start", ""))

    # build rows with google-ish pills + actions
    rows = ""
    for b in day_list:
        bid = b.get("id", 0)
        status = b.get("status", STATUS_BOOKED)

        if status == STATUS_BOOKED:
            pill = '<span class="pill pill-booked">จองแล้ว</span>'
        elif status == STATUS_CHECKED_IN:
            pill = '<span class="pill pill-in">เช็คอินแล้ว</span>'
        else:
            pill = '<span class="pill pill-out">เช็คเอาท์แล้ว</span>'

        can_checkin = (status == STATUS_BOOKED) and (active is None)
        can_checkout = (status == STATUS_CHECKED_IN)

        checkin_btn = ""
        checkout_btn = ""

        if can_checkin:
            checkin_btn = f"""
              <form method="POST">
                <input type="hidden" name="action" value="checkin">
                <input type="hidden" name="id" value="{bid}">
                <button class="btn btn-ghost" type="submit">Check-in</button>
              </form>
            """
        elif status == STATUS_BOOKED and active is not None:
            checkin_btn = "<span style='color:#9aa0a6; font-weight:700;'>รอคิว</span>"

        if can_checkout:
            checkout_btn = f"""
              <form method="POST">
                <input type="hidden" name="action" value="checkout">
                <input type="hidden" name="id" value="{bid}">
                <button class="btn btn-ghost" type="submit">Check-out</button>
              </form>
            """

        delete_btn = f"""
          <form method="POST">
            <input type="hidden" name="action" value="delete">
            <input type="hidden" name="id" value="{bid}">
            <button class="btn btn-danger" type="submit">ลบ</button>
          </form>
        """

        actions = f'<div class="actions">{checkin_btn}{checkout_btn}{delete_btn}</div>'

        rows += f"""
        <tr>
          <td><b>{b.get("name","")}</b></td>
          <td>{b.get("purpose","")}</td>
          <td>{b.get("start","")}-{b.get("end","")}</td>
          <td>{pill}</td>
          <td>{actions}</td>
        </tr>
        """

    # live bar (top status)
    if active:
        live_bar = f"""
        <div class="live live-ok">
          🟢 ตอนนี้กำลังใช้งาน: <b>{active.get("name")}</b>
          <span style="color:#5f6368;">|</span>
          เวลา {active.get("start")}-{active.get("end")}
          <span style="color:#5f6368;">|</span>
          วันที่ {active.get("date")}
        </div>
        """
    else:
        live_bar = """
        <div class="live live-idle">
          ⚪ ตอนนี้ยังไม่มีใครใช้งาน (พร้อมให้ Check-in)
        </div>
        """

    # ===== Return HTML (Google Calendar style) =====
    return f"""
<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Shared Account Calendar</title>
  <style>
    :root {{
      --bg: #f6f8fc;
      --card: #ffffff;
      --text: #1f1f1f;
      --muted: #5f6368;
      --line: #e0e3e7;
      --blue: #1a73e8;
      --green: #1e8e3e;
      --red: #d93025;
      --shadow: 0 1px 2px rgba(0,0,0,.08), 0 2px 6px rgba(0,0,0,.06);
      --radius: 16px;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: var(--text);
      background: var(--bg);
    }}

    .topbar {{
      position: sticky;
      top: 0;
      z-index: 50;
      background: rgba(246,248,252,.88);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid var(--line);
    }}
    .topbar-inner {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 650;
      letter-spacing: .2px;
    }}
    .logo {{
      width: 34px;
      height: 34px;
      border-radius: 10px;
      background: var(--blue);
      display: grid;
      place-items: center;
      color: #fff;
      font-weight: 800;
    }}
    .sub {{
      font-size: 12px;
      color: var(--muted);
      font-weight: 500;
      margin-top: 2px;
    }}

    .container {{
      max-width: 1100px;
      margin: 18px auto;
      padding: 0 16px 24px;
    }}

    .grid {{
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 16px;
    }}
    @media (max-width: 920px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}

    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 16px;
    }}

    h2 {{
      margin: 0 0 12px 0;
      font-size: 16px;
      font-weight: 700;
    }}

    .live {{
      border-radius: 14px;
      padding: 12px 14px;
      border: 1px solid var(--line);
      background: #fff;
      box-shadow: var(--shadow);
      margin-bottom: 14px;
    }}
    .live-ok {{ border-color: rgba(30,142,62,.25); background: rgba(30,142,62,.08); }}

    .msg {{
      margin: 10px 0 0;
      font-size: 13px;
      color: {msg_color};
      font-weight: 700;
    }}

    label {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin: 10px 0 6px;
    }}

    input, select {{
      width: 100%;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      outline: none;
      font-size: 14px;
      background: #fff;
    }}
    input:focus, select:focus {{
      border-color: rgba(26,115,232,.45);
      box-shadow: 0 0 0 4px rgba(26,115,232,.12);
    }}

    .row2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}

    .btn {{
      appearance: none;
      border: 1px solid transparent;
      background: var(--blue);
      color: #fff;
      padding: 10px 14px;
      border-radius: 999px;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 1px 0 rgba(0,0,0,.04);
    }}
    .btn:active {{ transform: translateY(1px); }}
    .btn-ghost {{
      background: #fff;
      color: var(--blue);
      border-color: rgba(26,115,232,.35);
    }}
    .btn-danger {{
      background: #fff;
      color: var(--red);
      border-color: rgba(217,48,37,.35);
    }}

    .agenda-head {{
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }}

    .date-picker {{
      display: flex;
      gap: 8px;
      align-items: center;
    }}
    .date-picker input {{ width: 160px; }}

    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: #fff;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      font-size: 13px;
      vertical-align: middle;
    }}
    th {{
      color: var(--muted);
      font-weight: 700;
      background: #fbfbfc;
    }}
    tr:last-child td {{ border-bottom: none; }}

    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      font-weight: 800;
      font-size: 12px;
      border: 1px solid var(--line);
      background: #fff;
    }}
    .pill-booked {{ border-color: rgba(26,115,232,.25); background: rgba(26,115,232,.08); color: var(--blue); }}
    .pill-in {{ border-color: rgba(30,142,62,.25); background: rgba(30,142,62,.10); color: var(--green); }}
    .pill-out {{ border-color: rgba(95,99,104,.25); background: rgba(95,99,104,.08); color: var(--muted); }}

    .actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .actions form {{ margin: 0; }}

    .hint {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }}
  </style>
</head>

<body>
  <div class="topbar">
    <div class="topbar-inner">
      <div class="brand">
        <div class="logo">C</div>
        <div>
          Shared Account Calendar
          <div class="sub">จองเวลา + Check-in/Check-out สำหรับบัญชีที่ใช้ร่วมกัน</div>
        </div>
      </div>
      <div style="color:var(--muted); font-size:12px;">
        Local: 127.0.0.1:5000
      </div>
    </div>
  </div>

  <div class="container">
    {live_bar}

    <div class="grid">
      <div class="card">
        <h2>สร้างการจอง</h2>
        <form method="POST">
          <input type="hidden" name="action" value="add" />

          <label>ผู้จอง</label>
          <select name="person">
            {options}
          </select>

          <label>ถ้าเลือก “อื่นๆ” ให้พิมพ์ชื่อ</label>
          <input name="other_name" placeholder="ชื่อ..." />

          <label>เรื่องที่จอง</label>
          <input name="purpose" placeholder="เช่น ใช้งานบัญชี, ทำ report" />

          <label>วันที่</label>
          <input type="date" name="date" />

          <div class="row2">
            <div>
              <label>เวลาเริ่ม</label>
              <input type="time" name="start" />
            </div>
            <div>
              <label>เวลาเลิก</label>
              <input type="time" name="end" />
            </div>
          </div>

          <div style="margin-top:12px; display:flex; gap:10px;">
            <button class="btn" type="submit">จอง</button>
            <a class="btn btn-ghost" href="/?date={selected_date}" style="text-decoration:none; display:inline-flex; align-items:center;">
              รีเฟรชวัน {selected_date}
            </a>
          </div>

          <div class="msg">{msg}</div>
        </form>

        <div class="hint">
          กติกา shared account: เช็คอินได้ทีละคนเท่านั้น<br/>
          ถ้ามีคนใช้อยู่ ระบบจะแสดง “รอคิว”
        </div>
      </div>

      <div class="card">
        <div class="agenda-head">
          <div>
            <h2 style="margin-bottom:4px;">ตารางรายวัน</h2>
            <div class="sub">ดูรายการจองแบบ agenda ของวันนั้น</div>
          </div>

          <form method="GET" class="date-picker">
            <input type="date" name="date" value="{selected_date}" />
            <button class="btn btn-ghost" type="submit">ดู</button>
          </form>
        </div>

        <table>
          <tr>
            <th>ชื่อ</th>
            <th>เรื่อง</th>
            <th>เวลา</th>
            <th>สถานะ</th>
            <th>จัดการ</th>
          </tr>
          {rows}
        </table>

        <div class="hint">
          ถ้าลืม Check-out เดี๋ยวทำ “Force check-out” ให้หัวหน้าทีมกดได้
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""


if __name__ == "__main__":
    app.run()
