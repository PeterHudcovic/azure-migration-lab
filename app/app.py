from flask import Flask
import socket
import psycopg2
import os
app = Flask(__name__)

DB_HOST = "migration-postgresql"
DB_NAME = "migrationdb"
DB_USER = "migrationuser"
DB_PASSWORD = os.environ["DB_PASSWORD"]


@app.route("/")
def home():
    return {
        "message": "Azure Migration Lab",
        "hostname": socket.gethostname(),
        "status": "running"
    }


@app.route("/health")
def health():
    return {"status": "healthy"}, 200


@app.route("/db")
def database_test():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

    cur = conn.cursor()
    cur.execute("SELECT id, message FROM test_table;")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return {"rows": rows}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)