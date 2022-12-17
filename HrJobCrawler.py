from JobCrawler import JobCrawler

hr_banks = {'104', '1111', '518', 'cakeresume'}

class HrJobCrawler(JobCrawler):

    def __init__(self, hr_bank, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert hr_bank in hr_banks, f'`hr_bank` must be one of the following: {hr_banks}.'
        self.hr_bank = hr_bank
    
    def get_headers(self):
        headers = {
            'Host': 'job.taiwanjobs.gov.tw',
            'User-Agent': self.get_random_user_agent(),
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Length': '32',
            'Origin': 'https://job.taiwanjobs.gov.tw',
            'Connection': 'keep-alive',
            'Referer': 'https://job.taiwanjobs.gov.tw/Internet/Index/job_search_list.aspx',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        return headers

    async def search(self, page, dist):
        page = await super().search(page, dist)
        hr_id = '#CPH1_btnTabHR'
        await self.js_click(page, hr_id)
        await page.waitForNavigation({'waitUntil': 'networkidle2'})
        hr_bank_id = f'#CPH1_lbtn{self.hr_bank}'
        await self.js_click(page, hr_bank_id)
        await page.waitForNavigation({'waitUntil': 'networkidle2'})
        return page
