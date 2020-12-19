import os
from smartystreets_python_sdk import StaticCredentials, exceptions, ClientBuilder
from smartystreets_python_sdk.us_street import Lookup as StreetLookup

auth_id = os.environ['SMARTY_AUTH_ID']
auth_token = os.environ['SMARTY_AUTH_TOKEN']


# Verify the validity of ab address with format [street, city state].
def verify(address):
    print(address)
    credentials = StaticCredentials(auth_id, auth_token)
    client = ClientBuilder(credentials).build_us_street_api_client()
    # Documentation for input fields can be found at:
    # https://smartystreets.com/docs/us-street-api#input-fields
    address_info = address.split(",")
    if len(address_info) != 2:
        return False
    street = address_info[0]
    city_state = address_info[1].strip()
    city_state_splitted = city_state.rsplit(" ", 1)
    if len(city_state_splitted) != 2:
        return False
    city = city_state_splitted[0]
    state = city_state_splitted[1]
    lookup = StreetLookup()
    lookup.street = street
    lookup.city = city
    lookup.state = state
    lookup.match = "invalid"

    try:
        client.send_lookup(lookup)
    except exceptions.SmartyException as err:
        print(err)
        return False

    result = lookup.result
    # Result is not none and there is at least one zipcode for the address
    if not result or not result[0].components.zipcode:
        print("No candidates. This means the address is not valid.")
        return False

    return True
