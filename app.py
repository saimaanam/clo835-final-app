from flask import Flask, render_template, request
import os
import random
import argparse
import boto3
from botocore.exceptions import ClientError, NoCredentialsError  # 👈 added NoCredentialsError
import pymysql  # ✅ import the actual module

app = Flask(__name__)

# ---------- DB CONFIG ----------
DB_CONFIG = {
    # Prefer K8s/ConfigMap values first, then fall back to Docker-style ones, then defaults
    "host": os.environ.get("DBHOST") or os.environ.get("MYSQL_HOST", "mysql"),
    "user": os.environ.get("DBUSER") or os.environ.get("MYSQL_USER", "appuser"),
    "password": os.environ.get("DBPWD") or os.environ.get("MYSQL_PASSWORD", "apppass"),
    "db": os.environ.get("DATABASE") or os.environ.get("MYSQL_DB", "employees"),
    # IMPORTANT: do NOT read MYSQL_PORT (K8s sets it to tcp://10.100.82.145:3306)
    "port": int(os.environ.get("DBPORT", 3306)),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}



def get_connection():
    return pymysql.connect(**DB_CONFIG)


# ---------- S3 BACKGROUND IMAGE (optional) ----------
BG_BUCKET_NAME = os.environ.get("BG_BUCKET_NAME")
# default key (if not set) is "background.jpg", but you can override with env
BG_OBJECT_KEY = os.environ.get("BG_OBJECT_KEY", "background.jpg")
NAME_HEADER = os.environ.get("NAME_HEADER", "Group2- Saima, Edra and Jay")


def download_bg_if_needed():
    """Download background image from S3 to static/background.jpg (best effort)."""
    if not BG_BUCKET_NAME:
        app.logger.info("No BG_BUCKET_NAME set, skipping S3 download")
        return

    static_dir = os.path.join(app.root_path, "static")
    os.makedirs(static_dir, exist_ok=True)
    target_path = os.path.join(static_dir, "background.jpg")

    s3 = boto3.client("s3")
    app.logger.info("Background image URL: s3://%s/%s", BG_BUCKET_NAME, BG_OBJECT_KEY)

    try:
        s3.download_file(BG_BUCKET_NAME, BG_OBJECT_KEY, target_path)
        app.logger.info("Downloaded background to %s", target_path)
    except NoCredentialsError:
        # 👇 new: don't crash the app if there are no AWS creds in the container
        app.logger.warning(
            "No AWS credentials available in container. Skipping S3 background download."
        )
    except ClientError as e:
        app.logger.error("Failed to download background image from S3: %s", e)


# Run once on import so the file is ready before requests hit templates
download_bg_if_needed()


def get_bg_color():
    # fallback color if APP_COLOR / COLOR not set
    return os.environ.get("COLOR") or os.environ.get("APP_COLOR", "lightgrey")


# ---------- ROUTES ----------

@app.route("/")
def home():
    return render_template(
        "addemp.html",
        color=get_bg_color(),
        name_header=NAME_HEADER,
    )


@app.route("/about")
def about():
    return render_template(
        "about.html",
        color=get_bg_color(),
        name=NAME_HEADER,
    )


@app.route("/addemp", methods=["POST"])
def addemp():
    """Insert a new employee into the MySQL table."""
    emp_id = request.form.get("emp_id")
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    primary_skill = request.form.get("primary_skill")
    location = request.form.get("location")

    # Basic sanity check
    if not emp_id or not first_name or not last_name:
        return "Missing required fields (emp_id, first_name, last_name)", 400

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO employee (emp_id, first_name, last_name, primary_skill, location)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (emp_id, first_name, last_name, primary_skill, location),
            )

    full_name = f"{first_name} {last_name}"
    return render_template(
        "addempoutput.html",
        color=get_bg_color(),
        name=full_name,
    )


@app.route("/getemp", methods=["GET"])
def getemp():
    """Show the form to enter an employee ID."""
    return render_template(
        "getemp.html",
        color=get_bg_color(),
    )


@app.route("/fetchdata", methods=["POST"])
def fetchdata():
    """Fetch employee info by ID and display it."""
    emp_id = request.form.get("emp_id")

    if not emp_id:
        return "emp_id not provided", 400

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT emp_id, first_name, last_name, primary_skill, location
                FROM employee
                WHERE emp_id = %s
                """,
                (emp_id,),
            )
            row = cur.fetchone()

    if not row:
        # Employee not found – show a simple "not found" page using the same template
        return render_template(
            "getempoutput.html",
            color=get_bg_color(),
            id=emp_id,
            fname="Not found",
            lname="",
            interest="",
            location="",
        )

    return render_template(
        "getempoutput.html",
        color=get_bg_color(),
        id=row["emp_id"],
        fname=row["first_name"],
        lname=row["last_name"],
        interest=row["primary_skill"],
        location=row["location"],
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81, debug=True)
