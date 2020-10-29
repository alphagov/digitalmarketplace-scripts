#!/usr/bin/env python3
"""
A script to create test suppliers and users for performance testing.
"""
import sys

from dmapiclient import DataAPIClient

sys.path.insert(0, '.')
from dmscripts.helpers.auth_helpers import get_auth_token
from dmutils.env_helpers import get_api_endpoint_from_stage

PASSWORD = 'Password1234'

stage = 'development'
data_api_client = DataAPIClient(get_api_endpoint_from_stage(stage), get_auth_token('api', stage))


def ensure_supplier_exists(data_api_client, duns_number):
    try:
        [supplier] = data_api_client.find_suppliers(duns_number=duns_number)['suppliers']
    except ValueError:
        print(f"Creating user with DUNS {duns_number}")
        data_api_client.create_supplier(
            {'companiesHouseNumber': '12345678',
             'contactInformation': [{'address1': 'Supplier Contact Address 1',
                                     'city': 'Supplier Contact City',
                                     'contactName': 'Supplier Contact',
                                     'email': 'simulate-delivered@notifications.service.gov.uk',
                                     'personalDataRemoved': False,
                                     'phoneNumber': '555123456788',
                                     'postcode': 'AA11 1AA'}],
             'description': 'Test supplier',
             'dunsNumber': str(duns_number),
             'name': 'Test Supplier',
             }
        )
        [supplier] = data_api_client.find_suppliers(duns_number=duns_number)['suppliers']

    data_api_client.update_supplier(
        supplier['id'],
        {
            'companyDetailsConfirmed': True,
            'organisationSize': 'small',
            'otherCompanyRegistrationNumber': 'Test',
            'registeredName': 'Test Supplier LIMITED',
            'registrationCountry': 'country:GB',
            'tradingStatus': 'limited company (LTD)',
            'vatNumber': '123456788'
        },
        user='benjamin.gill'
    )

    return data_api_client.find_suppliers(duns_number=duns_number)['suppliers'][0]


def ensure_user_exists_for_supplier(data_api_client, supplier_id, duns_number):
    email_address = f"supplier{duns_number}@example.com"

    user = data_api_client.get_user(email_address=email_address)
    if user:
        return user['users']

    data_api_client.create_user({
        "emailAddress": email_address,
        "name": "Test",
        "password": PASSWORD,
        'role': 'supplier',
        'phoneNumber': '555123456788',
        'supplierId': supplier_id,
    })
    return data_api_client.get_user(email_address=email_address)['users']


for duns_number in range(123456787, 123456790):
    supplier = ensure_supplier_exists(data_api_client, duns_number)
    user = ensure_user_exists_for_supplier(data_api_client, supplier['id'], duns_number)
    print(f"{user['emailAddress']},{PASSWORD}")
