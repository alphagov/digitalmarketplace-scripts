import csv
import sys
import multiprocessing
from multiprocessing.pool import ThreadPool

from dmutils.apiclient import DataAPIClient
from dmutils.apiclient.errors import HTTPError
from dmutils.audit import AuditTypes


def selection_status(client, framework_id):
    def inner_function(user):
        try:
            answer = client.get_selection_answers(user['supplier']['supplierId'], framework_id)
            status = answer['selectionAnswers']['questionAnswers']['status']
        except HTTPError as e:
            if e.status_code == 404:
                status = 'unstarted'
            else:
                status = 'error-{}'.format(e.status_code)
        except KeyError:
            status = 'error-key-error'
        return (status, user)

    return inner_function


def add_selection_status(client, framework_id, users):
    pool = ThreadPool(10)
    callback = selection_status(client, framework_id)
    return pool.imap_unordered(callback, users)


def is_registered_with_framework(client, framework_id):
    def is_of_framework(audit):
        return audit['data'].get('frameworkSlug') == framework_id

    def is_registered(user):
        audits = client.find_audit_events(
            audit_type=AuditTypes.register_framework_interest,
            object_type='suppliers',
            object_id=user['supplier']['supplierId'])
        return any(map(is_of_framework, audits['auditEvents'])), user
    return is_registered


def filter_is_registered_with_framework(client, framework_id, users):
    pool = ThreadPool(10)
    is_registered = is_registered_with_framework(client, framework_id)
    return (user
            for good, user in pool.imap_unordered(is_registered, users)
            if good)


def find_supplier_users(client):
    for user in client.find_users_iter():
        if user['active'] and user['role'] == 'supplier':
            yield user


def list_users(client, output, framework_slug, include_status):
    writer = csv.writer(output, delimiter=',', quotechar='"')
    users = find_supplier_users(client)
    if framework_slug is not None:
        users = filter_is_registered_with_framework(client, framework_slug, users)
    if include_status:
        users = add_selection_status(client, framework_slug, users)
    else:
        users = ((None, user) for user in users)

    for status, user in users:
        row = [] if status is None else [status]
        row += [
            user['emailAddress'],
            user['name'],
            user['supplier']['supplierId'],
            user['supplier']['name']
        ]
        writer.writerow(row)
