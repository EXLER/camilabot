import datetime
import urllib.parse


def url_validator(url: str) -> bool:
    """Validate if a given string is a URL"""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc, result.path])
    except:
        return False


def date_validator(date: str) -> bool:
    """Checks if the given string is in the correct date format and not in past.
       Date format: YYYY-MM-DD HH:MM"""
    try:
        datetime_obj = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M")

        if datetime_obj < datetime.datetime.now():
            return False
        return True
    except ValueError:
        return False
