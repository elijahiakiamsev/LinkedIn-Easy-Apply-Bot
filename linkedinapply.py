from __future__ import annotations
import logging
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.remote import webelement as WE
from selenium.webdriver.support import expected_conditions as EC

log = logging.getLogger('mainLogger')

class LinkedInSeeder:

    def __init__(self,
                 jobIDs: list | None = None,
                 browser: object | None = None) -> None:
        self.jobIDs = jobIDs
        self.browser = browser
        return None
    
    def setJobIDs(self,
                  jobIDs: list[int]) -> None:
        '''Setting JobIDs list'''
        if not isinstance(jobIDs, list):
            raise TypeError("jobIDs should be a list of integers")
        for _ in range(len(jobIDs)):
            if not isinstance(jobIDs[_], int):
                raise TypeError(f"Every JobID should be an integer. "
                                + f"The jobIDs[{_}] = {jobIDs[_]} is not the integer")
        self.jobIDs = jobIDs
        return None
    
    def getJobIDs(self) -> list | None:
        '''Getting jobIDs list'''
        return self.jobIDs

    def applyToJobs(self):
        pass

    def getApplyResults(self):
        pass

    def checkApplyType(self):
        applyType: str | None = None
        return applyType

class EasyApplySeeder:

    def __init__(self,
                 job_id: int | None = None,
                 browser: object | None = None,
                 blueprint: dict | None = None,
                 blueprintFile: str | None = None,
                 job_title: str | None = None,
                 file_resume: str | None = None,
                 file_photo: str | None = None,
                 apply_parameters: dict | None = None,
                 store_errors: bool = False
                 ) -> None:
        self.job_ids = job_id
        self.browser = browser
        self.blueprint = blueprint
        self.blueprintFile = blueprintFile
        self.jobTitle = job_title
        self.fileResume = file_resume
        self.filePhoto = file_photo
        self.applyParameters = apply_parameters
        self.storeErrors = store_errors
        return None
    
    def set_locators(self) -> dict:
        '''setting hardcoded locators for Easy Apply page'''
        # TODO put it into yaml file
        locators: dict = {"next" : {"xpath" : "//button[@aria-label='Continue to next step']",
                                             "action" : "nextPage"},
                "review" : {"xpath" : "//button[@aria-label='Review your application']",
                                             "action" : "nextPage"},
                "submit" : {"xpath" : "//button[@aria-label='Submit application']",
                                             "action" : "nextPage"},
                "error" : {"xpath" : "//div[@data-test-form-element-error-messages]",
                                             "action" : "error"},
                "follow" : {"xpath" : "//label[@for='follow-company-checkbox']",
                                             "action" : "fill"},
                "homeAddress" : {"xpath" : "//h3[contains(text(),'Home address')]",
                                             "action" : "fill"},
                "photo" : {"xpath" : "//span[contains(@class,'t-14') and contains(text(),'Photo')]",
                                             "action" : "fill"},
                "resume" : {"xpath" : "//span[contains(text(),'Be sure to include an updated resume')]",
                                             "action" : "upload"},
                "coverLetter" : {"xpath" : "//label[contains(text(),'Cover letter')]",
                                             "action" : "upload"},
                "succsess" : {"xpath" : "//h2[@id='post-apply-modal']",
                                             "action" : None},
                "phone" : {"xpath" : "//input[contains(@id,'phoneNumber-nationalNumber')]",
                                             "action" : "fill"}
                }
        return locators

    def set_blueprint_from_file(self,
                             filename: str) -> dict:
        blueprint = None
        if not isinstance(filename, str):
            raise TypeError(f"Blueprint should be a string. Now it is {type(blueprint)}")
        '''get blueprint from yaml file'''
        return blueprint

    def set_blueprint(self,
                     blueprint_source: dict | str) -> dict | None:
        blueprint: dict | None = None
        if isinstance(blueprint_source, dict) : blueprint = blueprint_source
        if isinstance(blueprint_source, str) : blueprint = self.setBlueprintFromFile(blueprint_source)
        if not isinstance(blueprint_source, dict) and not isinstance(blueprint_source, str):
            raise TypeError(f"Blueprint source should be a dictionary or a string. Now it is {type(blueprint_source)}")
        return blueprint

    def scanPage(self) -> bool:
        pass

    def check_locators(self,
                      locators: dict) -> (bool, str):
        '''All negative checks to continue in one place'''
        log.debug("Checks to continue started..")
        check_status : bool = True
        check_message : str = "All checks passed."
        # Didn't find anything on the page
        if locators is None :
            check_status = False
            check_message = "No locators found on the page."
            return check_status, check_message
        # Found an Error on page
        if locators['error']['element'] is not None:
            check_status = False
            check_message = f"EASY APPLY skipped by error: {locators['error']['element'].text}"
        # Didn't find any button to continue
        if len({key for key in locators if locators[key]['action'] == 'nextPage'}) == 0:
            check_status = False
            check_message = "EASY APPLY skipped by error: no continue buttons found"
        # Found more than one button to continue
        if len({key for key in locators if locators[key]['action'] == 'nextPage'
                and locators[key]['element'] is not None}) > 1:
            check_status = False
            log.debug(f"Length of buttons dict: {len({key for key in locators if locators[key]['action'] == 'nextPage' and locators[key]['element'] is not None})}")
            check_message = "EASY APPLY skipped by error: more than one button found"
        # All good
        log.debug(f"Check status {str(check_status)} : {check_message}")
        return check_status, check_message

    def start_apply_loop(self) -> bool:
        pass

    def store_results(self) -> dict:
        pass

    def fill_phone_number(self,
                        phone_element: WE.WebElement,
                        phone_number: str) -> bool:
        '''Fill the phone number correctly'''
        log.debug("Sending phone number...")
        if phone_element:
            phone_element.clear()
            phone_element.send_keys(phone_number)
        else:
            log.warning("No phone element sended")
        return True
