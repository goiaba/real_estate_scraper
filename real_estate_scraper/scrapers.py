import json
import logging
import requests
import time
from io import StringIO
from lxml import etree
from urllib.parse import urljoin
from . import get_config
from .utils import replace_props_in_string

logger = logging.getLogger("real_estate_scraper")
requests.packages.urllib3.disable_warnings()


def method_none(a_name, a_data) -> list:
    logger.warning("No method found to handle request to %s agency.", a_name)
    return []


def method_one(a_name, a_data) -> list:
    return _json_response(
        a_data,
        lambda e: "%s%s" % (a_data.get("base_url"), e.get("url")))


def method_two(a_name, a_data):
    def link_retriever_func(a_data, ref, house_set) -> str:
        base_url = a_data.get("base_url")
        result_search_string = a_data.get("result_search_string", None)
        if result_search_string:
            result_search_string = tuple(result_search_string.split(","))
        prepend_base_url_in_search = a_data.get(
            "prepend_base_url_in_search", False)
        if prepend_base_url_in_search:
            result_search_string = tuple(
                map(lambda e: urljoin(base_url, e), result_search_string))
        link = ref.get("href", "")
        sanitized_link = urljoin(base_url, link)
        if link.startswith(result_search_string) and sanitized_link not in house_set:
            return sanitized_link
        return ""
    return _html_response(a_data, link_retriever_func)


def method_three(a_name, a_data):
    def link_retriever_func(a_data, ref, house_set) -> str:
        json_item = json.loads(ref.text)
        if json_item.get("@type") == "RentAction":
            return json_item.get("object").get("url")
        return ""
    return _html_response(a_data, link_retriever_func)


def method_four(a_name, a_data) -> list:
    return _json_response(
        a_data,
        lambda e: "%s/imoveis/%s" % (a_data.get("base_url"), e.get("codigo")))


def method_five(a_name, a_data) -> list:
    return _json_response(
        a_data,
        lambda e: "%s/detalhe-imovel/%s" % (a_data.get("base_url"), e.get("codigo")),
        "POST")


def _html_response(a_data, link_retriever_func) -> list:
    house_set = set([])
    headers = {**get_config("headers"), **a_data.get("headers", {})}
    base_url = a_data.get("base_url")
    page = a_data.get("start_page")
    link_xpath = a_data.get("link_xpath", "//a")
    parser = etree.HTMLParser()
    charset = a_data.get("charset", "utf-8")
    pagination = a_data.get("pagination", True)

    a_data["query_str"] = replace_props_in_string(
        a_data.get("query_str"), **get_config("conf:search_filter"))

    while True:
        url = "%s/%s" % (base_url, a_data.get("query_str"))
        url = replace_props_in_string(url, page=page)
        logger.debug("Requesting '%s' (GET)" % url)
        response = requests.get(url, headers=headers, verify=False)
        html = response.content.decode(charset)
        tree = etree.parse(StringIO(html), parser=parser)
        refs = tree.xpath(link_xpath)
        links = set([])
        for ref in refs:
            link = link_retriever_func(a_data, ref, house_set)
            if link:
                links.add(link)
        if not links:
            break
        house_set.update(links)
        if not pagination:
            break
        page += 1
        time.sleep(1)
    return list(house_set)


def _json_response(a_data, result_map_func, http_method="GET") -> list:
    house_set = set([])
    headers = {**get_config("headers"), **a_data.get("headers", {})}
    base_url = a_data.get("base_url")
    page = a_data.get("start_page")
    result_list_name = a_data.get("result_list_name")

    a_data["query_str"] = replace_props_in_string(
        a_data.get("query_str"), **get_config("conf:search_filter"))

    while True:
        url = "%s/%s" % (base_url, a_data.get("query_str"))
        if http_method == "GET":
            logger.debug("Requesting '%s' (GET)" % url)
            url = replace_props_in_string(url, page=page)
            response = requests.get(url, headers=headers)
        elif http_method == "POST":
            logger.debug("Requesting '%s' (POST page %i)" % (url, page))
            body = replace_props_in_string(a_data.get("body"), page=page,
                                           **get_config("conf:search_filter"))
            response = requests.post(url, data=body, headers=headers)
        else:
            raise Exception("Invalid httpd method.")
        houses = response.json()
        if not houses.get(result_list_name, None):
            break
        house_set.update(map(result_map_func, houses.get(result_list_name)))
        page += 1
        time.sleep(1)
    return list(house_set)
