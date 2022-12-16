import json
import os
import re
import requests

import asyncio
from bs4 import BeautifulSoup as bs
from pyppeteer import launch
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem

class JobCrawler():
    def __init__(self, city_num, url='https://job.taiwanjobs.gov.tw/Internet/Index/job_search_list.aspx', START=0, BATCH_SIZE=1000) -> None:
        self.city_num = city_num
        self.url = url
        self.start = START
        self.batch_size = BATCH_SIZE
        self.ckeys = {'ccga', 'ccgas', '__RequestVerificationToken', 'ASP.NET_SessionId'}
        self.loop = asyncio.get_event_loop()
        self.__browser = None
        
        # generate random user-agent
        software_names = [SoftwareName.CHROME.value]
        operating_systems = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]   
        self.user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_systems, limit=100)
    
    # async def get_browser(self):
    #     if not self.__browser:
    #         self.__browser = await launch()
    #     return self.__browser

    # async def close_browser(self):
    #     if self.__browser:
    #         await self.__browser.close()
    #         self.__browser = None
    
    # async def new_page(self, url=None):
    #     browser = self.get_browser()
    #     page = await browser.newPage()
    #     url = url if url else self.url
    #     await page.goto(url)
    #     return page
    
    def get_random_user_agent(self):
        return self.user_agent_rotator.get_random_user_agent()

    def get_districts(self):
        res = requests.get(self.url)
        html = bs(res.text, 'html.parser')
        city_key = fr'UC_Modal-item_{self.city_num}'
        city = html.find('input', {'id': re.compile(city_key)})
        dists_key = fr'{city_key}_\d+'
        dists = html.findAll('input', {'id': re.compile(dists_key)})
        for dist in dists:
            yield {'city_name': city['title'], 'name': dist['title'], 'id': dist['id'], 'value': dist['value']}

    async def get_cookies(self, page, dist):
        print(f'{dist["city_name"]}{dist["name"]} - crawling')
        await page.waitForSelector('#CPH1_btnSearch')
        dist_btn = await page.querySelector(f'#{dist["id"]}')
        if dist_btn: await page.evaluate(f'document.querySelector("#{dist["id"]}").click();')
        await page.click('#CPH1_btnSearch')
        await page.waitForNavigation()
        cookies = await page.cookies()
        cookies = {d['name']: d['value'] for d in cookies if d['name'] in self.ckeys}
        return cookies

    def get_jobs(self, cookies, dist):
        list_url = 'https://job.taiwanjobs.gov.tw/Internet/Index/ajax/job_search_listPage.ashx'
        headers = {
            'Host': 'job.taiwanjobs.gov.tw',
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Content-Length': '2338',
            'Origin': 'https://job.taiwanjobs.gov.tw',
            'Connection': 'keep-alive',
            'Referer': 'https://job.taiwanjobs.gov.tw/Internet/Index/job_search_list.aspx',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        }
        raw_payload = f'startAt={self.start}&pageSize={self.batch_size}&sortField=TRANDATE+desc'
        res = requests.post(list_url, headers=headers, cookies=cookies, data=raw_payload)
        res.raise_for_status()
        data = json.loads(res.text)
        filename = f"data/{dist['city_name']}/{dist['name']}.json"
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w+') as file:
            file.write(json.dumps(data, indent=4, ensure_ascii=False))
        print(f'{dist["city_name"]}{dist["name"]} - saved')

    async def run(self, dist):
        browser = await launch()
        page = await browser.newPage()
        await page.goto(self.url)
        cookies = await self.get_cookies(page, dist)
        self.get_jobs(cookies, dist)
        await browser.close()

    def main(self):
        tasks = [self.loop.create_task(self.run(dist)) for dist in self.get_districts()]
        self.loop.run_until_complete(asyncio.wait(tasks))
