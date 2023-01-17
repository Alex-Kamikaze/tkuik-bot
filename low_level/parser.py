import os
from itertools import zip_longest

import aspose.words as aw
from bs4 import BeautifulSoup


class SubOrm():
    def __init__(self, group, pair_num, init_pair, sub_pair, cab):
        self.group = group
        self.pair_num = pair_num
        self.init_pair = init_pair
        self.sub_pair = sub_pair
        self.cab = cab


def chunk(lst):
    i_ = iter(lst)
    return list(zip_longest(i_, i_, i_, i_, i_))


def remove_cache():
    os.remove("parsed.html")
    os.remove("parsed.001.png")


def parse(filename: str):
    doc_data = aw.Document(filename)
    parsed_doc = doc_data.save("parsed.html")

    file = open("parsed.html", "r", encoding="utf-8")
    file_raw = file.read()

    file_formated = BeautifulSoup(file_raw, "html.parser")
    file_parsed = BeautifulSoup(file_formated.prettify(), "html.parser")

    all_data = file_parsed.findAll("td")
    del all_data[0:5]

    all_data = [data.text for data in all_data]

    for i in range(0, len(all_data)):
        received_data = all_data[i]
        filtred_data = received_data.rstrip().lstrip()
        all_data[i] = filtred_data

    subs = []

    for substitution in chunk(all_data):
        subs.append(
            SubOrm(group=substitution[0], pair_num=substitution[1], init_pair=substitution[2], sub_pair=substitution[3],
                   cab=substitution[4]))

    os.remove(filename)
    return subs
