from HrJobCrawler import HrJobCrawler
from JobCrawler import JobCrawler

if __name__ == '__main__':
    JobCrawler().main()
    crawlers = [ HrJobCrawler(bank) for bank in ['104', '1111', '518', 'cakeresume'] ]
    for crawler in crawlers:
        crawler.main()
