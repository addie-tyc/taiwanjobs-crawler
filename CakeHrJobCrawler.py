import re
import requests
from bs4 import BeautifulSoup as bs

from HrJobCrawler import HrJobCrawler

class CakeHrJobCrawler(HrJobCrawler):

    def __init__(self, hr_bank='cakeresume', *args, **kwargs):
        super().__init__(hr_bank, *args, **kwargs)

    def get_districts(self):
        res = requests.get(self.url)
        html = bs(res.text, 'html.parser')
        cities = html.findAll('input', {'id': re.compile(r'UC_Modal-item_([0-9]|1[0-9]|2[0-1])$')})
        for city in cities:
            yield {'city_name': city['title'], 'id': city['id'], 'name': ''}
