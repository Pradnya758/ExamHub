"""
ExamHub - Examination Management System
Flask + SQLite (built-in sqlite3). Run:  python app.py   ->  http://127.0.0.1:5000
Covers: user input -> processing -> output -> stored in DB, plus DDL, DML and DCL pages.
"""
import os, re, random, sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g

app = Flask(__name__)
app.secret_key = "examhub-secret"
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exam.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS STUDENT(student_id INTEGER PRIMARY KEY, name TEXT NOT NULL, dept TEXT, year INTEGER, email TEXT);
CREATE TABLE IF NOT EXISTS EXAM(exam_id INTEGER PRIMARY KEY, subject TEXT NOT NULL, exam_date DATE, max_marks INTEGER NOT NULL, pass_marks INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS MARKS(student_id INTEGER, exam_id INTEGER, marks_obtained REAL NOT NULL,
  PRIMARY KEY(student_id, exam_id),
  FOREIGN KEY(student_id) REFERENCES STUDENT(student_id) ON DELETE CASCADE,
  FOREIGN KEY(exam_id) REFERENCES EXAM(exam_id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS RESULT(student_id INTEGER, exam_id INTEGER, percentage REAL, grade TEXT, status TEXT,
  PRIMARY KEY(student_id, exam_id),
  FOREIGN KEY(student_id) REFERENCES STUDENT(student_id) ON DELETE CASCADE,
  FOREIGN KEY(exam_id) REFERENCES EXAM(exam_id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS app_users(username TEXT PRIMARY KEY, password TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS app_privileges(username TEXT, table_name TEXT, privilege TEXT, PRIMARY KEY(username, table_name, privilege));
INSERT OR IGNORE INTO app_users VALUES('admin','admin');
"""
CORE = {"STUDENT", "EXAM", "MARKS", "RESULT"}
IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,29}$")
OPS = ["=", "<>", ">", "<", ">=", "<=", "LIKE"]
TYPES = ["INTEGER", "TEXT", "REAL", "DATE"]
CONSTRAINTS = ["", "PRIMARY KEY", "NOT NULL", "UNIQUE"]
PRIVS = ["SELECT", "INSERT", "UPDATE", "DELETE", "ALL"]


# ------------------------------------------------------------ database helpers
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    c = sqlite3.connect(DB_FILE)
    c.executescript(SCHEMA)
    c.commit()
    c.close()


def ok(name):
    return bool(name) and IDENT.match(name) is not None


def info(sql="", msg=None, err=None):
    return {"sql": sql, "params": [], "message": msg, "error": err, "columns": [], "rows": []}


def run(sql, params=()):
    """Run any single statement; return a dict used by the result box."""
    res = info(sql)
    res["params"] = list(params)
    try:
        cur = db().execute(sql, list(params))
        if cur.description:
            res["columns"] = [d[0] for d in cur.description]
            res["rows"] = [list(r) for r in cur.fetchall()]
            res["message"] = f"{len(res['rows'])} row(s) returned."
        else:
            db().commit()
            res["message"] = "Executed successfully." if cur.rowcount < 0 else f"{cur.rowcount} row(s) affected."
    except sqlite3.Error as e:
        db().rollback()
        res["error"] = str(e)
    return res


def user_tables():
    rows = db().execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                        "AND name NOT LIKE 'app\\_%' ESCAPE '\\' ORDER BY name").fetchall()
    return [r[0] for r in rows]


def canon(name):
    for t in user_tables():
        if t.lower() == (name or "").strip().lower():
            return t
    return None


def columns_of(table):
    return [{"name": r["name"], "type": (r["type"] or "TEXT").upper()}
            for r in db().execute(f"PRAGMA table_info({table})").fetchall()]


def allowed(user, table, priv):
    if user == "admin":
        return True
    n = db().execute("SELECT COUNT(*) FROM app_privileges WHERE username=? AND table_name=? "
                     "AND privilege IN (?, 'ALL')", (user, table.upper(), priv)).fetchone()[0]
    return n > 0


# ------------------------------------------------------------ exam processing
def grade_of(p):
    for lim, gr in [(90, "O"), (80, "A+"), (70, "A"), (60, "B"), (50, "C"), (40, "D")]:
        if p >= lim:
            return gr
    return "F"


def save_mark(sid, eid, marks):
    """INPUT -> PROCESSING (percentage, grade, status) -> STORE in MARKS and RESULT."""
    ex = db().execute("SELECT * FROM EXAM WHERE exam_id=?", (eid,)).fetchone()
    pct = round(marks / ex["max_marks"] * 100, 2)
    status = "Pass" if marks >= ex["pass_marks"] else "Fail"
    db().execute("INSERT OR REPLACE INTO MARKS VALUES (?,?,?)", (sid, eid, marks))
    db().execute("INSERT OR REPLACE INTO RESULT VALUES (?,?,?,?,?)", (sid, eid, pct, grade_of(pct), status))
    db().commit()
    return pct, grade_of(pct), status


RESULT_SQL = """SELECT s.student_id, s.name, e.exam_id, e.subject, m.marks_obtained AS marks, e.max_marks,
       r.percentage, r.grade, r.status
FROM MARKS m JOIN STUDENT s ON s.student_id = m.student_id JOIN EXAM e ON e.exam_id = m.exam_id
JOIN RESULT r ON r.student_id = m.student_id AND r.exam_id = m.exam_id"""


@app.template_filter("initials")
def initials(name):
    p = (name or "?").split()
    return (p[0][0] + (p[1][0] if len(p) > 1 else "")).upper()


# ------------------------------------------------------------ dashboard
@app.route("/")
def index():
    one = lambda s: db().execute(s).fetchone()[0]
    n_stu, n_exam, n_res = one("SELECT COUNT(*) FROM STUDENT"), one("SELECT COUNT(*) FROM EXAM"), one("SELECT COUNT(*) FROM RESULT")
    passed = one("SELECT COUNT(*) FROM RESULT WHERE status='Pass'")
    pass_pct = round(passed / n_res * 100, 1) if n_res else 0
    subj = db().execute("SELECT e.subject AS subject, ROUND(AVG(r.percentage),1) AS avg, ROUND(MAX(r.percentage),1) AS hi "
                        "FROM RESULT r JOIN EXAM e ON e.exam_id=r.exam_id GROUP BY e.exam_id ORDER BY e.exam_id LIMIT 6").fetchall()
    slot, bars = 560 / max(len(subj), 1), []
    for i, r in enumerate(subj):
        x = 30 + i * slot
        bars.append(dict(label=r["subject"][:18], cx=round(x + slot / 2, 1), x=round(x + slot * .16, 1), w=round(slot * .3, 1),
                         ah=round(r["avg"] * 1.6, 1), hh=round(r["hi"] * 1.6, 1), avg=r["avg"], hi=r["hi"]))
    top = db().execute("SELECT s.student_id, s.name, s.dept, s.year, ROUND(AVG(r.percentage),1) AS avg, COUNT(*) AS n "
                       "FROM RESULT r JOIN STUDENT s ON s.student_id=r.student_id GROUP BY s.student_id "
                       "ORDER BY avg DESC LIMIT 5").fetchall()
    recent = db().execute(RESULT_SQL + " ORDER BY m.rowid DESC LIMIT 5").fetchall()
    return render_template("index.html", n_stu=n_stu, n_exam=n_exam, n_res=n_res, pass_pct=pass_pct,
                           passed=passed, failed=n_res - passed, bars=bars, top=top, recent=recent)


@app.route("/seed", methods=["POST"])
def seed():
    stu = [(101, "Aarav Sharma", "CSE", 2), (102, "Diya Patel", "CSE", 2), (103, "Karthik Raj", "ECE", 3),
           (104, "Meera Nair", "IT", 2), (105, "Rohan Iyer", "EEE", 3), (106, "Sneha Reddy", "CSE", 4),
           (107, "Vikram Singh", "MECH", 1), (108, "Ananya Das", "IT", 3)]
    ex = [(1, "DBMS", "2026-11-03"), (2, "Operating Systems", "2026-11-05"),
          (3, "Data Structures", "2026-11-08"), (4, "Computer Networks", "2026-11-11")]
    for sid, n, d, y in stu:
        db().execute("INSERT OR IGNORE INTO STUDENT VALUES (?,?,?,?,?)", (sid, n, d, y, n.split()[0].lower() + "@college.edu"))
    for eid, s, d in ex:
        db().execute("INSERT OR IGNORE INTO EXAM VALUES (?,?,?,100,40)", (eid, s, d))
    db().commit()
    rnd = random.Random(7)
    for sid, *_ in stu:
        for eid, *_ in ex:
            if not db().execute("SELECT 1 FROM MARKS WHERE student_id=? AND exam_id=?", (sid, eid)).fetchone():
                save_mark(sid, eid, rnd.randint(30, 98))
    flash("Sample data loaded: 8 students, 4 exams and 32 results.", "ok")
    return redirect(url_for("index"))


# ------------------------------------------------------------ Students and Exams (generic CRUD)
ENT = {
    "students": dict(table="STUDENT", pk="student_id", title="Students", singular="Student",
                     sub="Add, edit and remove students. Every change is saved in the STUDENT table.",
                     fields=[("student_id", "Student ID", "number"), ("name", "Full name", "text"),
                             ("dept", "Department", "select:CSE,ECE,EEE,IT,MECH,CIVIL"),
                             ("year", "Year", "select:1,2,3,4"), ("email", "Email", "email")]),
    "exams": dict(table="EXAM", pk="exam_id", title="Exams", singular="Exam",
                  sub="Schedule exams with maximum and passing marks. Saved in the EXAM table.",
                  fields=[("exam_id", "Exam ID", "number"), ("subject", "Subject", "text"),
                          ("exam_date", "Exam date", "date"), ("max_marks", "Max marks", "number"),
                          ("pass_marks", "Pass marks", "number")]),
}


def validate(ent, d):
    for k, v in d.items():
        if not v and k != "email":
            return f"{k.replace('_', ' ').capitalize()} is required."
    try:
        for k in ("student_id", "exam_id", "year", "max_marks", "pass_marks"):
            if k in d and int(d[k]) <= 0:
                return f"{k.replace('_', ' ').capitalize()} must be a positive number."
    except ValueError:
        return "Numeric fields must contain whole numbers."
    if ent == "exams" and int(d["pass_marks"]) > int(d["max_marks"]):
        return "Pass marks cannot be greater than max marks."
    return None


def crud(ent):
    c = ENT[ent]
    if request.method == "POST":
        data = {f[0]: request.form.get(f[0], "").strip() for f in c["fields"]}
        err = validate(ent, data)
        if err:
            flash(err, "error")
        else:
            try:
                if request.form.get("editing") == "1":
                    ks = [k for k in data if k != c["pk"]]
                    db().execute(f"UPDATE {c['table']} SET {', '.join(k + '=?' for k in ks)} WHERE {c['pk']}=?",
                                 [data[k] for k in ks] + [data[c["pk"]]])
                    flash(f"{c['singular']} updated.", "ok")
                else:
                    db().execute(f"INSERT INTO {c['table']} ({', '.join(data)}) VALUES ({', '.join('?' * len(data))})",
                                 list(data.values()))
                    flash(f"{c['singular']} added.", "ok")
                db().commit()
            except sqlite3.IntegrityError:
                flash(f"{c['singular']} ID already exists.", "error")
        return redirect(url_for(ent))
    rows = [dict(r) for r in db().execute(f"SELECT * FROM {c['table']} ORDER BY {c['pk']}").fetchall()]
    return render_template("crud.html", c=c, ent=ent, rows=rows)


@app.route("/students", methods=["GET", "POST"])
def students():
    return crud("students")


@app.route("/exams", methods=["GET", "POST"])
def exams():
    return crud("exams")


@app.route("/<ent>/delete/<int:pk>", methods=["POST"])
def delete(ent, pk):
    if ent not in ENT:
        return "Not found", 404
    c = ENT[ent]
    db().execute(f"DELETE FROM {c['table']} WHERE {c['pk']}=?", (pk,))
    db().commit()
    flash(f"{c['singular']} deleted (related marks and results removed too).", "ok")
    return redirect(url_for(ent))


# ------------------------------------------------------------ Marks, Results, Reports
@app.route("/marks", methods=["GET", "POST"])
def marks():
    if request.method == "POST":
        try:
            sid, eid, m = int(request.form["student_id"]), int(request.form["exam_id"]), float(request.form["marks"])
            ex = db().execute("SELECT * FROM EXAM WHERE exam_id=?", (eid,)).fetchone()
            if not ex or not db().execute("SELECT 1 FROM STUDENT WHERE student_id=?", (sid,)).fetchone():
                flash("Choose a valid student and exam.", "error")
            elif not 0 <= m <= ex["max_marks"]:
                flash(f"Marks must be between 0 and {ex['max_marks']} for {ex['subject']}.", "error")
            else:
                pct, gr, st = save_mark(sid, eid, m)
                flash(f"Saved. {pct}% - Grade {gr} - {st}.", "ok" if st == "Pass" else "error")
        except (ValueError, KeyError):
            flash("Enter valid values.", "error")
        return redirect(url_for("marks"))
    return render_template("marks.html", studs=db().execute("SELECT * FROM STUDENT ORDER BY name").fetchall(),
                           exams=db().execute("SELECT * FROM EXAM ORDER BY exam_id").fetchall(),
                           rows=db().execute(RESULT_SQL + " ORDER BY m.rowid DESC").fetchall())


@app.route("/marks/delete/<int:sid>/<int:eid>", methods=["POST"])
def delete_mark(sid, eid):
    db().execute("DELETE FROM MARKS WHERE student_id=? AND exam_id=?", (sid, eid))
    db().execute("DELETE FROM RESULT WHERE student_id=? AND exam_id=?", (sid, eid))
    db().commit()
    flash("Result deleted.", "ok")
    return redirect(request.referrer or url_for("marks"))


@app.route("/results")
def results():
    sid, eid = request.args.get("student", ""), request.args.get("exam", "")
    where, p = [], []
    if sid:
        where.append("s.student_id=?"); p.append(sid)
    if eid:
        where.append("e.exam_id=?"); p.append(eid)
    sql = RESULT_SQL + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY s.name, e.exam_id"
    rows = db().execute(sql, p).fetchall()
    return render_template("results.html", rows=rows, sid=sid, eid=eid,
                           studs=db().execute("SELECT * FROM STUDENT ORDER BY name").fetchall(),
                           exams=db().execute("SELECT * FROM EXAM ORDER BY exam_id").fetchall(),
                           passed=sum(1 for r in rows if r["status"] == "Pass"))


@app.route("/reports")
def reports():
    exams_ = db().execute("SELECT * FROM EXAM ORDER BY exam_id").fetchall()
    eid = request.args.get("exam") or (str(exams_[0]["exam_id"]) if exams_ else "")
    ranks = db().execute(RESULT_SQL + " WHERE e.exam_id=? ORDER BY m.marks_obtained DESC, s.name", (eid,)).fetchall() if eid else []
    stats = db().execute("SELECT e.subject, COUNT(*) AS n, ROUND(AVG(m.marks_obtained),1) AS avg, MAX(m.marks_obtained) AS hi, "
                         "MIN(m.marks_obtained) AS lo, ROUND(100.0*SUM(r.status='Pass')/COUNT(*),1) AS pp "
                         "FROM MARKS m JOIN EXAM e ON e.exam_id=m.exam_id JOIN RESULT r ON r.student_id=m.student_id "
                         "AND r.exam_id=m.exam_id GROUP BY e.exam_id ORDER BY e.exam_id").fetchall()
    dist = {gr: 0 for gr in ["O", "A+", "A", "B", "C", "D", "F"]}
    for r in ranks:
        dist[r["grade"]] += 1
    return render_template("reports.html", exams=exams_, eid=eid, ranks=ranks, stats=stats, dist=dist,
                           dmax=max(list(dist.values()) + [1]))


# ------------------------------------------------------------ DDL
def col_def(n, t, c=""):
    return f"{n} {t}" + (f" {c}" if c else "")


@app.route("/ddl", methods=["GET", "POST"])
def ddl():
    result = None
    if request.method == "POST":
        a, t = request.form.get("action"), request.form.get("table", "").strip()
        names, types, cons = (request.form.getlist(k) for k in ("col_name", "col_type", "col_con"))
        col, typ, new = (request.form.get(k, "").strip() for k in ("alt_col", "alt_type", "new_name"))
        if a == "create":
            parts, err = [], None
            if not ok(t) or t.lower().startswith(("app_", "sqlite_")):
                err = "Table name must start with a letter (letters, digits, underscore only) and cannot start with app_."
            for n, ty, cn in zip(names, types, cons):
                if not n.strip():
                    continue
                if not ok(n.strip()) or ty not in TYPES or cn not in CONSTRAINTS:
                    err = f"Invalid column: {n}"
                    break
                parts.append(col_def(n.strip(), ty, cn))
            fc, ft, fr = (request.form.get(k, "").strip() for k in ("fk_col", "fk_table", "fk_ref"))
            if not err and (fc or ft or fr):
                if ok(fc) and ok(ft) and ok(fr):
                    parts.append(f"FOREIGN KEY ({fc}) REFERENCES {ft}({fr})")
                else:
                    err = "Invalid foreign key details."
            if err or not parts:
                result = info(err=err or "Add at least one column.")
            else:
                result = run(f"CREATE TABLE {t} (\n  " + ",\n  ".join(parts) + "\n)")
        else:
            tt = canon(t)
            if not tt:
                result = info(err="Choose an existing table.")
            elif tt.upper() in CORE and a not in ("add",):
                result = info(err=f"{tt} is a core table and is protected. Create your own table to try this operation.")
            elif a == "add" and ok(col) and typ in TYPES:
                result = run(f"ALTER TABLE {tt} ADD COLUMN {col_def(col, typ)}")
            elif a == "rename_col" and ok(col) and ok(new):
                result = run(f"ALTER TABLE {tt} RENAME COLUMN {col} TO {new}")
            elif a == "rename_table" and ok(new) and not new.lower().startswith(("app_", "sqlite_")):
                result = run(f"ALTER TABLE {tt} RENAME TO {new}")
            elif a == "dropcol" and ok(col):
                result = run(f"ALTER TABLE {tt} DROP COLUMN {col}")
            elif a == "drop":
                result = run(f"DROP TABLE {tt}")
            else:
                result = info(err="Invalid input for this operation.")
    return render_template("ddl.html", result=result, tables=user_tables(), types=TYPES, cons=CONSTRAINTS)


# ------------------------------------------------------------ DML
@app.route("/columns/<table>")
def columns(table):
    t = canon(table)
    return jsonify(columns_of(t) if t else [])


@app.route("/dml", methods=["GET", "POST"])
def dml():
    result, sel, user = None, "", request.form.get("as_user", "admin")
    if request.method == "POST":
        op, sel = request.form.get("op"), canon(request.form.get("table")) or ""
        need = {"insert": "INSERT", "update": "UPDATE", "delete": "DELETE", "select": "SELECT"}.get(op)
        if not sel or not need:
            result = info(err="Choose a table and an operation.")
        else:
            cols = [c["name"] for c in columns_of(sel)]
            vals = {c: request.form.get("val_" + c, "").strip() for c in cols}
            vals = {k: v for k, v in vals.items() if v != ""}
            wc, wo, wv = request.form.get("where_col", ""), request.form.get("where_op", "="), request.form.get("where_val", "").strip()
            where, wp, bad = "", [], False
            if wc and wv != "":
                m = [c for c in cols if c.lower() == wc.lower()]
                if m and wo in OPS:
                    where, wp = f" WHERE {m[0]} {wo} ?", [wv]
                else:
                    bad = True
            ks = list(vals)
            if bad:
                result = info(err="Invalid condition.")
            elif not allowed(user, sel, need):
                result = info(f"-- {need} on {sel} as {user}", err=f"Permission denied: user '{user}' does not have {need} on {sel}. Use the DCL page to GRANT it.")
            elif op == "insert":
                result = run(f"INSERT INTO {sel} ({', '.join(ks)}) VALUES ({', '.join('?' * len(ks))})", [vals[k] for k in ks]) if ks else info(err="Enter at least one value.")
            elif op == "update":
                result = run(f"UPDATE {sel} SET {', '.join(k + ' = ?' for k in ks)}{where}", [vals[k] for k in ks] + wp) if ks and where else info(err="UPDATE needs new values and a condition.")
            elif op == "delete":
                result = run(f"DELETE FROM {sel}{where}", wp) if where else info(err="DELETE needs a condition.")
            else:
                result = run(f"SELECT * FROM {sel}{where}", wp)
    users = [r[0] for r in db().execute("SELECT username FROM app_users ORDER BY username").fetchall()]
    return render_template("dml.html", result=result, tables=user_tables(), selected=sel, ops=OPS, users=users, user=user)


# ------------------------------------------------------------ DCL (simulated GRANT / REVOKE)
@app.route("/dcl", methods=["GET", "POST"])
def dcl():
    result = None
    if request.method == "POST":
        a, u = request.form.get("action"), request.form.get("username", "").strip()
        t, privs = canon(request.form.get("table")), [p for p in request.form.getlist("priv") if p in PRIVS]
        if a == "create":
            pw = request.form.get("password", "")
            if not ok(u) or not pw:
                result = info(err="Enter a valid username and a password.")
            else:
                try:
                    db().execute("INSERT INTO app_users VALUES (?,?)", (u, pw)); db().commit()
                    result = info(f"CREATE USER {u} IDENTIFIED BY '****'", msg=f"User {u} created.")
                except sqlite3.IntegrityError:
                    result = info(err="That user already exists.")
        elif a in ("grant", "revoke"):
            exists = db().execute("SELECT 1 FROM app_users WHERE username=?", (u,)).fetchone()
            if not exists or u == "admin":
                result = info(err="Choose an existing user other than admin.")
            elif not t or not privs:
                result = info(err="Choose a table and at least one privilege.")
            elif a == "grant":
                for p in privs:
                    db().execute("INSERT OR IGNORE INTO app_privileges VALUES (?,?,?)", (u, t.upper(), p))
                db().commit()
                result = info(f"GRANT {', '.join(privs)} ON {t} TO {u}", msg="Privileges granted.")
            else:
                for p in privs:
                    if p == "ALL":
                        db().execute("DELETE FROM app_privileges WHERE username=? AND table_name=?", (u, t.upper()))
                    else:
                        db().execute("DELETE FROM app_privileges WHERE username=? AND table_name=? AND privilege=?", (u, t.upper(), p))
                db().commit()
                result = info(f"REVOKE {', '.join(privs)} ON {t} FROM {u}", msg="Privileges revoked.")
    users = [r[0] for r in db().execute("SELECT username FROM app_users ORDER BY username").fetchall()]
    privs = db().execute("SELECT username, table_name, GROUP_CONCAT(privilege, ', ') AS p FROM app_privileges "
                         "GROUP BY username, table_name ORDER BY username").fetchall()
    return render_template("dcl.html", result=result, users=users, tables=user_tables(), privs=privs, all_privs=PRIVS)


init_db()
if __name__ == "__main__":
    app.run(debug=True)
