#!/usr/bin/env python
"""Selectively migrate supplier organisation size from a recent framework declaration to the field on supplier itself.

   Based on scripts/oneoff/migrate-supplier-data-from-declarations.py

Usage:
    scripts/oneoff/migrate-supplier-organisation-size-from-declarations.py <stage> <data_api_token>
        [--dry-run]

Positional arguments:
    <stage>                                 API stage to perform operation on
    <data_api_token>                        appropriate API token for <stage>

Optional arguments:
    -h, --help                              show this help message and exit
    --dry-run                               skip update step
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime
import logging
import getpass

from docopt import docopt
from dmapiclient import DataAPIClient, HTTPError

from dmscripts.helpers.logging_helpers import configure_logger
from dmscripts.helpers.logging_helpers import INFO as loglevel_INFO
from dmutils.env_helpers import get_api_endpoint_from_stage


logger = logging.getLogger("script")


def _catch_404_none(func):
    try:
        return func()
    except HTTPError as e:
        if e.status_code == 404:
            return None
        else:
            raise


def _get_supplier_frameworks(data_api_client, supplier_id):
    # Get all supplierFrameworks for this supplier that have a declaration
    try:
        supplier_frameworks = _catch_404_none(
            lambda: data_api_client.get_supplier_frameworks(supplier_id)
        )
    except StopIteration:
        logger.info("Supplier %s: not on any relevant frameworks", supplier_id)
        return None

    # Filter out frameworks that do not have a declaration (i.e. containing the organisationSize) and where there
    # is no `agreementReturnedAt` date (needed for ordering)
    return [
        sfw for sfw in supplier_frameworks.get('frameworkInterest', [])
        if sfw.get('declaration') and sfw.get('agreementReturnedAt')
    ]


def _update_supplier_organisation_size(data_api_client, org_size, supplier_id, dry_run):
    try:
        logger.info("Updating supplier {} with org size {}".format(supplier_id, org_size))
        if not dry_run:
            data_api_client.update_supplier(
                supplier_id,
                {'organisationSize': org_size},
                user=f'{getpass.getuser()} (migrate organisation size script)',
            )
    except HTTPError:
        logger.info("HTTP ERROR UPDATING SUPPLIER {}".format(supplier_id))


if __name__ == '__main__':
    arguments = docopt(__doc__)

    configure_logger({"script": loglevel_INFO})

    client = DataAPIClient(get_api_endpoint_from_stage(arguments['<stage>']), arguments['<data_api_token>'])
    dry_run = bool(arguments.get("--dry-run"))
    updated_suppliers_count = 0
    skipped_suppliers_count = 0
    invalid_size_suppliers_count = invalid_declaration_suppliers_count = 0
    start_time = datetime.utcnow()
    invalid_size_supplier_ids = []
    invalid_declaration_supplier_ids = []
    updated_supplier_ids = []

    for supplier in client.find_suppliers_iter():
        if supplier.get("organisationSize"):
            skipped_suppliers_count += 1
            logger.info("  already done: supplier ID {}".format(supplier["id"]))
            continue

        supplier_frameworks = _get_supplier_frameworks(client, supplier['id'])

        if supplier_frameworks:
            # Get most recent framework declaration
            supplier_framework = sorted(
                supplier_frameworks, key=lambda x: str(x['agreementReturnedAt']), reverse=True
            )[0]

            logger.info(
                "Supplier %s: updating with data from framework %s", supplier["id"], supplier_framework["frameworkSlug"]
            )

            # Get the organisation size
            org_size = supplier_framework.get('declaration', {}).get('organisationSize')
            if org_size in ['micro', 'small', 'medium', 'large']:
                # Update the supplier
                logger.info('  Updating with org size {}'.format(org_size))
                _update_supplier_organisation_size(client, org_size, supplier['id'], dry_run)
                updated_supplier_ids.append(supplier['id'])
                updated_suppliers_count += 1
            else:
                invalid_size_supplier_ids.append(supplier['id'])
                logger.info('  Invalid organisation size "{}"'.format(org_size))
                invalid_size_suppliers_count += 1
        else:
            invalid_declaration_supplier_ids.append(supplier['id'])
            logger.info('No valid framework declarations for supplier {}'.format(supplier['id']))
            invalid_declaration_suppliers_count += 1

    duration = datetime.utcnow() - start_time

    with open('invalid_size_supplier_ids', 'w') as issis:
        for supplier_id in invalid_size_supplier_ids:
            issis.write(str(supplier_id) + '\n')
    with open('invalid_declaration_supplier_ids', 'w') as idsis:
        for supplier_id in invalid_declaration_supplier_ids:
            idsis.write(str(supplier_id) + '\n')
    with open('updated_supplier_ids', 'w') as usis:
        for supplier_id in updated_supplier_ids:
            usis.write(str(supplier_id) + '\n')

    logger.info("*** Updated {} suppliers in {}".format(updated_suppliers_count, str(duration)))
    logger.info("*** Skipped {} suppliers that already have org size info".format(skipped_suppliers_count))
    logger.info("*** Skipped {} suppliers with no valid declaration".format(invalid_declaration_suppliers_count))
    logger.info("*** Skipped {} suppliers with bad org size info".format(invalid_size_suppliers_count))
