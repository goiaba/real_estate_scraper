import glob
import jinja2
import json
import logging
import os
from functools import reduce
from datetime import datetime
from . import get_config, path_from_root_project_dir
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger("real_estate_scraper")


def to_view_date_format(dt: datetime) -> str:
    return _date_format(dt, get_config("conf:view_date_format"))


def read_from_disk(city_id: str) -> (datetime, dict):
    filename = _get_previous_check_filename(city_id)
    if not filename:
        return None, dict()
    with open(filename, "r") as json_file:
        return (_get_previous_check_time_from_filename(filename, city_id),
                json.load(json_file))


def write_to_disk(data: dict, start_time: datetime, city_id: str):
    data_dir = os.path.join(get_config("conf:data_directory", "data"), city_id)
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)
    filename = os.path.join(data_dir, _get_current_check_filename(start_time, city_id))
    with open(filename, "w") as json_file:
        json.dump(data, json_file, indent=4, sort_keys=True, ensure_ascii=False)


def send_email(name: str, total: int, added: list, removed: list,
               previous_check_time: datetime, current_check_time: datetime):
    if get_config("conf:email:enabled", False) and (added or removed):
        from_email = get_config("conf:email:from_email", None)
        to_emails = get_config("conf:email:to_emails", [])
        subject = get_config('conf:email:subject', None)
        template_name = get_config("conf:email:template_name", None)

        if from_email and to_emails and subject and template_name:
            context = {
                "added": added,
                "removed": removed,
                "total": total,
                "previous_check_time": to_view_date_format(previous_check_time),
                "current_check_time": to_view_date_format(current_check_time)
            }
            template_loader = jinja2.FileSystemLoader(
                searchpath=path_from_root_project_dir("templates"))
            template_env = jinja2.Environment(loader=template_loader)
            template = template_env.get_template(template_name)
            email_html_message = template.render(context=context)
            message = Mail(from_email=from_email,
                           to_emails=to_emails,
                           subject=f"{subject} ({name})",
                           html_content=email_html_message)
            try:
                sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
                if sendgrid_api_key:
                    sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
                    sg.send(message)
                    logger.info("Email with link updates sent to [%s]",
                                ", ".join(to_emails))
                else:
                    logger.warning("Sendgrid is not configured."
                                   " No 'SENDGRID_API_KEY' envvar found.")
            except Exception:
                logger.exception(
                    "An error occurred while trying to send the email.")
        else:
            logger.warning("Email not sent. Check 'conf.email' configuration.")


def replace_props_in_string(string, **props):
    for k, v in props.items():
        string = string.replace('${%s}' % k, str(v))
    return string


def _date_format(dt: datetime, fmt: str) -> str:
    return dt.strftime(fmt)


def _to_filename_date_format(dt: datetime) -> str:
    return _date_format(dt, get_config("conf:result_filename_date_format"))


def _get_previous_check_time_from_filename(filename: str, city_id: str) -> datetime:
    data_dir = os.path.join(get_config("conf:data_directory", "data"), city_id)
    fixed_slice_to_remove = os.path.join(data_dir, f"houses_")
    str_datetime = filename.replace(fixed_slice_to_remove, "")
    return datetime.strptime(str_datetime,
                             get_config("conf:result_filename_date_format"))


def _get_current_check_filename(start_time: datetime, city_id: str) -> str:
    return f"houses_{_to_filename_date_format(start_time)}"


def _get_previous_check_filename(city_id: str) -> str:
    data_dir = os.path.join(get_config("conf:data_directory", "data"), city_id)
    files = glob.glob(os.path.join(data_dir, "*"))
    return None if not files else reduce(lambda e, a: e if e > a else a, files)
