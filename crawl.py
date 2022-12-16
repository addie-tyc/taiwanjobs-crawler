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

