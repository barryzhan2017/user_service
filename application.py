from flask import Flask, request, Response, session
import json
import logging
import os
from passlib.hash import sha256_crypt
import middleware.security as security
import middleware.notification as notification
import database_access.user_access as user_access

application = Flask(__name__)
app = application
logger = logging.getLogger()
app.secret_key = os.urandom(24)


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


# Create error response by error message string and its status code
def create_error_res(error_msg, code):
    return Response(json.dumps({"message": error_msg}),
                    status=code, content_type="application/json")


# Create successful response by its json payload and status code
def create_res(json_msg, code):
    return Response(json.dumps(json_msg, default=str),
                    status=code, content_type="application/json")


# Authorization check. If it's for login, go ahead by returning none. The other request can only be done by support role
@app.before_request
def authorization():
    inputs = log_and_extract_input()
    # To enable user registration, the permission opens to any role.
    res = security.authorize(inputs, {"support", "ip"})
    # Pass through while_list without any action
    if not res:
        return None
    # Add authenticated user to session, note we need to have a secret key for app to use session
    if res[1] == 200:
        session["user_id"] = res[0]["user_id"]
        session["role"] = res[0]["role"]
        session["email"] = res[0]["email"]
        return None
    else:
        return create_error_res(res[0], res[1])


# Notify after request
@app.after_request
def notify(response):
    inputs = log_and_extract_input()
    notification.notify(inputs, response)
    return response


# Registration endpoint for users. If successful, send sns to ask for email verification
@app.route('/api/registration', methods=['POST'])
def register():
    return create_user()


# Login endpoint for users. If successful, add their id and role into JWT and send back to client
@app.route('/api/login', methods=['POST'])
def login():
    inputs = log_and_extract_input()
    user = inputs["body"]
    if "username" not in user or "password" not in user:
        return create_error_res("Username or password is empty", 400)
    users = user_access.query_users({"username": user["username"]})
    if not users:
        return create_error_res("Internal Server Error", 500)
    if len(users) == 0:
        return create_error_res("Username does not exist", 400)
    queried_user = users[0]
    if sha256_crypt.verify(user["password"], queried_user["password"]):
        if queried_user["status"] != "active":
            return create_error_res("User is not activated via email", 400)
        return create_res({"token": security.create_token(queried_user),
                           "message": "Login successfully"}, 200)
    else:
        return create_error_res("Password is incorrect", 400)


# Endpoint to query users, we can pass query string in path
@app.route('/api/users', methods=['GET'])
def query_users():
    inputs = log_and_extract_input()
    user = inputs["query_params"]
    users = user_access.query_users(user)
    if not users:
        return create_error_res("Internal Server Error", 500)
    else:
        return create_res({"data": users, "message": "Query successfully"}, 200)


# Endpoint to query a user by its id
@app.route('/api/users/<user_id>', methods=['GET'])
def query_user_by_id(user_id):
    user = user_access.query_user_by_id(user_id)
    if not user:
        return create_error_res("Internal Server Error", 500)
    else:
        return create_res({"data": user, "message": "Query successfully"}, 200)


# Create a new user and its password is hashed
@app.route('/api/users', methods=['POST'])
def create_user():
    inputs = log_and_extract_input()
    user = inputs["body"]
    if not user_access.required_field_exist(user):
        return create_error_res("Some fields are missing", 400)
    if not user or not all(user.values()):
        return create_error_res("Invalid data", 400)
    if "username" in user and user_access.is_duplicate_username(user["username"]):
        return create_error_res("Username is duplicate", 400)
    created_user = user_access.create_user(user)
    if not created_user:
        return create_error_res("Internal Server Error", 500)
    else:
        return create_res({"data": created_user, "message": "Create successfully"}, 201)


# Update a existing user by its id. Hash the password if updated
@app.route('/api/users/<id>', methods=['PUT'])
def update_users_by_id(id):
    inputs = log_and_extract_input()
    user = inputs["body"]
    if not user or not all(user.values()):
        return create_error_res("Invalid data", 400)
    if "username" in user and user_access.is_duplicate_username(user["username"]):
        return create_error_res("Username is duplicate", 400)
    updated_user = user_access.update_users_by_id(user, id)
    if not updated_user:
        return create_error_res("Internal Server Error", 500)
    else:
        return create_res({"data": user, "message": "Update successfully"}, 200)


# Delete a user by its id
@app.route('/api/users/<id>', methods=['DELETE'])
def delete_users_by_id(id):
    user_id = user_access.delete_users_by_id(id)
    if not user_id:
        return create_error_res("Internal Server Error", 500)
    else:
        return create_res({"message": "Delete successfully"}, 200)


if __name__ == '__main__':
    application.run(debug=True, port=8080)
