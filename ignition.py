from __future__ import annotations
import time, os
import logging
import argparse
import pickle
import datetime
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

import yaml
from datetime import datetime

log = logging.getLogger('mainLogger')

def setupLogger() -> None:
    dt: str = datetime.strftime(datetime.now(), "%m_%d_%y %H_%M_%S ")
    if not os.path.isdir('./logs'):
        os.mkdir('./logs')
    logging.basicConfig(filename=('./logs/' + str(dt) + 'applyJobs.log'),
                        filemode='w',
                        format='%(asctime)s::%(name)s::%(levelname)s::%(message)s',
                        datefmt='./logs/%d-%b-%y %H:%M:%S')
    log.setLevel(logging.DEBUG)
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.DEBUG)
    c_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S')
    c_handler.setFormatter(c_format)
    log.addHandler(c_handler)
    return None

def get_browser_options():
    '''Configure browser to be less scrape-type'''
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-extensions")
    # Disable webdriver flags or you will be easily detectable
    options.add_argument("--disable-blink-features")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return options

def read_configuration(configFile: str = 'config.yaml') -> tuple[dict, dict]:
    """
    Unpack the configuration and check the data format. Username and password
    are separated from other parameters for security reasons. 
    """
    log.debug("Reading configuration...")
    def check_missing_parameters(parametersToCheck: dict = None,
                                 keysToCheck: list = None) -> None:
        """Check and add missing parameters if something wrong
        with a config file
        """
        p = parametersToCheck
        if keysToCheck is None:
            keysToCheck = ['username',
                           'password',
                           'phoneNumber',
                           'positions',
                           'locations',
                           'uploads',
                           'outputFilename',
                           'blackListCompanies',
                           'blackListTitles',
                           'jobListFilterKeys']
        for key in keysToCheck:
            if key not in p:
                p[key] = None
                log.debug(f"Check: added missing parameter {key}")
        
        for key in list(p.keys()):
            if key not in keysToCheck:
               log.warning(f"Check: unknown parameter {key}") 
        return p

    def check_input_data(parametersToCheck: dict = None,
                         keysToCheck: list = None) -> bool:
        """Check the parameters data completion."""
        p = parametersToCheck
        if keysToCheck is None:
            keysToCheck = ['username',
                           'password',
                           'locations',
                           'positions',
                           'phoneNumber']
        for key in keysToCheck:
            try:
                assert key in p
            except AssertionError as err:
                log.exception("Parameter '" 
                              + key
                              + "' is missing")
                raise err
            try:
                assert p[key] is not None
            except AssertionError as err:
                log.exception(f"Parameter '"
                              + key
                              + "' is None")
                raise err
        try:
            assert len(p['positions'])*len(p['locations']) < 500
        except AssertionError as err:
            log.exception("Too many positions and/or locations")
            raise err
        log.debug("Input data checked for completion.")
        return p

    def removeNone(userParameters: dict = None,
                    keysToClean: list = None) -> dict:
        """
        Remove None from some lists in configuration.
        Just to avoid this check later.
        """
        p = userParameters
        if keysToClean is None:
            keysToClean: list = ['positions',
                                 'locations',
                                 'blackListCompanies',
                                 'blackListTitles']
        for key in keysToClean:
            a_list = p[key]
            if a_list is not None:
                a_list = list(set(a_list))
                log.debug("key, a_list: " + key + ", " + str(a_list))
                try:
                    a_list.remove(None)
                    log.debug(f"Removed 'None' from {key}")
                except:
                    log.debug(f"No 'None' in {key}")
            else:
                log.debug(f"The {key} is None, skipped")
            if not a_list:
                a_list = None
                log.debug(f"{key} is empty and None")
            p[key] = a_list
        log.debug(f"Parameters after none_remover: {p}")
        return p

    with open(configFile, 'r') as stream:
        try:
            userParameters: dict = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            log.error(exc)
            raise exc
    
    p = userParameters
    log.debug(f"Parameters dirty: {p.keys()}")
    p = check_input_data(p, None)
    p = check_missing_parameters(p, None)

    if ('uploads') in p and type(p['uploads']) == list:
        raise Exception("Uploads read from the config file appear to be in list format" +
                        " while should be dict. Try removing '-' from line containing" +
                        " filename & path")

    loginInformation={'username' : p['username'],
                      'password' : p['password'],}

    del p['username']
    del p['password']

    log.debug(f"Personal information is separated.")

    p = removeNone(p)
 
    if (('outputFilename' not in p)
        or (p['outputFilename'] is not type(str))):
        p['outputFilename'] = 'output.csv'

    log.debug(f"Cleared parameters: {p}")
    return userParameters, loginInformation

def parse_command_line_parameters(clParameters: list = None) -> dict:
    """Define input parameters for command string.
    Check config file for existing.
    """
    log.info("Checking command prompt parameters...")
    parser = argparse.ArgumentParser(prog="LinkedIn Easy Apply Bot",
                description="Some parameters to start with command line",
                usage="The bot options:",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--config",
                        type=str,
                        default="config.yaml",
                        help="configuration file, YAML formatted")
    parser.add_argument("--forcelogin",
                        action='store_true',
                        help="force login no matter cookies")
    parser.add_argument("--nobot",
                        action='store_true',
                        help="do all setup but not start the bot")
    parser.add_argument("--fastapply",
                        type=str,
                        default=None,
                        help="fast apply the job by id without apply loop")
    args = parser.parse_args(clParameters)
    log.debug(f"Command string parameters: {str(vars(args))}")
    try:
        assert os.path.isfile(args.config)
    except AssertionError as err:
        log.exception(f"Config file {args.config} doesn't exist")
        raise err
    log.debug(f"Config file {args.config} is exist.")
    if args.fastapply is not None:
        log.debug(f"Fast apply for {args.fastapply} requested")
    return vars(args)

def login_to_LinkedIn(login: dict = None,
                      config: str = None,
                      browserOptions = None,
                      forceLogin: bool = 0) -> dict | None:
    """Login to linkedIn and collect cookies
    if cookies aren't exist or expired.
    Otherwise, return stored cookies.
    """
    log.info('Login to LinkedIn...')
    cookiesFileName = config + ".cookies"

    def check_actual_cookies(cookiesFileName: str = None) -> bool:
        '''Define filename for cookies, try to open it
        and check cookies actuality
        '''
        log.debug("Checking cookies...")
        cookies: list = None
        if os.path.exists(cookiesFileName):
            log.debug(f"Found the cookie file {cookiesFileName}, reading...")
            try:
                cookies = pickle.load(open(cookiesFileName, "rb"))
                log.debug(f"Cookies loaded")
            except:
                log.error("Something wrong with the cookie file")
                raise
            loginExpires = [cookie['expiry'] for cookie in cookies
                            if cookie['name'] == 'li_at'][0]
            if datetime.fromtimestamp(loginExpires) <= datetime.today():
                log.warning("Auth cookie expiried, need to login.")
                cookies = None
            else:
                log.info("Auth cookie will expire "
                          + str(datetime.fromtimestamp(loginExpires))
                          + ", no need to login")
        else:
            log.debug(f"The cookie file {cookiesFileName} is not found.")
            cookies = None
        return cookies

    def login_in_browser(FileName: str = None,
                         browserOptions = None,
                         login: dict = None) -> list:
        '''Log in by browser and store cookies into the file,
        return actual cookies.
        '''
        log.info("Logging in.....Please wait :)  ")
        cookies: list = None
        driver = webdriver.Chrome(service =
                                  ChromeService(ChromeDriverManager().install()),
                                  options=browserOptions)
        driver.get("https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin")
        try:
            user_field = driver.find_element("id","username")
            pw_field = driver.find_element("id","password")
            login_button = driver.find_element("xpath",
                        '//*[@id="organic-div"]/form/div[3]/button')
            user_field.send_keys(login['username'])
            user_field.send_keys(Keys.TAB)
            time.sleep(2)
            pw_field.send_keys(login['password'])
            time.sleep(2)
            login_button.click()
            time.sleep(3)
        except TimeoutException as err:
            log.info("TimeoutException! Username/password field"
                     + "or login button not found")
            raise err
        # TODO check login result not by timeout
        cookies = driver.get_cookies()
        pickle.dump(cookies, open(FileName, "wb"))
        driver.close()
        driver.quit()
        return cookies
    
    if (forceLogin and os.path.exists(cookiesFileName)):
        log.info("Force Login - cookies are deleted")
        os.remove(cookiesFileName)
    cookies = check_actual_cookies(cookiesFileName)
    if cookies is None:
        cookies = login_in_browser(cookiesFileName,
                                   browserOptions,
                                   login)
    return cookies