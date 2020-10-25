from flask import Flask, request, Response
import pymysql
import json
import logging
from datetime import datetime
import os
from passlib.hash import sha256_crypt

app = Flask(__name__)

logger = logging.getLogger()
c_info = {
    "host": os.environ['rds_host'],
    "user": os.environ['rds_user'],
    "password": os.environ['rds_password'],
    "cursorclass": pymysql.cursors.DictCursor,
}

user_table_name = "user_service.users"
user_fields = ["username", "password", "email", "phone",
               "slack_id", "role", "created_date"]


def log_and_extract_input(path_params=None):
    path = request.path
    args = dict(request.args)
    headers = dict(request.headers)
    method = request.method

    try:
        if request.data is not None:
            data = request.json
        else:
            data = None
    except Exception as e:
        # This would fail the request in a more real solution.
        logger.error("You sent something but I could not get JSON out of it.")
        data = ""

    inputs = {
        "path": path,
        "method": method,
        "path_params": path_params,
        "query_params": args,
        "headers": headers,
        "body": data
    }

    return inputs


def create_insert_statement(table_name, parameters, data):
    if not parameters:
        return ""
    sql = """Insert Into {} ({}) """.format(table_name, ', '.join(user_fields))
    sql += """ Values ("""
    for parameter in parameters:
        # Suppose every parameter is a string
        if parameter != "created_date" and parameter in data:
            if parameter == "password":
                # Encrypt password
                sql += """'{}', """.format(sha256_crypt.encrypt(data[parameter]))
            else:
                sql += """'{}', """.format(data[parameter])
    # Handle case for created_date
    sql += """'{}')""".format(datetime.now().strftime("%A, %d. %B %Y %I:%M"))
    return sql


def create_update_by_id_statement(table_name, parameters, data, id):
    if not parameters:
        return ""
    sql = """UPDATE {} set """.format(table_name)
    for parameter in parameters:
        if parameter in data:
            if parameter == "password":
                # Encrypt password
                sql += """{} = "{}", """.format(parameter, sha256_crypt.encrypt(data[parameter]))
            else:
                sql += """{} = "{}", """.format(parameter, data[parameter])
    sql = sql[:-2]
    sql += """ where id = {}""".format(id)
    return sql


def create_select_statement(table_name):
    return """SELECT * FROM {} """.format(table_name)


def create_delete_by_id_statement(table_name, id):
    return """DELETE FROM {} where id = {}""".format(table_name, id)


@app.route('/users', methods=['GET'])
def query_users():
    sql = create_select_statement(user_table_name)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            rsp = Response(json.dumps(cursor.fetchall()), status=200, content_type="application/json")
            return rsp
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            rsp = Response("Internal Server Error", status=500, content_type="application/json")
            return rsp
        finally:
            conn.close()


@app.route('/users', methods=['POST'])
def create_user():
    inputs = log_and_extract_input()
    data = inputs["body"]
    sql = create_insert_statement(user_table_name, user_fields, data)
    conn = pymysql.connect(**c_info)
    print(sql)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            conn.commit()
            rsp = Response("Create Successfully", status=200, content_type="application/json")
            return rsp
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            conn.rollback()
            rsp = Response("Internal Server Error", status=500, content_type="application/json")
            return rsp
        finally:
            conn.close()


@app.route('/users/<id>', methods=['PUT'])
def update_users_by_id(id):
    inputs = log_and_extract_input()
    data = inputs["body"]
    sql = create_update_by_id_statement(user_table_name, user_fields, data, id)
    if not sql:
        rsp = Response("Nothing to Update", status=200, content_type="application/json")
        return rsp
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            conn.commit()
            rsp = Response("Successful Update", status=200, content_type="application/json")
            return rsp
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            rsp = Response("Internal Server Error", status=500, content_type="application/json")
            return rsp
        finally:
            conn.close()


@app.route('/users/<id>', methods=['DELETE'])
def delete_users_by_id(id):
    sql = create_delete_by_id_statement(user_table_name, id)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            conn.commit()
            rsp = Response("Successful Delete", status=200, content_type="application/json")
            return rsp
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            rsp = Response("Internal Server Error", status=500, content_type="application/json")
            return rsp
        finally:
            conn.close()


def main():
    app.run(debug=True, threaded=True, host='localhost', port='8000')


if __name__ == "__main__":
    main()
