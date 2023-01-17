from urllib.parse import urlparse

import os
import requests
from bs4 import BeautifulSoup


def download_docs():
    session = requests.Session()
    filenames = []

    url = "https://do.eduhouse.ru/login/index.php"
    r = session.post(url)
    req_body = r.text
    parsed_body = BeautifulSoup(req_body, "html.parser")
    logintoken = parsed_body.find("input", {"name": "logintoken"})['value']
    payload = {"anchor": "", "logintoken": logintoken, "username": os.environ["EDUHOUSE_LOGIN"],
               "password": os.environ["EDUHOUSE_PASSWORD"], "rememberusername": 1}
    auth = session.post(url, data=payload, cookies=r.cookies)

    session_cookies = session.cookies.get_dict()

    soup = BeautifulSoup(auth.text, "html.parser")

    all_links = soup.findAll("a")
    filtred_list = []
    for link in all_links:
        if "Изменения в расписании" in link.text:
            filtred_list.append(link.get("href"))

    for download_link in filtred_list:
        parsed_url = urlparse(download_link)
        filename = os.path.basename(parsed_url.path)
        f = open(f"{filename}", "wb")
        filenames.append(f.name)
        download_file = session.get(download_link, allow_redirects=True, cookies=session_cookies)
        f.write(download_file.content)
        f.close()

    return filenames
