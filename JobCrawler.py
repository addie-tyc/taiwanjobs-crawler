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
        self.hr_bank = '' # overwrite in each hr_bank crawler

        
        # generate random user-agent
        software_names = [SoftwareName.CHROME.value]
        operating_systems = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]   
        self.user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_systems, limit=100)
    
    def sink_path(self, dist, extra_prefix):
        prefix = f'data/{extra_prefix}' if extra_prefix else 'data/main'
        if not dist['name']: dist['name'] = '不分區'
        return f'{prefix}/{dist["city_name"]}/{dist["name"]}.json'

    def get_headers(self):
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
        return headers

    def log(self, dist, message):
        print(f'{dist["city_name"]}{dist["name"]} - {message} {self.hr_bank}')

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
    
    async def js_click(self, page, selector):
        btn = await page.querySelector(selector)
        if btn: await page.evaluate(f'document.querySelector("{selector}").click();')

    async def search(self, page, dist):
        self.log(dist, 'crawling')
        await page.waitForSelector('#CPH1_btnSearch')
        await self.js_click(page, f'#{dist["id"]}')
        await page.click('#CPH1_btnSearch')
        await page.waitForNavigation({'waitUntil': 'networkidle2'})
        return page

    async def get_cookies(self, page):
        cookies = await page.cookies()
        cookies = {d['name']: d['value'] for d in cookies if d['name'] in self.ckeys}
        return cookies
    
    def save_jobs(self, data, dist, extra_prefix):
        filename = self.sink_path(dist, extra_prefix)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w+') as file:
            file.write(json.dumps(data, indent=4, ensure_ascii=False))
        self.log(dist, 'saved')

    def save_bookmark(self, dist, extra_prefix):
        filename = 'over1000jobs.csv'
        with open(filename, 'a+') as file:
            hr_bank = extra_prefix if extra_prefix else 'main'
            file.write(f'{hr_bank},{dist["city_name"]},{dist["name"]}\n')

    async def get_jobs(self, cookies, dist):
        list_url = 'https://job.taiwanjobs.gov.tw/Internet/Index/ajax/job_search_listPage.ashx'
        raw_payload = f'startAt={self.start}&pageSize={self.batch_size}&sortField='
        res = requests.post(list_url, headers=self.get_headers(), cookies=cookies, data=raw_payload)
        res.raise_for_status()
        if res.text:
            data = json.loads(res.text)
            if len(data) >= 1000:
                await self.loop.run_in_executor(None, self.save_bookmark, dist, self.hr_bank)
            await self.loop.run_in_executor(None, self.save_jobs, data, dist, self.hr_bank)

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
