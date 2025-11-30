from flask import Flask, render_template, request
from pymysql import connections
import os
import random
import argparse
import logging
import boto3
import shutil

app = Flask(__name__)

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Database config from env ----------
DBHOST = os.environ.get("DBHOST", "localhost")
DBUSER = os.environ.get("DBUSER", "root")
DBPWD = os.environ.get("DBPWD", "password")
DATABASE = os.environ.get("DATABASE", "employees")
DBPORT = int(os.environ.get("DBPORT", "3306"))

# ---------- App config from env (will come from ConfigMap later) ----------
COLOR_FROM_ENV = os.environ.get("APP_COLOR", "lime")

# Background image info (from ConfigMap later)
BG_BUCKET_NAME = os.environ.get("BG_BUCKET_NAME")        # e.g. "my-bg-bucket"
BG_OBJECT_KEY = os.environ.get("BG_OBJECT_KEY")          # e.g. "background1.jpg"

# Your name in header (from ConfigMap later)
NAME_HEADER = os.environ.get("NAME_HEADER", "Saima Anam Syed")

# Where we'll store the background image locally
LOCAL_BG_PATH = "static/background.jpg"
TMP_BG_PATH = "/tmp/background.jpg"

# ---------- MySQL connection ----------
db_conn = connections.Connection(
    host=DBHOST,
    port=DBPORT,
    user=DBUSER,
    password=DBPWD,
    db=DATABASE
)

output = {}
table = 'employee'

# ---------- Color codes (still used for styling if needed) ----------
color_codes = {
    "red": "#e74c3c",
    "green": "#16a085",
    "blue": "#89CFF0",
    "blue2": "#30336b",
    "pink": "#f4c2c2",
    "darkblue": "#130f40",
    "lime": "#C1FF9C",
}

SUPPORTED_COLORS = ",".join(color_codes.keys())
COLOR = random.choice(["red", "green", "blue", "blue2", "darkblue", "pink", "lime"])


# ---------- S3 background download ----------
def download_bg_if_needed():
    """
    Download background image from S3 to static/background.jpg
    using BG_BUCKET_NAME and BG_OBJECT_KEY.
    """
    if not BG_BUCKET_NAME or not BG_OBJECT_KEY:
        logger.warning("Background bucket or key not set. Skipping download.")
        return

    logger.info(f"Background image URL: s3://{BG_BUCKET_NAME}/{BG_OBJECT_KEY}")

    try:
        s3 = boto3.client("s3")
        # Download to a temp path first
        s3.download_file(BG_BUCKET_NAME, BG_OBJECT_KEY, TMP_BG_PATH)

        # Ensure 'static' directory exists
        os.makedirs(os.path.dirname(LOCAL_BG_PATH), exist_ok=True)
        shutil.copyfile(TMP_BG_PATH, LOCAL_BG_PATH)

        logger.info(f"Background image downloaded to {LOCAL_BG_PATH}")
    except Exception as e:
        logger.exception("Failed to download background image from S3")


# Call once at startup
download_bg_if_needed()


# ---------- Routes ----------
@app.route("/", methods=['GET', 'POST'])
def home():
    return render_template(
        'addemp.html',
        color=color_codes[COLOR],
        name_header=NAME_HEADER
    )


@app.route("/about", methods=['GET', 'POST'])
def about():
    return render_template(
        'about.html',
        color=color_codes[COLOR],
        name_header=NAME_HEADER
    )


@app.route("/addemp", methods=['POST'])
def AddEmp():
    emp_id = request.form['emp_id']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    primary_skill = request.form['primary_skill']
    location = request.form['location']

    insert_sql = "INSERT INTO employee VALUES (%s, %s, %s, %s, %s)"
    cursor = db_conn.cursor()

    try:
        cursor.execute(insert_sql, (emp_id, first_name, last_name, primary_skill, location))
        db_conn.commit()
        emp_name = first_name + " " + last_name
    finally:
        cursor.close()

    print("all modification done...")
    return render_template(
        'addempoutput.html',
        name=emp_name,
        color=color_codes[COLOR],
        name_header=NAME_HEADER
    )


@app.route("/getemp", methods=['GET', 'POST'])
def GetEmp():
    return render_template(
        "getemp.html",
        color=color_codes[COLOR],
        name_header=NAME_HEADER
    )


@app.route("/fetchdata", methods=['GET', 'POST'])
def FetchData():
    emp_id = request.form['emp_id']

    output = {}
    select_sql = "SELECT emp_id, first_name, last_name, primary_skill, location FROM employee WHERE emp_id=%s"
    cursor = db_conn.cursor()

    try:
        cursor.execute(select_sql, (emp_id))
        result = cursor.fetchone()

        if not result:
            # Simple handling if not found
            return render_template(
                "getempoutput.html",
                id="N/A",
                fname="N/A",
                lname="N/A",
                interest="N/A",
                location="N/A",
                color=color_codes[COLOR],
                name_header=NAME_HEADER
            )

        output["emp_id"] = result[0]
        output["first_name"] = result[1]
        output["last_name"] = result[2]
        output["primary_skills"] = result[3]
        output["location"] = result[4]

    except Exception as e:
        print(e)
    finally:
        cursor.close()

    return render_template(
        "getempoutput.html",
        id=output["emp_id"],
        fname=output["first_name"],
        lname=output["last_name"],
        interest=output["primary_skills"],
        location=output["location"],
        color=color_codes[COLOR],
        name_header=NAME_HEADER
    )


if __name__ == '__main__':
    # Check for Command Line Parameters for color
    parser = argparse.ArgumentParser()
    parser.add_argument('--color', required=False)
    args = parser.parse_args()

    if args.color:
        print("Color from command line argument =" + args.color)
        COLOR = args.color
        if COLOR_FROM_ENV:
            print("A color was set through environment variable -" + COLOR_FROM_ENV + ". However, color from command line argument takes precendence.")
    elif COLOR_FROM_ENV:
        print("No Command line argument. Color from environment variable =" + COLOR_FROM_ENV)
        COLOR = COLOR_FROM_ENV
    else:
        print("No command line argument or environment variable. Picking a Random Color =" + COLOR)

    # Check if input color is a supported one
    if COLOR not in color_codes:
        print("Color not supported. Received '" + COLOR + "' expected one of " + SUPPORTED_COLORS)
        exit(1)

    # IMPORTANT: Listen on port 81 (assignment requirement)
    app.run(host='0.0.0.0', port=81, debug=True)
