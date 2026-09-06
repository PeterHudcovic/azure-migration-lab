from flask import Flask, request, redirect, render_template_string, jsonify
import socket
import psycopg2
import os

app = Flask(__name__)

DB_HOST = os.getenv("DB_HOST", "migration-postgresql")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "migrationdb")
DB_USER = os.getenv("DB_USER", "migrationuser")
DB_PASSWORD = os.environ["DB_PASSWORD"]


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def initialize_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS migration_events (
            id SERIAL PRIMARY KEY,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


@app.route("/")
def home():
    initialize_database()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, message, created_at
        FROM migration_events
        ORDER BY id DESC
        LIMIT 20;
    """)

    rows = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM migration_events;")
    count = cur.fetchone()[0]

    cur.close()
    conn.close()

    hostname = socket.gethostname()

    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Azure Migration Lab</title>

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: Arial, Helvetica, sans-serif;
            background: #f4f4f4;
            color: #222;
        }

        .topbar {
            background: #ffcc00;
            border-bottom: 7px solid #d40511;
            padding: 24px 40px;
        }

        .topbar h1 {
            margin: 0;
            font-size: 42px;
            font-weight: 900;
            letter-spacing: -1px;
            text-transform: uppercase;
        }

        .topbar .subtitle {
            margin-top: 6px;
            font-size: 18px;
            font-weight: 700;
            color: #d40511;
            text-transform: uppercase;
        }

        .container {
            max-width: 1200px;
            margin: 32px auto;
            padding: 0 24px;
        }

        .description {
            background: white;
            border-left: 8px solid #d40511;
            padding: 22px 26px;
            margin-bottom: 28px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .description h2 {
            margin-top: 0;
            text-transform: uppercase;
        }

        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 28px;
        }

        .card {
            background: white;
            padding: 22px;
            border-top: 5px solid #ffcc00;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .card h3 {
            margin: 0 0 12px 0;
            color: #555;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .big-value {
            font-size: 30px;
            font-weight: 900;
        }

        .healthy {
            color: #138a36;
        }

        .form-box {
            background: #ffcc00;
            padding: 26px;
            margin-bottom: 28px;
            border-bottom: 6px solid #d40511;
        }

        .form-box h2 {
            margin-top: 0;
            text-transform: uppercase;
        }

        .form-row {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }

        input[type="text"] {
            flex: 1;
            min-width: 260px;
            padding: 14px;
            border: 2px solid #222;
            font-size: 16px;
        }

        button {
            background: #d40511;
            color: white;
            border: none;
            padding: 14px 26px;
            font-size: 16px;
            font-weight: 900;
            text-transform: uppercase;
            cursor: pointer;
        }

        button:hover {
            background: #a9000b;
        }

        .history {
            background: white;
            padding: 26px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .history h2 {
            margin-top: 0;
            text-transform: uppercase;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th {
            background: #222;
            color: white;
            text-align: left;
            padding: 12px;
            text-transform: uppercase;
        }

        td {
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }

        tr:nth-child(even) {
            background: #fafafa;
        }

        .architecture {
            margin-top: 28px;
            background: #222;
            color: white;
            padding: 24px;
        }

        .architecture h2 {
            color: #ffcc00;
            text-transform: uppercase;
            margin-top: 0;
        }

        .flow {
            font-family: Consolas, monospace;
            line-height: 1.8;
            font-size: 15px;
            overflow-x: auto;
        }

        .footer {
            margin-top: 30px;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 13px;
        }

        .badge {
            display: inline-block;
            background: #d40511;
            color: white;
            padding: 6px 10px;
            font-weight: bold;
            text-transform: uppercase;
        }
    </style>
</head>

<body>

<div class="topbar">
    <h1>Azure Migration Lab</h1>
    <div class="subtitle">
        Cloud-Native Migration & Deployment Demonstration
    </div>
</div>

<div class="container">

    <div class="description">
        <h2>Project Overview</h2>

        <p>
            This environment demonstrates a production-style migration
            workflow built on Microsoft Azure and Kubernetes.
        </p>

        <p>
            The solution includes Infrastructure as Code, containerized
            workloads, Helm deployments, PostgreSQL persistent storage,
            CI/CD automation, Azure Key Vault, Workload Identity,
            NGINX Ingress and public application delivery.
        </p>

        <p>
            Migration events entered below are stored permanently in
            PostgreSQL and remain available across application Pod restarts.
        </p>
    </div>

    <div class="cards">

        <div class="card">
            <h3>System Status</h3>
            <div class="big-value healthy">HEALTHY</div>
        </div>

        <div class="card">
            <h3>Environment</h3>
            <div class="big-value">PRODUCTION</div>
        </div>

        <div class="card">
            <h3>Stored Events</h3>
            <div class="big-value">{{ count }}</div>
        </div>

        <div class="card">
            <h3>Request Served By</h3>
            <div class="big-value" style="font-size:18px;">
                {{ hostname }}
            </div>
        </div>

    </div>

    <div class="form-box">

        <h2>Add Migration Event</h2>

        <form method="POST" action="/add">

            <div class="form-row">

                <input
                    type="text"
                    name="message"
                    placeholder="Describe deployment or migration event..."
                    required
                >

                <button type="submit">
                    Save Event
                </button>

            </div>

        </form>

    </div>

    <div class="history">

        <h2>Deployment History</h2>

        <table>

            <tr>
                <th>ID</th>
                <th>Migration Event</th>
                <th>Created</th>
            </tr>

            {% for row in rows %}

            <tr>
                <td>{{ row[0] }}</td>
                <td>{{ row[1] }}</td>
                <td>{{ row[2] }}</td>
            </tr>

            {% endfor %}

        </table>

    </div>

    <div class="architecture">

        <h2>Runtime Architecture</h2>

        <div class="flow">
Internet<br>
&nbsp;&nbsp;↓<br>
Public IP (Internet Protocol)<br>
&nbsp;&nbsp;↓<br>
Azure Load Balancer<br>
&nbsp;&nbsp;↓<br>
NGINX Ingress Controller<br>
&nbsp;&nbsp;↓<br>
Kubernetes Service<br>
&nbsp;&nbsp;↓<br>
2 × Flask Application Pods<br>
&nbsp;&nbsp;↓<br>
PostgreSQL StatefulSet<br>
&nbsp;&nbsp;↓<br>
PVC (Persistent Volume Claim)
        </div>

        <br>

        <h2>Secret Management</h2>

        <div class="flow">
Azure Key Vault<br>
&nbsp;&nbsp;↓<br>
Managed Identity<br>
&nbsp;&nbsp;↓<br>
OIDC (OpenID Connect) / Workload Identity<br>
&nbsp;&nbsp;↓<br>
CSI (Container Storage Interface) Secrets Store<br>
&nbsp;&nbsp;↓<br>
Application + PostgreSQL
        </div>

    </div>

    <div class="footer">
        <span class="badge">Azure Migration Lab</span>
        <br><br>
        DevOps portfolio demonstration environment
    </div>

</div>

</body>
</html>
    """,
        hostname=hostname,
        rows=rows,
        count=count
    )


@app.route("/add", methods=["POST"])
def add_event():
    initialize_database()

    message = request.form["message"]

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO migration_events (message) VALUES (%s);",
        (message,)
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect("/")


@app.route("/health")
def health():
    return {
        "status": "healthy",
        "hostname": socket.gethostname()
    }, 200


@app.route("/api/events")
def api_events():
    initialize_database()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, message, created_at
        FROM migration_events
        ORDER BY id DESC;
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify([
        {
            "id": row[0],
            "message": row[1],
            "created_at": row[2]
        }
        for row in rows
    ])


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )