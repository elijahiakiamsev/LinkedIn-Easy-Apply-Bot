from __future__ import annotations
import time, random, os, csv, sys
import logging
import datetime
from itertools import product
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import bs4
import pandas as pd
import pyautogui
import ignition
import linkedinapply as LA

import yaml
from datetime import datetime, timedelta

log = logging.getLogger('mainLogger')
ignition.setupLogger()
class EasyApplyBot:
    # MAX_SEARCH_TIME is 10 hours by default, feel free to modify it
    MAX_SEARCH_TIME = 10 * 60 * 60

    def __init__(self,
                 userParameters: dict = None,
                 cookies: list = []) -> None:

        log.info("Welcome to Easy Apply Bot!")
        dirpath: str = os.getcwd()
        log.info("Current directory is : " + dirpath)
        log.debug(f"Parameters in bot: {str(userParameters)}")

        self.userParameters = userParameters
        self.uploads = userParameters['uploads']
        self.filename: str = userParameters['outputFilename']
        past_ids: list | None = self.get_appliedIDs(self.filename)
        self.appliedJobIDs: list = past_ids if past_ids != None else []
        self.blackList = userParameters['blackListCompanies']
        self.blackListTitles = userParameters['blackListTitles']
        self.jobListFilterKeys = userParameters['jobListFilterKeys']
        self.phoneNumber = userParameters['phoneNumber']

        self.jobsData = None
        
        #browser start
        self.options = ignition.get_browser_options()
        self.cookies = cookies
        try:
            self.browser = webdriver.Chrome(service = 
                            ChromeService(ChromeDriverManager().install()),
                            options=self.options)
        except Exception as err:
            log.error(f"Browser is not started: {str(err)}")
            self.browser.close()
            self.browser.exit()
            raise err
        log.debug("Browser loaded.")
        self.browser.get('https://www.linkedin.com/')
        for cookie in self.cookies: self.browser.add_cookie(cookie)
        self.wait = WebDriverWait(self.browser, 30)
        log.debug("Cookies sended.")

        self.seeder = LA.LinkedInSeeder(browser=self.browser)
        self.seedEA = LA.EasyApplySeeder(browser=self.browser)

        return None

    def get_appliedIDs(self,
                       filename: str = None) -> list | None:
        '''Trying to get applied jobs ID from the given csv file'''
        try:
            df = pd.read_csv(filename,
                             header=None,
                             names=['timestamp', 
                                    'jobID',
                                    'job', 
                                    'company', 
                                    'attempted',
                                    'result'],
                             lineterminator='\n',
                             encoding='utf-8')
            df['timestamp'] = pd.to_datetime(df['timestamp'], format="%Y-%m-%d %H:%M:%S")
            df = df[df['timestamp'] > (datetime.now() - timedelta(days=2))]
            jobIDs: list = list(df.jobID)
            log.debug(f"JobIDs from CSV file: {str(jobIDs)}")
            log.info(f"{len(jobIDs)} jobIDs found in {filename}")
            return jobIDs
        except Exception as err:
            log.info(f"{str(err)} - jobIDs could not be loaded from {filename}")
            return None

    def get_job_filters_uri(self,
                            jobListFilterKeys: dict = None) -> str:
        """Building URI (a part of URL) for filters"""
        jobListFiltersURI: str = ''
        filterKeysMap = {
            "sort by" : ["Most Relevant",
                         "Most Recent"],
            "date posted" : ["Any Time", 
                             "Past Month",
                             "Past Week",
                             "Past 24 hours"],
            "easy apply enabler" : ["Easy Apply",
                                    "Usual Apply"]
            }
        filterKeysAlignment = {
            "Most Relevant" : "R",
            "Most Recent" : "DD",
            "Any Time" : None,
            "Past Week" : "r604800",
            "Past Month" : "r2592000",
            "Past 24 hours" : "r86400",
            "Easy Apply" : "f_AL",
            "Usual Apply" : None
            }
        filterKeysMapPrefix = {
            "sort by" : "sortBy",
            "date posted" : "f_TPR",
            "easy apply enabler" : "f_LF"
            }
        for element in jobListFilterKeys:
            if filterKeysAlignment[element] is not None:
                for key in filterKeysMapPrefix:
                    if element in filterKeysMap[key]:
                        jobListFiltersURI=str(jobListFiltersURI 
                                             + "&" 
                                             + filterKeysMapPrefix[key]
                                             + "="
                                             + filterKeysAlignment[element])
        log.debug(f"URI for filters: {jobListFiltersURI}")
        return jobListFiltersURI

    def apply_to_positions(self, 
                    positions:list,
                    locations:list,
                    jobListFilterKeys:list
                    ) -> None:
        '''Sets starting list for positions/locations combinatons
        and starts application fo each combination in the list.
        '''
        log.info("Start apllying")
        combos: list = None
#        self.browser.set_window_size(1, 1)
#        self.browser.set_window_position(2000, 2000)
        jobFiltersURI: str = self.get_job_filters_uri(jobListFilterKeys)
        combos = list(product(positions, locations))
        log.debug(str(combos))
        for combo in combos:
            position, location = list(combo)
            log.info(f"Applying to: {position}, {location}")
            fullJobURI: str = ("keywords="
                               + position
                               + "&location="
                               + location
                               + jobFiltersURI)
            log.debug(f"Full Job URI: {fullJobURI}")
            self.get_jobs_data(fullJobURI)
            # Remove already applied jobs
            self.jobsData = {k: self.jobsData[k] for k in self.jobsData.keys() - self.appliedJobIDs}
            log.debug(f"jobsID - {str(self.jobsData.keys())}")
            self.dump_current_jobs_to_log()
            # Remove blacklisted keywords
            if self.blackListTitles is not None:
                for key in self.jobsData:
                    if any(word in self.jobsData[key]['title'] for word in self.blackListTitles):
                        log.info(f"Skipping application {key},"
                                 + " a blacklisted keyword"
                                 + " was found in the job title")
                        self.jobsData[key]['skipReason'] = "blacklisted keyword"
            # Remove blacklisted companies
            if self.blackList is not None:
                for key in self.jobsData:
                    if any(word in self.jobsData[key]['company'] for word in self.blackList):
                        log.info(f"Skipping application {key},"
                                 + f" a blacklisted keyword"
                                 + " was found in the job title")
                        self.jobsData[key]['skipReason'] = "blacklisted company"
            # go easy apply
            self.easy_apply()
            # sleep for a moment
            sleepTime: int = random.randint(60, 300)
            log.info(f"Time for a nap - see you in:{int(sleepTime/60)} min.")
            time.sleep(sleepTime)
        return None

    def get_jobs_data(self,
                      fullJobURI: str = None) -> None:
        """The loop to collect jobsID by given URI"""
        log.debug("Collecting jobs URI...")
        start_time: float = time.time()
        self.jobsData: dict = {}
        jobsDataDelta: dict = {}
#        self.browser.set_window_position(1, 1)
#        self.browser.maximize_window()
        jobSearchPages = 3
        for jobSearchPage in range(1, jobSearchPages):
            log.debug(f"jobSearchPage - {jobSearchPage}")
            # get a soup for the search page
            soup = self.read_job_search_page(fullJobURI, jobSearchPage)
            # Break the cycle if no jobs found
            if soup is None:
                log.info(f"No search results for page {jobSearchPage}, "
                         + "stop collecting jobs for this search combo")
                break
            # rewrite number of pages with the first search result
            if jobSearchPage == 1:
                pages = soup.select_one('div .artdeco-pagination__page-state')
                if pages is None:
                    jobSearchPages = 1
                    log.debug("Only one page for this combo")
                else:
                    log.debug(str(pages))
                    pagesString = pages.string
                    pagesString = pagesString.strip()
                    index = pagesString.rfind(" ")
                    jobSearchPages = int(pagesString[index+1:])
                    log.debug(f"For this combo {str(jobSearchPages)} "
                              + "pages to take.")
            # get jobs delta
            jobsDataDelta = self.extract_data_from_search(jobSearchPage, soup)
            if jobsDataDelta is not None:
                self.jobsData = self.jobsData | jobsDataDelta
                log.debug(f"Jobs in jobsData: {len(self.jobsData)}")
        log.info(f"{(self.MAX_SEARCH_TIME-(time.time()-start_time)) // 60} minutes left in this search")
        return None

    def extract_data_from_search(self,
                                 page: int,
                                 soup: bs4.BeautifulSoup) -> dict | None:
        '''Deconstruct search page to usable dictionary'''
        log.info(f"Extract search page {page} data...")
        log.debug(f"Soup status: Size={str(sys.getsizeof(soup))}")
        jd: dict = {}  # result delta
        # collect all blocks with a job ID
        jobBlocks = soup.select('div[data-job-id]')
        log.debug(f"JobBlocks: {type(jobBlocks)} and len = {len(list(jobBlocks))}")
        if jobBlocks is None:
            log.debug(f"No job cards found on the page {page}")
            return None
        for block in jobBlocks:
            jobID: int = int(str(block['data-job-id']))
            # create dictionary for each job with ID as the key
            jd[jobID] = {}
            jd[jobID]['title'] = block.select_one('div' 
                +' .job-card-list__title').get_text().strip()
            jd[jobID]['company'] = block.select_one('div' 
                +' .job-card-container__primary-description').get_text().strip()
            jd[jobID]['metadata'] = block.select_one('li'
                + ' .job-card-container__metadata-item').get_text().strip()
#            jd[jobID]['applyMethod'] = block.select_one('li'
#                + ' .job-card-container__apply-method').get_text().strip()
        log.info(f"{str(len(jd))} jobs collected on page {page}.")
        return jd

    def easy_apply(self) -> None:
        '''Apply to easy apply jobs'''
        log.info("Start easy apply...")
        # Check for data
        if self.jobsData is None:
            log.warning("No jobs sended to easy apply. Go back.")
            return None
        self.dump_current_jobs_to_log()
        # Extract JobID, ensure of correct apply method
        jobsID = [k for k in self.jobsData]
        log.debug(f"{str(jobsID)} - {type(jobsID)}")
        # Check for zero list
        if len(jobsID) == 0:
            log.info("Zero Easy Apply jobs found, skip section.")
            return None
        # Let's loop applications
        self.seeder.setJobIDs(jobsID)

        for jobID in jobsID:
            jobApplied, sendingText = self.apply_easy_job(jobID)
            self.write_to_file(jobID, sendingText, jobApplied)
        return None

    def apply_easy_job(self,
                       jobID : int | None = None,
                       ) -> (bool, str):
        '''Applying one EASY APPLY job'''
        log.info(f"Start applying to {jobID}")
        jobApplied: bool = False
        sendingText: str
        if jobID is None:
            jobApplied = False
            sendingText = "No job sended to apply"
            log.warning(sendingText)
            log.debug(f"The jobID is {str(jobID)}.")
            return jobApplied, sendingText
        self.get_job_page(jobID)
        # get easy apply button
        button, message = self.get_easy_apply_button()
        # if there is something wrong with Easy Apply button
        if button is False:
            sendingText = f"{str(jobID)} : {message}."
            log.warning(sendingText)
            jobApplied = False
            return jobApplied, sendingText
        # easy apply button exists! click!
        log.info("Clicking the EASY APPLY button...")
        button.click()
        time.sleep(3)
        # fill these pop-up forms and send the answer
        # breaks on error message and on success window
        jobApplied, sendingText = self.send_resume()
        if jobApplied is False:
            log.info(f"resume for {jobID} is not sended")
            log.info(f"The reason is {sendingText}")
            self.write_parsing_error(jobID)
            log.debug(f"Button cycle is finished")
        return jobApplied, sendingText

    def write_parsing_error(self, jobID) -> (bool, str):
        '''Get full information about error in the modal window'''
        dumpDir: str = "./logs/screenshots"
        screenshotPath: str = f"{dumpDir}/{jobID}/error.png"
        htmlDumpPath: str = f"{dumpDir}/{jobID}/error.html" 
        log.debug(f'Writing error to {dumpDir}...')
        #check directory
        if not os.path.isdir(f'{dumpDir}'):
            os.mkdir(f'{dumpDir}')
        if os.path.isdir(f'{dumpDir}/{jobID}'):
            if os.path.isfile(screenshotPath):
                os.remove(screenshotPath)
            if os.path.isfile(htmlDumpPath):
                os.remove(htmlDumpPath)
            os.rmdir(f'{dumpDir}/{jobID}')
        os.mkdir(f'{dumpDir}/{jobID}')
        #write screenshot
        self.browser.get_screenshot_as_file(screenshotPath)
        log.debug(f"Screenshot: {screenshotPath}")
        #get webelement div data-test-modal get_attribute('outerHTML')
        modalElement = self.browser.find_element(By.XPATH, "//div[contains(@class, 'jobs-easy-apply-modal')]")
        html = f'''{modalElement.get_attribute('outerHTML')}'''
        #write to file webelement html
        with open(htmlDumpPath, "w", encoding="utf-8") as file:
            file.write(html)
            log.debug(f"Html dump: {htmlDumpPath}")
        return True, 'All ok with error'

    def write_to_file(self,
                      jobID: int,
                      result: bool,
                      title: str = 'Unknown',
                      company: str = 'Unknown',
                      sendingText: str = 'Unknown',
                      filename: str = 'Unknown'
                      ) -> None:
        log.debug(f"Writting result of applying {jobID} to file...")
        timestamp: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if filename == "Unknown": filename = self.filename
        log.debug(f"Saving {filename} : {timestamp}; {result}; {title}; {company}; {sendingText}")
        with open(filename, 'a', encoding="utf-8") as f:
            toWrite: list = [timestamp,
                             jobID,
                             title,
                             company,
                             sendingText,
                             str(result)]
            writer = csv.writer(f)
            writer.writerow(toWrite)
        return None

    def get_job_page(self, jobID: int):
        '''Getting the job page'''
        log.debug(f"Getting {str(jobID)} page...")
        job: str = 'https://www.linkedin.com/jobs/view/' + str(jobID)
        self.browser.get(job)
        self.load_page(sleep=0.5)
        return None

    def get_easy_apply_button(self) -> object | None:
        log.debug('Getting EASY APPLY button...')
        button = None
        message = ""
        # get the button
        try:
            button = self.browser.find_element("xpath",
                '//div[contains(@class, "jobs-apply-button--top-card")]//button[contains(@class, "jobs-apply-button")]')
            message = "The button is found"
            log.debug(message)
        except Exception as e:
            button = None
            message = (f"Exception: {e}") 
            log.debug(message)
            return button, message
        # check enabled button
        if button.is_enabled() == False:
            button = None
            message = "The Easy Apply button is not enabled. Perhaps this job is already applied."
        # check displayed
        if button.is_displayed() == False:
            button = None
            message = "The Easy Apply button is not displayed. Perhaps it is not an Easy Apply job."
        return button, message

    def send_resume(self) -> (bool, str):
        '''The sending resume loop'''
        locatorsBlueprint = self.seedEA.setBlueprint(self.seedEA.setLocators())
        submitted: bool = False

        def get_easy_apply_locators(blueprint: dict = locatorsBlueprint
                                         ) -> (dict | None, str):
            '''Scan an EASY APPLY page for avaiable locators'''
            log.debug('Scanning page for locators...')
            # Create dictionary of possible locators
            lc: dict | None = blueprint
            lcMessage: str = ''
            # Get elements and clean data
            for key in lc:
                try:
                    e = self.browser.find_element(By.XPATH, lc[key]['xpath'])
                    lc[key]['element'] = e
                except:
                    lc[key]['element'] = None
            # Check for any valuable data
            if all(lc[key]['element'] == None for key in lc):
                lc = None
                lcMessage = 'No element is found on the page'
            else:
                log.debug('Locators found:')
                for key in lc:
                    if lc[key]['element'] is not None:
                        log.debug(f"{key} :")
                        log.debug(f"{key} : xpath : {str(lc[key]['xpath'])}")
                        log.debug(f"{key} : action : {str(lc[key]['action'])}")
                        log.debug(f"{key} : element : {str(lc[key]['element'])}")
            return lc, lcMessage

        def upload_resume(locators: dict) -> bool:
            '''Upload resume'''
            # Check for data
            if locators['resume'] is None :
                log.debug("No resume locator sended in upload function")
                return False
            log.debug("Resume upload started...")
            input_buttons = self.browser.find_elements(locators['resume'][0],
                                                    locators['resume'][1])
            for input_button in input_buttons:
                parent = input_button.find_element(By.XPATH, "..")
                sibling = parent.find_element(By.XPATH, "preceding-sibling::*[1]")
                grandparent = sibling.find_element(By.XPATH, "..")
                for key in self.uploads.keys():
                    sibling_text = sibling.text
                    gparent_text = grandparent.text
                    if key.lower() in sibling_text.lower() or key in gparent_text.lower():
                        input_button.send_keys(self.uploads[key])
            return False

        def press_next_button(locators: dict) -> bool:
            '''Pressing next, review or submit button'''
            log.debug("Pressing next page button...")
            pressingResult: bool = True
            pressingMessage: str = ''
            # Get active button on page
            for key in locators:
                if locators[key]['action'] == 'nextPage' and locators[key]['element'] is not None:
                    buttonToPress = locators[key]['element']
            # Check for one button (at least)
            button = self.wait.until(EC.element_to_be_clickable(buttonToPress))
            if button:
                button.click()
                pressingMessage = (f"Button '{key}' is clicked.")
            else:
                pressingMessage = ("Can't press the button")
            log.debug(f"Pressing result: {pressingResult}, {pressingMessage}")
            return pressingResult, pressingMessage

        log.debug("Starting apply loop...")
        while True:
            locators, message = get_easy_apply_locators()
            # Check to continue (fail fast)
            isItGood, message = self.seedEA.checkLocators(locators)
            if not isItGood :
                log.debug("Check failed, breaking the loop.")
                break
            # Found final message
            if locators['succsess']['element'] is not None:
                log.info(f"EASY APPLY done.")
                submitted = True
                message = "All good!"
                break
            # Let's fill known forms and upload known files
            time.sleep(random.uniform(1.5, 2.5))
            if locators['phone']['element'] is not None:
                self.seedEA.fillPhoneNumber(locators['phone']['element'],
                                            self.phoneNumber)
# TODO           fill_address(locators)
# TODO           upload_resume(locators)
# TODO           upload_photo(locators)
# TODO           uncheck_follow(locators)
            time.sleep(random.uniform(4.5, 6.5))
            if press_next_button(locators) == False:
                submitted = False
                message = "Can't press any button"
                break
            time.sleep(random.uniform(1.5, 2.5))
        return submitted, message

    def load_page(self, sleep=1):
        log.debug("Load page like a human mode...")
        scroll_page = 0
        while scroll_page < 4000:
            self.browser.execute_script("window.scrollTo(0," + str(scroll_page) + " );")
            scroll_page += 200
            time.sleep(sleep)
        if sleep != 1:
            self.browser.execute_script("window.scrollTo(0,0);")
            time.sleep(sleep * 3)
        return None
    
    def load_job_cards(self) -> None:
        '''Need to scroll jobcards column to load them all'''
        log.debug("Load job cards...")
        scriptScrollDiv: str = str("document.querySelector"
                                   + "('.jobs-search-results-list')"
                                   + ".scroll(0, 1000, 'smooth');")
        for p in range(0, 5):
            scriptScrollDiv: str = str((f"document.querySelector")
                                   + (f"('.jobs-search-results-list')")
                                   + (f".scroll({str(1000*p)}, ")
                                   + (f"{str(1000*(p+1))}, ")
                                   + "'smooth');")
            self.browser.execute_script(scriptScrollDiv)
            time.sleep(2)
        return None

    def avoid_lock(self) -> None:
        '''Imitate human on page'''
        x, _ = pyautogui.position()
        pyautogui.moveTo(x + 200, pyautogui.position().y, duration=1.0)
        pyautogui.moveTo(x, pyautogui.position().y, duration=0.5)
        pyautogui.keyDown('ctrl')
        pyautogui.press('esc')
        pyautogui.keyUp('ctrl')
        time.sleep(0.5)
        pyautogui.press('esc')
        log.debug("Lock avoided.")
        return None

    def read_job_search_page(self,
                           fullJobURI: str = None,
                           jobPage: int = 1) -> bs4.BeautifulSoup | None:
        """Get current search page and save it to soup object
        """
        log.debug("Start reading search page...")
        jobPageURI: str = ''
        # Find page URI
        if jobPage != 1:
            jobPageURI = str ("&start="
                              + str((jobPage-1)*25))
        self.browser.get("https://www.linkedin.com/jobs/search/?"
                         + fullJobURI
                         + jobPageURI)
        self.avoid_lock()
        # Check 'No jobs found'
        if ('No matching jobs' in self.browser.page_source):
            log.info("No jobs found for this page")
            return None
        self.load_page()
        self.load_job_cards()
        # Get the column with list of jobs
        jobCardDiv = self.browser.find_element(By.CSS_SELECTOR,
                                               '.jobs-search-results-list')
        htmlChunk = jobCardDiv.get_attribute('innerHTML')
        # Store the column in soup lxml structure
        soup = bs4.BeautifulSoup(htmlChunk, "lxml")
        if soup is None:
            log.warning(f"Soup is not created.")
            return None
        log.debug(f"Soup is created.")
        # TODO check full jobcard column load
        return soup

    def shutdown(self) -> None:
        self.browser.close()
        self.browser.quit()
        log.debug("Browser is closed.")
        log.info("Bye!")
        return None
    
    def dump_current_jobs_to_log(self,
                                 context: str = 'undefined') -> None:
        '''For test / debug purpose. Dumps current jobs dictionary
        in logs in readable format
        '''
        if self.jobsData is None:
            log.warning(f'No jobs to dump into logs for {context}')
            return None
        log.debug(f"*** Jobs right now for {context}")
        for key in self.jobsData:
            log.debug(f"{key}:{type(self.jobsData[key])} collected data:")
            for p in self.jobsData[key]:
                log.debug(f"{p}:{type(self.jobsData[key][p])} {(self.jobsData[key][p])}")
        log.debug(f"*** End of jobs for {context}")
        return None

def main() -> None:
    
    userParameters: dict = None
    login: dict = None
    configCommandString: dict = None
    cookies: list = None
    browserOptions = ignition.get_browser_options()

    configCommandString = ignition.parse_command_line_parameters(sys.argv[1:])
    userParameters, login = ignition.read_configuration(configCommandString['config'])

    cookies = ignition.login_to_LinkedIn(login,
                                configCommandString['config'],
                                browserOptions,
                                configCommandString['forcelogin'])

    if configCommandString['nobot']:
        log.info("Launched with --nobot parameter. Forced exit.")
        exit()

    bot = EasyApplyBot(userParameters, cookies)

    if configCommandString['fastapply'] is None:
        bot.apply_to_positions(userParameters['positions'],
                               userParameters['locations'],
                               userParameters['jobListFilterKeys'])
    else:
        log.info(f"Fast apply for {configCommandString['fastapply']} requested")
        jobApplied, sendingText = bot.apply_easy_job(int(configCommandString['fastapply']))
        bot.write_to_file(configCommandString['fastapply'],
                          jobApplied,
                          'Fast Apply Title',
                          'Fast Apply Company',
                          sendingText,
                          userParameters['outputFilename']
                          )
        log.info(f"Forced easy apply cycle for"
                 + f" {configCommandString['fastapply']} finished.")

    bot.shutdown()
    return None

if __name__ == '__main__':
    main()
