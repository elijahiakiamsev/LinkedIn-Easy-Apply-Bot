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
import ignition
import linkedinapply as LA

from datetime import datetime, timedelta

log = logging.getLogger('mainLogger')
ignition.setupLogger()
class EasyApplyBot:
    # MAX_SEARCH_TIME is 10 hours by default, feel free to modify it
    MAX_SEARCH_TIME = 10 * 60 * 60

    def __init__(self,
                 user_parameters: dict = None,
                 cookies: list = []) -> None:

        log.info("Welcome to Easy Apply Bot!")
        dirpath: str = os.getcwd()
        log.info("Current directory is : " + dirpath)
        log.debug(f"Parameters in bot: {str(user_parameters)}")

        self.user_parameters = user_parameters
        self.uploads = user_parameters['uploads']
        self.filename: str = user_parameters['output_filename']
        past_ids: list | None = self.get_appliedIDs(self.filename)
        self.applied_job_ids: list = past_ids if past_ids != None else []
        self.black_list = user_parameters['black_list_companies']
        self.black_list_titles = user_parameters['black_list_titles']
        self.job_list_filter_keys = user_parameters['job_list_filter_keys']
        self.phone_number = user_parameters['phone_number']

        self.jobs_data = None
        
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
                                    'job_id',
                                    'job', 
                                    'company', 
                                    'attempted',
                                    'result'],
                             lineterminator='\n',
                             encoding='utf-8')
            df['timestamp'] = pd.to_datetime(df['timestamp'], format="%Y-%m-%d %H:%M:%S")
            df = df[df['timestamp'] > (datetime.now() - timedelta(days=2))]
            job_ids: list = list(df.job_id)
            log.debug(f"job_ids from CSV file: {str(job_ids)}")
            log.info(f"{len(job_ids)} job_ids found in {filename}")
            return job_ids
        except Exception as err:
            log.info(f"{str(err)} - job_ids could not be loaded from {filename}")
            return None

    def get_job_filters_uri(self,
                            job_list_filter_keys: dict = None) -> str:
        """Building URI (a part of URL) for filters"""
        job_list_filters_uri: str = ''
        filter_keys_map = {
            "sort by" : ["Most Relevant",
                         "Most Recent"],
            "date posted" : ["Any Time", 
                             "Past Month",
                             "Past Week",
                             "Past 24 hours"],
            "easy apply enabler" : ["Easy Apply",
                                    "Usual Apply"]
            }
        filter_keys_alignment = {
            "Most Relevant" : "R",
            "Most Recent" : "DD",
            "Any Time" : None,
            "Past Week" : "r604800",
            "Past Month" : "r2592000",
            "Past 24 hours" : "r86400",
            "Easy Apply" : "f_AL",
            "Usual Apply" : None
            }
        filter_keys_map_prefix = {
            "sort by" : "sortBy",
            "date posted" : "f_TPR",
            "easy apply enabler" : "f_LF"
            }
        for element in job_list_filter_keys:
            if filter_keys_alignment[element] is not None:
                for key in filter_keys_map_prefix:
                    if element in filter_keys_map[key]:
                        job_list_filters_uri=str(job_list_filters_uri 
                                             + "&" 
                                             + filter_keys_map_prefix[key]
                                             + "="
                                             + filter_keys_alignment[element])
        log.debug(f"URI for filters: {job_list_filters_uri}")
        return job_list_filters_uri

    def apply_to_positions(self, 
                    positions:list,
                    locations:list,
                    job_list_filter_keys:list
                    ) -> None:
        '''Sets starting list for positions/locations combinatons
        and starts application fo each combination in the list.
        '''
        log.info("Start apllying")
        combos: list = None
#        self.browser.set_window_size(1, 1)
#        self.browser.set_window_position(2000, 2000)
        job_filters_uri: str = self.get_job_filters_uri(job_list_filter_keys)
        combos = list(product(positions, locations))
        log.debug(str(combos))
        for combo in combos:
            position, location = list(combo)
            log.info(f"Applying to: {position}, {location}")
            full_job_uri: str = ("keywords="
                               + position
                               + "&location="
                               + location
                               + job_filters_uri)
            log.debug(f"Full Job URI: {full_job_uri}")
            self.get_jobs_data(full_job_uri)
            # Remove already applied jobs
            self.jobs_data = {k: self.jobs_data[k] for k in self.jobs_data.keys() - self.applied_job_ids}
            log.debug(f"jobs_id - {str(self.jobs_data.keys())}")
            self.dump_current_jobs_to_log()
            # Remove blacklisted keywords
            if self.black_list_titles is not None:
                for key in self.jobs_data:
                    if any(word in self.jobs_data[key]['title'] for word in self.black_list_titles):
                        log.info(f"Skipping application {key},"
                                 + " a blacklisted keyword"
                                 + " was found in the job title")
                        self.jobs_data[key]['skipReason'] = "blacklisted keyword"
            # Remove blacklisted companies
            if self.black_list is not None:
                for key in self.jobs_data:
                    if any(word in self.jobs_data[key]['company'] for word in self.black_list):
                        log.info(f"Skipping application {key},"
                                 + f" a blacklisted keyword"
                                 + " was found in the job title")
                        self.jobs_data[key]['skipReason'] = "blacklisted company"
            # go easy apply
            self.easy_apply()
            # sleep for a moment
            sleep_time: int = random.randint(60, 300)
            log.info(f"Time for a nap - see you in:{int(sleep_time/60)} min.")
            time.sleep(sleep_time)
        return None

    def get_jobs_data(self,
                      full_job_uri: str = None) -> None:
        """The loop to collect jobs_id by given URI"""
        log.debug("Collecting jobs URI...")
        start_time: float = time.time()
        self.jobs_data: dict = {}
        jobs_data_delta: dict = {}
#        self.browser.set_window_position(1, 1)
#        self.browser.maximize_window()
        job_search_pages = 3
        for job_search_page in range(1, job_search_pages):
            log.debug(f"job_search_page - {job_search_page}")
            # get a soup for the search page
            soup = self.read_job_search_page(full_job_uri, job_search_page)
            # Break the cycle if no jobs found
            if soup is None:
                log.info(f"No search results for page {job_search_page}, "
                         + "stop collecting jobs for this search combo")
                break
            # rewrite number of pages with the first search result
            if job_search_page == 1:
                pages = soup.select_one('div .artdeco-pagination__page-state')
                if pages is None:
                    job_search_pages = 1
                    log.debug("Only one page for this combo")
                else:
                    log.debug(str(pages))
                    pages_string = pages.string
                    pages_string = pages_string.strip()
                    index = pages_string.rfind(" ")
                    job_search_pages = int(pages_string[index+1:])
                    log.debug(f"For this combo {str(job_search_pages)} "
                              + "pages to take.")
            # get jobs delta
            jobs_data_delta = self.extract_data_from_search(job_search_page, soup)
            if jobs_data_delta is not None:
                self.jobs_data = self.jobs_data | jobs_data_delta
                log.debug(f"Jobs in jobs_data: {len(self.jobs_data)}")
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
        job_blocks = soup.select('div[data-job-id]')
        log.debug(f"job_blocks: {type(job_blocks)} and len = {len(list(job_blocks))}")
        if job_blocks is None:
            log.debug(f"No job cards found on the page {page}")
            return None
        for block in job_blocks:
            job_id: int = int(str(block['data-job-id']))
            # create dictionary for each job with ID as the key
            jd[job_id] = {}
            jd[job_id]['title'] = block.select_one('div' 
                +' .job-card-list__title').get_text().strip()
            jd[job_id]['company'] = block.select_one('div' 
                +' .job-card-container__primary-description').get_text().strip()
            jd[job_id]['metadata'] = block.select_one('li'
                + ' .job-card-container__metadata-item').get_text().strip()
#            jd[job_id]['applyMethod'] = block.select_one('li'
#                + ' .job-card-container__apply-method').get_text().strip()
        log.info(f"{str(len(jd))} jobs collected on page {page}.")
        return jd

    def easy_apply(self) -> None:
        '''Apply to easy apply jobs'''
        log.info("Start easy apply...")
        # Check for data
        if self.jobs_data is None:
            log.warning("No jobs sended to easy apply. Go back.")
            return None
        self.dump_current_jobs_to_log()
        # Extract job_id, ensure of correct apply method
        jobs_id = [k for k in self.jobs_data]
        log.debug(f"{str(jobs_id)} - {type(jobs_id)}")
        # Check for zero list
        if len(jobs_id) == 0:
            log.info("Zero Easy Apply jobs found, skip section.")
            return None
        # Let's loop applications
        self.seeder.setJobIDs(jobs_id)

        for job_id in jobs_id:
            job_applied, sending_text = self.apply_easy_job(job_id)
            self.write_to_file(job_id, sending_text, job_applied)
        return None

    def apply_easy_job(self,
                       job_id : int | None = None,
                       ) -> (bool, str):
        '''Applying one EASY APPLY job'''
        log.info(f"Start applying to {job_id}")
        job_applied: bool = False
        sending_text: str
        if job_id is None:
            job_applied = False
            sending_text = "No job sended to apply"
            log.warning(sending_text)
            log.debug(f"The job_id is {str(job_id)}.")
            return job_applied, sending_text
        self.get_job_page(job_id)
        # get easy apply button
        button, message = self.get_easy_apply_button()
        # if there is something wrong with Easy Apply button
        if button is False:
            sending_text = f"{str(job_id)} : {message}."
            log.warning(sending_text)
            job_applied = False
            return job_applied, sending_text
        # easy apply button exists! click!
        log.info("Clicking the EASY APPLY button...")
        button.click()
        time.sleep(3)
        # fill these pop-up forms and send the answer
        # breaks on error message and on success window
        job_applied, sending_text = self.send_resume()
        if job_applied is False:
            log.info(f"resume for {job_id} is not sended")
            log.info(f"The reason is {sending_text}")
            self.write_parsing_error(job_id)
            log.debug(f"Button cycle is finished")
        return job_applied, sending_text

    def write_parsing_error(self, job_id) -> (bool, str):
        '''Get full information about error in the modal window'''
        dump_dir: str = "./logs/screenshots"
        screenshot_path: str = f"{dump_dir}/{job_id}/error.png"
        html_dump_path: str = f"{dump_dir}/{job_id}/error.html" 
        log.debug(f'Writing error to {dump_dir}...')
        #check directory
        if not os.path.isdir(f'{dump_dir}'):
            os.mkdir(f'{dump_dir}')
        if os.path.isdir(f'{dump_dir}/{job_id}'):
            if os.path.isfile(screenshot_path):
                os.remove(screenshot_path)
            if os.path.isfile(html_dump_path):
                os.remove(html_dump_path)
            os.rmdir(f'{dump_dir}/{job_id}')
        os.mkdir(f'{dump_dir}/{job_id}')
        #write screenshot
        self.browser.get_screenshot_as_file(screenshot_path)
        log.debug(f"Screenshot: {screenshot_path}")
        #get webelement div data-test-modal get_attribute('outerHTML')
        modal_element = self.browser.find_element(By.XPATH, "//div[contains(@class, 'jobs-easy-apply-modal')]")
        html = f'''{modal_element.get_attribute('outerHTML')}'''
        #write to file webelement html
        with open(html_dump_path, "w", encoding="utf-8") as file:
            file.write(html)
            log.debug(f"Html dump: {html_dump_path}")
        return True, 'All ok with error'

    def write_to_file(self,
                      job_id: int,
                      result: bool,
                      title: str = 'Unknown',
                      company: str = 'Unknown',
                      sending_text: str = 'Unknown',
                      filename: str = 'Unknown'
                      ) -> None:
        log.debug(f"Writting result of applying {job_id} to file...")
        timestamp: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if filename == "Unknown": filename = self.filename
        log.debug(f"Saving {filename} : {timestamp}; {result}; {title}; {company}; {sending_text}")
        with open(filename, 'a', encoding="utf-8") as f:
            toWrite: list = [timestamp,
                             job_id,
                             title,
                             company,
                             sending_text,
                             str(result)]
            writer = csv.writer(f)
            writer.writerow(toWrite)
        return None

    def get_job_page(self, job_id: int):
        '''Getting the job page'''
        log.debug(f"Getting {str(job_id)} page...")
        job: str = 'https://www.linkedin.com/jobs/view/' + str(job_id)
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
        locators_blueprint = self.seedEA.set_blueprint(self.seedEA.set_locators())
        submitted: bool = False

        def get_easy_apply_locators(blueprint: dict = locators_blueprint
                                         ) -> (dict | None, str):
            '''Scan an EASY APPLY page for avaiable locators'''
            log.debug('Scanning page for locators...')
            # Create dictionary of possible locators
            lc: dict | None = blueprint
            lc_message: str = ''
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
                lc_message = 'No element is found on the page'
            else:
                log.debug('Locators found:')
                for key in lc:
                    if lc[key]['element'] is not None:
                        log.debug(f"{key} :")
                        log.debug(f"{key} : xpath : {str(lc[key]['xpath'])}")
                        log.debug(f"{key} : action : {str(lc[key]['action'])}")
                        log.debug(f"{key} : element : {str(lc[key]['element'])}")
            return lc, lc_message

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
            pressing_result: bool = True
            pressing_message: str = ''
            # Get active button on page
            for key in locators:
                if locators[key]['action'] == 'nextPage' and locators[key]['element'] is not None:
                    buttonToPress = locators[key]['element']
            # Check for one button (at least)
            button = self.wait.until(EC.element_to_be_clickable(buttonToPress))
            if button:
                button.click()
                pressing_message = (f"Button '{key}' is clicked.")
            else:
                pressing_message = ("Can't press the button")
            log.debug(f"Pressing result: {pressing_result}, {pressing_message}")
            return pressing_result, pressing_message

        log.debug("Starting apply loop...")
        while True:
            locators, message = get_easy_apply_locators()
            # Check to continue (fail fast)
            is_it_good, message = self.seedEA.check_locators(locators)
            if not is_it_good :
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
                self.seedEA.fill_phone_number(locators['phone']['element'],
                                            self.phone_number)
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
        script_scroll_div: str = str("document.querySelector"
                                   + "('.jobs-search-results-list')"
                                   + ".scroll(0, 1000, 'smooth');")
        for p in range(0, 5):
            script_scroll_div: str = str((f"document.querySelector")
                                   + (f"('.jobs-search-results-list')")
                                   + (f".scroll({str(1000*p)}, ")
                                   + (f"{str(1000*(p+1))}, ")
                                   + "'smooth');")
            self.browser.execute_script(script_scroll_div)
            time.sleep(2)
        return None

    def avoid_lock(self) -> None:
        '''Imitate human on page'''
        time.sleep(0.5)
        log.debug("Lock avoided.")
        return None

    def read_job_search_page(self,
                           full_job_uri: str = None,
                           job_page: int = 1) -> bs4.BeautifulSoup | None:
        """Get current search page and save it to soup object
        """
        log.debug("Start reading search page...")
        job_page_uri: str = ''
        # Find page URI
        if job_page != 1:
            job_page_uri = str ("&start="
                              + str((job_page-1)*25))
        self.browser.get("https://www.linkedin.com/jobs/search/?"
                         + full_job_uri
                         + job_page_uri)
        self.avoid_lock()
        # Check 'No jobs found'
        if ('No matching jobs' in self.browser.page_source):
            log.info("No jobs found for this page")
            return None
        self.load_page()
        self.load_job_cards()
        # Get the column with list of jobs
        job_card_div = self.browser.find_element(By.CSS_SELECTOR,
                                               '.jobs-search-results-list')
        html_chunk = job_card_div.get_attribute('innerHTML')
        # Store the column in soup lxml structure
        soup = bs4.BeautifulSoup(html_chunk, "lxml")
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
        if self.jobs_data is None:
            log.warning(f'No jobs to dump into logs for {context}')
            return None
        log.debug(f"*** Jobs right now for {context}")
        for key in self.jobs_data:
            log.debug(f"{key}:{type(self.jobs_data[key])} collected data:")
            for p in self.jobs_data[key]:
                log.debug(f"{p}:{type(self.jobs_data[key][p])} {(self.jobs_data[key][p])}")
        log.debug(f"*** End of jobs for {context}")
        return None

def main() -> None:
    
    user_parameters: dict = None
    login: dict = None
    config_command_string: dict = None
    cookies: list = None
    browser_options = ignition.get_browser_options()

    config_command_string = ignition.parse_command_line_parameters(sys.argv[1:])
    user_parameters, login = ignition.read_configuration(config_command_string['config'])

    cookies = ignition.login_to_linkedin(login,
                                config_command_string['config'],
                                browser_options,
                                config_command_string['forcelogin'])

    if config_command_string['nobot']:
        log.info("Launched with --nobot parameter. Forced exit.")
        exit()

    bot = EasyApplyBot(user_parameters, cookies)

    if config_command_string['fastapply'] is None:
        bot.apply_to_positions(user_parameters['positions'],
                               user_parameters['locations'],
                               user_parameters['job_list_filter_keys'])
    else:
        log.info(f"Fast apply for {config_command_string['fastapply']} requested")
        job_applied, sending_text = bot.apply_easy_job(int(config_command_string['fastapply']))
        bot.write_to_file(config_command_string['fastapply'],
                          job_applied,
                          'Fast Apply Title',
                          'Fast Apply Company',
                          sending_text,
                          user_parameters['output_filename']
                          )
        log.info(f"Forced easy apply cycle for"
                 + f" {config_command_string['fastapply']} finished.")

    bot.shutdown()
    return None

if __name__ == '__main__':
    main()
