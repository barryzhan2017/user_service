import pymysql
import logging
from datetime import datetime
import os
from passlib.hash import sha256_crypt

logger = logging.getLogger()

c_info = {
    "host": os.environ['USER_SERVICE_HOST'],
    "user": os.environ['USER_SERVICE_USER'],
    "password": os.environ['USER_SERVICE_PASSWORD'],
    "port": int(os.environ["USER_SERVICE_PORT"]),
    "cursorclass": pymysql.cursors.DictCursor,
}

user_table_name = "signals.users"
# date should be the last one
user_fields = ["username", "password", "email", "phone",
               "slack_id", "role", "status", "address", "created_date"]
required_user_fields = ["username", "password", "email", "phone",
                        "slack_id", "role", "status", "address"]


# Create a sql statement to insert data according to parameters into a table by its table_name
def create_insert_statement(table_name, parameters, data):
    if data is None or len(data) == 0:
        return ""
    sql = """INSERT INTO {} ({}) """.format(table_name, ', '.join(parameters))
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
            sql += """ {} = "{}" AND """.format(parameter, data[parameter])
    sql = sql[:-4]
    return sql


def create_select_by_id_statement(table_name, id):
    return """SELECT * FROM {} WHERE user_id = {}""".format(table_name, id)


def create_delete_by_id_statement(table_name, id):
    return """DELETE FROM {} WHERE user_id = {}""".format(table_name, id)


# Check if there is a duplicate username
def exist_duplicate_user_with_field(field_dic):
    sql = create_select_statement(user_table_name, user_fields, field_dic)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            users = cursor.fetchall()
            if len(users) != 0:
                return True
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            conn.rollback()
            return True
        finally:
            conn.close()
    return False

# Check if all fields required are in user
def required_field_exist(user):
    for field in required_user_fields:
        if field not in user:
            return False
    return True


# Endpoint to query users from a given user dictionary
def query_users(user):
    sql = create_select_statement(user_table_name, user_fields, user)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            users = cursor.fetchall()
            # If there is no match, return empty dictionary
            if not users:
                return dict()
            return users
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            return None
        finally:
            conn.close()


# Endpoint to query a user by its id
def query_user_by_id(id):
    sql = create_select_by_id_statement(user_table_name, id)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            return cursor.fetchall()
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            return None
        finally:
            conn.close()


# Create a new user and its password is hashed, return the new user with id if created successfully
def create_user(user, parameters=None):
    if parameters is None:
        parameters = user_fields
    sql = create_insert_statement(user_table_name, parameters, user)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            conn.commit()
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            conn.rollback()
            return None
        finally:
            conn.close()
        created_user = query_users({"username": user["username"]})
        if not created_user:
            return None
        else:
            return created_user


# Update a existing user by its id. Hash the password if updated
def update_users_by_id(user, id):
    sql = create_update_by_id_statement(user_table_name, user_fields, user, id)
    # Nothing to update, return originated user
    if not sql:
        updated_user = query_user_by_id(id)
        if not updated_user:
            return None
        else:
            return updated_user
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            conn.commit()
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            return None
        finally:
            conn.close()
        updated_user = query_user_by_id(id)
        if not updated_user:
            return None
        else:
            return updated_user


# Delete a user by its id
def delete_users_by_id(id):
    sql = create_delete_by_id_statement(user_table_name, id)
    conn = pymysql.connect(**c_info)
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
            conn.commit()
            return id
        except (pymysql.Error, pymysql.Warning) as e:
            logger.error(e)
            return None
        finally:
            conn.close()
