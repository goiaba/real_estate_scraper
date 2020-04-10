#!/bin/python

from datetime import datetime
import concurrent.futures

from . import get_config
from .utils import read_from_disk, write_to_disk, send_email, to_view_date_format
from .scrapers import method_none, method_one, method_two, method_three, method_four, method_five
import logging

logger = logging.getLogger("real_estate_scraper")

method_dispatcher = {
    "none": method_none,
    "one": method_one,
    "two": method_two,
    "three": method_three,
    "four": method_four,
    "five": method_five
}

def get_house_links():
    max_workers = get_config("conf:max_workers", 1)
    house_links = dict()
    total_house_links = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        agencies = { k: v for k, v in get_config("agencies").items() if v.get("enabled", False) }
        futures = { executor.submit(method_dispatcher.get(a_data.get("method", "none")), a_name, a_data): a_name for a_name, a_data in agencies.items() }
        for future in concurrent.futures.as_completed(futures):
            a_name = futures[future]
            try:
                data = future.result()
            except Exception as exc:
                logger.exception("Retrieving house links from %s agency generated an exception", a_name)
            else:
                num_links_returned = len(data)
                if num_links_returned > 0:
                    data.sort()
                    house_links[a_name] = data
                    total_house_links += num_links_returned
                    logger.info("%4i house links returned from %s agency", num_links_returned, a_name)
                else:
                    logger.warning("%4i house links returned from %s agency. It will be ignored during this execution.", num_links_returned, a_name)
        executor.shutdown(wait=True)
    return (total_house_links, house_links)

def log_ignored_agencies(house_links: dict, previous_house_links: dict):
    new_agencies_been_ignored = set(house_links.keys()).difference(set(previous_house_links.keys()))
    for a_name in new_agencies_been_ignored:
        logger.info("'%s' agency is been ignored since it does not exists in the previous agencies list. It will be taken into account in the next execution.", a_name)
    old_agencies_been_ignored = set(previous_house_links.keys()).difference(set(house_links.keys()))
    for a_name in old_agencies_been_ignored:
        logger.info("'%s' agency is been ignored since it does not exists in the current agencies list. It will be taken into account in the next execution.", a_name)

def filter_added_house_links(house_links: dict, previous_house_links: dict) -> set:
    added_house_links = set([])
    agencies = set(house_links.keys()).intersection(set(previous_house_links.keys()))
    for a_name in agencies:
        logger.debug("Adding new '%s' house links to the set.", a_name)
        added_house_links.update(set(house_links.get(a_name)).difference(set(previous_house_links.get(a_name))))
    return added_house_links

def filter_removed_house_links(house_links: dict, previous_house_links: dict) -> set:
    removed_house_links = set([])
    agencies = set(house_links.keys()).intersection(set(previous_house_links.keys()))
    for a_name in agencies:
        logger.debug("Removing '%s' house links from the set.", a_name)
        removed_house_links.update(set(previous_house_links.get(a_name)).difference(house_links.get(a_name)))
    return removed_house_links

if __name__ == "__main__":
    current_check_time = datetime.now()
    logger.info("Real estate scraper execution started at %s", to_view_date_format(current_check_time))
    (total_house_links, current_house_links) = get_house_links()
    (previous_check_time, previous_house_links) = read_from_disk()
    write_to_disk(current_house_links, current_check_time)
    if total_house_links > 0:
        log_ignored_agencies(current_house_links, previous_house_links)
        added_house_links = filter_added_house_links(current_house_links, previous_house_links)
        removed_house_links = filter_removed_house_links(current_house_links, previous_house_links)
        logger.info("Total house links retrieved: %i", total_house_links)
        logger.info("Added house links")
        for l in added_house_links: logger.info(l)
        logger.info("Removed house links")
        for l in removed_house_links: logger.info(l)
        if get_config("conf:email:enabled", False) and (added_house_links or removed_house_links):
            send_email(total_house_links, added_house_links, removed_house_links, previous_check_time, current_check_time)
        end_time = datetime.now()
        spent_time = end_time - current_check_time
        logger.info("Real estate scraper execution ended at %s (%s)", to_view_date_format(end_time), spent_time)
    else:
        logger.warning("No house links retrieved.")
