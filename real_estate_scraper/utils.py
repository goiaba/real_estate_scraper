import glob
import jinja2
import json
import logging
import os
from functools import reduce
from datetime import datetime
from . import get_config
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger("real_estate_scraper")


def to_view_date_format(dt: datetime) -> str:
    return _date_format(dt, get_config("conf:view_date_format"))


def read_from_disk() -> (datetime, dict):
    filename = _get_previous_check_filename()
    if not filename:
        return (None, dict())
    with open(filename, "r") as json_file:
        return (_get_previous_check_time_from_filename(filename),
                json.load(json_file))


def write_to_disk(data: dict, start_time: datetime):
    data_dir = get_config("conf:data_directory", "data")
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)
    filename = "%s/%s" % (data_dir, _get_current_check_filename(start_time))
    with open(filename, "w") as json_file:
        json.dump(data, json_file, indent=4, sort_keys=True)


def send_email(total: int, added: set, removed: set,
               previous_check_time: datetime, current_check_time: datetime):
    if get_config("conf:email:enabled"):
        if not get_config("conf:email:to_emails", None):
            logger.warning("Add emails to \"conf.email.to_emails\" in order to"
                           " send the list by email")
            exit(0)
        context = {
            "added": added,
            "removed": removed,
            "total": total,
            "previous_check_time": to_view_date_format(previous_check_time),
            "current_check_time": to_view_date_format(current_check_time)
        }
        templateLoader = jinja2.FileSystemLoader(
            searchpath="real_estate_scraper/templates")
        templateEnv = jinja2.Environment(loader=templateLoader)
        template = templateEnv.get_template(
            get_config("conf:email:template_name"))
        email_html_message = template.render(context=context)
        message = Mail(from_email=get_config("conf:email:from_email"),
                       to_emails=get_config("conf:email:to_emails"),
                       subject=get_config("conf:email:subject"),
                       html_content=email_html_message)
        try:
            sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
            sg.send(message)
            logger.info("Email with link updates sent to [%s]",
                        ", ".join(get_config("conf:email:to_emails")))
        except Exception:
            logger.exception(
                "An error occured while trying to send the email.")


def _date_format(dt: datetime, format: str) -> str:
    return dt.strftime(format)


def _to_filename_date_format(dt: datetime) -> str:
    return _date_format(dt, get_config("conf:result_filename_date_format"))


def _get_previous_check_time_from_filename(filename: str) -> datetime:
    data_dir = get_config("conf:data_directory", "data")
    fixed_slice_to_remove = "%s/houses_" % data_dir
    str_datetime = filename.replace(fixed_slice_to_remove, "")
    return datetime.strptime(str_datetime,
                             get_config("conf:result_filename_date_format"))


def _get_current_check_filename(start_time: datetime) -> str:
    return "houses_%s" % (_to_filename_date_format(start_time))


def _get_previous_check_filename() -> str:
    data_dir = get_config("conf:data_directory", "data")
    files = glob.glob("%s/*" % data_dir)
    return None if not files else reduce(lambda e, a: e if e > a else a, files)
