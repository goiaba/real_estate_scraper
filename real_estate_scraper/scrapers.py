import json
import logging
import requests
import time
from lxml import etree
from io import StringIO
from urllib.parse import urljoin
from . import get_config

logger = logging.getLogger("real_estate_scraper")


def method_none(a_name, a_data):
    logger.info("No method found to handle request to %s agency.",
                a_name)
    return []


def method_one_four(a_name, a_data, result_map_func):
    headers = get_config("headers")
    base_url = a_data.get("base_url")
    page = a_data.get("start_page")
    result_list_name = a_data.get("result_list_name")
    house_set = set([])
    while True:
        url = "%s/%s=%i" % (base_url, a_data.get("query_str"), page)
        logger.debug("Requesting '%s'" % url)
        response = requests.get(url, headers=headers)
        houses = response.json()
        if not houses.get(result_list_name, None):
            break
        house_set.update(map(result_map_func, houses.get(result_list_name)))
        page += 1
        time.sleep(1)
    return list(house_set)


def method_one(a_name, a_data):
    base_url = a_data.get("base_url")
    return method_one_four(a_name, a_data, lambda e: "%s%s" % (base_url, e.get("url")))


def method_four(a_name, a_data):
    base_url = a_data.get("base_url")
    return method_one_four(
        a_name, a_data, lambda e: "%s/imoveis/%s" % (base_url, e.get("codigo"))
    )


def method_five(a_name, a_data):
    headers = {**get_config("headers"), **a_data.get("headers", {})}
    base_url = a_data.get("base_url")
    page = a_data.get("start_page")
    house_set = set([])
    url = "%s/%s" % (base_url, a_data.get("query_str"))
    while True:
        logger.debug("Requesting '%s' (POST page %i)" % (url, page))
        body = "%s=%i" % (a_data.get("body"), page)
        response = requests.post(url, data=body, headers=headers)
        houses = response.json()
        if not houses.get("lista", None):
            break
        house_set.update(
            map(
                lambda e: "%s/detalhe-imovel/%s" % (base_url, e.get("codigo")),
                houses.get("lista"),
            )
        )
        page += 1
        time.sleep(1)
    return list(house_set)


def method_two(a_name, a_data):
    headers = get_config("headers")
    parser = etree.HTMLParser()
    base_url = a_data.get("base_url")
    prepend_base_url_in_search = a_data.get("prepend_base_url_in_search", False)
    result_search_string = tuple(
        map(str, a_data.get("result_search_string").split(","))
    )
    charset = a_data.get("charset", "utf-8")
    page = a_data.get("start_page")
    pagination = a_data.get("pagination", True)
    page_param_separator = a_data.get("page_param_separator", "=")
    if prepend_base_url_in_search:
        result_search_string = tuple(
            map(lambda e: urljoin(base_url, e), result_search_string)
        )
    house_set = set([])
    while True:
        url = "%s/%s" % (base_url, a_data.get("query_str"))
        if pagination:
            url = "%s%s%i" % (url, page_param_separator, page)
        logger.debug("Requesting '%s'" % url)
        response = requests.get(url, headers=headers)
        html = response.content.decode(charset)
        tree = etree.parse(StringIO(html), parser=parser)
        refs = tree.xpath("//a")
        links = set([])
        for ref in refs:
            link = ref.get("href", "")
            sanitized_link = urljoin(base_url, link)
            if (
                link.startswith(result_search_string)
                and sanitized_link not in house_set
            ):
                links.add(sanitized_link)
        if not links:
            break
        house_set.update(links)
        if not pagination:
            break
        page += 1
        time.sleep(1)
    return list(house_set)


def method_three(a_name, a_data):
    headers = get_config("headers")
    parser = etree.HTMLParser()
    base_url = a_data.get("base_url")
    page = a_data.get("start_page")
    house_set = set([])
    while True:
        url = "%s/%s=%i" % (base_url, a_data.get("query_str"), page)
        logger.debug("Requesting '%s'" % url)
        response = requests.get(url, headers=headers)
        html = response.content.decode("utf-8")
        tree = etree.parse(StringIO(html), parser=parser)
        refs = tree.xpath("//script[@type='application/ld+json']")
        tmp_house_set = set([])
        for ref in refs:
            json_item = json.loads(ref.text)
            if json_item.get("@type") == "RentAction":
                tmp_house_set.add(json_item.get("object").get("url"))
        if not tmp_house_set:
            break
        house_set.update(tmp_house_set)
        page += 1
        time.sleep(1)
    return list(house_set)
