ExamHub - Examination Management System (Flask + SQLite)

RUN
  1. Open this folder in VS Code (File > Open Folder; you should see app.py)
  2. Terminal (Ctrl+`):   pip install -r requirements.txt
  3. Terminal:            python app.py
  4. Browser:             http://127.0.0.1:5000
  The database file exam.db is created automatically.

DEMO FLOW
  Dashboard  -> "Load sample data"
  Students / Exams -> add, edit, delete (stored in DB)
  Enter Marks -> input marks, app calculates percentage, grade, Pass/Fail, stores it
  Results / Reports -> filters, rank list, subject statistics, print
  DDL -> create your own table with any columns, alter it, drop it
  DML -> pick any table, insert / update / delete / select
  DCL -> create user, GRANT/REVOKE; then in DML choose "Working as user" and see Permission denied

FILES
  app.py (all routes + SQL), templates/ (pages), static/style.css, static/app.js
