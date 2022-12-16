import json
import os
import re
import requests

import asyncio
from bs4 import BeautifulSoup as bs
from pyppeteer import launch
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem

# generate random user-agent
software_names = [SoftwareName.CHROME.value]
operating_systems = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]   
user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_systems, limit=100)

START, BATCH_SIZE = 0, 1000
url = 'https://job.taiwanjobs.gov.tw/Internet/Index/job_search_list.aspx'
ckeys = {'ccga', 'ccgas', '__RequestVerificationToken', 'ASP.NET_SessionId'}

async def get_cookies(page, dist):
    await page.goto(url)
    await page.waitForSelector('#CPH1_btnSearch')
    dist_btn = await page.querySelector(f'#{dist["id"]}')
    if dist_btn: await page.evaluate(f'document.querySelector("#{dist["id"]}").click();')
    await page.click('#CPH1_btnSearch')
    await page.waitForNavigation()
    cookies = await page.cookies()
    cookies = {d['name']: d['value'] for d in cookies if d['name'] in ckeys}
    return cookies

def get_districts():
    res = requests.get(url)
    html = bs(res.text, 'html.parser')
    for num in range(22):
        city_key = fr'UC_Modal-item_{num}'
        city = html.find('input', {'id': re.compile(city_key)})
        dists_key = fr'{city_key}_\d+'
        dists = html.findAll('input', {'id': re.compile(dists_key)})
        for dist in dists:
            yield {'city_name': city['title'], 'name': dist['title'], 'id': dist['id'], 'value': dist['value']}

async def get_jobs(cookies, dist):
    list_url = 'https://job.taiwanjobs.gov.tw/Internet/Index/ajax/job_search_listPage.ashx'
    headers = {
        'Host': 'job.taiwanjobs.gov.tw',
        'User-Agent': user_agent_rotator.get_random_user_agent(),
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
    raw_payload = f'startAt={START}&pageSize={BATCH_SIZE}&sortField=TRANDATE+desc'
    res = requests.post(list_url, headers=headers, cookies=cookies, data=raw_payload)
    res.raise_for_status()
    data = json.loads(res.text)
    filename = f"data/{dist['city_name']}/{dist['name']}.json"
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w+') as file:
        file.write(json.dumps(data, indent=4, ensure_ascii=False))
    print(f'{dist["city_name"]}{dist["name"]} - saved')

async def run(dist):
    browser = await launch(
        # headless=False
        )
    page = await browser.newPage()
    cookies = await get_cookies(page, dist)
    print(f'{dist["city_name"]}{dist["name"]} - crawling')
    await get_jobs(cookies, dist)
    await browser.close()

loop = asyncio.get_event_loop()
tasks = [loop.create_task(run(dist)) for dist in get_districts()]
loop.run_until_complete(asyncio.wait(tasks))
