import time
import json
import os
import re
import requests

import asyncio
from bs4 import BeautifulSoup as bs
from pyppeteer import launch, errors
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem

HOUR = 3600
class JobCrawler():
    def __init__(self, num_sema=10, url='https://job.taiwanjobs.gov.tw/Internet/Index/job_search_list.aspx', START=0, BATCH_SIZE=1000) -> None:
        self.sema = asyncio.Semaphore(value=num_sema)
        self.url = url
        self.start = START
        self.batch_size = BATCH_SIZE
        self.ckeys = {'ccga', 'ccgas', '__RequestVerificationToken', 'ASP.NET_SessionId'}
        self.loop = asyncio.get_event_loop()
        self.__browser = None
        self.hr_bank = '' # overwrite in each hr_bank crawler
        
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
    
    def sink_path(self, dist, extra_prefix):
        prefix = f'data/{extra_prefix}' if extra_prefix else 'data'
        return f'{prefix}/{dist["city_name"]}/{dist["name"]}.json'

    def log(self, dist, message):
        print(f'{dist["city_name"]}{dist["name"]} - {message}')

    def get_random_user_agent(self):
        return self.user_agent_rotator.get_random_user_agent()

    def get_districts(self):
        res = requests.get(self.url)
        html = bs(res.text, 'html.parser')
        for city_num in range(22):
            city_key = fr'UC_Modal-item_{city_num}'
            city = html.find('input', {'id': re.compile(city_key)})
            dists_key = fr'{city_key}_\d+'
            dists = html.findAll('input', {'id': re.compile(dists_key)})
            for dist in dists:
                yield {'city_name': city['title'], 'name': dist['title'], 'id': dist['id'], 'value': dist['value']}

    async def search(self, page, dist):
        self.log(dist, 'crawling')
        await page.waitForSelector('#CPH1_btnSearch')
        dist_btn = await page.querySelector(f'#{dist["id"]}')
        if dist_btn: await page.evaluate(f'document.querySelector("#{dist["id"]}").click();')
        await page.click('#CPH1_btnSearch')
        await page.waitForNavigation({'waitUntil': 'networkidle2'})
        return page

    async def get_cookies(self, page):
        cookies = await page.cookies()
        cookies = {d['name']: d['value'] for d in cookies if d['name'] in self.ckeys}
        return cookies

    # async def retry(self, asyncfn, retries=3):
    #     try:
    #         return await asyncfn
    #     except errors.TimeoutError as e:
    #         if retries <= 0:
    #             raise e
    #         print(f'retry for {asyncfn.__name__}, {retries} times left.')
    #         return await self.retry(asyncfn, retries - 1)
    
    def save_jobs(self, data, dist, extra_prefix):
        filename = self.sink_path(dist, extra_prefix)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w+') as file:
            file.write(json.dumps(data, indent=4, ensure_ascii=False))
        self.log(dist, 'saved')

    async def get_jobs(self, cookies, dist):
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
        if res.text:
            data = json.loads(res.text)
            await self.loop.run_in_executor(None, self.save_jobs, data, dist)
        else:
            self.log(dist, 'no job, skipping')

    def is_cache_fresh(self, dist, extra_prefix='', cache_expiry_seconds=12 * HOUR):
        threshold = time.time() - cache_expiry_seconds
        path = self.sink_path(dist, extra_prefix)
        try:
            mtime = os.path.getmtime(path)
            return mtime > threshold
        except OSError:
            return False

    async def run(self, dist):
        async with self.sema:
            browser = await launch()
            page = await browser.newPage()
            await page.goto(self.url)
            page = await self.search(page, dist)
            cookies = await self.get_cookies(page)
            await browser.close()
            await self.get_jobs(cookies, dist)

    def main(self):
        tasks = []
        for dist in self.get_districts():
            if self.is_cache_fresh(dist, self.hr_bank):
                self.log(dist, 'cache hit, skipping')
                continue
            tasks.append(self.loop.create_task(self.run(dist)))
        self.loop.run_until_complete(asyncio.wait(tasks))
