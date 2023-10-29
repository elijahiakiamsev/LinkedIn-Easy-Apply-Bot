from __future__ import annotations
import time, random, os, csv, sys
import logging
import argparse
import pickle
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
import yaml
from datetime import datetime

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
                 jobID: int | None = None,
                 browser: object | None = None,
                 blueprint: dict | None = None,
                 blueprintFile: str | None = None,
                 jobTitle: str | None = None,
                 fileResume: str | None = None,
                 filePhoto: str | None = None,
                 applyParameters: dict | None = None,
                 storeErrors: bool = False
                 ) -> None:
        self.jobIDs = jobID
        self.browser = browser
        self.blueprint = blueprint
        self.blueprintFile = blueprintFile
        self.jobTitle = jobTitle
        self.fileResume = fileResume
        self.filePhoto = filePhoto
        self.applyParameters = applyParameters
        self.storeErrors = storeErrors
        return None
    
    def setBlueprintFromFile(self,
                             filename: str) -> dict:
        blueprint = None
        if not isinstance(filename, str):
            raise TypeError(f"Blueprint should be a string. Now it is {type(blueprint)}")
        '''get blueprint from yaml file'''
        return blueprint

    def setBlueprintFromDict(self,
                             blueprint: dict) -> dict:
        '''get blueprint from dictionary'''
        pass

    def setBlueprint(self,
                     blueprint: dict | str) -> dict | None:
        if isinstance(blueprint, dict) : self.setBlueprintFromDict(blueprint)
        if isinstance(blueprint, str) : self.setBlueprintFromFile(blueprint)
        if not isinstance(blueprint, str) and not isinstance(blueprint, str):
            raise TypeError(f"Blueprint should be dictionary or string. Now it is {type(blueprint)}")
        return None

    def scanPage(self) -> bool:
        pass

    def checkLocators(self,
                       locators: dict) -> (bool, str):
        '''All negative checks to continue in one place'''
        log.debug("Checks to continue started..")
        checkStatus : bool = True
        checkMessage : str = "All checks passed."
        # Didn't find anything on the page
        if locators is None :
            checkStatus = False
            checkMessage = "No locators found on the page."
            return checkStatus, checkMessage
        # Found an Error on page
        if locators['error']['element'] is not None:
            checkStatus = False
            checkMessage = f"EASY APPLY skipped by error: {locators['error']['element'].text}"
        # Didn't find any button to continue
        if len({key for key in locators if locators[key]['action'] == 'nextPage'}) == 0:
            checkStatus = False
            checkMessage = "EASY APPLY skipped by error: no continue buttons found"
        # Found more than one button to continue
        if len({key for key in locators if locators[key]['action'] == 'nextPage'
                and locators[key]['element'] is not None}) > 1:
            checkStatus = False
            log.debug(f"Length of buttons dict: {len({key for key in locators if locators[key]['action'] == 'nextPage' and locators[key]['element'] is not None})}")
            checkMessage = "EASY APPLY skipped by error: more than one button found"
        # All good
        log.debug(f"Check status {str(checkStatus)} : {checkMessage}")
        return checkStatus, checkMessage

    def startApplyLoop(self) -> bool:
        pass

    def storeResults(self) -> dict:
        pass

    def fillPhoneNumber(self,
                        phoneElement,
                        phoneNumber: str) -> bool:
        '''Fill the phone number correctly'''
        log.debug("Sending phone number...")
        if phoneElement:
            phoneElement.clear()
            phoneElement.send_keys(phoneNumber)
        else:
            log.warning("No phone element sended")
        return True
