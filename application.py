from flask import Flask, request, Response
import pymysql
import json
import logging
from datetime import datetime, timedelta
import os
from passlib.hash import sha256_crypt
import jwt

application = Flask(__name__)
app = application
logger = logging.getLogger()

jwt_secret = os.environ['JWT_SECRET']
jwt_algo = os.environ['JWT_ALGO']
jwt_exp_delta_sec = float(os.environ['JWT_EXP'])

c_info = {
    "host": os.environ['USER_SERVICE_HOST'],
    "user": os.environ['USER_SERVICE_USER'],
    "password": os.environ['USER_SERVICE_PASSWORD'],
    "port": int(os.environ["USER_SERVICE_PORT"]),
    "cursorclass": pymysql.cursors.DictCursor,
}

user_table_name = "signals.users"
user_fields = ["username", "password", "email", "phone",
               "slack_id", "role", "created_date"]

# Get each field from request
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
    print(inputs)
    return inputs


# Create a sql statement to insert data according to parameters into a table by its table_name
def create_insert_statement(table_name, parameters, data):
    if data is None or len(data) == 0:
        return ""
    sql = """INSERT INTO {} ({}) """.format(table_name, ', '.join(user_fields))
    sql += """ VALUES ("""
    for parameter in parameters:
        # Suppose every parameter is a string
        if parameter != "created_date" and parameter in data:
            if parameter == "password":
                # Encrypt password
                sql += """'{}', """.format(sha256_crypt.hash(data[parameter]))
            else:
                sql += """'{}', """.format(data[parameter])
    # Handle case for created_date
    sql += """'{}')""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return sql


# Create a sql statement to update a row by its id and table_name with data and its parameters
def create_update_by_id_statement(table_name, parameters, data, id):
    if data is None or len(data) == 0:
        return ""
    sql = """UPDATE {} SET """.format(table_name)
    for parameter in parameters:
        if parameter in data:
            if parameter == "password":
                # Encrypt password
                sql += """{} = "{}", """.format(parameter, sha256_crypt.hash(data[parameter]))
            else:
                sql += """{} = "{}", """.format(parameter, data[parameter])
    sql = sql[:-2]
    sql += """ WHERE user_id = {}""".format(id)
    return sql


def create_select_statement(table_name, parameters, data):
    # Select all
    sql = """SELECT * FROM {} """.format(table_name)
    if data is None or len(data) == 0:
        return sql
    sql += "WHERE "
    for parameter in parameters:
        if parameter in data:
            sql += """{} = "{}", """.format(parameter, data[parameter])
    sql = sql[:-2]
    return sql


def create_select_by_id_statement(table_name, id):
    return """SELECT * FROM {} WHERE user_id = {}""".format(table_name, id)


def create_delete_by_id_statement(table_name, id):
    return """DELETE FROM {} WHERE user_id = {}""".format(table_name, id)


def create_select_by_username_statement(table_name, username):
    return """SELECT * FROM {} WHERE username = "{}" """.format(table_name, username)


# Create error response by error message string and its status code
def create_error_res(error_msg, code):
    return Response(json.dumps({"message": error_msg}),
                    status=code, content_type="application/json")


# Create successful response by its json payload and status code
def create_res(json_msg, code):
    return Response(json.dumps(json_msg, default=str),
                    status=code, content_type="application/json")


# Check if there is a duplicate username
def is_duplicate_username(username):
    sql = create_select_by_username_statement(user_table_name, username)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            users = cursor.fetchall()
            if len(users) != 0:
                return False
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            conn.rollback()
            return False
        finally:
            conn.close()
    return True


# Authorization check. If it's for login, go ahead. The other request can only be done by support role
@app.before_request
def authorization():
    inputs = log_and_extract_input()
    # Return None will handle the request to the actual method
    if inputs["path"] == "/api/login":
        return None
    header = inputs["headers"]
    print(header)
    if "Authorization" not in header:
        return create_error_res("Not authenticated", 400)
    jwt_token = header["Authorization"]
    # For bearer token, remove the bearer part
    if jwt_token.startswith("Bearer "):
        jwt_token = jwt_token[7:]
    try:
        payload = jwt.decode(jwt_token, jwt_secret,
                             algorithms=[jwt_algo])
        print(payload)
        if payload["role"] != "support":
            return create_error_res("Permission Denied", 403)
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        return create_error_res("Token is invalid", 401)


# Login endpoint for users. If successful, add their id and role into JWT and send back to client
@app.route('/api/login', methods=['POST'])
def login():
    inputs = log_and_extract_input()
    data = inputs["body"]
    if "username" not in data or "password" not in data:
        return create_error_res("Username or password is empty", 400)
    sql = create_select_by_username_statement(user_table_name, data["username"])
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            users = cursor.fetchall()
            if len(users) == 0:
                return create_error_res("Username does not exist", 400)
            user = users[0]
            if sha256_crypt.verify(data["password"], user["password"]):
                payload = {
                    "user_id": user["user_id"],
                    "role": user["role"],
                    "exp": datetime.utcnow() + timedelta(seconds=jwt_exp_delta_sec)
                }
                jwt_token = jwt.encode(payload, jwt_secret, jwt_algo)
                return create_res({"token": jwt_token.decode('utf-8'),
                                   "message": "Login successfully"}, 200)
            else:
                return create_error_res("Password is incorrect", 400)
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            return create_error_res("Internal Server Error", 500)
        finally:
            conn.close()


# Endpoint to query users, we can pass query string in path
@app.route('/api/users', methods=['GET'])
def query_users():
    inputs = log_and_extract_input()
    data = inputs["query_params"]
    sql = create_select_statement(user_table_name, user_fields, data)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            return create_res({"data": cursor.fetchall(), "message": "Query successfully"}, 200)
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            return create_error_res("Internal Server Error", 500)
        finally:
            conn.close()


# Endpoint to query a user by its id
@app.route('/api/users/<id>', methods=['GET'])
def query_user_by_id(id):
    sql = create_select_by_id_statement(user_table_name, id)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            return create_res({"data": cursor.fetchall(), "message": "Query successfully"}, 200)
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            return create_error_res("Internal Server Error", 500)
        finally:
            conn.close()


# Create a new user and its password is hashed
@app.route('/api/users', methods=['POST'])
def create_user():
    inputs = log_and_extract_input()
    data = inputs["body"]
    contain_none = not all(data.values())
    if contain_none:
        return create_error_res("Contains none value in data", 400)
    if not ("username" in data and is_duplicate_username(data["username"])):
        return create_error_res("Username is duplicate", 400)
    sql = create_insert_statement(user_table_name, user_fields, data)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            conn.commit()
            return create_res({"message": "Create successfully"}, 200)
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            conn.rollback()
            return create_error_res("Internal Server Error", 500)
        finally:
            conn.close()


# Update a existing user by its id. Hash the password if updated
@app.route('/api/users/<id>', methods=['PUT'])
def update_users_by_id(id):
    inputs = log_and_extract_input()
    data = inputs["body"]
    contain_none = not all(data.values())
    if contain_none:
        return create_error_res("Contains none value in data", 400)
    if "username" in data and is_duplicate_username(data["username"]):
        return create_error_res("Username is duplicate", 400)
    sql = create_update_by_id_statement(user_table_name, user_fields, data, id)
    if not sql:
        return create_res({"message": "Nothing to update"}, 200)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            conn.commit()
            return create_res({"message": "Update successfully"}, 200)
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            return create_error_res("Internal Server Error", 500)
        finally:
            conn.close()


# Delete a user by its id
@app.route('/api/users/<id>', methods=['DELETE'])
def delete_users_by_id(id):
    sql = create_delete_by_id_statement(user_table_name, id)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            conn.commit()
            return create_res({"message": "Delete successfully"}, 200)
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            return create_error_res("Internal Server Error", 500)
        finally:
            conn.close()


if __name__ == '__main__':
    application.run(debug=True, port=8080)


