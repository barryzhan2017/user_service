import jwt
import os
from datetime import datetime, timedelta


white_list = {"/api/login", "/api/registration"}

jwt_secret = os.environ['JWT_SECRET']
jwt_algo = os.environ['JWT_ALGO']
jwt_exp_delta_sec = float(os.environ['JWT_EXP'])


# Authorize the request to check if the token in header corresponds to the one of roles
# For while_list path, return none
# For error, return error message and status code in an array
# For success, return payload which is a map like {"user_id": "123", "role": "ip", "email": "dada@dad.com"}
# and 200 status code
def authorize(inputs, roles):
    if inputs["path"] in white_list:
        return None
    header = inputs["headers"]
    print(header)
    if "Authorization" not in header:
        return ["Not authenticated", 400]
    jwt_token = header["Authorization"]
    # For bearer token, remove the bearer part
    if jwt_token.startswith("Bearer "):
        jwt_token = jwt_token[7:]
    try:
        payload = jwt.decode(jwt_token, jwt_secret,
                             algorithms=[jwt_algo])
        print(payload)
        if payload["role"] not in roles:
            return ["Permission Denied", 403]
    except (jwt.DecodeError, jwt.ExpiredSignatureError):
        return ["Token is invalid", 401]
    return [payload, 200]


# Create token and store user_id, role, email in it
def create_token(user):
    payload = {
        "user_id": user["user_id"],
        "role": user["role"],
        "email": user["email"],
        "exp": datetime.utcnow() + timedelta(seconds=jwt_exp_delta_sec)
    }
    return jwt.encode(payload, jwt_secret, jwt_algo).decode('utf-8')