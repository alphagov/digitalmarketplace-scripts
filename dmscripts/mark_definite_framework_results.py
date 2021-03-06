from collections import Counter
import logging


import jsonschema


def _passes_validation(candidate, schema, logger, schema_name="schema", tablevel=0, loglevel=logging.INFO):
    try:
        jsonschema.validate(candidate, schema)
    except jsonschema.ValidationError as e:
        # extracting multiple errors from a single validation is possible but a bit more involved than i'm willing
        # to go right now
        logger.log(loglevel, "%sFailed %s @ %s: %s", "\t" * tablevel, schema_name, "/".join(e.absolute_path), e.message)
        return False
    else:
        return True


def _assess_draft_services(
    client,
    framework_slug,
    supplier_id,
    logger=logging.getLogger("script"),
):
    # A supplier must have at least 1 submitted service
    counter = Counter()
    for draft_service in client.find_draft_services_by_framework_iter(framework_slug, supplier_id=supplier_id):
        counter[draft_service["status"]] += 1

    logger.info(
        "\tDraft services:  %s submitted, %s not-submitted",
        counter["submitted"],
        counter["not-submitted"],
    )
    return counter


def mark_definite_framework_results(
    client,
    updated_by,
    framework_slug,
    declaration_definite_pass_schema,
    declaration_discretionary_pass_schema=None,
    reassess_passed_suppliers=False,
    reassess_failed_suppliers=False,
    dry_run=True,
    supplier_ids=None,
    logger=logging.getLogger("script"),
    excluded_supplier_ids=None,
):
    interested_supplier_ids = supplier_ids or client.get_interested_suppliers(
        framework_slug
    ).get('interestedSuppliers', ())
    total_interested_suppliers = len(interested_supplier_ids)

    # exclude suppliers with IDs the executioner defined
    if excluded_supplier_ids is not None:
        interested_supplier_ids = list(set(interested_supplier_ids) - set(excluded_supplier_ids))

    # Loop over suppliers breaking out if they pass or fail, if they make it to the end they get a discretionary pass
    for i, supplier_id in enumerate(interested_supplier_ids, start=1):
        logger.info(
            "Supplier {i}/{total_interested_suppliers}: {supplier_id}",
            extra={'i': i, 'supplier_id': supplier_id, 'total_interested_suppliers': total_interested_suppliers}
        )
        supplier_framework = client.get_supplier_framework_info(supplier_id, framework_slug)["frameworkInterest"]

        # Skip suppliers who have already failed?
        if not reassess_failed_suppliers and supplier_framework["onFramework"] is False:
            logger.info("\tSkipping: already failed")
            continue
        # Skip suppliers who have already passed?
        if not reassess_passed_suppliers and supplier_framework["onFramework"] is True:
            logger.info("\tSkipping: already passed")
            continue

        # A supplier must have completed their declaration to pass their application
        if supplier_framework["declaration"].get("status") != "complete":
            fail_supplier(supplier_id, framework_slug, updated_by, supplier_framework, client, logger, dry_run=dry_run)
            continue

        # A supplier should have at least one valid service to pass their application
        service_counter = _assess_draft_services(
            client,
            framework_slug,
            supplier_id,
            logger=logger
        )
        if not service_counter["submitted"]:
            fail_supplier(supplier_id, framework_slug, updated_by, supplier_framework, client, logger, dry_run=dry_run)
            continue

        # Check for a definite pass
        supplier_passes_validation = _passes_validation(
            supplier_framework["declaration"],
            declaration_definite_pass_schema,
            logger,
            schema_name="declaration_definite_pass_schema",
            tablevel=1
        )
        if supplier_passes_validation:
            # Congratulations supplier, you pass!
            pass_supplier(supplier_id, framework_slug, updated_by, supplier_framework, client, logger, dry_run=dry_run)
            continue

        # The supplier didn't pass, but check for, and default to, a discretionary pass
        if declaration_discretionary_pass_schema:
            supplier_passes_discretionary_validation = _passes_validation(
                supplier_framework["declaration"],
                declaration_discretionary_pass_schema,
                logger,
                schema_name="declaration_discretionary_pass_schema",
                tablevel=1,
            )
            if not supplier_passes_discretionary_validation:
                fail_supplier(
                    supplier_id,
                    framework_slug,
                    updated_by,
                    supplier_framework,
                    client,
                    logger,
                    dry_run=dry_run
                )
                continue
        # a result of DISCRETIONARY should pretty much never overwrite an already-made decision
        log_message = "\tResult: DISCRETIONARY%s"
        if supplier_framework["onFramework"] is not None:
            log_message += " (but leaving as {})".format("PASS" if supplier_framework["onFramework"] else "FAIL")
        logger.info(log_message)


def pass_supplier(supplier_id, framework_slug, updated_by, supplier_framework, client, logger, dry_run=True):
    logger.info("\tResult: PASS")
    if not dry_run:
        if supplier_framework["onFramework"] is not True:
            client.set_framework_result(supplier_id, framework_slug, True, updated_by)
        else:
            logger.debug("\tUnchanged result - not re-setting")


def fail_supplier(supplier_id, framework_slug, updated_by, supplier_framework, client, logger, dry_run=True):
    logger.info("\tResult: FAIL")
    if not dry_run:
        if supplier_framework["onFramework"] is not False:
            client.set_framework_result(supplier_id, framework_slug, False, updated_by)
        else:
            logger.debug("\tUnchanged result - not re-setting")
