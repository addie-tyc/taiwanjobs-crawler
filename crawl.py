from JobCrawler import JobCrawler

if __name__ == '__main__':
    for city_num in range(22):
        job_crawler = JobCrawler(city_num)
        job_crawler.main()
