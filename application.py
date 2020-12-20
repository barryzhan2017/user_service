from flask import Flask, request, Response, session, url_for, redirect
import json
import logging
import os
from passlib.hash import sha256_crypt
import middlewares.security as security
import middlewares.notification as notification
import database_access.user_access as user_access
import tools.address_verification as address_verification
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
from cryptography.fernet import Fernet

application = Flask(__name__)
catalog_url = os.environ["CATALOG_URL"]
app = application
logger = logging.getLogger()
app.secret_key = os.urandom(24)
oauth = OAuth(app)
secret = os.environ['TOKEN_SECRET'].encode('utf-8')
google = oauth.register(
    name="google",
    client_id=os.environ["OAUTH2_CLIENT_ID"],
    client_secret=os.environ["OAUTH2_CLIENT_SECRET"],
    access_token_url="https://accounts.google.com/o/oauth2/token",
    access_token_params=None,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params=None,
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={"scope": "openid profile email"}
)


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

# # Verify if the token is valid
# @app.route('/api/verify_token', methods=['POST'])
# def verify_token():
#     inputs = log_and_extract_input()
#     res = security.authorize(inputs, {"support", "ip"})
#     return create_res(res[0], res[1])

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
    if not users or len(users) == 0:
        return create_error_res("Username does not exist", 400)
    queried_user = users[0]
    if sha256_crypt.verify(user["password"], queried_user["password"]):
        if queried_user["status"] != "active":
            return create_error_res("User is not activated via email", 400)
        return redirect({"token": security.create_token(queried_user),
                           "message": "Login successfully"}, 200)
    else:
        return create_error_res("Password is incorrect", 400)


# Login endpoint for goolge users. If successful, it will redirect to g_authorize for further user information.
@app.route("/api/g_login", methods=['GET'])
def g_login():
    google = oauth.create_client("google")  # create the google oauth client
    redirect_uri = url_for("g_authorize", _external=True)
    return google.authorize_redirect(redirect_uri)


# Access the user_info and if that email does not exist, we will create a new user based on that email.
@app.route("/api/g_authorize")
def g_authorize():
    google = oauth.create_client("google")  # create the google oauth client
    # Use code passed in query parameter to find token and then use token to get user info
    if "code" not in request.args:
        return create_error_res("Not authorized google user", 400)
    try:
        token = google.authorize_access_token()  # Access token from google (needed to get user info)
    except OAuthError:
        return create_error_res("Invalid google code", 401)
    resp = google.get("userinfo", token=token)  # userinfo contains stuff u specificed in the scrope
    user_info = resp.json()
    email = user_info["email"]
    # If there does not exist a duplicate user with such email, create a new one
    if not user_access.exist_duplicate_user_with_field({"email": email}):
        created_user = user_access.create_user({"username": email, "email": email, "status": "active", "role": "ip"},
                                               ["username", "email", "status", "role", "created_date"])
        if not created_user:
            return create_error_res("Internal Server Error", 500)
    users = user_access.query_users({"email": email})
    # Query the user with that email address
    if not users or len(users) != 1:
        return create_error_res("Internal Server Error", 500)
    user = users[0]
    # Create a token and access the main page by the token
    token = security.create_token(user)
    fernet = Fernet(secret)
    return redirect(catalog_url + "?token=" + fernet.encrypt(token.encode("utf-8")).decode("utf-8"))


# Endpoint to query users, we can pass query string in path
@app.route('/api/users', methods=['GET'])
def query_users():
    inputs = log_and_extract_input()
    user = inputs["query_params"]
    users = user_access.query_users(user)
    if users is None:
        return create_error_res("Internal Server Error", 500)
    else:
        return create_res({"data": users, "message": "Query successfully"}, 200)


# Endpoint to query a user by its id
@app.route('/api/users/<user_id>', methods=['GET'])
def query_user_by_id(user_id):
    user = user_access.query_user_by_id(user_id)
    if user is None:
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
    # Check all the fields are not none
    if not user or not all(user.values()):
        return create_error_res("Invalid data", 400)
    if user_access.exist_duplicate_user_with_field({"username": user["username"]}):
        return create_error_res("Username is duplicate", 400)
    # Check if the address is valid
    if "address" in user and not address_verification.verify(user["address"]):
        return create_error_res("Address is invalid", 400)
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
    if "username" in user and user_access.exist_duplicate_user_with_field({"username": user["username"]}):
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
