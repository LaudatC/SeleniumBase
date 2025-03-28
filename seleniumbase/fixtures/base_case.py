# -*- coding: utf-8 -*-
r"""  ------------>  ------------>  ------------>  ------------>
   ______     __           _                 ____
  / ____/__  / /__  ____  (_)_  ______ ___  / _  \____  ________
  \__ \/ _ \/ / _ \/ __ \/ / / / / __ `__ \/ /_) / __ \/ ___/ _ \
 ___/ /  __/ /  __/ / / / / /_/ / / / / / / /_) / (_/ /__  /  __/
/____/\___/_/\___/_/ /_/_/\__,_/_/ /_/ /_/_____/\__,_/____/\___/

------------>  ------------>  ------------>  ------------>

The BaseCase class is the main gateway for using The SeleniumBase Framework.
It inherits Python's unittest.TestCase class, and runs with Pytest or Nose.
All tests using BaseCase automatically launch WebDriver browsers for tests.

Usage:

    from seleniumbase import BaseCase
    class MyTestClass(BaseCase):
        def test_anything(self):
            # Write your code here. Example:
            self.open("https://github.com/")
            self.type("input.header-search-input", "SeleniumBase\n")
            self.click('a[href="/seleniumbase/SeleniumBase"]')
            self.assert_element("div.repository-content")
            ....

SeleniumBase methods expand and improve on existing WebDriver commands.
Improvements include making WebDriver more robust, reliable, and flexible.
Page elements are given enough time to load before WebDriver acts on them.
Code becomes greatly simplified and easier to maintain.
"""

import codecs
import json
import logging
import os
import re
import sys
import time
import unittest
import urllib3
from selenium.common.exceptions import (
    ElementClickInterceptedException as ECI_Exception,
    ElementNotInteractableException as ENI_Exception,
    MoveTargetOutOfBoundsException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.remote_connection import LOGGER
from seleniumbase import config as sb_config
from seleniumbase.common import decorators
from seleniumbase.config import settings
from seleniumbase.core import log_helper
from seleniumbase.fixtures import constants
from seleniumbase.fixtures import css_to_xpath
from seleniumbase.fixtures import js_utils
from seleniumbase.fixtures import page_actions
from seleniumbase.fixtures import page_utils
from seleniumbase.fixtures import shared_utils
from seleniumbase.fixtures import xpath_to_css

logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
urllib3.disable_warnings()
LOGGER.setLevel(logging.WARNING)
if sys.version_info[0] < 3:
    reload(sys)  # noqa: F821
    sys.setdefaultencoding("utf8")


class BaseCase(unittest.TestCase):
    """ <Class seleniumbase.BaseCase> """

    def __init__(self, *args, **kwargs):
        super(BaseCase, self).__init__(*args, **kwargs)
        self.driver = None
        self.environment = None
        self.env = None  # Add a shortened version of self.environment
        self.__page_sources = []
        self.__extra_actions = []
        self.__js_start_time = 0
        self.__set_c_from_switch = False
        self.__called_setup = False
        self.__called_teardown = False
        self.__start_time_ms = None
        self.__requests_timeout = None
        self.__screenshot_count = 0
        self.__will_be_skipped = False
        self.__passed_then_skipped = False
        self.__last_url_of_deferred_assert = "data:,"
        self.__last_page_load_url = "data:,"
        self.__last_page_screenshot = None
        self.__last_page_screenshot_png = None
        self.__last_page_url = None
        self.__last_page_source = None
        self.__skip_reason = None
        self.__overrided_default_timeouts = False
        self.__added_pytest_html_extra = None
        self.__deferred_assert_count = 0
        self.__deferred_assert_failures = []
        self.__device_width = None
        self.__device_height = None
        self.__device_pixel_ratio = None
        self.__driver_browser_map = {}
        self.__changed_jqc_theme = False
        self.__jqc_default_theme = None
        self.__jqc_default_color = None
        self.__jqc_default_width = None
        # Requires self._* instead of self.__* for external class use
        self._language = "English"
        self._presentation_slides = {}
        self._presentation_transition = {}
        self._rec_overrides_switch = True  # Recorder-Mode uses set_c vs switch
        self._sb_test_identifier = None
        self._html_report_extra = []  # (Used by pytest_plugin.py)
        self._default_driver = None
        self._drivers_list = []
        self._chart_data = {}
        self._chart_count = 0
        self._chart_label = {}
        self._chart_xcount = 0
        self._chart_first_series = {}
        self._chart_series_count = {}
        self._tour_steps = {}

    def open(self, url):
        """ Navigates the current browser window to the specified page. """
        self.__check_scope()
        if type(url) is str:
            url = url.strip()  # Remove leading and trailing whitespace
        if (type(url) is not str) or not self.__looks_like_a_page_url(url):
            # url should start with one of the following:
            # "http:", "https:", "://", "data:", "file:",
            # "about:", "chrome:", "opera:", or "edge:".
            msg = 'Did you forget to prefix your URL with "http:" or "https:"?'
            raise Exception('Invalid URL: "%s"\n%s' % (url, msg))
        self.__last_page_load_url = None
        js_utils.clear_out_console_logs(self.driver)
        if url.startswith("://"):
            # Convert URLs such as "://google.com" into "https://google.com"
            url = "https" + url
        if self.recorder_mode:
            c_url = self.driver.current_url
            if ("http:") in c_url or ("https:") in c_url or ("file:") in c_url:
                if self.get_domain_url(url) != self.get_domain_url(c_url):
                    self.open_new_window(switch_to=True)
        if self.browser == "safari" and url.startswith("data:"):
            url = re.escape(url)
            url = self.__escape_quotes_if_needed(url)
            self.execute_script("window.location.href='%s';" % url)
        else:
            self.driver.get(url)
        if settings.WAIT_FOR_RSC_ON_PAGE_LOADS:
            self.wait_for_ready_state_complete()
        self.__demo_mode_pause_if_active()

    def get(self, url):
        """If "url" looks like a page URL, open the URL in the web browser.
        Otherwise, return self.get_element(URL_AS_A_SELECTOR)
        Examples:
            self.get("https://seleniumbase.io")  # Navigates to the URL
            self.get("input.class")  # Finds and returns the WebElement
        """
        self.__check_scope()
        if self.__looks_like_a_page_url(url):
            self.open(url)
        else:
            return self.get_element(url)  # url is treated like a selector

    def click(
        self, selector, by=By.CSS_SELECTOR, timeout=None, delay=0, scroll=True
    ):
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        original_selector = selector
        original_by = by
        selector, by = self.__recalculate_selector(selector, by)
        if delay and (type(delay) in [int, float]) and delay > 0:
            time.sleep(delay)
        if page_utils.is_link_text_selector(selector) or by == By.LINK_TEXT:
            if not self.is_link_text_visible(selector):
                # Handle a special case of links hidden in dropdowns
                self.click_link_text(selector, timeout=timeout)
                return
        if (
            page_utils.is_partial_link_text_selector(selector)
            or by == By.PARTIAL_LINK_TEXT
        ):
            if not self.is_partial_link_text_visible(selector):
                # Handle a special case of partial links hidden in dropdowns
                self.click_partial_link_text(selector, timeout=timeout)
                return
        if self.__is_shadow_selector(selector):
            self.__shadow_click(selector)
            return
        element = page_actions.wait_for_element_visible(
            self.driver, selector, by, timeout=timeout
        )
        self.__demo_mode_highlight_if_active(original_selector, original_by)
        if scroll and not self.demo_mode and not self.slow_mode:
            self.__scroll_to_element(element, selector, by)
        pre_action_url = self.driver.current_url
        pre_window_count = len(self.driver.window_handles)
        try:
            if self.browser == "ie" and by == By.LINK_TEXT:
                # An issue with clicking Link Text on IE means using jquery
                self.__jquery_click(selector, by=by)
            elif self.browser == "safari":
                if by == By.LINK_TEXT:
                    self.__jquery_click(selector, by=by)
                else:
                    self.__js_click(selector, by=by)
            else:
                href = None
                new_tab = False
                onclick = None
                try:
                    if self.headless and element.tag_name == "a":
                        # Handle a special case of opening a new tab (headless)
                        href = element.get_attribute("href").strip()
                        onclick = element.get_attribute("onclick")
                        target = element.get_attribute("target")
                        if target == "_blank":
                            new_tab = True
                        if new_tab and self.__looks_like_a_page_url(href):
                            if onclick:
                                try:
                                    self.execute_script(onclick)
                                except Exception:
                                    pass
                            current_window = self.driver.current_window_handle
                            self.open_new_window()
                            try:
                                self.open(href)
                            except Exception:
                                pass
                            self.switch_to_window(current_window)
                            return
                except Exception:
                    pass
                # Normal click
                element.click()
        except StaleElementReferenceException:
            self.wait_for_ready_state_complete()
            time.sleep(0.16)
            element = page_actions.wait_for_element_visible(
                self.driver, selector, by, timeout=timeout
            )
            try:
                self.__scroll_to_element(element, selector, by)
            except Exception:
                pass
            if self.browser == "safari":
                if by == By.LINK_TEXT:
                    self.__jquery_click(selector, by=by)
                else:
                    self.__js_click(selector, by=by)
            else:
                element.click()
        except ENI_Exception:
            self.wait_for_ready_state_complete()
            time.sleep(0.1)
            element = page_actions.wait_for_element_visible(
                self.driver, selector, by, timeout=timeout
            )
            href = None
            new_tab = False
            onclick = None
            try:
                if element.tag_name == "a":
                    # Handle a special case of opening a new tab (non-headless)
                    href = element.get_attribute("href").strip()
                    onclick = element.get_attribute("onclick")
                    target = element.get_attribute("target")
                    if target == "_blank":
                        new_tab = True
                    if new_tab and self.__looks_like_a_page_url(href):
                        if onclick:
                            try:
                                self.execute_script(onclick)
                            except Exception:
                                pass
                        current_window = self.driver.current_window_handle
                        self.open_new_window()
                        try:
                            self.open(href)
                        except Exception:
                            pass
                        self.switch_to_window(current_window)
                        return
            except Exception:
                pass
            self.__scroll_to_element(element, selector, by)
            if self.browser == "safari":
                if by == By.LINK_TEXT:
                    self.__jquery_click(selector, by=by)
                else:
                    self.__js_click(selector, by=by)
            else:
                element.click()
        except (WebDriverException, MoveTargetOutOfBoundsException):
            self.wait_for_ready_state_complete()
            try:
                self.__js_click(selector, by=by)
            except Exception:
                try:
                    self.__jquery_click(selector, by=by)
                except Exception:
                    # One more attempt to click on the element
                    element = page_actions.wait_for_element_visible(
                        self.driver, selector, by, timeout=timeout
                    )
                    element.click()
        latest_window_count = len(self.driver.window_handles)
        if (
            latest_window_count > pre_window_count
            and (
                self.recorder_mode
                or (
                    settings.SWITCH_TO_NEW_TABS_ON_CLICK
                    and self.driver.current_url == pre_action_url
                )
            )
        ):
            self.switch_to_newest_window()
        if settings.WAIT_FOR_RSC_ON_CLICKS:
            self.wait_for_ready_state_complete()
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()

    def slow_click(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """Similar to click(), but pauses for a brief moment before clicking.
        When used in combination with setting the user-agent, you can often
        bypass bot-detection by tricking websites into thinking that you're
        not a bot. (Useful on websites that block web automation tools.)
        To set the user-agent, use: ``--agent=AGENT``.
        Here's an example message from GitHub's bot-blocker:
        ``You have triggered an abuse detection mechanism...``
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        if not self.demo_mode and not self.slow_mode:
            self.click(selector, by=by, timeout=timeout, delay=1.05)
        elif self.slow_mode:
            self.click(selector, by=by, timeout=timeout, delay=0.65)
        else:
            # Demo Mode already includes a small delay
            self.click(selector, by=by, timeout=timeout, delay=0.25)

    def double_click(self, selector, by=By.CSS_SELECTOR, timeout=None):
        from selenium.webdriver.common.action_chains import ActionChains

        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        original_selector = selector
        original_by = by
        selector, by = self.__recalculate_selector(selector, by)
        element = page_actions.wait_for_element_visible(
            self.driver, selector, by, timeout=timeout
        )
        self.__demo_mode_highlight_if_active(original_selector, original_by)
        if not self.demo_mode and not self.slow_mode:
            self.__scroll_to_element(element, selector, by)
        self.wait_for_ready_state_complete()
        # Find the element one more time in case scrolling hid it
        element = page_actions.wait_for_element_visible(
            self.driver, selector, by, timeout=timeout
        )
        pre_action_url = self.driver.current_url
        try:
            if self.browser == "safari":
                # Jump to the "except" block where the other script should work
                raise Exception("This Exception will be caught.")
            actions = ActionChains(self.driver)
            actions.double_click(element).perform()
        except Exception:
            css_selector = self.convert_to_css_selector(selector, by=by)
            css_selector = re.escape(css_selector)  # Add "\\" to special chars
            css_selector = self.__escape_quotes_if_needed(css_selector)
            double_click_script = (
                """var targetElement1 = document.querySelector('%s');
                var clickEvent1 = document.createEvent('MouseEvents');
                clickEvent1.initEvent('dblclick', true, true);
                targetElement1.dispatchEvent(clickEvent1);"""
                % css_selector
            )
            if ":contains\\(" not in css_selector:
                self.execute_script(double_click_script)
            else:
                double_click_script = (
                    """jQuery('%s').dblclick();""" % css_selector
                )
                self.safe_execute_script(double_click_script)
        if settings.WAIT_FOR_RSC_ON_CLICKS:
            self.wait_for_ready_state_complete()
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()

    def click_chain(
        self, selectors_list, by=By.CSS_SELECTOR, timeout=None, spacing=0
    ):
        """This method clicks on a list of elements in succession.
        @Params
        selectors_list - The list of selectors to click on.
        by - The type of selector to search by (Default: CSS_Selector).
        timeout - How long to wait for the selector to be visible.
        spacing - The amount of time to wait between clicks (in seconds).
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        for selector in selectors_list:
            self.click(selector, by=by, timeout=timeout)
            if spacing > 0:
                time.sleep(spacing)

    def update_text(
        self, selector, text, by=By.CSS_SELECTOR, timeout=None, retry=False
    ):
        """This method updates an element's text field with new text.
        Has multiple parts:
        * Waits for the element to be visible.
        * Waits for the element to be interactive.
        * Clears the text field.
        * Types in the new text.
        * Hits Enter/Submit (if the text ends in "\n").
        @Params
        selector - the selector of the text field
        text - the new text to type into the text field
        by - the type of selector to search by (Default: CSS Selector)
        timeout - how long to wait for the selector to be visible
        retry - if True, use JS if the Selenium text update fails
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            self.__shadow_type(selector, text)
            return
        element = self.wait_for_element_visible(
            selector, by=by, timeout=timeout
        )
        self.__demo_mode_highlight_if_active(selector, by)
        if not self.demo_mode and not self.slow_mode:
            self.__scroll_to_element(element, selector, by)
        try:
            element.clear()  # May need https://stackoverflow.com/a/50691625
            backspaces = Keys.BACK_SPACE * 42  # Is the answer to everything
            element.send_keys(backspaces)  # In case autocomplete keeps text
        except (StaleElementReferenceException, ENI_Exception):
            self.wait_for_ready_state_complete()
            time.sleep(0.16)
            element = self.wait_for_element_visible(
                selector, by=by, timeout=timeout
            )
            try:
                element.clear()
            except Exception:
                pass  # Clearing the text field first might not be necessary
        except Exception:
            pass  # Clearing the text field first might not be necessary
        self.__demo_mode_pause_if_active(tiny=True)
        pre_action_url = self.driver.current_url
        if type(text) is int or type(text) is float:
            text = str(text)
        try:
            if not text.endswith("\n"):
                element.send_keys(text)
                if settings.WAIT_FOR_RSC_ON_PAGE_LOADS:
                    self.wait_for_ready_state_complete()
            else:
                element.send_keys(text[:-1])
                element.send_keys(Keys.RETURN)
                if settings.WAIT_FOR_RSC_ON_PAGE_LOADS:
                    self.wait_for_ready_state_complete()
        except (StaleElementReferenceException, ENI_Exception):
            self.wait_for_ready_state_complete()
            time.sleep(0.16)
            element = self.wait_for_element_visible(
                selector, by=by, timeout=timeout
            )
            element.clear()
            if not text.endswith("\n"):
                element.send_keys(text)
            else:
                element.send_keys(text[:-1])
                element.send_keys(Keys.RETURN)
                if settings.WAIT_FOR_RSC_ON_PAGE_LOADS:
                    self.wait_for_ready_state_complete()
        except Exception:
            exc_message = self.__get_improved_exception_message()
            raise Exception(exc_message)
        if (
            retry
            and element.get_attribute("value") != text
            and not text.endswith("\n")
        ):
            logging.debug("update_text() is falling back to JavaScript!")
            self.set_value(selector, text, by=by)
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()

    def add_text(self, selector, text, by=By.CSS_SELECTOR, timeout=None):
        """The more-reliable version of driver.send_keys()
        Similar to update_text(), but won't clear the text field first."""
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            self.__shadow_type(selector, text, clear_first=False)
            return
        element = self.wait_for_element_visible(
            selector, by=by, timeout=timeout
        )
        self.__demo_mode_highlight_if_active(selector, by)
        if not self.demo_mode and not self.slow_mode:
            self.__scroll_to_element(element, selector, by)
        pre_action_url = self.driver.current_url
        if type(text) is int or type(text) is float:
            text = str(text)
        try:
            if not text.endswith("\n"):
                element.send_keys(text)
            else:
                element.send_keys(text[:-1])
                element.send_keys(Keys.RETURN)
                if settings.WAIT_FOR_RSC_ON_PAGE_LOADS:
                    self.wait_for_ready_state_complete()
        except (StaleElementReferenceException, ENI_Exception):
            self.wait_for_ready_state_complete()
            time.sleep(0.16)
            element = self.wait_for_element_visible(
                selector, by=by, timeout=timeout
            )
            if not text.endswith("\n"):
                element.send_keys(text)
            else:
                element.send_keys(text[:-1])
                element.send_keys(Keys.RETURN)
                if settings.WAIT_FOR_RSC_ON_PAGE_LOADS:
                    self.wait_for_ready_state_complete()
        except Exception:
            exc_message = self.__get_improved_exception_message()
            raise Exception(exc_message)
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()

    def type(
        self, selector, text, by=By.CSS_SELECTOR, timeout=None, retry=False
    ):
        """Same as self.update_text()
        This method updates an element's text field with new text.
        Has multiple parts:
        * Waits for the element to be visible.
        * Waits for the element to be interactive.
        * Clears the text field.
        * Types in the new text.
        * Hits Enter/Submit (if the text ends in "\n").
        @Params
        selector - the selector of the text field
        text - the new text to type into the text field
        by - the type of selector to search by (Default: CSS Selector)
        timeout - how long to wait for the selector to be visible
        retry - if True, use JS if the Selenium text update fails
        DO NOT confuse self.type() with Python type()! They are different!
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.update_text(selector, text, by=by, timeout=timeout, retry=retry)

    def submit(self, selector, by=By.CSS_SELECTOR):
        """ Alternative to self.driver.find_element_by_*(SELECTOR).submit() """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        element = self.wait_for_element_visible(
            selector, by=by, timeout=settings.SMALL_TIMEOUT
        )
        element.submit()
        self.__demo_mode_pause_if_active()

    def clear(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """This method clears an element's text field.
        A clear() is already included with most methods that type text,
        such as self.type(), self.update_text(), etc.
        Does not use Demo Mode highlights, mainly because we expect
        that some users will be calling an unnecessary clear() before
        calling a method that already includes clear() as part of it.
        In case websites trigger an autofill after clearing a field,
        add backspaces to make sure autofill doesn't undo the clear.
        @Params
        selector - the selector of the text field
        by - the type of selector to search by (Default: CSS Selector)
        timeout - how long to wait for the selector to be visible
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            self.__shadow_clear(selector)
            return
        element = self.wait_for_element_visible(
            selector, by=by, timeout=timeout
        )
        self.scroll_to(selector, by=by, timeout=timeout)
        try:
            element.clear()
            backspaces = Keys.BACK_SPACE * 42  # Autofill Defense
            element.send_keys(backspaces)
        except (StaleElementReferenceException, ENI_Exception):
            self.wait_for_ready_state_complete()
            time.sleep(0.16)
            element = self.wait_for_element_visible(
                selector, by=by, timeout=timeout
            )
            element.clear()
            try:
                backspaces = Keys.BACK_SPACE * 42  # Autofill Defense
                element.send_keys(backspaces)
            except Exception:
                pass
        except Exception:
            element.clear()

    def focus(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """Make the current page focus on an interactable element.
        If the element is not interactable, only scrolls to it.
        The "tab" key is another way of setting the page focus."""
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        element = self.wait_for_element_visible(
            selector, by=by, timeout=timeout
        )
        self.scroll_to(selector, by=by, timeout=timeout)
        try:
            element.send_keys(Keys.NULL)
        except (StaleElementReferenceException, ENI_Exception):
            self.wait_for_ready_state_complete()
            time.sleep(0.12)
            element = self.wait_for_element_visible(
                selector, by=by, timeout=timeout
            )
            try:
                element.send_keys(Keys.NULL)
            except ENI_Exception:
                # Non-interactable element. Skip focus and continue.
                pass
        self.__demo_mode_pause_if_active()

    def refresh_page(self):
        self.__check_scope()
        self.__last_page_load_url = None
        js_utils.clear_out_console_logs(self.driver)
        self.driver.refresh()
        self.wait_for_ready_state_complete()

    def refresh(self):
        """ The shorter version of self.refresh_page() """
        self.refresh_page()

    def get_current_url(self):
        self.__check_scope()
        current_url = self.driver.current_url
        if "%" in current_url and sys.version_info[0] >= 3:
            try:
                from urllib.parse import unquote

                current_url = unquote(current_url, errors="strict")
            except Exception:
                pass
        return current_url

    def get_origin(self):
        self.__check_scope()
        return self.execute_script("return window.location.origin;")

    def get_page_source(self):
        self.wait_for_ready_state_complete()
        return self.driver.page_source

    def get_page_title(self):
        self.wait_for_ready_state_complete()
        self.wait_for_element_present("title", timeout=settings.SMALL_TIMEOUT)
        time.sleep(0.03)
        return self.driver.title

    def get_title(self):
        """ The shorter version of self.get_page_title() """
        return self.get_page_title()

    def get_user_agent(self):
        self.__check_scope()
        user_agent = self.driver.execute_script("return navigator.userAgent;")
        return user_agent

    def get_locale_code(self):
        self.__check_scope()
        locale_code = self.driver.execute_script(
            "return navigator.language || navigator.languages[0];"
        )
        return locale_code

    def go_back(self):
        self.__check_scope()
        self.__last_page_load_url = None
        self.driver.back()
        if self.browser == "safari":
            self.wait_for_ready_state_complete()
            self.driver.refresh()
        self.wait_for_ready_state_complete()
        self.__demo_mode_pause_if_active()

    def go_forward(self):
        self.__check_scope()
        self.__last_page_load_url = None
        self.driver.forward()
        self.wait_for_ready_state_complete()
        self.__demo_mode_pause_if_active()

    def open_start_page(self):
        """Navigates the current browser window to the start_page.
        You can set the start_page on the command-line in three ways:
        '--start_page=URL', '--start-page=URL', or '--url=URL'.
        If the start_page is not set, then "data:," will be used."""
        self.__check_scope()
        start_page = self.start_page
        if type(start_page) is str:
            start_page = start_page.strip()  # Remove extra whitespace
        if start_page and len(start_page) >= 4:
            if page_utils.is_valid_url(start_page):
                self.open(start_page)
            else:
                new_start_page = "http://" + start_page
                if page_utils.is_valid_url(new_start_page):
                    self.open(new_start_page)
                else:
                    logging.info('Invalid URL: "%s"!' % start_page)
                    self.open("data:,")
        else:
            self.open("data:,")

    def open_if_not_url(self, url):
        """ Opens the url in the browser if it's not the current url. """
        self.__check_scope()
        if self.driver.current_url != url:
            self.open(url)

    def is_element_present(self, selector, by=By.CSS_SELECTOR):
        self.wait_for_ready_state_complete()
        selector, by = self.__recalculate_selector(selector, by)
        return page_actions.is_element_present(self.driver, selector, by)

    def is_element_visible(self, selector, by=By.CSS_SELECTOR):
        self.wait_for_ready_state_complete()
        selector, by = self.__recalculate_selector(selector, by)
        return page_actions.is_element_visible(self.driver, selector, by)

    def is_element_enabled(self, selector, by=By.CSS_SELECTOR):
        self.wait_for_ready_state_complete()
        selector, by = self.__recalculate_selector(selector, by)
        return page_actions.is_element_enabled(self.driver, selector, by)

    def is_text_visible(self, text, selector="html", by=By.CSS_SELECTOR):
        self.wait_for_ready_state_complete()
        time.sleep(0.01)
        selector, by = self.__recalculate_selector(selector, by)
        return page_actions.is_text_visible(self.driver, text, selector, by)

    def is_attribute_present(
        self, selector, attribute, value=None, by=By.CSS_SELECTOR
    ):
        """Returns True if the element attribute/value is found.
        If the value is not specified, the attribute only needs to exist."""
        self.wait_for_ready_state_complete()
        time.sleep(0.01)
        selector, by = self.__recalculate_selector(selector, by)
        return page_actions.is_attribute_present(
            self.driver, selector, attribute, value, by
        )

    def is_link_text_visible(self, link_text):
        self.wait_for_ready_state_complete()
        time.sleep(0.01)
        return page_actions.is_element_visible(
            self.driver, link_text, by=By.LINK_TEXT
        )

    def is_partial_link_text_visible(self, partial_link_text):
        self.wait_for_ready_state_complete()
        time.sleep(0.01)
        return page_actions.is_element_visible(
            self.driver, partial_link_text, by=By.PARTIAL_LINK_TEXT
        )

    def is_link_text_present(self, link_text):
        """Returns True if the link text appears in the HTML of the page.
        The element doesn't need to be visible,
        such as elements hidden inside a dropdown selection."""
        self.wait_for_ready_state_complete()
        soup = self.get_beautiful_soup()
        html_links = soup.find_all("a")
        for html_link in html_links:
            if html_link.text.strip() == link_text.strip():
                return True
        return False

    def is_partial_link_text_present(self, link_text):
        """Returns True if the partial link appears in the HTML of the page.
        The element doesn't need to be visible,
        such as elements hidden inside a dropdown selection."""
        self.wait_for_ready_state_complete()
        soup = self.get_beautiful_soup()
        html_links = soup.find_all("a")
        for html_link in html_links:
            if link_text.strip() in html_link.text.strip():
                return True
        return False

    def get_link_attribute(self, link_text, attribute, hard_fail=True):
        """Finds a link by link text and then returns the attribute's value.
        If the link text or attribute cannot be found, an exception will
        get raised if hard_fail is True (otherwise None is returned)."""
        self.wait_for_ready_state_complete()
        soup = self.get_beautiful_soup()
        html_links = soup.find_all("a")
        for html_link in html_links:
            if html_link.text.strip() == link_text.strip():
                if html_link.has_attr(attribute):
                    attribute_value = html_link.get(attribute)
                    return attribute_value
                if hard_fail:
                    raise Exception(
                        "Unable to find attribute {%s} from link text {%s}!"
                        % (attribute, link_text)
                    )
                else:
                    return None
        if hard_fail:
            raise Exception("Link text {%s} was not found!" % link_text)
        else:
            return None

    def get_link_text_attribute(self, link_text, attribute, hard_fail=True):
        """Same as self.get_link_attribute()
        Finds a link by link text and then returns the attribute's value.
        If the link text or attribute cannot be found, an exception will
        get raised if hard_fail is True (otherwise None is returned)."""
        return self.get_link_attribute(link_text, attribute, hard_fail)

    def get_partial_link_text_attribute(
        self, link_text, attribute, hard_fail=True
    ):
        """Finds a link by partial link text and then returns the attribute's
        value. If the partial link text or attribute cannot be found, an
        exception will get raised if hard_fail is True (otherwise None
        is returned)."""
        self.wait_for_ready_state_complete()
        soup = self.get_beautiful_soup()
        html_links = soup.find_all("a")
        for html_link in html_links:
            if link_text.strip() in html_link.text.strip():
                if html_link.has_attr(attribute):
                    attribute_value = html_link.get(attribute)
                    return attribute_value
                if hard_fail:
                    raise Exception(
                        "Unable to find attribute {%s} from "
                        "partial link text {%s}!" % (attribute, link_text)
                    )
                else:
                    return None
        if hard_fail:
            raise Exception(
                "Partial Link text {%s} was not found!" % link_text
            )
        else:
            return None

    def click_link_text(self, link_text, timeout=None):
        """ This method clicks link text on a page """
        # If using phantomjs, might need to extract and open the link directly
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        if self.browser == "phantomjs":
            if self.is_link_text_visible(link_text):
                element = self.wait_for_link_text_visible(
                    link_text, timeout=timeout
                )
                element.click()
                return
            self.open(self.__get_href_from_link_text(link_text))
            return
        if self.browser == "safari":
            if self.demo_mode:
                self.wait_for_link_text_present(link_text, timeout=timeout)
                try:
                    self.__jquery_slow_scroll_to(link_text, by=By.LINK_TEXT)
                except Exception:
                    element = self.wait_for_link_text_visible(
                        link_text, timeout=timeout
                    )
                    self.__slow_scroll_to_element(element)
                o_bs = ""  # original_box_shadow
                loops = settings.HIGHLIGHTS
                selector = self.convert_to_css_selector(
                    link_text, by=By.LINK_TEXT
                )
                selector = self.__make_css_match_first_element_only(selector)
                try:
                    selector = re.escape(selector)
                    selector = self.__escape_quotes_if_needed(selector)
                    self.__highlight_with_jquery(selector, loops, o_bs)
                except Exception:
                    pass  # JQuery probably couldn't load. Skip highlighting.
            self.__jquery_click(link_text, by=By.LINK_TEXT)
            return
        if not self.is_link_text_present(link_text):
            self.wait_for_link_text_present(link_text, timeout=timeout)
        pre_action_url = self.get_current_url()
        try:
            element = self.wait_for_link_text_visible(link_text, timeout=0.2)
            self.__demo_mode_highlight_if_active(link_text, by=By.LINK_TEXT)
            try:
                element.click()
            except (StaleElementReferenceException, ENI_Exception):
                self.wait_for_ready_state_complete()
                time.sleep(0.16)
                element = self.wait_for_link_text_visible(
                    link_text, timeout=timeout
                )
                element.click()
        except Exception:
            found_css = False
            text_id = self.get_link_attribute(link_text, "id", False)
            if text_id:
                link_css = '[id="%s"]' % link_text
                found_css = True

            if not found_css:
                href = self.__get_href_from_link_text(link_text, False)
                if href:
                    if href.startswith("/") or page_utils.is_valid_url(href):
                        link_css = '[href="%s"]' % href
                        found_css = True

            if not found_css:
                ngclick = self.get_link_attribute(link_text, "ng-click", False)
                if ngclick:
                    link_css = '[ng-click="%s"]' % ngclick
                    found_css = True

            if not found_css:
                onclick = self.get_link_attribute(link_text, "onclick", False)
                if onclick:
                    link_css = '[onclick="%s"]' % onclick
                    found_css = True

            success = False
            if found_css:
                if self.is_element_visible(link_css):
                    self.click(link_css)
                    success = True
                else:
                    # The link text might be hidden under a dropdown menu
                    success = self.__click_dropdown_link_text(
                        link_text, link_css
                    )

            if not success:
                element = self.wait_for_link_text_visible(
                    link_text, timeout=settings.MINI_TIMEOUT
                )
                element.click()

        if settings.WAIT_FOR_RSC_ON_CLICKS:
            self.wait_for_ready_state_complete()
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()

    def click_partial_link_text(self, partial_link_text, timeout=None):
        """ This method clicks the partial link text on a page. """
        # If using phantomjs, might need to extract and open the link directly
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        if self.browser == "phantomjs":
            if self.is_partial_link_text_visible(partial_link_text):
                element = self.wait_for_partial_link_text(partial_link_text)
                element.click()
                return
            soup = self.get_beautiful_soup()
            html_links = soup.fetch("a")
            for html_link in html_links:
                if partial_link_text in html_link.text:
                    for html_attribute in html_link.attrs:
                        if html_attribute[0] == "href":
                            href = html_attribute[1]
                            if href.startswith("//"):
                                link = "http:" + href
                            elif href.startswith("/"):
                                url = self.driver.current_url
                                domain_url = self.get_domain_url(url)
                                link = domain_url + href
                            else:
                                link = href
                            self.open(link)
                            return
                    raise Exception(
                        "Could not parse link from partial link_text "
                        "{%s}" % partial_link_text
                    )
            raise Exception(
                "Partial link text {%s} was not found!" % partial_link_text
            )
        if not self.is_partial_link_text_present(partial_link_text):
            self.wait_for_partial_link_text_present(
                partial_link_text, timeout=timeout
            )
        pre_action_url = self.get_current_url()
        try:
            element = self.wait_for_partial_link_text(
                partial_link_text, timeout=0.2
            )
            self.__demo_mode_highlight_if_active(
                partial_link_text, by=By.LINK_TEXT
            )
            try:
                element.click()
            except (StaleElementReferenceException, ENI_Exception):
                self.wait_for_ready_state_complete()
                time.sleep(0.16)
                element = self.wait_for_partial_link_text(
                    partial_link_text, timeout=timeout
                )
                element.click()
        except Exception:
            found_css = False
            text_id = self.get_partial_link_text_attribute(
                partial_link_text, "id", False
            )
            if text_id:
                link_css = '[id="%s"]' % partial_link_text
                found_css = True

            if not found_css:
                href = self.__get_href_from_partial_link_text(
                    partial_link_text, False
                )
                if href:
                    if href.startswith("/") or page_utils.is_valid_url(href):
                        link_css = '[href="%s"]' % href
                        found_css = True

            if not found_css:
                ngclick = self.get_partial_link_text_attribute(
                    partial_link_text, "ng-click", False
                )
                if ngclick:
                    link_css = '[ng-click="%s"]' % ngclick
                    found_css = True

            if not found_css:
                onclick = self.get_partial_link_text_attribute(
                    partial_link_text, "onclick", False
                )
                if onclick:
                    link_css = '[onclick="%s"]' % onclick
                    found_css = True

            success = False
            if found_css:
                if self.is_element_visible(link_css):
                    self.click(link_css)
                    success = True
                else:
                    # The link text might be hidden under a dropdown menu
                    success = self.__click_dropdown_partial_link_text(
                        partial_link_text, link_css
                    )

            if not success:
                element = self.wait_for_partial_link_text(
                    partial_link_text, timeout=settings.MINI_TIMEOUT
                )
                element.click()

        if settings.WAIT_FOR_RSC_ON_CLICKS:
            self.wait_for_ready_state_complete()
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()

    def get_text(self, selector, by=By.CSS_SELECTOR, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            return self.__get_shadow_text(selector)
        self.wait_for_ready_state_complete()
        time.sleep(0.01)
        element = page_actions.wait_for_element_visible(
            self.driver, selector, by, timeout
        )
        try:
            element_text = element.text
        except (StaleElementReferenceException, ENI_Exception):
            self.wait_for_ready_state_complete()
            time.sleep(0.14)
            element = page_actions.wait_for_element_visible(
                self.driver, selector, by, timeout
            )
            element_text = element.text
        return element_text

    def get_attribute(
        self,
        selector,
        attribute,
        by=By.CSS_SELECTOR,
        timeout=None,
        hard_fail=True,
    ):
        """ This method uses JavaScript to get the value of an attribute. """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_ready_state_complete()
        time.sleep(0.01)
        element = page_actions.wait_for_element_present(
            self.driver, selector, by, timeout
        )
        try:
            attribute_value = element.get_attribute(attribute)
        except (StaleElementReferenceException, ENI_Exception):
            self.wait_for_ready_state_complete()
            time.sleep(0.14)
            element = page_actions.wait_for_element_present(
                self.driver, selector, by, timeout
            )
            attribute_value = element.get_attribute(attribute)
        if attribute_value is not None:
            return attribute_value
        else:
            if hard_fail:
                raise Exception(
                    "Element {%s} has no attribute {%s}!"
                    % (selector, attribute)
                )
            else:
                return None

    def set_attribute(
        self,
        selector,
        attribute,
        value,
        by=By.CSS_SELECTOR,
        timeout=None,
        scroll=False,
    ):
        """This method uses JavaScript to set/update an attribute.
        Only the first matching selector from querySelector() is used."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if scroll and self.is_element_visible(selector, by=by):
            try:
                self.scroll_to(selector, by=by, timeout=timeout)
            except Exception:
                pass
        attribute = re.escape(attribute)
        attribute = self.__escape_quotes_if_needed(attribute)
        value = re.escape(value)
        value = self.__escape_quotes_if_needed(value)
        css_selector = self.convert_to_css_selector(selector, by=by)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        script = (
            """document.querySelector('%s').setAttribute('%s','%s');"""
            % (css_selector, attribute, value)
        )
        self.execute_script(script)

    def set_attributes(self, selector, attribute, value, by=By.CSS_SELECTOR):
        """This method uses JavaScript to set/update a common attribute.
        All matching selectors from querySelectorAll() are used.
        Example => (Make all links on a website redirect to Google):
        self.set_attributes("a", "href", "https://google.com")"""
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        attribute = re.escape(attribute)
        attribute = self.__escape_quotes_if_needed(attribute)
        value = re.escape(value)
        value = self.__escape_quotes_if_needed(value)
        css_selector = self.convert_to_css_selector(selector, by=by)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        script = """var $elements = document.querySelectorAll('%s');
                  var index = 0, length = $elements.length;
                  for(; index < length; index++){
                  $elements[index].setAttribute('%s','%s');}""" % (
            css_selector,
            attribute,
            value,
        )
        try:
            self.execute_script(script)
        except Exception:
            pass

    def set_attribute_all(
        self, selector, attribute, value, by=By.CSS_SELECTOR
    ):
        """Same as set_attributes(), but using querySelectorAll naming scheme.
        This method uses JavaScript to set/update a common attribute.
        All matching selectors from querySelectorAll() are used.
        Example => (Make all links on a website redirect to Google):
        self.set_attribute_all("a", "href", "https://google.com")"""
        self.set_attributes(selector, attribute, value, by=by)

    def remove_attribute(
        self, selector, attribute, by=By.CSS_SELECTOR, timeout=None
    ):
        """This method uses JavaScript to remove an attribute.
        Only the first matching selector from querySelector() is used."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.is_element_visible(selector, by=by):
            try:
                self.scroll_to(selector, by=by, timeout=timeout)
            except Exception:
                pass
        attribute = re.escape(attribute)
        attribute = self.__escape_quotes_if_needed(attribute)
        css_selector = self.convert_to_css_selector(selector, by=by)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        script = """document.querySelector('%s').removeAttribute('%s');""" % (
            css_selector,
            attribute,
        )
        self.execute_script(script)

    def remove_attributes(self, selector, attribute, by=By.CSS_SELECTOR):
        """This method uses JavaScript to remove a common attribute.
        All matching selectors from querySelectorAll() are used."""
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        attribute = re.escape(attribute)
        attribute = self.__escape_quotes_if_needed(attribute)
        css_selector = self.convert_to_css_selector(selector, by=by)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        script = """var $elements = document.querySelectorAll('%s');
                  var index = 0, length = $elements.length;
                  for(; index < length; index++){
                  $elements[index].removeAttribute('%s');}""" % (
            css_selector,
            attribute,
        )
        try:
            self.execute_script(script)
        except Exception:
            pass

    def get_property_value(
        self, selector, property, by=By.CSS_SELECTOR, timeout=None
    ):
        """Returns the property value of a page element's computed style.
        Example:
            opacity = self.get_property_value("html body a", "opacity")
            self.assertTrue(float(opacity) > 0, "Element not visible!")"""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_ready_state_complete()
        page_actions.wait_for_element_present(
            self.driver, selector, by, timeout
        )
        try:
            selector = self.convert_to_css_selector(selector, by=by)
        except Exception:
            # Don't run action if can't convert to CSS_Selector for JavaScript
            raise Exception(
                "Exception: Could not convert {%s}(by=%s) to CSS_SELECTOR!"
                % (selector, by)
            )
        selector = re.escape(selector)
        selector = self.__escape_quotes_if_needed(selector)
        script = """var $elm = document.querySelector('%s');
                  $val = window.getComputedStyle($elm).getPropertyValue('%s');
                  return $val;""" % (
            selector,
            property,
        )
        value = self.execute_script(script)
        if value is not None:
            return value
        else:
            return ""  # Return an empty string if the property doesn't exist

    def get_image_url(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """ Extracts the URL from an image element on the page. """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.get_attribute(
            selector, attribute="src", by=by, timeout=timeout
        )

    def find_elements(self, selector, by=By.CSS_SELECTOR, limit=0):
        """Returns a list of matching WebElements.
        Elements could be either hidden or visible on the page.
        If "limit" is set and > 0, will only return that many elements."""
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_ready_state_complete()
        time.sleep(0.05)
        elements = self.driver.find_elements(by=by, value=selector)
        if limit and limit > 0 and len(elements) > limit:
            elements = elements[:limit]
        return elements

    def find_visible_elements(self, selector, by=By.CSS_SELECTOR, limit=0):
        """Returns a list of matching WebElements that are visible.
        If "limit" is set and > 0, will only return that many elements."""
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_ready_state_complete()
        time.sleep(0.05)
        v_elems = page_actions.find_visible_elements(self.driver, selector, by)
        if limit and limit > 0 and len(v_elems) > limit:
            v_elems = v_elems[:limit]
        return v_elems

    def click_visible_elements(
        self, selector, by=By.CSS_SELECTOR, limit=0, timeout=None
    ):
        """Finds all matching page elements and clicks visible ones in order.
        If a click reloads or opens a new page, the clicking will stop.
        If no matching elements appear, an Exception will be raised.
        If "limit" is set and > 0, will only click that many elements.
        Also clicks elements that become visible from previous clicks.
        Works best for actions such as clicking all checkboxes on a page.
        Example:  self.click_visible_elements('input[type="checkbox"]')"""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_element_present(selector, by=by, timeout=timeout)
        elements = self.find_elements(selector, by=by)
        if self.browser == "safari":
            if not limit:
                limit = 0
            num_elements = len(elements)
            if num_elements == 0:
                raise Exception(
                    "No matching elements found for selector {%s}!" % selector
                )
            elif num_elements < limit or limit == 0:
                limit = num_elements
            selector, by = self.__recalculate_selector(selector, by)
            css_selector = self.convert_to_css_selector(selector, by=by)
            last_css_chunk = css_selector.split(" ")[-1]
            if ":" in last_css_chunk:
                self.__js_click_all(css_selector)
                self.wait_for_ready_state_complete()
                return
            else:
                for i in range(1, limit + 1):
                    new_selector = css_selector + ":nth-of-type(%s)" % str(i)
                    if self.is_element_visible(new_selector):
                        self.__js_click(new_selector)
                        self.wait_for_ready_state_complete()
                return
        click_count = 0
        for element in elements:
            if limit and limit > 0 and click_count >= limit:
                return
            try:
                if element.is_displayed():
                    self.__scroll_to_element(element)
                    element.click()
                    click_count += 1
                    self.wait_for_ready_state_complete()
            except ECI_Exception:
                continue  # ElementClickInterceptedException (Overlay likely)
            except (StaleElementReferenceException, ENI_Exception):
                self.wait_for_ready_state_complete()
                time.sleep(0.12)
                try:
                    if element.is_displayed():
                        self.__scroll_to_element(element)
                        element.click()
                        click_count += 1
                        self.wait_for_ready_state_complete()
                except (StaleElementReferenceException, ENI_Exception):
                    return  # Probably on new page / Elements are all stale

    def click_nth_visible_element(
        self, selector, number, by=By.CSS_SELECTOR, timeout=None
    ):
        """Finds all matching page elements and clicks the nth visible one.
        Example:  self.click_nth_visible_element('[type="checkbox"]', 5)
                    (Clicks the 5th visible checkbox on the page.)"""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_ready_state_complete()
        self.wait_for_element_present(selector, by=by, timeout=timeout)
        elements = self.find_visible_elements(selector, by=by)
        if len(elements) < number:
            raise Exception(
                "Not enough matching {%s} elements of type {%s} to "
                "click number %s!" % (selector, by, number)
            )
        number = number - 1
        if number < 0:
            number = 0
        element = elements[number]
        try:
            self.__scroll_to_element(element)
            element.click()
        except (StaleElementReferenceException, ENI_Exception):
            time.sleep(0.12)
            self.wait_for_ready_state_complete()
            self.wait_for_element_present(selector, by=by, timeout=timeout)
            elements = self.find_visible_elements(selector, by=by)
            if len(elements) < number:
                raise Exception(
                    "Not enough matching {%s} elements of type {%s} to "
                    "click number %s!" % (selector, by, number)
                )
            number = number - 1
            if number < 0:
                number = 0
            element = elements[number]
            element.click()

    def click_if_visible(self, selector, by=By.CSS_SELECTOR):
        """If the page selector exists and is visible, clicks on the element.
        This method only clicks on the first matching element found.
        (Use click_visible_elements() to click all matching elements.)"""
        self.wait_for_ready_state_complete()
        if self.is_element_visible(selector, by=by):
            self.click(selector, by=by)

    def click_active_element(self):
        self.wait_for_ready_state_complete()
        pre_action_url = self.driver.current_url
        self.execute_script("document.activeElement.click();")
        if settings.WAIT_FOR_RSC_ON_CLICKS:
            self.wait_for_ready_state_complete()
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()

    def is_checked(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """Determines if a checkbox or a radio button element is checked.
        Returns True if the element is checked.
        Returns False if the element is not checked.
        If the element is not present on the page, raises an exception.
        If the element is not a checkbox or radio, raises an exception."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        kind = self.get_attribute(selector, "type", by=by, timeout=timeout)
        if kind != "checkbox" and kind != "radio":
            raise Exception("Expecting a checkbox or a radio button element!")
        is_checked = self.get_attribute(
            selector, "checked", by=by, timeout=timeout, hard_fail=False
        )
        if is_checked:
            return True
        else:  # (NoneType)
            return False

    def is_selected(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """ Same as is_checked() """
        return self.is_checked(selector, by=by, timeout=timeout)

    def check_if_unchecked(self, selector, by=By.CSS_SELECTOR):
        """ If a checkbox or radio button is not checked, will check it. """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        if not self.is_checked(selector, by=by):
            if self.is_element_visible(selector, by=by):
                self.click(selector, by=by)
            else:
                selector = self.convert_to_css_selector(selector, by=by)
                self.js_click(selector, by=By.CSS_SELECTOR)

    def select_if_unselected(self, selector, by=By.CSS_SELECTOR):
        """ Same as check_if_unchecked() """
        self.check_if_unchecked(selector, by=by)

    def uncheck_if_checked(self, selector, by=By.CSS_SELECTOR):
        """ If a checkbox is checked, will uncheck it. """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        if self.is_checked(selector, by=by):
            if self.is_element_visible(selector, by=by):
                self.click(selector, by=by)
            else:
                selector = self.convert_to_css_selector(selector, by=by)
                self.js_click(selector, by=By.CSS_SELECTOR)

    def unselect_if_selected(self, selector, by=By.CSS_SELECTOR):
        """ Same as uncheck_if_checked() """
        self.uncheck_if_checked(selector, by=by)

    def is_element_in_an_iframe(self, selector, by=By.CSS_SELECTOR):
        """Returns True if the selector's element is located in an iframe.
        Otherwise returns False."""
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        if self.is_element_present(selector, by=by):
            return False
        soup = self.get_beautiful_soup()
        iframe_list = soup.select("iframe")
        for iframe in iframe_list:
            iframe_identifier = None
            if iframe.has_attr("name") and len(iframe["name"]) > 0:
                iframe_identifier = iframe["name"]
            elif iframe.has_attr("id") and len(iframe["id"]) > 0:
                iframe_identifier = iframe["id"]
            elif iframe.has_attr("class") and len(iframe["class"]) > 0:
                iframe_class = " ".join(iframe["class"])
                iframe_identifier = '[class="%s"]' % iframe_class
            else:
                continue
            self.switch_to_frame(iframe_identifier)
            if self.is_element_present(selector, by=by):
                self.switch_to_default_content()
                return True
            self.switch_to_default_content()
        return False

    def switch_to_frame_of_element(self, selector, by=By.CSS_SELECTOR):
        """Set driver control to the iframe containing element (assuming the
        element is in a single-nested iframe) and returns the iframe name.
        If element is not in an iframe, returns None, and nothing happens.
        May not work if multiple iframes are nested within each other."""
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        if self.is_element_present(selector, by=by):
            return None
        soup = self.get_beautiful_soup()
        iframe_list = soup.select("iframe")
        for iframe in iframe_list:
            iframe_identifier = None
            if iframe.has_attr("name") and len(iframe["name"]) > 0:
                iframe_identifier = iframe["name"]
            elif iframe.has_attr("id") and len(iframe["id"]) > 0:
                iframe_identifier = iframe["id"]
            elif iframe.has_attr("class") and len(iframe["class"]) > 0:
                iframe_class = " ".join(iframe["class"])
                iframe_identifier = '[class="%s"]' % iframe_class
            else:
                continue
            try:
                self.switch_to_frame(iframe_identifier, timeout=1)
                if self.is_element_present(selector, by=by):
                    return iframe_identifier
            except Exception:
                pass
            self.switch_to_default_content()
        try:
            self.switch_to_frame(selector, timeout=1)
            return selector
        except Exception:
            if self.is_element_present(selector, by=by):
                return ""
            raise Exception(
                "Could not switch to iframe containing "
                "element {%s}!" % selector
            )

    def hover_on_element(self, selector, by=By.CSS_SELECTOR):
        self.__check_scope()
        original_selector = selector
        original_by = by
        selector, by = self.__recalculate_selector(selector, by)
        if page_utils.is_xpath_selector(selector):
            selector = self.convert_to_css_selector(selector, By.XPATH)
            by = By.CSS_SELECTOR
        self.wait_for_element_visible(
            selector, by=by, timeout=settings.SMALL_TIMEOUT
        )
        self.__demo_mode_highlight_if_active(original_selector, original_by)
        self.scroll_to(selector, by=by)
        time.sleep(0.05)  # Settle down from scrolling before hovering
        if self.browser != "chrome":
            return page_actions.hover_on_element(self.driver, selector)
        # Using Chrome
        # (Pure hover actions won't work on early chromedriver versions)
        try:
            return page_actions.hover_on_element(self.driver, selector)
        except WebDriverException as e:
            driver_capabilities = self.driver.__dict__["capabilities"]
            if "version" in driver_capabilities:
                chrome_version = driver_capabilities["version"]
            else:
                chrome_version = driver_capabilities["browserVersion"]
            major_chrome_version = chrome_version.split(".")[0]
            chrome_dict = self.driver.__dict__["capabilities"]["chrome"]
            chromedriver_version = chrome_dict["chromedriverVersion"]
            chromedriver_version = chromedriver_version.split(" ")[0]
            major_chromedriver_version = chromedriver_version.split(".")[0]
            install_sb = (
                "seleniumbase install chromedriver %s" % major_chrome_version
            )
            if major_chromedriver_version < major_chrome_version:
                # Upgrading the driver is required for performing hover actions
                message = (
                    "\n"
                    "You need a newer chromedriver to perform hover actions!\n"
                    "Your version of chromedriver is: %s\n"
                    "And your version of Chrome is: %s\n"
                    "You can fix this issue by running:\n>>> %s\n"
                    % (chromedriver_version, chrome_version, install_sb)
                )
                raise Exception(message)
            else:
                raise Exception(e)

    def hover_and_click(
        self,
        hover_selector,
        click_selector,
        hover_by=By.CSS_SELECTOR,
        click_by=By.CSS_SELECTOR,
        timeout=None,
    ):
        """When you want to hover over an element or dropdown menu,
        and then click an element that appears after that."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        original_selector = hover_selector
        original_by = hover_by
        hover_selector, hover_by = self.__recalculate_selector(
            hover_selector, hover_by
        )
        hover_selector = self.convert_to_css_selector(hover_selector, hover_by)
        hover_by = By.CSS_SELECTOR
        click_selector, click_by = self.__recalculate_selector(
            click_selector, click_by
        )
        dropdown_element = self.wait_for_element_visible(
            hover_selector, by=hover_by, timeout=timeout
        )
        self.__demo_mode_highlight_if_active(original_selector, original_by)
        self.scroll_to(hover_selector, by=hover_by)
        pre_action_url = self.driver.current_url
        outdated_driver = False
        element = None
        try:
            if self.mobile_emulator:
                # On mobile, click to hover the element
                dropdown_element.click()
            elif self.browser == "safari":
                # Use the workaround for hover-clicking on Safari
                raise Exception("This Exception will be caught.")
            else:
                page_actions.hover_element(self.driver, dropdown_element)
        except Exception:
            outdated_driver = True
            element = self.wait_for_element_present(
                click_selector, click_by, timeout
            )
            if click_by == By.LINK_TEXT:
                self.open(self.__get_href_from_link_text(click_selector))
            elif click_by == By.PARTIAL_LINK_TEXT:
                self.open(
                    self.__get_href_from_partial_link_text(click_selector)
                )
            else:
                self.js_click(click_selector, by=click_by)
        if outdated_driver:
            pass  # Already did the click workaround
        elif self.mobile_emulator:
            self.click(click_selector, by=click_by)
        elif not outdated_driver:
            element = page_actions.hover_and_click(
                self.driver,
                hover_selector,
                click_selector,
                hover_by,
                click_by,
                timeout,
            )
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()
        return element

    def hover_and_double_click(
        self,
        hover_selector,
        click_selector,
        hover_by=By.CSS_SELECTOR,
        click_by=By.CSS_SELECTOR,
        timeout=None,
    ):
        """When you want to hover over an element or dropdown menu,
        and then double-click an element that appears after that."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        original_selector = hover_selector
        original_by = hover_by
        hover_selector, hover_by = self.__recalculate_selector(
            hover_selector, hover_by
        )
        hover_selector = self.convert_to_css_selector(hover_selector, hover_by)
        hover_by = By.CSS_SELECTOR
        click_selector, click_by = self.__recalculate_selector(
            click_selector, click_by
        )
        dropdown_element = self.wait_for_element_visible(
            hover_selector, by=hover_by, timeout=timeout
        )
        self.__demo_mode_highlight_if_active(original_selector, original_by)
        self.scroll_to(hover_selector, by=hover_by)
        pre_action_url = self.driver.current_url
        outdated_driver = False
        element = None
        try:
            page_actions.hover_element(self.driver, dropdown_element)
        except Exception:
            outdated_driver = True
            element = self.wait_for_element_present(
                click_selector, click_by, timeout
            )
            if click_by == By.LINK_TEXT:
                self.open(self.__get_href_from_link_text(click_selector))
            elif click_by == By.PARTIAL_LINK_TEXT:
                self.open(
                    self.__get_href_from_partial_link_text(click_selector)
                )
            else:
                self.js_click(click_selector, click_by)
        if not outdated_driver:
            element = page_actions.hover_element_and_double_click(
                self.driver,
                dropdown_element,
                click_selector,
                click_by=By.CSS_SELECTOR,
                timeout=timeout,
            )
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()
        return element

    def drag_and_drop(
        self,
        drag_selector,
        drop_selector,
        drag_by=By.CSS_SELECTOR,
        drop_by=By.CSS_SELECTOR,
        timeout=None,
    ):
        """ Drag and drop an element from one selector to another. """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        drag_selector, drag_by = self.__recalculate_selector(
            drag_selector, drag_by
        )
        drop_selector, drop_by = self.__recalculate_selector(
            drop_selector, drop_by
        )
        drag_element = self.wait_for_element_visible(
            drag_selector, by=drag_by, timeout=timeout
        )
        self.__demo_mode_highlight_if_active(drag_selector, drag_by)
        self.wait_for_element_visible(
            drop_selector, by=drop_by, timeout=timeout
        )
        self.__demo_mode_highlight_if_active(drop_selector, drop_by)
        self.scroll_to(drag_selector, by=drag_by)
        drag_selector = self.convert_to_css_selector(drag_selector, drag_by)
        drop_selector = self.convert_to_css_selector(drop_selector, drop_by)
        drag_and_drop_script = js_utils.get_drag_and_drop_script()
        self.safe_execute_script(
            drag_and_drop_script
            + (
                "$('%s').simulateDragDrop("
                "{dropTarget: "
                "'%s'});" % (drag_selector, drop_selector)
            )
        )
        if self.demo_mode:
            self.__demo_mode_pause_if_active()
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()
        return drag_element

    def drag_and_drop_with_offset(
        self, selector, x, y, by=By.CSS_SELECTOR, timeout=None
    ):
        """ Drag and drop an element to an {X,Y}-offset location. """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        css_selector = self.convert_to_css_selector(selector, by=by)
        element = self.wait_for_element_visible(css_selector, timeout=timeout)
        self.__demo_mode_highlight_if_active(css_selector, By.CSS_SELECTOR)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        script = js_utils.get_drag_and_drop_with_offset_script(
            css_selector, x, y
        )
        self.safe_execute_script(script)
        if self.demo_mode:
            self.__demo_mode_pause_if_active()
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()
        return element

    def __select_option(
        self,
        dropdown_selector,
        option,
        dropdown_by=By.CSS_SELECTOR,
        option_by="text",
        timeout=None,
    ):
        """Selects an HTML <select> option by specification.
        Option specifications are by "text", "index", or "value".
        Defaults to "text" if option_by is unspecified or unknown."""
        from selenium.webdriver.support.ui import Select

        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        dropdown_selector, dropdown_by = self.__recalculate_selector(
            dropdown_selector, dropdown_by
        )
        self.wait_for_ready_state_complete()
        element = self.wait_for_element_present(
            dropdown_selector, by=dropdown_by, timeout=timeout
        )
        if self.is_element_visible(dropdown_selector, by=dropdown_by):
            self.__demo_mode_highlight_if_active(
                dropdown_selector, dropdown_by
            )
        pre_action_url = self.driver.current_url
        try:
            if option_by == "index":
                Select(element).select_by_index(option)
            elif option_by == "value":
                Select(element).select_by_value(option)
            else:
                Select(element).select_by_visible_text(option)
        except (StaleElementReferenceException, ENI_Exception):
            self.wait_for_ready_state_complete()
            time.sleep(0.14)
            element = self.wait_for_element_present(
                dropdown_selector, by=dropdown_by, timeout=timeout
            )
            if option_by == "index":
                Select(element).select_by_index(option)
            elif option_by == "value":
                Select(element).select_by_value(option)
            else:
                Select(element).select_by_visible_text(option)
        if settings.WAIT_FOR_RSC_ON_CLICKS:
            self.wait_for_ready_state_complete()
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()

    def select_option_by_text(
        self,
        dropdown_selector,
        option,
        dropdown_by=By.CSS_SELECTOR,
        timeout=None,
    ):
        """Selects an HTML <select> option by option text.
        @Params
        dropdown_selector - the <select> selector.
        option - the text of the option.
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.__select_option(
            dropdown_selector,
            option,
            dropdown_by=dropdown_by,
            option_by="text",
            timeout=timeout,
        )

    def select_option_by_index(
        self,
        dropdown_selector,
        option,
        dropdown_by=By.CSS_SELECTOR,
        timeout=None,
    ):
        """Selects an HTML <select> option by option index.
        @Params
        dropdown_selector - the <select> selector.
        option - the index number of the option.
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.__select_option(
            dropdown_selector,
            option,
            dropdown_by=dropdown_by,
            option_by="index",
            timeout=timeout,
        )

    def select_option_by_value(
        self,
        dropdown_selector,
        option,
        dropdown_by=By.CSS_SELECTOR,
        timeout=None,
    ):
        """Selects an HTML <select> option by option value.
        @Params
        dropdown_selector - the <select> selector.
        option - the value property of the option.
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.__select_option(
            dropdown_selector,
            option,
            dropdown_by=dropdown_by,
            option_by="value",
            timeout=timeout,
        )

    def load_html_string(self, html_string, new_page=True):
        """Loads an HTML string into the web browser.
        If new_page==True, the page will switch to: "data:text/html,"
        If new_page==False, will load HTML into the current page."""
        self.__check_scope()
        soup = self.get_beautiful_soup(html_string)
        found_base = False
        links = soup.findAll("link")
        href = None
        for link in links:
            if link.get("rel") == ["canonical"] and link.get("href"):
                found_base = True
                href = link.get("href")
                href = self.get_domain_url(href)
        if (
            found_base
            and html_string.count("<head>") == 1
            and html_string.count("<base") == 0
        ):
            html_string = html_string.replace(
                "<head>", '<head><base href="%s">' % href
            )
        elif not found_base:
            bases = soup.findAll("base")
            for base in bases:
                if base.get("href"):
                    href = base.get("href")
        if href:
            html_string = html_string.replace('base: "."', 'base: "%s"' % href)

        soup = self.get_beautiful_soup(html_string)
        scripts = soup.findAll("script")
        for script in scripts:
            if script.get("type") != "application/json":
                html_string = html_string.replace(str(script), "")
        soup = self.get_beautiful_soup(html_string)

        found_head = False
        found_body = False
        html_head = None
        html_body = None
        if soup.head and len(str(soup.head)) > 12:
            found_head = True
            html_head = str(soup.head)
            html_head = re.escape(html_head)
            html_head = self.__escape_quotes_if_needed(html_head)
            html_head = html_head.replace("\\ ", " ")
        if soup.body and len(str(soup.body)) > 12:
            found_body = True
            html_body = str(soup.body)
            html_body = html_body.replace("\xc2\xa0", "&#xA0;")
            html_body = html_body.replace("\xc2\xa1", "&#xA1;")
            html_body = html_body.replace("\xc2\xa9", "&#xA9;")
            html_body = html_body.replace("\xc2\xb7", "&#xB7;")
            html_body = html_body.replace("\xc2\xbf", "&#xBF;")
            html_body = html_body.replace("\xc3\x97", "&#xD7;")
            html_body = html_body.replace("\xc3\xb7", "&#xF7;")
            html_body = re.escape(html_body)
            html_body = self.__escape_quotes_if_needed(html_body)
            html_body = html_body.replace("\\ ", " ")
        html_string = re.escape(html_string)
        html_string = self.__escape_quotes_if_needed(html_string)
        html_string = html_string.replace("\\ ", " ")

        if new_page:
            self.open("data:text/html,")
        inner_head = """document.getElementsByTagName("head")[0].innerHTML"""
        inner_body = """document.getElementsByTagName("body")[0].innerHTML"""
        if not found_body:
            self.execute_script('''%s = \"%s\"''' % (inner_body, html_string))
        elif found_body and not found_head:
            self.execute_script('''%s = \"%s\"''' % (inner_body, html_body))
        elif found_body and found_head:
            self.execute_script('''%s = \"%s\"''' % (inner_head, html_head))
            self.execute_script('''%s = \"%s\"''' % (inner_body, html_body))
        else:
            raise Exception("Logic Error!")

        for script in scripts:
            js_code = script.string
            js_src = script.get("src")
            if js_code and script.get("type") != "application/json":
                js_code_lines = js_code.split("\n")
                new_lines = []
                for line in js_code_lines:
                    line = line.strip()
                    new_lines.append(line)
                js_code = "\n".join(new_lines)
                js_code = re.escape(js_code)
                js_utils.add_js_code(self.driver, js_code)
            elif js_src:
                js_utils.add_js_link(self.driver, js_src)
            else:
                pass

    def set_content(self, html_string, new_page=False):
        """ Same as load_html_string(), but "new_page" defaults to False. """
        self.load_html_string(html_string, new_page=new_page)

    def load_html_file(self, html_file, new_page=True):
        """Loads a local html file into the browser from a relative file path.
        If new_page==True, the page will switch to: "data:text/html,"
        If new_page==False, will load HTML into the current page.
        Local images and other local src content WILL BE IGNORED.
        """
        self.__check_scope()
        if self.__looks_like_a_page_url(html_file):
            self.open(html_file)
            return
        if len(html_file) < 6 or not html_file.endswith(".html"):
            raise Exception('Expecting a ".html" file!')
        abs_path = os.path.abspath(".")
        file_path = None
        if abs_path in html_file:
            file_path = html_file
        else:
            file_path = abs_path + "/%s" % html_file
        html_string = None
        with open(file_path, "r") as f:
            html_string = f.read().strip()
        self.load_html_string(html_string, new_page)

    def open_html_file(self, html_file):
        """Opens a local html file into the browser from a relative file path.
        The URL displayed in the web browser will start with "file://".
        """
        self.__check_scope()
        if self.__looks_like_a_page_url(html_file):
            self.open(html_file)
            return
        if len(html_file) < 6 or not html_file.endswith(".html"):
            raise Exception('Expecting a ".html" file!')
        abs_path = os.path.abspath(".")
        file_path = None
        if abs_path in html_file:
            file_path = html_file
        else:
            file_path = abs_path + "/%s" % html_file
        self.open("file://" + file_path)

    def execute_script(self, script, *args, **kwargs):
        self.__check_scope()
        return self.driver.execute_script(script, *args, **kwargs)

    def execute_async_script(self, script, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.EXTREME_TIMEOUT
        return js_utils.execute_async_script(self.driver, script, timeout)

    def safe_execute_script(self, script, *args, **kwargs):
        """When executing a script that contains a jQuery command,
        it's important that the jQuery library has been loaded first.
        This method will load jQuery if it wasn't already loaded."""
        self.__check_scope()
        if not js_utils.is_jquery_activated(self.driver):
            self.activate_jquery()
        return self.driver.execute_script(script, *args, **kwargs)

    def set_window_rect(self, x, y, width, height):
        self.__check_scope()
        self.driver.set_window_rect(x, y, width, height)
        self.__demo_mode_pause_if_active()

    def set_window_size(self, width, height):
        self.__check_scope()
        self.driver.set_window_size(width, height)
        self.__demo_mode_pause_if_active()

    def maximize_window(self):
        self.__check_scope()
        self.driver.maximize_window()
        self.__demo_mode_pause_if_active()

    def switch_to_frame(self, frame, timeout=None):
        """Wait for an iframe to appear, and switch to it. This should be
        usable as a drop-in replacement for driver.switch_to.frame().
        The iframe identifier can be a selector, an index, an id, a name,
        or a web element, but scrolling to the iframe first will only occur
        for visible iframes with a string selector.
        @Params
        frame - the frame element, name, id, index, or selector
        timeout - the time to wait for the alert in seconds
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        if type(frame) is str and self.is_element_visible(frame):
            try:
                self.scroll_to(frame, timeout=1)
            except Exception:
                pass
        if self.recorder_mode and self._rec_overrides_switch:
            url = self.get_current_url()
            if url and len(url) > 0:
                if ("http:") in url or ("https:") in url or ("file:") in url:
                    r_a = self.get_session_storage_item("recorder_activated")
                    if r_a == "yes":
                        time_stamp = self.execute_script("return Date.now();")
                        action = ["sk_op", "", "", time_stamp]
                        self.__extra_actions.append(action)
                        self.__set_c_from_switch = True
                        self.set_content_to_frame(frame, timeout=timeout)
                        self.__set_c_from_switch = False
                        time_stamp = self.execute_script("return Date.now();")
                        origin = self.get_origin()
                        action = ["sw_fr", frame, origin, time_stamp]
                        self.__extra_actions.append(action)
                        return
        page_actions.switch_to_frame(self.driver, frame, timeout)

    def switch_to_default_content(self):
        """Brings driver control outside the current iframe.
        (If the driver control is inside an iframe, the driver control
        will be set to one level above the current frame. If the driver
        control is not currently in an iframe, nothing will happen.)"""
        self.__check_scope()
        if self.recorder_mode and self._rec_overrides_switch:
            url = self.get_current_url()
            if url and len(url) > 0:
                if ("http:") in url or ("https:") in url or ("file:") in url:
                    r_a = self.get_session_storage_item("recorder_activated")
                    if r_a == "yes":
                        self.__set_c_from_switch = True
                        self.set_content_to_default()
                        self.__set_c_from_switch = False
                        time_stamp = self.execute_script("return Date.now();")
                        origin = self.get_origin()
                        action = ["sw_dc", "", origin, time_stamp]
                        self.__extra_actions.append(action)
                        return
        self.driver.switch_to.default_content()

    def set_content_to_frame(self, frame, timeout=None):
        """Replaces the page html with an iframe's html from that page.
        If the iFrame contains an "src" field that includes a valid URL,
        then instead of replacing the current html, this method will then
        open up the "src" URL of the iFrame in a new browser tab.
        To return to default content, use: self.set_content_to_default().
        This method also sets the state of the browser window so that the
        self.set_content_to_default() method can bring the user back to
        the original content displayed, which is similar to how the methods
        self.switch_to_frame(frame) and self.switch_to_default_content()
        work together to get the user into frames and out of all of them.
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        current_url = self.get_current_url()
        c_tab = self.driver.current_window_handle
        current_page_source = self.get_page_source()
        self.execute_script("document.cframe_swap = 0;")
        page_actions.switch_to_frame(self.driver, frame, timeout)
        iframe_html = self.get_page_source()
        self.driver.switch_to.default_content()
        self.wait_for_ready_state_complete()
        frame_found = False
        o_frame = frame
        if self.is_element_present(frame):
            frame_found = True
        elif " " not in frame:
            frame = 'iframe[name="%s"]' % frame
            if self.is_element_present(frame):
                frame_found = True
        url = None
        if frame_found:
            url = self.execute_script(
                """return document.querySelector('%s').src;""" % frame
            )
            if url and len(url) > 0:
                if ("http:") in url or ("https:") in url or ("file:") in url:
                    pass
                else:
                    url = None
        cframe_tab = False
        if url:
            cframe_tab = True
        self.__page_sources.append([current_url, current_page_source, c_tab])

        if self.recorder_mode and not self.__set_c_from_switch:
            time_stamp = self.execute_script("return Date.now();")
            action = ["sk_op", "", "", time_stamp]
            self.__extra_actions.append(action)

        if cframe_tab:
            self.execute_script("document.cframe_tab = 1;")
            self.open_new_window(switch_to=True)
            self.open(url)
            self.execute_script("document.cframe_tab = 1;")
        else:
            self.set_content(iframe_html)
            if not self.execute_script("return document.cframe_swap;"):
                self.execute_script("document.cframe_swap = 1;")
            else:
                self.execute_script("document.cframe_swap += 1;")

        if self.recorder_mode and not self.__set_c_from_switch:
            time_stamp = self.execute_script("return Date.now();")
            action = ["s_c_f", o_frame, "", time_stamp]
            self.__extra_actions.append(action)

    def set_content_to_default(self, nested=True):
        """After using self.set_content_to_frame(), this reverts the page back.
        If self.set_content_to_frame() hasn't been called here, only refreshes.
        If "nested" is set to False when the content was set to nested iFrames,
        then the control will only move above the last iFrame that was entered.
        """
        self.__check_scope()
        swap_cnt = self.execute_script("return document.cframe_swap;")
        tab_sta = self.execute_script("return document.cframe_tab;")

        if self.recorder_mode and not self.__set_c_from_switch:
            time_stamp = self.execute_script("return Date.now();")
            action = ["sk_op", "", "", time_stamp]
            self.__extra_actions.append(action)

        if nested:
            if (
                len(self.__page_sources) > 0
                and (
                    (swap_cnt and int(swap_cnt) > 0)
                    or (tab_sta and int(tab_sta) > 0)
                )
            ):
                past_content = self.__page_sources[0]
                past_url = past_content[0]
                past_source = past_content[1]
                past_tab = past_content[2]
                current_tab = self.driver.current_window_handle
                if not current_tab == past_tab:
                    if past_tab in self.driver.window_handles:
                        self.switch_to_window(past_tab)
                url_of_past_tab = self.get_current_url()
                if url_of_past_tab == past_url:
                    self.set_content(past_source)
                else:
                    self.refresh_page()
            else:
                self.refresh_page()
            self.execute_script("document.cframe_swap = 0;")
            self.__page_sources = []
        else:
            just_refresh = False
            if swap_cnt and int(swap_cnt) > 0 and len(self.__page_sources) > 0:
                self.execute_script("document.cframe_swap -= 1;")
                current_url = self.get_current_url()
                past_content = self.__page_sources.pop()
                past_url = past_content[0]
                past_source = past_content[1]
                if current_url == past_url:
                    self.set_content(past_source)
                else:
                    just_refresh = True
            elif tab_sta and int(tab_sta) > 0 and len(self.__page_sources) > 0:
                past_content = self.__page_sources.pop()
                past_tab = past_content[2]
                if past_tab in self.driver.window_handles:
                    self.switch_to_window(past_tab)
                else:
                    just_refresh = True
            else:
                just_refresh = True
            if just_refresh:
                self.refresh_page()
                self.execute_script("document.cframe_swap = 0;")
                self.__page_sources = []

        if self.recorder_mode and not self.__set_c_from_switch:
            time_stamp = self.execute_script("return Date.now();")
            action = ["s_c_d", nested, "", time_stamp]
            self.__extra_actions.append(action)

    def open_new_window(self, switch_to=True):
        """ Opens a new browser tab/window and switches to it by default. """
        self.__check_scope()
        self.driver.execute_script("window.open('');")
        time.sleep(0.01)
        if switch_to:
            self.switch_to_newest_window()
            time.sleep(0.01)
            if self.browser == "safari":
                self.wait_for_ready_state_complete()

    def switch_to_window(self, window, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        page_actions.switch_to_window(self.driver, window, timeout)

    def switch_to_default_window(self):
        self.switch_to_window(0)

    def switch_to_newest_window(self):
        self.switch_to_window(len(self.driver.window_handles) - 1)

    def get_new_driver(
        self,
        browser=None,
        headless=None,
        locale_code=None,
        protocol=None,
        servername=None,
        port=None,
        proxy=None,
        agent=None,
        switch_to=True,
        cap_file=None,
        cap_string=None,
        recorder_ext=None,
        disable_csp=None,
        enable_ws=None,
        enable_sync=None,
        use_auto_ext=None,
        no_sandbox=None,
        disable_gpu=None,
        incognito=None,
        guest_mode=None,
        devtools=None,
        remote_debug=None,
        swiftshader=None,
        ad_block_on=None,
        block_images=None,
        chromium_arg=None,
        firefox_arg=None,
        firefox_pref=None,
        user_data_dir=None,
        extension_zip=None,
        extension_dir=None,
        is_mobile=None,
        d_width=None,
        d_height=None,
        d_p_r=None,
    ):
        """This method spins up an extra browser for tests that require
        more than one. The first browser is already provided by tests
        that import base_case.BaseCase from seleniumbase. If parameters
        aren't specified, the method uses the same as the default driver.
        @Params
        browser - the browser to use. (Ex: "chrome", "firefox")
        headless - the option to run webdriver in headless mode
        locale_code - the Language Locale Code for the web browser
        protocol - if using a Selenium Grid, set the host protocol here
        servername - if using a Selenium Grid, set the host address here
        port - if using a Selenium Grid, set the host port here
        proxy - if using a proxy server, specify the "host:port" combo here
        switch_to - the option to switch to the new driver (default = True)
        cap_file - the file containing desired capabilities for the browser
        cap_string - the string with desired capabilities for the browser
        recorder_ext - the option to enable the SBase Recorder extension
        disable_csp - an option to disable Chrome's Content Security Policy
        enable_ws - the option to enable the Web Security feature (Chrome)
        enable_sync - the option to enable the Chrome Sync feature (Chrome)
        use_auto_ext - the option to enable Chrome's Automation Extension
        no_sandbox - the option to enable the "No-Sandbox" feature (Chrome)
        disable_gpu - the option to enable Chrome's "Disable GPU" feature
        incognito - the option to enable Chrome's Incognito mode (Chrome)
        guest - the option to enable Chrome's Guest mode (Chrome)
        devtools - the option to open Chrome's DevTools on start (Chrome)
        remote_debug - the option to enable Chrome's Remote Debugger
        swiftshader - the option to use Chrome's swiftshader (Chrome-only)
        ad_block_on - the option to block ads from loading (Chromium-only)
        block_images - the option to block images from loading (Chrome)
        chromium_arg - the option to add a Chromium arg to Chrome/Edge
        firefox_arg - the option to add a Firefox arg to Firefox runs
        firefox_pref - the option to add a Firefox pref:value set (Firefox)
        user_data_dir - Chrome's User Data Directory to use (Chrome-only)
        extension_zip - A Chrome Extension ZIP file to use (Chrome-only)
        extension_dir - A Chrome Extension folder to use (Chrome-only)
        is_mobile - the option to use the mobile emulator (Chrome-only)
        d_width - the device width of the mobile emulator (Chrome-only)
        d_height - the device height of the mobile emulator (Chrome-only)
        d_p_r - the device pixel ratio of the mobile emulator (Chrome-only)
        """
        self.__check_scope()
        if self.browser == "remote" and self.servername == "localhost":
            raise Exception(
                'Cannot use "remote" browser driver on localhost!'
                " Did you mean to connect to a remote Grid server"
                " such as BrowserStack or Sauce Labs? In that"
                ' case, you must specify the "server" and "port"'
                " parameters on the command line! "
                "Example: "
                "--server=user:key@hub.browserstack.com --port=80"
            )
        browserstack_ref = "https://browserstack.com/automate/capabilities"
        sauce_labs_ref = (
            "https://wiki.saucelabs.com/display/DOCS/Platform+Configurator#/"
        )
        if self.browser == "remote" and not (self.cap_file or self.cap_string):
            raise Exception(
                "Need to specify a desired capabilities file when "
                'using "--browser=remote". Add "--cap_file=FILE". '
                "File should be in the Python format used by: "
                "%s OR "
                "%s "
                "See SeleniumBase/examples/sample_cap_file_BS.py "
                "and SeleniumBase/examples/sample_cap_file_SL.py"
                % (browserstack_ref, sauce_labs_ref)
            )
        if browser is None:
            browser = self.browser
        browser_name = browser
        if headless is None:
            headless = self.headless
        if locale_code is None:
            locale_code = self.locale_code
        if protocol is None:
            protocol = self.protocol
        if servername is None:
            servername = self.servername
        if port is None:
            port = self.port
        use_grid = False
        if servername != "localhost":
            # Use Selenium Grid (Use "127.0.0.1" for localhost Grid)
            use_grid = True
        proxy_string = proxy
        if proxy_string is None:
            proxy_string = self.proxy_string
        user_agent = agent
        if user_agent is None:
            user_agent = self.user_agent
        if recorder_ext is None:
            recorder_ext = self.recorder_ext
        if disable_csp is None:
            disable_csp = self.disable_csp
        if enable_ws is None:
            enable_ws = self.enable_ws
        if enable_sync is None:
            enable_sync = self.enable_sync
        if use_auto_ext is None:
            use_auto_ext = self.use_auto_ext
        if no_sandbox is None:
            no_sandbox = self.no_sandbox
        if disable_gpu is None:
            disable_gpu = self.disable_gpu
        if incognito is None:
            incognito = self.incognito
        if guest_mode is None:
            guest_mode = self.guest_mode
        if devtools is None:
            devtools = self.devtools
        if remote_debug is None:
            remote_debug = self.remote_debug
        if swiftshader is None:
            swiftshader = self.swiftshader
        if ad_block_on is None:
            ad_block_on = self.ad_block_on
        if block_images is None:
            block_images = self.block_images
        if chromium_arg is None:
            chromium_arg = self.chromium_arg
        if firefox_arg is None:
            firefox_arg = self.firefox_arg
        if firefox_pref is None:
            firefox_pref = self.firefox_pref
        if user_data_dir is None:
            user_data_dir = self.user_data_dir
        if extension_zip is None:
            extension_zip = self.extension_zip
        if extension_dir is None:
            extension_dir = self.extension_dir
        test_id = self.__get_test_id()
        if cap_file is None:
            cap_file = self.cap_file
        if cap_string is None:
            cap_string = self.cap_string
        if is_mobile is None:
            is_mobile = self.mobile_emulator
        if d_width is None:
            d_width = self.__device_width
        if d_height is None:
            d_height = self.__device_height
        if d_p_r is None:
            d_p_r = self.__device_pixel_ratio
        valid_browsers = constants.ValidBrowsers.valid_browsers
        if browser_name not in valid_browsers:
            raise Exception(
                "Browser: {%s} is not a valid browser option. "
                "Valid options = {%s}" % (browser, valid_browsers)
            )
        # Launch a web browser
        from seleniumbase.core import browser_launcher

        new_driver = browser_launcher.get_driver(
            browser_name=browser_name,
            headless=headless,
            locale_code=locale_code,
            use_grid=use_grid,
            protocol=protocol,
            servername=servername,
            port=port,
            proxy_string=proxy_string,
            user_agent=user_agent,
            cap_file=cap_file,
            cap_string=cap_string,
            recorder_ext=recorder_ext,
            disable_csp=disable_csp,
            enable_ws=enable_ws,
            enable_sync=enable_sync,
            use_auto_ext=use_auto_ext,
            no_sandbox=no_sandbox,
            disable_gpu=disable_gpu,
            incognito=incognito,
            guest_mode=guest_mode,
            devtools=devtools,
            remote_debug=remote_debug,
            swiftshader=swiftshader,
            ad_block_on=ad_block_on,
            block_images=block_images,
            chromium_arg=chromium_arg,
            firefox_arg=firefox_arg,
            firefox_pref=firefox_pref,
            user_data_dir=user_data_dir,
            extension_zip=extension_zip,
            extension_dir=extension_dir,
            test_id=test_id,
            mobile_emulator=is_mobile,
            device_width=d_width,
            device_height=d_height,
            device_pixel_ratio=d_p_r,
        )
        self._drivers_list.append(new_driver)
        self.__driver_browser_map[new_driver] = browser_name
        if switch_to:
            self.driver = new_driver
            self.browser = browser_name
            if self.headless or self.xvfb:
                # Make sure the invisible browser window is big enough
                width = settings.HEADLESS_START_WIDTH
                height = settings.HEADLESS_START_HEIGHT
                try:
                    self.driver.set_window_size(width, height)
                    self.wait_for_ready_state_complete()
                except Exception:
                    # This shouldn't fail, but in case it does,
                    # get safely through setUp() so that
                    # WebDrivers can get closed during tearDown().
                    pass
            else:
                if self.browser == "chrome" or self.browser == "edge":
                    width = settings.CHROME_START_WIDTH
                    height = settings.CHROME_START_HEIGHT
                    try:
                        if self.maximize_option:
                            self.driver.maximize_window()
                        else:
                            self.driver.set_window_size(width, height)
                        self.wait_for_ready_state_complete()
                    except Exception:
                        pass  # Keep existing browser resolution
                elif self.browser == "firefox":
                    width = settings.CHROME_START_WIDTH
                    try:
                        if self.maximize_option:
                            self.driver.maximize_window()
                        else:
                            self.driver.set_window_size(width, 720)
                        self.wait_for_ready_state_complete()
                    except Exception:
                        pass  # Keep existing browser resolution
                elif self.browser == "safari":
                    width = settings.CHROME_START_WIDTH
                    if self.maximize_option:
                        try:
                            self.driver.maximize_window()
                            self.wait_for_ready_state_complete()
                        except Exception:
                            pass  # Keep existing browser resolution
                    else:
                        try:
                            self.driver.set_window_rect(10, 30, width, 630)
                        except Exception:
                            pass
                elif self.browser == "opera":
                    width = settings.CHROME_START_WIDTH
                    if self.maximize_option:
                        try:
                            self.driver.maximize_window()
                            self.wait_for_ready_state_complete()
                        except Exception:
                            pass  # Keep existing browser resolution
                    else:
                        try:
                            self.driver.set_window_rect(10, 30, width, 700)
                        except Exception:
                            pass
            if self.start_page and len(self.start_page) >= 4:
                if page_utils.is_valid_url(self.start_page):
                    self.open(self.start_page)
                else:
                    new_start_page = "http://" + self.start_page
                    if page_utils.is_valid_url(new_start_page):
                        self.open(new_start_page)
        return new_driver

    def switch_to_driver(self, driver):
        """Sets self.driver to the specified driver.
        You may need this if using self.get_new_driver() in your code."""
        self.__check_scope()
        self.driver = driver
        if self.driver in self.__driver_browser_map:
            self.browser = self.__driver_browser_map[self.driver]

    def switch_to_default_driver(self):
        """ Sets self.driver to the default/original driver. """
        self.__check_scope()
        self.driver = self._default_driver
        if self.driver in self.__driver_browser_map:
            self.browser = self.__driver_browser_map[self.driver]

    def save_screenshot(
        self, name, folder=None, selector=None, by=By.CSS_SELECTOR
    ):
        """
        Saves a screenshot of the current page.
        If no folder is specified, uses the folder where pytest was called.
        The screenshot will include the entire page unless a selector is given.
        If a provided selector is not found, then takes a full-page screenshot.
        If the folder provided doesn't exist, it will get created.
        The screenshot will be in PNG format: (*.png)
        """
        self.wait_for_ready_state_complete()
        if selector and by:
            selector, by = self.__recalculate_selector(selector, by)
            if page_actions.is_element_present(self.driver, selector, by):
                return page_actions.save_screenshot(
                    self.driver, name, folder, selector, by
                )
        return page_actions.save_screenshot(self.driver, name, folder)

    def save_screenshot_to_logs(
        self, name=None, selector=None, by=By.CSS_SELECTOR
    ):
        """Saves a screenshot of the current page to the "latest_logs" folder.
        Naming is automatic:
            If NO NAME provided: "_1_screenshot.png", "_2_screenshot.png", etc.
            If NAME IS provided, it becomes: "_1_name.png", "_2_name.png", etc.
        The screenshot will include the entire page unless a selector is given.
        If a provided selector is not found, then takes a full-page screenshot.
        (The last_page / failure screenshot is always "screenshot.png")
        The screenshot will be in PNG format."""
        self.wait_for_ready_state_complete()
        test_id = self.__get_test_id()
        test_logpath = self.log_path + "/" + test_id
        self.__create_log_path_as_needed(test_logpath)
        if name:
            name = str(name)
        self.__screenshot_count += 1
        if not name or len(name) == 0:
            name = "_%s_screenshot.png" % self.__screenshot_count
        else:
            pre_name = "_%s_" % self.__screenshot_count
            if len(name) >= 4 and name[-4:].lower() == ".png":
                name = name[:-4]
                if len(name) == 0:
                    name = "screenshot"
            name = "%s%s.png" % (pre_name, name)
        if selector and by:
            selector, by = self.__recalculate_selector(selector, by)
            if page_actions.is_element_present(self.driver, selector, by):
                return page_actions.save_screenshot(
                    self.driver, name, test_logpath, selector, by
                )
        return page_actions.save_screenshot(self.driver, name, test_logpath)

    def save_page_source(self, name, folder=None):
        """Saves the page HTML to the current directory (or given subfolder).
        If the folder specified doesn't exist, it will get created.
        @Params
        name - The file name to save the current page's HTML to.
        folder - The folder to save the file to. (Default = current folder)
        """
        self.wait_for_ready_state_complete()
        return page_actions.save_page_source(self.driver, name, folder)

    def save_cookies(self, name="cookies.txt"):
        """ Saves the page cookies to the "saved_cookies" folder. """
        self.wait_for_ready_state_complete()
        cookies = self.driver.get_cookies()
        json_cookies = json.dumps(cookies)
        if name.endswith("/"):
            raise Exception("Invalid filename for Cookies!")
        if "/" in name:
            name = name.split("/")[-1]
        if len(name) < 1:
            raise Exception("Filename for Cookies is too short!")
        if not name.endswith(".txt"):
            name = name + ".txt"
        folder = constants.SavedCookies.STORAGE_FOLDER
        abs_path = os.path.abspath(".")
        file_path = abs_path + "/%s" % folder
        if not os.path.exists(file_path):
            os.makedirs(file_path)
        cookies_file_path = "%s/%s" % (file_path, name)
        cookies_file = codecs.open(cookies_file_path, "w+", encoding="utf-8")
        cookies_file.writelines(json_cookies)
        cookies_file.close()

    def load_cookies(self, name="cookies.txt"):
        """ Loads the page cookies from the "saved_cookies" folder. """
        self.wait_for_ready_state_complete()
        if name.endswith("/"):
            raise Exception("Invalid filename for Cookies!")
        if "/" in name:
            name = name.split("/")[-1]
        if len(name) < 1:
            raise Exception("Filename for Cookies is too short!")
        if not name.endswith(".txt"):
            name = name + ".txt"
        folder = constants.SavedCookies.STORAGE_FOLDER
        abs_path = os.path.abspath(".")
        file_path = abs_path + "/%s" % folder
        cookies_file_path = "%s/%s" % (file_path, name)
        json_cookies = None
        with open(cookies_file_path, "r") as f:
            json_cookies = f.read().strip()
        cookies = json.loads(json_cookies)
        for cookie in cookies:
            if "expiry" in cookie:
                del cookie["expiry"]
            self.driver.add_cookie(cookie)

    def delete_all_cookies(self):
        """Deletes all cookies in the web browser.
        Does NOT delete the saved cookies file."""
        self.wait_for_ready_state_complete()
        self.driver.delete_all_cookies()

    def delete_saved_cookies(self, name="cookies.txt"):
        """Deletes the cookies file from the "saved_cookies" folder.
        Does NOT delete the cookies from the web browser."""
        self.wait_for_ready_state_complete()
        if name.endswith("/"):
            raise Exception("Invalid filename for Cookies!")
        if "/" in name:
            name = name.split("/")[-1]
        if len(name) < 1:
            raise Exception("Filename for Cookies is too short!")
        if not name.endswith(".txt"):
            name = name + ".txt"
        folder = constants.SavedCookies.STORAGE_FOLDER
        abs_path = os.path.abspath(".")
        file_path = abs_path + "/%s" % folder
        cookies_file_path = "%s/%s" % (file_path, name)
        if os.path.exists(cookies_file_path):
            if cookies_file_path.endswith(".txt"):
                os.remove(cookies_file_path)

    def wait_for_ready_state_complete(self, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.EXTREME_TIMEOUT
        if self.timeout_multiplier and timeout == settings.EXTREME_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        is_ready = js_utils.wait_for_ready_state_complete(self.driver, timeout)
        self.wait_for_angularjs(timeout=settings.MINI_TIMEOUT)
        if self.js_checking_on:
            self.assert_no_js_errors()
        if self.ad_block_on and (self.headless or not self.is_chromium()):
            # For Chromium browsers in headed mode, the extension is used
            current_url = self.get_current_url()
            if not current_url == self.__last_page_load_url:
                if page_actions.is_element_present(
                    self.driver, "iframe", By.CSS_SELECTOR
                ):
                    self.ad_block()
                self.__last_page_load_url = current_url
        return is_ready

    def wait_for_angularjs(self, timeout=None, **kwargs):
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        js_utils.wait_for_angularjs(self.driver, timeout, **kwargs)

    def sleep(self, seconds):
        self.__check_scope()
        if not sb_config.time_limit:
            time.sleep(seconds)
        elif seconds <= 0.3:
            shared_utils.check_if_time_limit_exceeded()
            time.sleep(seconds)
            shared_utils.check_if_time_limit_exceeded()
        else:
            start_ms = time.time() * 1000.0
            stop_ms = start_ms + (seconds * 1000.0)
            for x in range(int(seconds * 5)):
                shared_utils.check_if_time_limit_exceeded()
                now_ms = time.time() * 1000.0
                if now_ms >= stop_ms:
                    break
                time.sleep(0.2)

    def install_addon(self, xpi_file):
        """Installs a Firefox add-on instantly at run-time.
        @Params
        xpi_file - A file archive in .xpi format.
        """
        self.wait_for_ready_state_complete()
        if self.browser != "firefox":
            raise Exception(
                "install_addon(xpi_file) is for Firefox ONLY!\n"
                "To load a Chrome extension, use the comamnd-line:\n"
                "--extension_zip=CRX_FILE  OR  --extension_dir=DIR"
            )
        xpi_path = os.path.abspath(xpi_file)
        self.driver.install_addon(xpi_path, temporary=True)

    def activate_design_mode(self):
        # Activate Chrome's Design Mode, which lets you edit a site directly.
        # See: https://twitter.com/sulco/status/1177559150563344384
        self.wait_for_ready_state_complete()
        script = """document.designMode = 'on';"""
        self.execute_script(script)

    def deactivate_design_mode(self):
        # Deactivate Chrome's Design Mode.
        self.wait_for_ready_state_complete()
        script = """document.designMode = 'off';"""
        self.execute_script(script)

    def activate_recorder(self):
        from seleniumbase.js_code.recorder_js import recorder_js

        if not self.is_chromium():
            raise Exception(
                "The Recorder is only for Chromium browsers: (Chrome or Edge)")
        url = self.driver.current_url
        if (
            url.startswith("data:") or url.startswith("about:")
            or url.startswith("chrome:") or url.startswith("edge:")
        ):
            message = (
                'The URL in Recorder-Mode cannot start with: '
                '"data:", "about:", "chrome:", or "edge:"!')
            print("\n" + message)
            return
        if self.recorder_ext:
            return  # The Recorder extension is already active
        try:
            recorder_on = self.get_session_storage_item("recorder_activated")
            if not recorder_on == "yes":
                self.execute_script(recorder_js)
            self.recorder_mode = True
            message = "Recorder Mode ACTIVE. [ESC]: Pause. [~`]: Resume."
            print("\n" + message)
            p_msg = "Recorder Mode ACTIVE.<br>[ESC]: Pause. [~`]: Resume."
            self.post_message(p_msg, pause=False, style="error")
        except Exception:
            pass

    def __get_recorded_actions_on_active_tab(self):
        url = self.driver.current_url
        if (
            url.startswith("data:") or url.startswith("about:")
            or url.startswith("chrome:") or url.startswith("edge:")
        ):
            return []
        actions = self.get_session_storage_item('recorded_actions')
        if actions:
            actions = json.loads(actions)
            return actions
        else:
            return []

    def __process_recorded_actions(self):
        import colorama

        raw_actions = []  # All raw actions from sessionStorage
        srt_actions = []
        cleaned_actions = []
        sb_actions = []
        used_actions = []
        action_dict = {}
        for window in self.driver.window_handles:
            self.switch_to_window(window)
            tab_actions = self.__get_recorded_actions_on_active_tab()
            for action in tab_actions:
                if action not in used_actions:
                    used_actions.append(action)
                    raw_actions.append(action)
        for action in self.__extra_actions:
            if action not in used_actions:
                used_actions.append(action)
                raw_actions.append(action)
        for action in raw_actions:
            if self._reuse_session:
                if int(action[3]) < int(self.__js_start_time):
                    continue
            # Use key for sorting and preventing duplicates
            key = str(action[3]) + "-" + str(action[0])
            action_dict[key] = action
        for key in sorted(action_dict):
            # print(action_dict[key])  # For debugging purposes
            srt_actions.append(action_dict[key])
        for n in range(len(srt_actions)):
            if (
                (srt_actions[n][0] == "begin" or srt_actions[n][0] == "_url_")
                and n > 0
                and srt_actions[n-1][0] == "sk_op"
            ):
                srt_actions[n][0] = "_skip"
        for n in range(len(srt_actions)):
            if (
                (srt_actions[n][0] == "begin" or srt_actions[n][0] == "_url_")
                and n > 0
                and (
                    srt_actions[n-1][0] == "click"
                    or srt_actions[n-1][0] == "js_cl"
                )
            ):
                url1 = srt_actions[n-1][2]
                if url1.endswith("/"):
                    url1 = url1[:-1]
                url2 = srt_actions[n][2]
                if url2.endswith("/"):
                    url2 = url2[:-1]
                if url1 == url2:
                    srt_actions[n][0] = "f_url"
        for n in range(len(srt_actions)):
            if (
                (srt_actions[n][0] == "begin" or srt_actions[n][0] == "_url_")
                and n > 0
                and (
                    srt_actions[n-1][0] == "begin"
                    or srt_actions[n-1][0] == "_url_"
                )
            ):
                url1 = srt_actions[n-1][2]
                if url1.endswith("/"):
                    url1 = url1[:-1]
                url2 = srt_actions[n][2]
                if url2.endswith("/"):
                    url2 = url2[:-1]
                if url1 == url2:
                    srt_actions[n-1][0] = "_skip"
        for n in range(len(srt_actions)):
            if (
                (srt_actions[n][0] == "begin" or srt_actions[n][0] == "_url_")
                and n > 0
                and (
                    srt_actions[n-1][0] == "click"
                    or srt_actions[n-1][0] == "js_cl"
                    or srt_actions[n-1][0] == "input"
                )
                and (int(srt_actions[n][3]) - int(srt_actions[n-1][3]) < 6500)
            ):
                if (
                    srt_actions[n-1][0] == "click"
                    or srt_actions[n-1][0] == "js_cl"
                ):
                    if (
                        srt_actions[n-1][1].startswith("input")
                        or srt_actions[n-1][1].startswith("button")
                    ):
                        srt_actions[n][0] = "f_url"
                elif srt_actions[n-1][0] == "input":
                    if srt_actions[n-1][2].endswith("\n"):
                        srt_actions[n][0] = "f_url"
        for n in range(len(srt_actions)):
            cleaned_actions.append(srt_actions[n])
        for action in srt_actions:
            if action[0] == "begin" or action[0] == "_url_":
                sb_actions.append('self.open("%s")' % action[2])
            elif action[0] == "f_url":
                sb_actions.append('self.open_if_not_url("%s")' % action[2])
            elif action[0] == "click":
                method = "click"
                if '"' not in action[1]:
                    sb_actions.append('self.%s("%s")' % (method, action[1]))
                else:
                    sb_actions.append("self.%s('%s')" % (method, action[1]))
            elif action[0] == "js_cl":
                method = "js_click"
                if '"' not in action[1]:
                    sb_actions.append('self.%s("%s")' % (method, action[1]))
                else:
                    sb_actions.append("self.%s('%s')" % (method, action[1]))
            elif action[0] == "input":
                method = "type"
                text = action[2].replace("\n", "\\n")
                if '"' not in action[1] and '"' not in text:
                    sb_actions.append('self.%s("%s", "%s")' % (
                        method, action[1], text))
                elif '"' not in action[1] and '"' in text:
                    sb_actions.append('self.%s("%s", \'%s\')' % (
                        method, action[1], text))
                elif '"' in action[1] and '"' not in text:
                    sb_actions.append('self.%s(\'%s\', "%s")' % (
                        method, action[1], text))
                elif '"' in action[1] and '"' in text:
                    sb_actions.append("self.%s('%s', '%s')" % (
                        method, action[1], text))
            elif action[0] == "h_clk":
                method = "hover_and_click"
                if '"' not in action[1] and '"' not in action[2]:
                    sb_actions.append('self.%s("%s", "%s")' % (
                        method, action[1], action[2]))
                elif '"' not in action[1] and '"' in action[2]:
                    sb_actions.append('self.%s("%s", \'%s\')' % (
                        method, action[1], action[2]))
                elif '"' in action[1] and '"' not in action[2]:
                    sb_actions.append('self.%s(\'%s\', "%s")' % (
                        method, action[1], action[2]))
                elif '"' in action[1] and '"' in action[2]:
                    sb_actions.append("self.%s('%s', '%s')" % (
                        method, action[1], action[2]))
            elif action[0] == "ddrop":
                method = "drag_and_drop"
                if '"' not in action[1] and '"' not in action[2]:
                    sb_actions.append('self.%s("%s", "%s")' % (
                        method, action[1], action[2]))
                elif '"' not in action[1] and '"' in action[2]:
                    sb_actions.append('self.%s("%s", \'%s\')' % (
                        method, action[1], action[2]))
                elif '"' in action[1] and '"' not in action[2]:
                    sb_actions.append('self.%s(\'%s\', "%s")' % (
                        method, action[1], action[2]))
                elif '"' in action[1] and '"' in action[2]:
                    sb_actions.append("self.%s('%s', '%s')" % (
                        method, action[1], action[2]))
            elif action[0] == "s_opt":
                method = "select_option_by_text"
                if '"' not in action[1] and '"' not in action[2]:
                    sb_actions.append('self.%s("%s", "%s")' % (
                        method, action[1], action[2]))
                elif '"' not in action[1] and '"' in action[2]:
                    sb_actions.append('self.%s("%s", \'%s\')' % (
                        method, action[1], action[2]))
                elif '"' in action[1] and '"' not in action[2]:
                    sb_actions.append('self.%s(\'%s\', "%s")' % (
                        method, action[1], action[2]))
                elif '"' in action[1] and '"' in action[2]:
                    sb_actions.append("self.%s('%s', '%s')" % (
                        method, action[1], action[2]))
            elif action[0] == "set_v":
                method = "set_value"
                if '"' not in action[1] and '"' not in action[2]:
                    sb_actions.append('self.%s("%s", "%s")' % (
                        method, action[1], action[2]))
                elif '"' not in action[1] and '"' in action[2]:
                    sb_actions.append('self.%s("%s", \'%s\')' % (
                        method, action[1], action[2]))
                elif '"' in action[1] and '"' not in action[2]:
                    sb_actions.append('self.%s(\'%s\', "%s")' % (
                        method, action[1], action[2]))
                elif '"' in action[1] and '"' in action[2]:
                    sb_actions.append("self.%s('%s', '%s')" % (
                        method, action[1], action[2]))
            elif action[0] == "cho_f":
                method = "choose_file"
                action[2] = action[2].replace("\\", "\\\\")
                if '"' not in action[1] and '"' not in action[2]:
                    sb_actions.append('self.%s("%s", "%s")' % (
                        method, action[1], action[2]))
                elif '"' not in action[1] and '"' in action[2]:
                    sb_actions.append('self.%s("%s", \'%s\')' % (
                        method, action[1], action[2]))
                elif '"' in action[1] and '"' not in action[2]:
                    sb_actions.append('self.%s(\'%s\', "%s")' % (
                        method, action[1], action[2]))
                elif '"' in action[1] and '"' in action[2]:
                    sb_actions.append("self.%s('%s', '%s')" % (
                        method, action[1], action[2]))
            elif action[0] == "sw_fr":
                method = "switch_to_frame"
                if '"' not in action[1]:
                    sb_actions.append('self.%s("%s")' % (method, action[1]))
                else:
                    sb_actions.append("self.%s('%s')" % (method, action[1]))
            elif action[0] == "sw_dc":
                sb_actions.append("self.switch_to_default_content()")
            elif action[0] == "s_c_f":
                method = "set_content_to_frame"
                if '"' not in action[1]:
                    sb_actions.append('self.%s("%s")' % (method, action[1]))
                else:
                    sb_actions.append("self.%s('%s')" % (method, action[1]))
            elif action[0] == "s_c_d":
                method = "set_content_to_default"
                nested = action[1]
                if nested:
                    sb_actions.append("self.%s()" % method)
                else:
                    sb_actions.append("self.%s(nested=False)" % method)
            elif action[0] == "as_el":
                method = "assert_element"
                if '"' not in action[1]:
                    sb_actions.append('self.%s("%s")' % (method, action[1]))
                else:
                    sb_actions.append("self.%s('%s')" % (method, action[1]))
            elif action[0] == "as_ep":
                method = "assert_element_present"
                if '"' not in action[1]:
                    sb_actions.append('self.%s("%s")' % (method, action[1]))
                else:
                    sb_actions.append("self.%s('%s')" % (method, action[1]))
            elif action[0] == "asenv":
                method = "assert_element_not_visible"
                if '"' not in action[1]:
                    sb_actions.append('self.%s("%s")' % (method, action[1]))
                else:
                    sb_actions.append("self.%s('%s')" % (method, action[1]))
            elif action[0] == "as_lt":
                method = "assert_link_text"
                if '"' not in action[1]:
                    sb_actions.append('self.%s("%s")' % (method, action[1]))
                else:
                    sb_actions.append("self.%s('%s')" % (method, action[1]))
            elif action[0] == "as_ti":
                method = "assert_title"
                if '"' not in action[1]:
                    sb_actions.append('self.%s("%s")' % (method, action[1]))
                else:
                    sb_actions.append("self.%s('%s')" % (method, action[1]))
            elif action[0] == "as_te" or action[0] == "as_et":
                method = "assert_text"
                if action[0] == "as_et":
                    method = "assert_exact_text"
                if action[2] != "html":
                    if '"' not in action[1] and '"' not in action[2]:
                        sb_actions.append('self.%s("%s", "%s")' % (
                            method, action[1], action[2]))
                    elif '"' not in action[1] and '"' in action[2]:
                        sb_actions.append('self.%s("%s", \'%s\')' % (
                            method, action[1], action[2]))
                    elif '"' in action[1] and '"' not in action[2]:
                        sb_actions.append('self.%s(\'%s\', "%s")' % (
                            method, action[1], action[2]))
                    elif '"' in action[1] and '"' in action[2]:
                        sb_actions.append("self.%s('%s', '%s')" % (
                            method, action[1], action[2]))
                else:
                    if '"' not in action[1]:
                        sb_actions.append('self.%s("%s")' % (
                            method, action[1]))
                    else:
                        sb_actions.append("self.%s('%s')" % (
                            method, action[1]))
            elif action[0] == "c_box":
                cb_method = "check_if_unchecked"
                if action[2] == "no":
                    cb_method = "uncheck_if_checked"
                if '"' not in action[1]:
                    sb_actions.append('self.%s("%s")' % (cb_method, action[1]))
                else:
                    sb_actions.append("self.%s('%s')" % (cb_method, action[1]))

        filename = self.__get_filename()
        new_file = False
        data = []
        if filename not in sb_config._recorded_actions:
            new_file = True
            sb_config._recorded_actions[filename] = []
            data.append("from seleniumbase import BaseCase")
            data.append("")
            data.append("")
            data.append("class %s(BaseCase):" % self.__class__.__name__)
        else:
            data = sb_config._recorded_actions[filename]
        data.append("    def %s(self):" % self._testMethodName)
        if len(sb_actions) > 0:
            for action in sb_actions:
                data.append("        " + action)
        else:
            data.append("        pass")
        data.append("")
        sb_config._recorded_actions[filename] = data

        recordings_folder = constants.Recordings.SAVED_FOLDER
        if recordings_folder.endswith("/"):
            recordings_folder = recordings_folder[:-1]
        if not os.path.exists(recordings_folder):
            try:
                os.makedirs(recordings_folder)
            except Exception:
                pass

        file_name = self.__class__.__module__.split(".")[-1] + "_rec.py"
        file_path = "%s/%s" % (recordings_folder, file_name)
        out_file = codecs.open(file_path, "w+", "utf-8")
        out_file.writelines("\r\n".join(data))
        out_file.close()
        rec_message = ">>> RECORDING SAVED as: "
        if not new_file:
            rec_message = ">>> RECORDING ADDED to: "
        star_len = len(rec_message) + len(file_path)
        try:
            terminal_size = os.get_terminal_size().columns
            if terminal_size > 30 and star_len > terminal_size:
                star_len = terminal_size
        except Exception:
            pass
        stars = "*" * star_len
        c1 = ""
        c2 = ""
        cr = ""
        if "linux" not in sys.platform:
            colorama.init(autoreset=True)
            c1 = colorama.Fore.RED + colorama.Back.LIGHTYELLOW_EX
            c2 = colorama.Fore.LIGHTRED_EX + colorama.Back.LIGHTYELLOW_EX
            cr = colorama.Style.RESET_ALL
            rec_message = rec_message.replace(">>>", c2 + ">>>" + cr)
        print("\n\n%s%s%s%s\n%s" % (rec_message, c1, file_path, cr, stars))

    def activate_jquery(self):
        """If "jQuery is not defined", use this method to activate it for use.
        This happens because jQuery is not always defined on web sites."""
        self.wait_for_ready_state_complete()
        js_utils.activate_jquery(self.driver)
        self.wait_for_ready_state_complete()

    def __are_quotes_escaped(self, string):
        return js_utils.are_quotes_escaped(string)

    def __escape_quotes_if_needed(self, string):
        return js_utils.escape_quotes_if_needed(string)

    def bring_to_front(self, selector, by=By.CSS_SELECTOR):
        """Updates the Z-index of a page element to bring it into view.
        Useful when getting a WebDriverException, such as the one below:
            { Element is not clickable at point (#, #).
              Other element would receive the click: ... }"""
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_element_visible(
            selector, by=by, timeout=settings.SMALL_TIMEOUT
        )
        try:
            selector = self.convert_to_css_selector(selector, by=by)
        except Exception:
            # Don't run action if can't convert to CSS_Selector for JavaScript
            return
        selector = re.escape(selector)
        selector = self.__escape_quotes_if_needed(selector)
        script = (
            """document.querySelector('%s').style.zIndex = '999999';"""
            % selector
        )
        self.execute_script(script)

    def highlight_click(
        self, selector, by=By.CSS_SELECTOR, loops=3, scroll=True
    ):
        self.__check_scope()
        if not self.demo_mode:
            self.highlight(selector, by=by, loops=loops, scroll=scroll)
        self.click(selector, by=by)

    def highlight_update_text(
        self, selector, text, by=By.CSS_SELECTOR, loops=3, scroll=True
    ):
        self.__check_scope()
        if not self.demo_mode:
            self.highlight(selector, by=by, loops=loops, scroll=scroll)
        self.update_text(selector, text, by=by)

    def highlight(self, selector, by=By.CSS_SELECTOR, loops=None, scroll=True):
        """This method uses fancy JavaScript to highlight an element.
        Used during demo_mode.
        @Params
        selector - the selector of the element to find
        by - the type of selector to search by (Default: CSS)
        loops - # of times to repeat the highlight animation
                (Default: 4. Each loop lasts for about 0.18s)
        scroll - the option to scroll to the element first (Default: True)
        """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by, xp_ok=False)
        element = self.wait_for_element_visible(
            selector, by=by, timeout=settings.SMALL_TIMEOUT
        )
        if not loops:
            loops = settings.HIGHLIGHTS
        if scroll:
            try:
                if self.browser != "safari":
                    scroll_distance = js_utils.get_scroll_distance_to_element(
                        self.driver, element
                    )
                    if abs(scroll_distance) > constants.Values.SSMD:
                        self.__jquery_slow_scroll_to(selector, by)
                    else:
                        self.__slow_scroll_to_element(element)
                else:
                    self.__jquery_slow_scroll_to(selector, by)
            except Exception:
                self.wait_for_ready_state_complete()
                time.sleep(0.12)
                element = self.wait_for_element_visible(
                    selector, by=by, timeout=settings.SMALL_TIMEOUT
                )
                self.__slow_scroll_to_element(element)
        try:
            selector = self.convert_to_css_selector(selector, by=by)
        except Exception:
            # Don't highlight if can't convert to CSS_SELECTOR
            return

        if self.highlights:
            loops = self.highlights
        if self.browser == "ie":
            loops = 1  # Override previous setting because IE is slow
        loops = int(loops)

        o_bs = ""  # original_box_shadow
        try:
            style = element.get_attribute("style")
        except Exception:
            self.wait_for_ready_state_complete()
            time.sleep(0.12)
            element = self.wait_for_element_visible(
                selector, by=By.CSS_SELECTOR, timeout=settings.SMALL_TIMEOUT
            )
            style = element.get_attribute("style")
        if style:
            if "box-shadow: " in style:
                box_start = style.find("box-shadow: ")
                box_end = style.find(";", box_start) + 1
                original_box_shadow = style[box_start:box_end]
                o_bs = original_box_shadow

        if ":contains" not in selector and ":first" not in selector:
            selector = re.escape(selector)
            selector = self.__escape_quotes_if_needed(selector)
            self.__highlight_with_js(selector, loops, o_bs)
        else:
            selector = self.__make_css_match_first_element_only(selector)
            selector = re.escape(selector)
            selector = self.__escape_quotes_if_needed(selector)
            try:
                self.__highlight_with_jquery(selector, loops, o_bs)
            except Exception:
                pass  # JQuery probably couldn't load. Skip highlighting.
        time.sleep(0.065)

    def __highlight_with_js(self, selector, loops, o_bs):
        self.wait_for_ready_state_complete()
        js_utils.highlight_with_js(self.driver, selector, loops, o_bs)

    def __highlight_with_jquery(self, selector, loops, o_bs):
        self.wait_for_ready_state_complete()
        js_utils.highlight_with_jquery(self.driver, selector, loops, o_bs)

    def press_up_arrow(self, selector="html", times=1, by=By.CSS_SELECTOR):
        """Simulates pressing the UP Arrow on the keyboard.
        By default, "html" will be used as the CSS Selector target.
        You can specify how many times in-a-row the action happens."""
        self.__check_scope()
        if times < 1:
            return
        element = self.wait_for_element_present(selector)
        self.__demo_mode_highlight_if_active(selector, by)
        if not self.demo_mode and not self.slow_mode:
            self.__scroll_to_element(element, selector, by)
        for i in range(int(times)):
            try:
                element.send_keys(Keys.ARROW_UP)
            except Exception:
                self.wait_for_ready_state_complete()
                element = self.wait_for_element_visible(selector)
                element.send_keys(Keys.ARROW_UP)
            time.sleep(0.01)
            if self.slow_mode:
                time.sleep(0.1)

    def press_down_arrow(self, selector="html", times=1, by=By.CSS_SELECTOR):
        """Simulates pressing the DOWN Arrow on the keyboard.
        By default, "html" will be used as the CSS Selector target.
        You can specify how many times in-a-row the action happens."""
        self.__check_scope()
        if times < 1:
            return
        element = self.wait_for_element_present(selector)
        self.__demo_mode_highlight_if_active(selector, by)
        if not self.demo_mode and not self.slow_mode:
            self.__scroll_to_element(element, selector, by)
        for i in range(int(times)):
            try:
                element.send_keys(Keys.ARROW_DOWN)
            except Exception:
                self.wait_for_ready_state_complete()
                element = self.wait_for_element_visible(selector)
                element.send_keys(Keys.ARROW_DOWN)
            time.sleep(0.01)
            if self.slow_mode:
                time.sleep(0.1)

    def press_left_arrow(self, selector="html", times=1, by=By.CSS_SELECTOR):
        """Simulates pressing the LEFT Arrow on the keyboard.
        By default, "html" will be used as the CSS Selector target.
        You can specify how many times in-a-row the action happens."""
        self.__check_scope()
        if times < 1:
            return
        element = self.wait_for_element_present(selector)
        self.__demo_mode_highlight_if_active(selector, by)
        if not self.demo_mode and not self.slow_mode:
            self.__scroll_to_element(element, selector, by)
        for i in range(int(times)):
            try:
                element.send_keys(Keys.ARROW_LEFT)
            except Exception:
                self.wait_for_ready_state_complete()
                element = self.wait_for_element_visible(selector)
                element.send_keys(Keys.ARROW_LEFT)
            time.sleep(0.01)
            if self.slow_mode:
                time.sleep(0.1)

    def press_right_arrow(self, selector="html", times=1, by=By.CSS_SELECTOR):
        """Simulates pressing the RIGHT Arrow on the keyboard.
        By default, "html" will be used as the CSS Selector target.
        You can specify how many times in-a-row the action happens."""
        self.__check_scope()
        if times < 1:
            return
        element = self.wait_for_element_present(selector)
        self.__demo_mode_highlight_if_active(selector, by)
        if not self.demo_mode and not self.slow_mode:
            self.__scroll_to_element(element, selector, by)
        for i in range(int(times)):
            try:
                element.send_keys(Keys.ARROW_RIGHT)
            except Exception:
                self.wait_for_ready_state_complete()
                element = self.wait_for_element_visible(selector)
                element.send_keys(Keys.ARROW_RIGHT)
            time.sleep(0.01)
            if self.slow_mode:
                time.sleep(0.1)

    def scroll_to(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """ Fast scroll to destination """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        if self.demo_mode or self.slow_mode:
            self.slow_scroll_to(selector, by=by, timeout=timeout)
            return
        element = self.wait_for_element_visible(
            selector, by=by, timeout=timeout
        )
        try:
            self.__scroll_to_element(element, selector, by)
        except (StaleElementReferenceException, ENI_Exception):
            self.wait_for_ready_state_complete()
            time.sleep(0.12)
            element = self.wait_for_element_visible(
                selector, by=by, timeout=timeout
            )
            self.__scroll_to_element(element, selector, by)

    def scroll_to_element(self, selector, by=By.CSS_SELECTOR, timeout=None):
        self.scroll_to(selector, by=by, timeout=timeout)

    def slow_scroll_to(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """ Slow motion scroll to destination """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        element = self.wait_for_element_visible(
            selector, by=by, timeout=timeout
        )
        try:
            scroll_distance = js_utils.get_scroll_distance_to_element(
                self.driver, element
            )
            if abs(scroll_distance) > constants.Values.SSMD:
                self.__jquery_slow_scroll_to(selector, by)
            else:
                self.__slow_scroll_to_element(element)
        except Exception:
            self.wait_for_ready_state_complete()
            time.sleep(0.12)
            element = self.wait_for_element_visible(
                selector, by=by, timeout=timeout
            )
            self.__slow_scroll_to_element(element)

    def slow_scroll_to_element(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        self.slow_scroll_to(selector, by=by, timeout=timeout)

    def scroll_to_top(self):
        """ Scroll to the top of the page. """
        self.__check_scope()
        scroll_script = "window.scrollTo(0, 0);"
        try:
            self.execute_script(scroll_script)
            time.sleep(0.012)
            return True
        except Exception:
            return False

    def scroll_to_bottom(self):
        """ Scroll to the bottom of the page. """
        self.__check_scope()
        scroll_script = "window.scrollTo(0, 10000);"
        try:
            self.execute_script(scroll_script)
            time.sleep(0.012)
            return True
        except Exception:
            return False

    def click_xpath(self, xpath):
        # Technically self.click() will automatically detect an xpath selector,
        # so self.click_xpath() is just a longer name for the same action.
        self.click(xpath, by=By.XPATH)

    def js_click(
        self, selector, by=By.CSS_SELECTOR, all_matches=False, scroll=True
    ):
        """Clicks an element using JavaScript.
        Can be used to click hidden / invisible elements.
        If "all_matches" is False, only the first match is clicked.
        If "scroll" is False, won't scroll unless running in Demo Mode."""
        self.wait_for_ready_state_complete()
        selector, by = self.__recalculate_selector(selector, by, xp_ok=False)
        if by == By.LINK_TEXT:
            message = (
                "Pure JavaScript doesn't support clicking by Link Text. "
                "You may want to use self.jquery_click() instead, which "
                "allows this with :contains(), assuming jQuery isn't blocked. "
                "For now, self.js_click() will use a regular WebDriver click."
            )
            logging.debug(message)
            self.click(selector, by=by)
            return
        element = self.wait_for_element_present(
            selector, by=by, timeout=settings.SMALL_TIMEOUT
        )
        if self.is_element_visible(selector, by=by):
            self.__demo_mode_highlight_if_active(selector, by)
            if scroll and not self.demo_mode and not self.slow_mode:
                success = js_utils.scroll_to_element(self.driver, element)
                if not success:
                    self.wait_for_ready_state_complete()
                    timeout = settings.SMALL_TIMEOUT
                    element = page_actions.wait_for_element_present(
                        self.driver, selector, by, timeout=timeout
                    )
        css_selector = self.convert_to_css_selector(selector, by=by)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        action = None
        pre_action_url = self.driver.current_url
        pre_window_count = len(self.driver.window_handles)
        if self.recorder_mode:
            time_stamp = self.execute_script("return Date.now();")
            tag_name = None
            href = ""
            if ":contains\\(" not in css_selector:
                tag_name = self.execute_script(
                    "return document.querySelector('%s').tagName.toLowerCase()"
                    % css_selector
                )
            if tag_name == "a":
                href = self.execute_script(
                    "return document.querySelector('%s').href" % css_selector
                )
            action = ["js_cl", selector, href, time_stamp]
        if not all_matches:
            if ":contains\\(" not in css_selector:
                self.__js_click(selector, by=by)
            else:
                click_script = """jQuery('%s')[0].click();""" % css_selector
                self.safe_execute_script(click_script)
        else:
            if ":contains\\(" not in css_selector:
                self.__js_click_all(selector, by=by)
            else:
                click_script = """jQuery('%s').click();""" % css_selector
                self.safe_execute_script(click_script)
        if self.recorder_mode and action:
            self.__extra_actions.append(action)
        latest_window_count = len(self.driver.window_handles)
        if (
            latest_window_count > pre_window_count
            and (
                self.recorder_mode
                or (
                    settings.SWITCH_TO_NEW_TABS_ON_CLICK
                    and self.driver.current_url == pre_action_url
                )
            )
        ):
            self.switch_to_newest_window()
        self.wait_for_ready_state_complete()
        self.__demo_mode_pause_if_active()

    def js_click_all(self, selector, by=By.CSS_SELECTOR):
        """ Clicks all matching elements using pure JS. (No jQuery) """
        self.js_click(selector, by=By.CSS_SELECTOR, all_matches=True)

    def jquery_click(self, selector, by=By.CSS_SELECTOR):
        """Clicks an element using jQuery. (Different from using pure JS.)
        Can be used to click hidden / invisible elements."""
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by, xp_ok=False)
        self.wait_for_element_present(
            selector, by=by, timeout=settings.SMALL_TIMEOUT
        )
        if self.is_element_visible(selector, by=by):
            self.__demo_mode_highlight_if_active(selector, by)
        selector = self.convert_to_css_selector(selector, by=by)
        selector = self.__make_css_match_first_element_only(selector)
        click_script = """jQuery('%s')[0].click();""" % selector
        self.safe_execute_script(click_script)
        self.__demo_mode_pause_if_active()

    def jquery_click_all(self, selector, by=By.CSS_SELECTOR):
        """ Clicks all matching elements using jQuery. """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by, xp_ok=False)
        self.wait_for_element_present(
            selector, by=by, timeout=settings.SMALL_TIMEOUT
        )
        if self.is_element_visible(selector, by=by):
            self.__demo_mode_highlight_if_active(selector, by)
        css_selector = self.convert_to_css_selector(selector, by=by)
        click_script = """jQuery('%s').click();""" % css_selector
        self.safe_execute_script(click_script)
        self.__demo_mode_pause_if_active()

    def hide_element(self, selector, by=By.CSS_SELECTOR):
        """ Hide the first element on the page that matches the selector. """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        selector = self.convert_to_css_selector(selector, by=by)
        selector = self.__make_css_match_first_element_only(selector)
        hide_script = """jQuery('%s').hide();""" % selector
        self.safe_execute_script(hide_script)

    def hide_elements(self, selector, by=By.CSS_SELECTOR):
        """ Hide all elements on the page that match the selector. """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        selector = self.convert_to_css_selector(selector, by=by)
        hide_script = """jQuery('%s').hide();""" % selector
        self.safe_execute_script(hide_script)

    def show_element(self, selector, by=By.CSS_SELECTOR):
        """ Show the first element on the page that matches the selector. """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        selector = self.convert_to_css_selector(selector, by=by)
        selector = self.__make_css_match_first_element_only(selector)
        show_script = """jQuery('%s').show(0);""" % selector
        self.safe_execute_script(show_script)

    def show_elements(self, selector, by=By.CSS_SELECTOR):
        """ Show all elements on the page that match the selector. """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        selector = self.convert_to_css_selector(selector, by=by)
        show_script = """jQuery('%s').show(0);""" % selector
        self.safe_execute_script(show_script)

    def remove_element(self, selector, by=By.CSS_SELECTOR):
        """ Remove the first element on the page that matches the selector. """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        selector = self.convert_to_css_selector(selector, by=by)
        selector = self.__make_css_match_first_element_only(selector)
        remove_script = """jQuery('%s').remove();""" % selector
        self.safe_execute_script(remove_script)

    def remove_elements(self, selector, by=By.CSS_SELECTOR):
        """ Remove all elements on the page that match the selector. """
        self.__check_scope()
        selector, by = self.__recalculate_selector(selector, by)
        selector = self.convert_to_css_selector(selector, by=by)
        remove_script = """jQuery('%s').remove();""" % selector
        self.safe_execute_script(remove_script)

    def ad_block(self):
        """ Block ads that appear on the current web page. """
        from seleniumbase.config import ad_block_list

        self.__check_scope()  # Using wait_for_RSC would cause an infinite loop
        for css_selector in ad_block_list.AD_BLOCK_LIST:
            css_selector = re.escape(css_selector)  # Add "\\" to special chars
            css_selector = self.__escape_quotes_if_needed(css_selector)
            script = (
                """var $elements = document.querySelectorAll('%s');
                var index = 0, length = $elements.length;
                for(; index < length; index++){
                $elements[index].remove();}"""
                % css_selector
            )
            try:
                self.execute_script(script)
            except Exception:
                pass  # Don't fail test if ad_blocking fails

    def show_file_choosers(self):
        """Display hidden file-chooser input fields on sites if present."""
        css_selector = 'input[type="file"]'
        try:
            self.show_elements(css_selector)
        except Exception:
            pass
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        script = (
            """var $elements = document.querySelectorAll('%s');
            var index = 0, length = $elements.length;
            for(; index < length; index++){
            the_class = $elements[index].getAttribute('class');
            new_class = the_class.replaceAll('hidden', 'visible');
            $elements[index].setAttribute('class', new_class);}"""
            % css_selector
        )
        try:
            self.execute_script(script)
        except Exception:
            pass

    def get_domain_url(self, url):
        self.__check_scope()
        return page_utils.get_domain_url(url)

    def get_beautiful_soup(self, source=None):
        """BeautifulSoup is a toolkit for dissecting an HTML document
        and extracting what you need. It's great for screen-scraping!
        See: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
        """
        from bs4 import BeautifulSoup

        if not source:
            source = self.get_page_source()
        soup = BeautifulSoup(source, "html.parser")
        return soup

    def get_unique_links(self):
        """Get all unique links in the html of the page source.
        Page links include those obtained from:
        "a"->"href", "img"->"src", "link"->"href", and "script"->"src".
        """
        page_url = self.get_current_url()
        soup = self.get_beautiful_soup(self.get_page_source())
        links = page_utils._get_unique_links(page_url, soup)
        return links

    def get_link_status_code(self, link, allow_redirects=False, timeout=5):
        """Get the status code of a link.
        If the timeout is set to less than 1, it becomes 1.
        If the timeout is exceeded by requests.get(), it will return a 404.
        For a list of available status codes, see:
        https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
        """
        if self.__requests_timeout:
            timeout = self.__requests_timeout
        if timeout < 1:
            timeout = 1
        status_code = page_utils._get_link_status_code(
            link, allow_redirects=allow_redirects, timeout=timeout
        )
        return status_code

    def assert_link_status_code_is_not_404(self, link):
        status_code = str(self.get_link_status_code(link))
        bad_link_str = 'Error: "%s" returned a 404!' % link
        self.assertNotEqual(status_code, "404", bad_link_str)

    def __get_link_if_404_error(self, link):
        status_code = str(self.get_link_status_code(link))
        if status_code == "404":
            # Verify again to be sure. (In case of multi-threading overload.)
            status_code = str(self.get_link_status_code(link))
            if status_code == "404":
                return link
            else:
                return None
        else:
            return None

    def assert_no_404_errors(self, multithreaded=True, timeout=None):
        """Assert no 404 errors from page links obtained from:
        "a"->"href", "img"->"src", "link"->"href", and "script"->"src".
        Timeout is on a per-link basis using the "requests" library.
        (A 404 error represents a broken link on a web page.)
        """
        all_links = self.get_unique_links()
        links = []
        for link in all_links:
            if (
                "javascript:" not in link
                and "mailto:" not in link
                and "data:" not in link
            ):
                links.append(link)
        if timeout:
            if not type(timeout) is int and not type(timeout) is float:
                raise Exception('Expecting a numeric value for "timeout"!')
            if timeout < 0:
                raise Exception('The "timeout" cannot be a negative number!')
            self.__requests_timeout = timeout
        broken_links = []
        if multithreaded:
            from multiprocessing.dummy import Pool as ThreadPool

            pool = ThreadPool(10)
            results = pool.map(self.__get_link_if_404_error, links)
            pool.close()
            pool.join()
            for result in results:
                if result:
                    broken_links.append(result)
        else:
            broken_links = []
            for link in links:
                if self.__get_link_if_404_error(link):
                    broken_links.append(link)
        self.__requests_timeout = None  # Reset the requests.get() timeout
        if len(broken_links) > 0:
            bad_links_str = "\n".join(broken_links)
            if len(broken_links) == 1:
                self.fail("Broken link detected:\n%s" % bad_links_str)
            elif len(broken_links) > 1:
                self.fail("Broken links detected:\n%s" % bad_links_str)
        if self.demo_mode:
            a_t = "ASSERT NO 404 ERRORS"
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert_no_404_errors(self._language)
            messenger_post = "%s" % a_t
            self.__highlight_with_assert_success(messenger_post, "html")

    def print_unique_links_with_status_codes(self):
        """Finds all unique links in the html of the page source
        and then prints out those links with their status codes.
        Format:  ["link"  ->  "status_code"]  (per line)
        Page links include those obtained from:
        "a"->"href", "img"->"src", "link"->"href", and "script"->"src".
        """
        page_url = self.get_current_url()
        soup = self.get_beautiful_soup(self.get_page_source())
        page_utils._print_unique_links_with_status_codes(page_url, soup)

    def __fix_unicode_conversion(self, text):
        """ Fixing Chinese characters when converting from PDF to HTML. """
        text = text.replace("\u2f8f", "\u884c")
        text = text.replace("\u2f45", "\u65b9")
        text = text.replace("\u2f08", "\u4eba")
        text = text.replace("\u2f70", "\u793a")
        text = text.replace("\xe2\xbe\x8f", "\xe8\xa1\x8c")
        text = text.replace("\xe2\xbd\xb0", "\xe7\xa4\xba")
        text = text.replace("\xe2\xbe\x8f", "\xe8\xa1\x8c")
        text = text.replace("\xe2\xbd\x85", "\xe6\x96\xb9")
        return text

    def get_pdf_text(
        self,
        pdf,
        page=None,
        maxpages=None,
        password=None,
        codec="utf-8",
        wrap=False,
        nav=False,
        override=False,
    ):
        """Gets text from a PDF file.
        PDF can be either a URL or a file path on the local file system.
        @Params
        pdf - The URL or file path of the PDF file.
        page - The page number (or a list of page numbers) of the PDF.
                If a page number is provided, looks only at that page.
                    (1 is the first page, 2 is the second page, etc.)
                If no page number is provided, returns all PDF text.
        maxpages - Instead of providing a page number, you can provide
                   the number of pages to use from the beginning.
        password - If the PDF is password-protected, enter it here.
        codec - The compression format for character encoding.
                (The default codec used by this method is 'utf-8'.)
        wrap - Replaces ' \n' with ' ' so that individual sentences
               from a PDF don't get broken up into separate lines when
               getting converted into text format.
        nav - If PDF is a URL, navigates to the URL in the browser first.
              (Not needed because the PDF will be downloaded anyway.)
        override - If the PDF file to be downloaded already exists in the
                   downloaded_files/ folder, that PDF will be used
                   instead of downloading it again."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            from pdfminer.high_level import extract_text
        if not password:
            password = ""
        if not maxpages:
            maxpages = 0
        if not pdf.lower().endswith(".pdf"):
            raise Exception("%s is not a PDF file! (Expecting a .pdf)" % pdf)
        file_path = None
        if page_utils.is_valid_url(pdf):
            from seleniumbase.core import download_helper

            downloads_folder = download_helper.get_downloads_folder()
            if nav:
                if self.get_current_url() != pdf:
                    self.open(pdf)
            file_name = pdf.split("/")[-1]
            file_path = downloads_folder + "/" + file_name
            if not os.path.exists(file_path):
                self.download_file(pdf)
            elif override:
                self.download_file(pdf)
        else:
            if not os.path.exists(pdf):
                raise Exception("%s is not a valid URL or file path!" % pdf)
            file_path = os.path.abspath(pdf)
        page_search = None  # (Pages are delimited by '\x0c')
        if type(page) is list:
            pages = page
            page_search = []
            for page in pages:
                page_search.append(page - 1)
        elif type(page) is int:
            page = page - 1
            if page < 0:
                page = 0
            page_search = [page]
        else:
            page_search = None
        pdf_text = extract_text(
            file_path,
            password="",
            page_numbers=page_search,
            maxpages=maxpages,
            caching=False,
            codec=codec,
        )
        pdf_text = self.__fix_unicode_conversion(pdf_text)
        if wrap:
            pdf_text = pdf_text.replace(" \n", " ")
        pdf_text = pdf_text.strip()  # Remove leading and trailing whitespace
        return pdf_text

    def assert_pdf_text(
        self,
        pdf,
        text,
        page=None,
        maxpages=None,
        password=None,
        codec="utf-8",
        wrap=True,
        nav=False,
        override=False,
    ):
        """Asserts text in a PDF file.
        PDF can be either a URL or a file path on the local file system.
        @Params
        pdf - The URL or file path of the PDF file.
        text - The expected text to verify in the PDF.
        page - The page number of the PDF to use (optional).
                If a page number is provided, looks only at that page.
                    (1 is the first page, 2 is the second page, etc.)
                If no page number is provided, looks at all the pages.
        maxpages - Instead of providing a page number, you can provide
                   the number of pages to use from the beginning.
        password - If the PDF is password-protected, enter it here.
        codec - The compression format for character encoding.
                (The default codec used by this method is 'utf-8'.)
        wrap - Replaces ' \n' with ' ' so that individual sentences
               from a PDF don't get broken up into separate lines when
               getting converted into text format.
        nav - If PDF is a URL, navigates to the URL in the browser first.
              (Not needed because the PDF will be downloaded anyway.)
        override - If the PDF file to be downloaded already exists in the
                   downloaded_files/ folder, that PDF will be used
                   instead of downloading it again."""
        text = self.__fix_unicode_conversion(text)
        if not codec:
            codec = "utf-8"
        pdf_text = self.get_pdf_text(
            pdf,
            page=page,
            maxpages=maxpages,
            password=password,
            codec=codec,
            wrap=wrap,
            nav=nav,
            override=override,
        )
        if type(page) is int:
            if text not in pdf_text:
                raise Exception(
                    "PDF [%s] is missing expected text [%s] on "
                    "page [%s]!" % (pdf, text, page)
                )
        else:
            if text not in pdf_text:
                raise Exception(
                    "PDF [%s] is missing expected text [%s]!" % (pdf, text)
                )
        return True

    def create_folder(self, folder):
        """ Creates a folder of the given name if it doesn't already exist. """
        if folder.endswith("/"):
            folder = folder[:-1]
        if len(folder) < 1:
            raise Exception("Minimum folder name length = 1.")
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
            except Exception:
                pass

    def choose_file(
        self, selector, file_path, by=By.CSS_SELECTOR, timeout=None
    ):
        """This method is used to choose a file to upload to a website.
        It works by populating a file-chooser "input" field of type="file".
        A relative file_path will get converted into an absolute file_path.

        Example usage:
            self.choose_file('input[type="file"]', "my_dir/my_file.txt")
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        abs_path = os.path.abspath(file_path)
        element = self.wait_for_element_present(
            selector, by=by, timeout=timeout
        )
        if self.is_element_visible(selector, by=by):
            self.__demo_mode_highlight_if_active(selector, by)
            if not self.demo_mode and not self.slow_mode:
                self.__scroll_to_element(element, selector, by)
        pre_action_url = self.driver.current_url
        if type(abs_path) is int or type(abs_path) is float:
            abs_path = str(abs_path)
        try:
            element.send_keys(abs_path)
        except (StaleElementReferenceException, ENI_Exception):
            self.wait_for_ready_state_complete()
            time.sleep(0.16)
            element = self.wait_for_element_present(
                selector, by=by, timeout=timeout
            )
            element.send_keys(abs_path)
        except Exception:
            exc_message = self.__get_improved_exception_message()
            raise Exception(exc_message)
        if self.demo_mode:
            if self.driver.current_url != pre_action_url:
                self.__demo_mode_pause_if_active()
            else:
                self.__demo_mode_pause_if_active(tiny=True)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()

    def save_element_as_image_file(
        self, selector, file_name, folder=None, overlay_text=""
    ):
        """Take a screenshot of an element and save it as an image file.
        If no folder is specified, will save it to the current folder.
        If overlay_text is provided, will add that to the saved image."""
        element = self.wait_for_element_visible(selector)
        element_png = element.screenshot_as_png
        if len(file_name.split(".")[0]) < 1:
            raise Exception("Error: file_name length must be > 0.")
        if not file_name.endswith(".png"):
            file_name = file_name + ".png"
        image_file_path = None
        if folder:
            if folder.endswith("/"):
                folder = folder[:-1]
            if len(folder) > 0:
                self.create_folder(folder)
                image_file_path = "%s/%s" % (folder, file_name)
        if not image_file_path:
            image_file_path = file_name
        with open(image_file_path, "wb") as file:
            file.write(element_png)
        # Add a text overlay if given
        if type(overlay_text) is str and len(overlay_text) > 0:
            from PIL import Image, ImageDraw

            text_rows = overlay_text.split("\n")
            len_text_rows = len(text_rows)
            max_width = 0
            for text_row in text_rows:
                if len(text_row) > max_width:
                    max_width = len(text_row)
            image = Image.open(image_file_path)
            draw = ImageDraw.Draw(image)
            draw.rectangle(
                (0, 0, (max_width * 6) + 6, 16 * len_text_rows),
                fill=(236, 236, 28),
            )
            draw.text(
                (4, 2),  # Coordinates
                overlay_text,  # Text
                (8, 38, 176),  # Color
            )
            image.save(image_file_path, "PNG", quality=100, optimize=True)

    def download_file(self, file_url, destination_folder=None):
        """Downloads the file from the url to the destination folder.
        If no destination folder is specified, the default one is used.
        (The default [Downloads Folder] = "./downloaded_files")"""
        if not destination_folder:
            destination_folder = constants.Files.DOWNLOADS_FOLDER
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)
        page_utils._download_file_to(file_url, destination_folder)

    def save_file_as(self, file_url, new_file_name, destination_folder=None):
        """Similar to self.download_file(), except that you get to rename the
        file being downloaded to whatever you want."""
        if not destination_folder:
            destination_folder = constants.Files.DOWNLOADS_FOLDER
        page_utils._download_file_to(
            file_url, destination_folder, new_file_name
        )

    def save_data_as(self, data, file_name, destination_folder=None):
        """Saves the data specified to a file of the name specified.
        If no destination folder is specified, the default one is used.
        (The default [Downloads Folder] = "./downloaded_files")"""
        if not destination_folder:
            destination_folder = constants.Files.DOWNLOADS_FOLDER
        page_utils._save_data_as(data, destination_folder, file_name)

    def get_downloads_folder(self):
        """Returns the path of the SeleniumBase "downloaded_files/" folder.
        Calling self.download_file(file_url) will put that file in here.
        With the exception of Safari, IE, and Chromium Guest Mode,
          any clicks that download files will also use this folder
          rather than using the browser's default "downloads/" path."""
        self.__check_scope()
        from seleniumbase.core import download_helper

        return download_helper.get_downloads_folder()

    def get_browser_downloads_folder(self):
        """Returns the path that is used when a click initiates a download.
        SeleniumBase overrides the system path to be "downloaded_files/"
        The path can't be changed on Safari, IE, or Chromium Guest Mode.
        The same problem occurs when using an out-of-date chromedriver.
        """
        self.__check_scope()
        if self.is_chromium() and self.guest_mode and not self.headless:
            # Guest Mode (non-headless) can force the default downloads path
            return os.path.join(os.path.expanduser("~"), "downloads")
        elif self.browser == "safari" or self.browser == "ie":
            # Can't change the system [Downloads Folder] on Safari or IE
            return os.path.join(os.path.expanduser("~"), "downloads")
        elif (
            self.driver.capabilities["browserName"].lower() == "chrome"
            and int(self.get_chromedriver_version().split(".")[0]) < 73
            and self.headless
        ):
            return os.path.join(os.path.expanduser("~"), "downloads")
        else:
            from seleniumbase.core import download_helper

            return download_helper.get_downloads_folder()
        return os.path.join(os.path.expanduser("~"), "downloads")

    def get_path_of_downloaded_file(self, file, browser=False):
        """ Returns the OS path of the downloaded file. """
        if browser:
            return os.path.join(self.get_browser_downloads_folder(), file)
        else:
            return os.path.join(self.get_downloads_folder(), file)

    def is_downloaded_file_present(self, file, browser=False):
        """Returns True if the file exists in the pre-set [Downloads Folder].
        For browser click-initiated downloads, SeleniumBase will override
            the system [Downloads Folder] to be "./downloaded_files/",
            but that path can't be overridden when using Safari, IE,
            or Chromium Guest Mode, which keeps the default system path.
        self.download_file(file_url) will always use "./downloaded_files/".
        @Params
        file - The filename of the downloaded file.
        browser - If True, uses the path set by click-initiated downloads.
                  If False, uses the self.download_file(file_url) path.
                  Those paths are often the same. (browser-dependent)
                  (Default: False).
        """
        return os.path.exists(
            self.get_path_of_downloaded_file(file, browser=browser)
        )

    def delete_downloaded_file_if_present(self, file, browser=False):
        """Deletes the file from the [Downloads Folder] if the file exists.
        For browser click-initiated downloads, SeleniumBase will override
            the system [Downloads Folder] to be "./downloaded_files/",
            but that path can't be overridden when using Safari, IE,
            or Chromium Guest Mode, which keeps the default system path.
        self.download_file(file_url) will always use "./downloaded_files/".
        @Params
        file - The filename to be deleted from the [Downloads Folder].
        browser - If True, uses the path set by click-initiated downloads.
                  If False, uses the self.download_file(file_url) path.
                  Those paths are usually the same. (browser-dependent)
                  (Default: False).
        """
        if self.is_downloaded_file_present(file, browser=browser):
            file_path = self.get_path_of_downloaded_file(file, browser=browser)
            try:
                os.remove(file_path)
            except Exception:
                pass

    def delete_downloaded_file(self, file, browser=False):
        """Same as self.delete_downloaded_file_if_present()
        Deletes the file from the [Downloads Folder] if the file exists.
        For browser click-initiated downloads, SeleniumBase will override
            the system [Downloads Folder] to be "./downloaded_files/",
            but that path can't be overridden when using Safari, IE,
            or Chromium Guest Mode, which keeps the default system path.
        self.download_file(file_url) will always use "./downloaded_files/".
        @Params
        file - The filename to be deleted from the [Downloads Folder].
        browser - If True, uses the path set by click-initiated downloads.
                  If False, uses the self.download_file(file_url) path.
                  Those paths are usually the same. (browser-dependent)
                  (Default: False).
        """
        if self.is_downloaded_file_present(file, browser=browser):
            file_path = self.get_path_of_downloaded_file(file, browser=browser)
            try:
                os.remove(file_path)
            except Exception:
                pass

    def assert_downloaded_file(self, file, timeout=None, browser=False):
        """Asserts that the file exists in SeleniumBase's [Downloads Folder].
        For browser click-initiated downloads, SeleniumBase will override
            the system [Downloads Folder] to be "./downloaded_files/",
            but that path can't be overridden when using Safari, IE,
            or Chromium Guest Mode, which keeps the default system path.
        self.download_file(file_url) will always use "./downloaded_files/".
        @Params
        file - The filename of the downloaded file.
        timeout - The time (seconds) to wait for the download to complete.
        browser - If True, uses the path set by click-initiated downloads.
                  If False, uses the self.download_file(file_url) path.
                  Those paths are often the same. (browser-dependent)
                  (Default: False).
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        start_ms = time.time() * 1000.0
        stop_ms = start_ms + (timeout * 1000.0)
        downloaded_file_path = self.get_path_of_downloaded_file(file, browser)
        found = False
        for x in range(int(timeout)):
            shared_utils.check_if_time_limit_exceeded()
            try:
                self.assertTrue(
                    os.path.exists(downloaded_file_path),
                    "File [%s] was not found in the downloads folder [%s]!"
                    % (file, self.get_downloads_folder()),
                )
                found = True
                break
            except Exception:
                now_ms = time.time() * 1000.0
                if now_ms >= stop_ms:
                    break
                time.sleep(1)
        if not found and not os.path.exists(downloaded_file_path):
            message = (
                "File {%s} was not found in the downloads folder {%s} "
                "after %s seconds! (Or the download didn't complete!)"
                % (file, self.get_downloads_folder(), timeout)
            )
            page_actions.timeout_exception("NoSuchFileException", message)
        if self.demo_mode:
            messenger_post = "ASSERT DOWNLOADED FILE: [%s]" % file
            try:
                js_utils.activate_jquery(self.driver)
                js_utils.post_messenger_success_message(
                    self.driver, messenger_post, self.message_duration
                )
            except Exception:
                pass

    def assert_true(self, expr, msg=None):
        """Asserts that the expression is True.
        Will raise an exception if the statement if False."""
        self.assertTrue(expr, msg=msg)

    def assert_false(self, expr, msg=None):
        """Asserts that the expression is False.
        Will raise an exception if the statement if True."""
        self.assertFalse(expr, msg=msg)

    def assert_equal(self, first, second, msg=None):
        """Asserts that the two values are equal.
        Will raise an exception if the values are not equal."""
        self.assertEqual(first, second, msg=msg)

    def assert_not_equal(self, first, second, msg=None):
        """Asserts that the two values are not equal.
        Will raise an exception if the values are equal."""
        self.assertNotEqual(first, second, msg=msg)

    def assert_in(self, first, second, msg=None):
        """Asserts that the first string is in the second string.
        Will raise an exception if the first string is not in the second."""
        self.assertIn(first, second, msg=msg)

    def assert_not_in(self, first, second, msg=None):
        """Asserts that the first string is not in the second string.
        Will raise an exception if the first string is in the second string."""
        self.assertNotIn(first, second, msg=msg)

    def assert_raises(self, *args, **kwargs):
        """Asserts that the following block of code raises an exception.
        Will raise an exception if the block of code has no exception.
        Usage Example =>
                # Verify that the expected exception is raised.
                with self.assert_raises(Exception):
                    raise Exception("Expected Exception!")
        """
        return self.assertRaises(*args, **kwargs)

    def wait_for_attribute(
        self, selector, attribute, value=None, by=By.CSS_SELECTOR, timeout=None
    ):
        """Raises an exception if the element attribute/value is not found.
        If the value is not specified, the attribute only needs to exist.
        Returns the element that contains the attribute if successful.
        Default timeout = LARGE_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            return self.__wait_for_shadow_attribute_present(
                selector, attribute, value=value, timeout=timeout
            )
        return page_actions.wait_for_attribute(
            self.driver,
            selector,
            attribute,
            value=value,
            by=by,
            timeout=timeout,
        )

    def assert_attribute(
        self, selector, attribute, value=None, by=By.CSS_SELECTOR, timeout=None
    ):
        """Raises an exception if the element attribute/value is not found.
        If the value is not specified, the attribute only needs to exist.
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_attribute(
            selector, attribute, value=value, by=by, timeout=timeout
        )
        if (
            self.demo_mode
            and not self.__is_shadow_selector(selector)
            and self.is_element_visible(selector, by=by)
        ):
            a_a = "ASSERT ATTRIBUTE"
            i_n = "in"
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_a = SD.translate_assert_attribute(self._language)
                i_n = SD.translate_in(self._language)
            if not value:
                messenger_post = "%s: {%s} %s %s: %s" % (
                    a_a,
                    attribute,
                    i_n,
                    by.upper(),
                    selector,
                )
            else:
                messenger_post = '%s: {%s == "%s"} %s %s: %s' % (
                    a_a,
                    attribute,
                    value,
                    i_n,
                    by.upper(),
                    selector,
                )
            self.__highlight_with_assert_success(messenger_post, selector, by)
        return True

    def assert_title(self, title):
        """Asserts that the web page title matches the expected title.
        When a web page initially loads, the title starts as the URL,
        but then the title switches over to the actual page title.
        A slow connection could delay the actual title from displaying."""
        self.wait_for_ready_state_complete()
        expected = title.strip()
        actual = self.get_page_title().strip()
        error = (
            "Expected page title [%s] does not match the actual title [%s]!"
        )
        try:
            self.assertEqual(expected, actual, error % (expected, actual))
        except Exception:
            self.wait_for_ready_state_complete()
            self.sleep(settings.MINI_TIMEOUT)
            actual = self.get_page_title().strip()
            try:
                self.assertEqual(expected, actual, error % (expected, actual))
            except Exception:
                self.wait_for_ready_state_complete()
                self.sleep(settings.MINI_TIMEOUT)
                actual = self.get_page_title().strip()
                self.assertEqual(expected, actual, error % (expected, actual))
        if self.demo_mode:
            a_t = "ASSERT TITLE"
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert_title(self._language)
            messenger_post = "%s: {%s}" % (a_t, title)
            self.__highlight_with_assert_success(messenger_post, "html")
        if self.recorder_mode:
            url = self.get_current_url()
            if url and len(url) > 0:
                if ("http:") in url or ("https:") in url or ("file:") in url:
                    if self.get_session_storage_item("pause_recorder") == "no":
                        time_stamp = self.execute_script("return Date.now();")
                        action = ["as_ti", title, "", time_stamp]
                        self.__extra_actions.append(action)
        return True

    def assert_no_js_errors(self):
        """Asserts that there are no JavaScript "SEVERE"-level page errors.
        Works ONLY for Chrome (non-headless) and Chrome-based browsers.
        Does NOT work on Firefox, Edge, IE, and some other browsers:
            * See https://github.com/SeleniumHQ/selenium/issues/1161
        Based on the following Stack Overflow solution:
            * https://stackoverflow.com/a/41150512/7058266
        """
        self.__check_scope()
        time.sleep(0.1)  # May take a moment for errors to appear after loads.
        try:
            browser_logs = self.driver.get_log("browser")
        except (ValueError, WebDriverException):
            # If unable to get browser logs, skip the assert and return.
            return

        messenger_library = "//cdnjs.cloudflare.com/ajax/libs/messenger"
        errors = []
        for entry in browser_logs:
            if entry["level"] == "SEVERE":
                if messenger_library not in entry["message"]:
                    # Add errors if not caused by SeleniumBase dependencies
                    errors.append(entry)
        if len(errors) > 0:
            current_url = self.get_current_url()
            raise Exception(
                "JavaScript errors found on %s => %s" % (current_url, errors)
            )
        if self.demo_mode:
            if self.browser == "chrome" or self.browser == "edge":
                a_t = "ASSERT NO JS ERRORS"
                if self._language != "English":
                    from seleniumbase.fixtures.words import SD

                    a_t = SD.translate_assert_no_js_errors(self._language)
                messenger_post = "%s" % a_t
                self.__highlight_with_assert_success(messenger_post, "html")

    def __activate_html_inspector(self):
        self.wait_for_ready_state_complete()
        time.sleep(0.05)
        js_utils.activate_html_inspector(self.driver)

    def inspect_html(self):
        """Inspects the Page HTML with HTML-Inspector.
        (https://github.com/philipwalton/html-inspector)
        (https://cdnjs.com/libraries/html-inspector)
        Prints the results and also returns them."""
        self.__activate_html_inspector()
        self.wait_for_ready_state_complete()
        script = """HTMLInspector.inspect();"""
        try:
            self.execute_script(script)
        except Exception:
            # If unable to load the JavaScript, skip inspection and return.
            msg = "(Unable to load HTML-Inspector JS! Inspection Skipped!)"
            print("\n" + msg)
            return msg
        time.sleep(0.1)
        browser_logs = []
        try:
            browser_logs = self.driver.get_log("browser")
        except (ValueError, WebDriverException):
            # If unable to get browser logs, skip the assert and return.
            msg = "(Unable to Inspect HTML! -> Only works on Chromium!)"
            print("\n" + msg)
            return msg
        messenger_library = "//cdnjs.cloudflare.com/ajax/libs/messenger"
        url = self.get_current_url()
        header = "\n* HTML Inspection Results: %s" % url
        results = [header]
        row_count = 0
        for entry in browser_logs:
            message = entry["message"]
            if "0:6053 " in message:
                message = message.split("0:6053")[1]
            message = message.replace("\\u003C", "<")
            if message.startswith(' "') and message.count('"') == 2:
                message = message.split('"')[1]
            message = "X - " + message
            if messenger_library not in message:
                if message not in results:
                    results.append(message)
                    row_count += 1
        if row_count > 0:
            results.append("* (See the Console output for details!)")
        else:
            results.append("* (No issues detected!)")
        results = "\n".join(results)
        print(results)
        return results

    def is_chromium(self):
        """ Return True if the browser is Chrome, Edge, or Opera. """
        self.__check_scope()
        chromium = False
        browser_name = self.driver.capabilities["browserName"]
        if browser_name.lower() in ("chrome", "edge", "msedge", "opera"):
            chromium = True
        return chromium

    def __fail_if_not_using_chrome(self, method):
        chrome = False
        browser_name = self.driver.capabilities["browserName"]
        if browser_name.lower() == "chrome":
            chrome = True
        if not chrome:
            from seleniumbase.common.exceptions import NotUsingChromeException

            message = (
                'Error: "%s" should only be called '
                'by tests running with self.browser == "chrome"! '
                'You should add an "if" statement to your code before calling '
                "this method if using browsers that are Not Chrome! "
                'The browser detected was: "%s".' % (method, browser_name)
            )
            raise NotUsingChromeException(message)

    def get_chrome_version(self):
        self.__check_scope()
        self.__fail_if_not_using_chrome("get_chrome_version()")
        driver_capabilities = self.driver.capabilities
        if "version" in driver_capabilities:
            chrome_version = driver_capabilities["version"]
        else:
            chrome_version = driver_capabilities["browserVersion"]
        return chrome_version

    def get_chromedriver_version(self):
        self.__check_scope()
        self.__fail_if_not_using_chrome("get_chromedriver_version()")
        chrome_dict = self.driver.capabilities["chrome"]
        chromedriver_version = chrome_dict["chromedriverVersion"]
        chromedriver_version = chromedriver_version.split(" ")[0]
        return chromedriver_version

    def is_chromedriver_too_old(self):
        """There are known issues with chromedriver versions below 73.
        This can impact tests that need to hover over an element, or ones
        that require a custom downloads folder ("./downloaded_files").
        Due to the situation that newer versions of chromedriver require
        an exact match to the version of Chrome, an "old" version of
        chromedriver is installed by default. It is then up to the user
        to upgrade to the correct version of chromedriver from there.
        This method can be used to change test behavior when trying
        to perform an action that is impacted by having an old version
        of chromedriver installed."""
        self.__check_scope()
        self.__fail_if_not_using_chrome("is_chromedriver_too_old()")
        if int(self.get_chromedriver_version().split(".")[0]) < 73:
            return True  # chromedriver is too old! Please upgrade!
        return False

    def get_google_auth_password(self, totp_key=None):
        """Returns a time-based one-time password based on the
        Google Authenticator password algorithm. Works with Authy.
        If "totp_key" is not specified, defaults to using the one
        provided in seleniumbase/config/settings.py
        Google Auth passwords expire and change at 30-second intervals.
        If the fetched password expires in the next 1.5 seconds, waits
        for a new one before returning it (may take up to 1.5 seconds).
        See https://pyotp.readthedocs.io/en/latest/ for details."""
        import pyotp

        if not totp_key:
            totp_key = settings.TOTP_KEY

        epoch_interval = time.time() / 30.0
        cycle_lifespan = float(epoch_interval) - int(epoch_interval)
        if float(cycle_lifespan) > 0.95:
            # Password expires in the next 1.5 seconds. Wait for a new one.
            for i in range(30):
                time.sleep(0.05)
                epoch_interval = time.time() / 30.0
                cycle_lifespan = float(epoch_interval) - int(epoch_interval)
                if not float(cycle_lifespan) > 0.95:
                    # The new password cycle has begun
                    break

        totp = pyotp.TOTP(totp_key)
        return str(totp.now())

    def convert_css_to_xpath(self, css):
        return css_to_xpath.convert_css_to_xpath(css)

    def convert_xpath_to_css(self, xpath):
        return xpath_to_css.convert_xpath_to_css(xpath)

    def convert_to_css_selector(self, selector, by):
        """This method converts a selector to a CSS_SELECTOR.
        jQuery commands require a CSS_SELECTOR for finding elements.
        This method should only be used for jQuery/JavaScript actions.
        Pure JavaScript doesn't support using a:contains("LINK_TEXT")."""
        if by == By.CSS_SELECTOR:
            return selector
        elif by == By.ID:
            return "#%s" % selector
        elif by == By.CLASS_NAME:
            return ".%s" % selector
        elif by == By.NAME:
            return '[name="%s"]' % selector
        elif by == By.TAG_NAME:
            return selector
        elif by == By.XPATH:
            return self.convert_xpath_to_css(selector)
        elif by == By.LINK_TEXT:
            return 'a:contains("%s")' % selector
        elif by == By.PARTIAL_LINK_TEXT:
            return 'a:contains("%s")' % selector
        else:
            raise Exception(
                "Exception: Could not convert {%s}(by=%s) to CSS_SELECTOR!"
                % (selector, by)
            )

    def set_value(
        self, selector, text, by=By.CSS_SELECTOR, timeout=None, scroll=True
    ):
        """ This method uses JavaScript to update a text field. """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by, xp_ok=False)
        self.wait_for_ready_state_complete()
        self.wait_for_element_present(selector, by=by, timeout=timeout)
        orginal_selector = selector
        css_selector = self.convert_to_css_selector(selector, by=by)
        self.__demo_mode_highlight_if_active(orginal_selector, by)
        if scroll and not self.demo_mode and not self.slow_mode:
            self.scroll_to(orginal_selector, by=by, timeout=timeout)
        if type(text) is int or type(text) is float:
            text = str(text)
        value = re.escape(text)
        value = self.__escape_quotes_if_needed(value)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        the_type = None
        if ":contains\\(" not in css_selector:
            get_type_script = (
                """return document.querySelector('%s').getAttribute('type');"""
                % css_selector
            )
            the_type = self.execute_script(get_type_script)  # Used later
            script = """document.querySelector('%s').value='%s';""" % (
                css_selector,
                value,
            )
            self.execute_script(script)
        else:
            script = """jQuery('%s')[0].value='%s';""" % (css_selector, value)
            self.safe_execute_script(script)
        if text.endswith("\n"):
            element = self.wait_for_element_present(
                orginal_selector, by=by, timeout=timeout
            )
            element.send_keys(Keys.RETURN)
            if settings.WAIT_FOR_RSC_ON_PAGE_LOADS:
                self.wait_for_ready_state_complete()
        else:
            if the_type == "range" and ":contains\\(" not in css_selector:
                # Some input sliders need a mouse event to trigger listeners.
                try:
                    mouse_move_script = (
                        """m_elm = document.querySelector('%s');"""
                        """m_evt = new Event('mousemove');"""
                        """m_elm.dispatchEvent(m_evt);"""
                        % css_selector
                    )
                    self.execute_script(mouse_move_script)
                except Exception:
                    pass
        self.__demo_mode_pause_if_active()

    def js_update_text(self, selector, text, by=By.CSS_SELECTOR, timeout=None):
        """JavaScript + send_keys are used to update a text field.
        Performs self.set_value() and triggers event listeners.
        If text ends in "\n", set_value() presses RETURN after.
        Works faster than send_keys() alone due to the JS call.
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if type(text) is int or type(text) is float:
            text = str(text)
        self.set_value(selector, text, by=by, timeout=timeout)
        if not text.endswith("\n"):
            try:
                element = page_actions.wait_for_element_present(
                    self.driver, selector, by, timeout=0.2
                )
                element.send_keys(" " + Keys.BACK_SPACE)
            except Exception:
                pass

    def js_type(self, selector, text, by=By.CSS_SELECTOR, timeout=None):
        """Same as self.js_update_text()
        JavaScript + send_keys are used to update a text field.
        Performs self.set_value() and triggers event listeners.
        If text ends in "\n", set_value() presses RETURN after.
        Works faster than send_keys() alone due to the JS call.
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.js_update_text(selector, text, by=by, timeout=timeout)

    def set_text(self, selector, text, by=By.CSS_SELECTOR, timeout=None):
        """Same as self.js_update_text()
        JavaScript + send_keys are used to update a text field.
        Performs self.set_value() and triggers event listeners.
        If text ends in "\n", set_value() presses RETURN after.
        Works faster than send_keys() alone due to the JS call.
        If not an input or textarea, sets textContent instead."""
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_ready_state_complete()
        element = page_actions.wait_for_element_present(
            self.driver, selector, by, timeout
        )
        if element.tag_name == "input" or element.tag_name == "textarea":
            self.js_update_text(selector, text, by=by, timeout=timeout)
        else:
            self.set_text_content(selector, text, by=by, timeout=timeout)

    def set_text_content(
        self, selector, text, by=By.CSS_SELECTOR, timeout=None, scroll=False
    ):
        """This method uses JavaScript to set an element's textContent.
        If the element is an input or textarea, sets the value instead."""
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_ready_state_complete()
        element = page_actions.wait_for_element_present(
            self.driver, selector, by, timeout
        )
        if element.tag_name == "input" or element.tag_name == "textarea":
            self.js_update_text(selector, text, by=by, timeout=timeout)
            return
        orginal_selector = selector
        css_selector = self.convert_to_css_selector(selector, by=by)
        if scroll:
            self.__demo_mode_highlight_if_active(orginal_selector, by)
            if not self.demo_mode and not self.slow_mode:
                self.scroll_to(orginal_selector, by=by, timeout=timeout)
        if type(text) is int or type(text) is float:
            text = str(text)
        value = re.escape(text)
        value = self.__escape_quotes_if_needed(value)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        if ":contains\\(" not in css_selector:
            script = """document.querySelector('%s').textContent='%s';""" % (
                css_selector,
                value,
            )
            self.execute_script(script)
        else:
            script = """jQuery('%s')[0].textContent='%s';""" % (
                css_selector,
                value,
            )
            self.safe_execute_script(script)
        self.__demo_mode_pause_if_active()

    def jquery_update_text(
        self, selector, text, by=By.CSS_SELECTOR, timeout=None
    ):
        """This method uses jQuery to update a text field.
        If the text string ends with the newline character,
        Selenium finishes the call, which simulates pressing
        {Enter/Return} after the text is entered."""
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by, xp_ok=False)
        element = self.wait_for_element_visible(
            selector, by=by, timeout=timeout
        )
        self.__demo_mode_highlight_if_active(selector, by)
        self.scroll_to(selector, by=by)
        selector = self.convert_to_css_selector(selector, by=by)
        selector = self.__make_css_match_first_element_only(selector)
        selector = self.__escape_quotes_if_needed(selector)
        text = re.escape(text)
        text = self.__escape_quotes_if_needed(text)
        update_text_script = """jQuery('%s').val('%s');""" % (selector, text)
        self.safe_execute_script(update_text_script)
        if text.endswith("\n"):
            element.send_keys("\n")
        self.__demo_mode_pause_if_active()

    def get_value(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """This method uses JavaScript to get the value of an input field.
        (Works on both input fields and textarea fields.)"""
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_ready_state_complete()
        self.wait_for_element_present(selector, by=by, timeout=timeout)
        orginal_selector = selector
        css_selector = self.convert_to_css_selector(selector, by=by)
        self.__demo_mode_highlight_if_active(orginal_selector, by)
        if not self.demo_mode and not self.slow_mode:
            self.scroll_to(orginal_selector, by=by, timeout=timeout)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        if ":contains\\(" not in css_selector:
            script = """return document.querySelector('%s').value;""" % (
                css_selector
            )
            value = self.execute_script(script)
        else:
            script = """return jQuery('%s')[0].value;""" % css_selector
            value = self.safe_execute_script(script)
        return value

    def set_time_limit(self, time_limit):
        self.__check_scope()
        if time_limit:
            try:
                sb_config.time_limit = float(time_limit)
            except Exception:
                sb_config.time_limit = None
        else:
            sb_config.time_limit = None
        if sb_config.time_limit and sb_config.time_limit > 0:
            sb_config.time_limit_ms = int(sb_config.time_limit * 1000.0)
            self.time_limit = sb_config.time_limit
        else:
            self.time_limit = None
            sb_config.time_limit = None
            sb_config.time_limit_ms = None

    def set_default_timeout(self, timeout):
        """This method changes the default timeout values of test methods
        for the duration of the current test.
        Effected timeouts: (used by methods that wait for elements)
            * settings.SMALL_TIMEOUT - (default value: 6 seconds)
            * settings.LARGE_TIMEOUT - (default value: 10 seconds)
        The minimum allowable default timeout is: 0.5 seconds.
        The maximum allowable default timeout is: 60.0 seconds.
        (Test methods can still override timeouts outside that range.)
        """
        self.__check_scope()
        if not type(timeout) is int and not type(timeout) is float:
            raise Exception('Expecting a numeric value for "timeout"!')
        if timeout < 0:
            raise Exception('The "timeout" cannot be a negative number!')
        timeout = float(timeout)
        # Min default timeout: 0.5 seconds. Max default timeout: 60.0 seconds.
        min_timeout = 0.5
        max_timeout = 60.0
        if timeout < min_timeout:
            logging.info("Minimum default timeout = %s" % min_timeout)
            timeout = min_timeout
        elif timeout > max_timeout:
            logging.info("Maximum default timeout = %s" % max_timeout)
            timeout = max_timeout
        self.__overrided_default_timeouts = True
        sb_config._is_timeout_changed = True
        settings.SMALL_TIMEOUT = timeout
        settings.LARGE_TIMEOUT = timeout

    def reset_default_timeout(self):
        """Reset default timeout values to the original from settings.py
        This method reverts the changes made by set_default_timeout()"""
        if self.__overrided_default_timeouts:
            if sb_config._SMALL_TIMEOUT and sb_config._LARGE_TIMEOUT:
                settings.SMALL_TIMEOUT = sb_config._SMALL_TIMEOUT
                settings.LARGE_TIMEOUT = sb_config._LARGE_TIMEOUT
                sb_config._is_timeout_changed = False
                self.__overrided_default_timeouts = False

    def skip(self, reason=""):
        """ Mark the test as Skipped. """
        self.__check_scope()
        if self.dashboard:
            test_id = self.__get_test_id_2()
            if hasattr(self, "_using_sb_fixture"):
                test_id = sb_config._test_id
            if (
                test_id in sb_config._results.keys()
                and sb_config._results[test_id] == "Passed"
            ):
                # Duplicate tearDown() called where test already passed
                self.__passed_then_skipped = True
            self.__will_be_skipped = True
            sb_config._results[test_id] = "Skipped"
        if self.with_db_reporting:
            if self.is_pytest:
                self.__skip_reason = reason
            else:
                self._nose_skip_reason = reason
        # Add skip reason to the logs
        if not hasattr(self, "_using_sb_fixture"):
            test_id = self.__get_test_id()  # Recalculate the test id
        test_logpath = os.path.join(self.log_path, test_id)
        self.__create_log_path_as_needed(test_logpath)
        browser = self.browser
        if not reason:
            reason = "No skip reason given"
        log_helper.log_skipped_test_data(self, test_logpath, browser, reason)
        # Finally skip the test for real
        self.skipTest(reason)

    ############

    # Shadow DOM / Shadow-root methods

    def __get_shadow_element(self, selector, timeout=None):
        self.wait_for_ready_state_complete()
        if timeout is None:
            timeout = settings.SMALL_TIMEOUT
        elif timeout == 0:
            timeout = 0.1  # Use for: is_shadow_element_* (* = present/visible)
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.__fail_if_invalid_shadow_selector_usage(selector)
        if "::shadow " not in selector:
            raise Exception(
                'A Shadow DOM selector must contain at least one "::shadow "!'
            )
        selectors = selector.split("::shadow ")
        element = self.get_element(selectors[0])
        selector_chain = selectors[0]
        for selector_part in selectors[1:]:
            shadow_root = self.execute_script(
                "return arguments[0].shadowRoot", element
            )
            if timeout == 0.1 and not shadow_root:
                raise Exception(
                    "Element {%s} has no shadow root!" % selector_chain
                )
            elif not shadow_root:
                time.sleep(2)  # Wait two seconds for the shadow root to appear
                shadow_root = self.execute_script(
                    "return arguments[0].shadowRoot", element
                )
                if not shadow_root:
                    raise Exception(
                        "Element {%s} has no shadow root!" % selector_chain
                    )
            selector_chain += "::shadow "
            selector_chain += selector_part
            try:
                element = page_actions.wait_for_element_present(
                    shadow_root,
                    selector_part,
                    by=By.CSS_SELECTOR,
                    timeout=timeout,
                )
            except Exception:
                msg = (
                    "Shadow DOM Element {%s} was not present after %s seconds!"
                    % (selector_chain, timeout)
                )
                page_actions.timeout_exception("NoSuchElementException", msg)
        return element

    def __fail_if_invalid_shadow_selector_usage(self, selector):
        if selector.strip().endswith("::shadow"):
            msg = (
                "A Shadow DOM selector cannot end on a shadow root element!"
                " End the selector with an element inside the shadow root!"
            )
            raise Exception(msg)

    def __is_shadow_selector(self, selector):
        self.__fail_if_invalid_shadow_selector_usage(selector)
        if "::shadow " in selector:
            return True
        return False

    def __shadow_click(self, selector):
        element = self.__get_shadow_element(selector)
        element.click()

    def __shadow_type(self, selector, text, clear_first=True):
        element = self.__get_shadow_element(selector)
        if clear_first:
            try:
                element.clear()
                backspaces = Keys.BACK_SPACE * 42  # Autofill Defense
                element.send_keys(backspaces)
            except Exception:
                pass
        if type(text) is int or type(text) is float:
            text = str(text)
        if not text.endswith("\n"):
            element.send_keys(text)
            if settings.WAIT_FOR_RSC_ON_PAGE_LOADS:
                self.wait_for_ready_state_complete()
        else:
            element.send_keys(text[:-1])
            element.send_keys(Keys.RETURN)
            if settings.WAIT_FOR_RSC_ON_PAGE_LOADS:
                self.wait_for_ready_state_complete()

    def __shadow_clear(self, selector):
        element = self.__get_shadow_element(selector)
        try:
            element.clear()
            backspaces = Keys.BACK_SPACE * 42  # Autofill Defense
            element.send_keys(backspaces)
        except Exception:
            pass

    def __get_shadow_text(self, selector):
        element = self.__get_shadow_element(selector)
        return element.text

    def __wait_for_shadow_text_visible(self, text, selector):
        start_ms = time.time() * 1000.0
        stop_ms = start_ms + (settings.SMALL_TIMEOUT * 1000.0)
        for x in range(int(settings.SMALL_TIMEOUT * 10)):
            try:
                actual_text = self.__get_shadow_text(selector).strip()
                text = text.strip()
                if text not in actual_text:
                    msg = (
                        "Expected text {%s} in element {%s} was not visible!"
                        % (text, selector)
                    )
                    page_actions.timeout_exception(
                        "ElementNotVisibleException", msg
                    )
                return True
            except Exception:
                now_ms = time.time() * 1000.0
                if now_ms >= stop_ms:
                    break
                time.sleep(0.1)
        actual_text = self.__get_shadow_text(selector).strip()
        text = text.strip()
        if text not in actual_text:
            msg = "Expected text {%s} in element {%s} was not visible!" % (
                text,
                selector,
            )
            page_actions.timeout_exception("ElementNotVisibleException", msg)
        return True

    def __wait_for_exact_shadow_text_visible(self, text, selector):
        start_ms = time.time() * 1000.0
        stop_ms = start_ms + (settings.SMALL_TIMEOUT * 1000.0)
        for x in range(int(settings.SMALL_TIMEOUT * 10)):
            try:
                actual_text = self.__get_shadow_text(selector).strip()
                text = text.strip()
                if text != actual_text:
                    msg = (
                        "Expected exact text {%s} in element {%s} not visible!"
                        "" % (text, selector)
                    )
                    page_actions.timeout_exception(
                        "ElementNotVisibleException", msg
                    )
                return True
            except Exception:
                now_ms = time.time() * 1000.0
                if now_ms >= stop_ms:
                    break
                time.sleep(0.1)
        actual_text = self.__get_shadow_text(selector).strip()
        text = text.strip()
        if text != actual_text:
            msg = (
                "Expected exact text {%s} in element {%s} was not visible!"
                % (text, selector)
            )
            page_actions.timeout_exception("ElementNotVisibleException", msg)
        return True

    def __assert_shadow_text_visible(self, text, selector):
        self.__wait_for_shadow_text_visible(text, selector)
        if self.demo_mode:
            a_t = "ASSERT TEXT"
            i_n = "in"
            by = By.CSS_SELECTOR
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert_text(self._language)
                i_n = SD.translate_in(self._language)
            messenger_post = "%s: {%s} %s %s: %s" % (
                a_t,
                text,
                i_n,
                by.upper(),
                selector,
            )
            try:
                js_utils.activate_jquery(self.driver)
                js_utils.post_messenger_success_message(
                    self.driver, messenger_post, self.message_duration
                )
            except Exception:
                pass

    def __assert_exact_shadow_text_visible(self, text, selector):
        self.__wait_for_exact_shadow_text_visible(text, selector)
        if self.demo_mode:
            a_t = "ASSERT EXACT TEXT"
            i_n = "in"
            by = By.CSS_SELECTOR
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert_exact_text(self._language)
                i_n = SD.translate_in(self._language)
            messenger_post = "%s: {%s} %s %s: %s" % (
                a_t,
                text,
                i_n,
                by.upper(),
                selector,
            )
            try:
                js_utils.activate_jquery(self.driver)
                js_utils.post_messenger_success_message(
                    self.driver, messenger_post, self.message_duration
                )
            except Exception:
                pass

    def __is_shadow_element_present(self, selector):
        try:
            element = self.__get_shadow_element(selector, timeout=0.1)
            return element is not None
        except Exception:
            return False

    def __is_shadow_element_visible(self, selector):
        try:
            element = self.__get_shadow_element(selector, timeout=0.1)
            return element.is_displayed()
        except Exception:
            return False

    def __wait_for_shadow_element_present(self, selector):
        element = self.__get_shadow_element(selector)
        return element

    def __wait_for_shadow_element_visible(self, selector):
        element = self.__get_shadow_element(selector)
        if not element.is_displayed():
            msg = "Shadow DOM Element {%s} was not visible!" % selector
            page_actions.timeout_exception("NoSuchElementException", msg)
        return element

    def __wait_for_shadow_attribute_present(
        self, selector, attribute, value=None, timeout=None
    ):
        element = self.__get_shadow_element(selector, timeout=timeout)
        actual_value = element.get_attribute(attribute)
        plural = "s"
        if timeout == 1:
            plural = ""
        if value is None:
            # The element attribute only needs to exist
            if actual_value is not None:
                return element
            else:
                # The element does not have the attribute
                message = (
                    "Expected attribute {%s} of element {%s} "
                    "was not present after %s second%s!"
                    % (attribute, selector, timeout, plural)
                )
                page_actions.timeout_exception(
                    "NoSuchAttributeException", message
                )
        else:
            if actual_value == value:
                return element
            else:
                message = (
                    "Expected value {%s} for attribute {%s} of element "
                    "{%s} was not present after %s second%s! "
                    "(The actual value was {%s})"
                    % (
                        value,
                        attribute,
                        selector,
                        timeout,
                        plural,
                        actual_value,
                    )
                )
                page_actions.timeout_exception(
                    "NoSuchAttributeException", message
                )

    def __assert_shadow_element_present(self, selector):
        self.__get_shadow_element(selector)
        if self.demo_mode:
            a_t = "ASSERT"
            by = By.CSS_SELECTOR
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert(self._language)
            messenger_post = "%s %s: %s" % (a_t, by.upper(), selector)
            try:
                js_utils.activate_jquery(self.driver)
                js_utils.post_messenger_success_message(
                    self.driver, messenger_post, self.message_duration
                )
            except Exception:
                pass

    def __assert_shadow_element_visible(self, selector):
        element = self.__get_shadow_element(selector)
        if not element.is_displayed():
            msg = "Shadow DOM Element {%s} was not visible!" % selector
            page_actions.timeout_exception("NoSuchElementException", msg)
        if self.demo_mode:
            a_t = "ASSERT"
            by = By.CSS_SELECTOR
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert(self._language)
            messenger_post = "%s %s: %s" % (a_t, by.upper(), selector)
            try:
                js_utils.activate_jquery(self.driver)
                js_utils.post_messenger_success_message(
                    self.driver, messenger_post, self.message_duration
                )
            except Exception:
                pass

    ############

    # Application "Local Storage" controls

    def set_local_storage_item(self, key, value):
        self.__check_scope()
        self.execute_script(
            "window.localStorage.setItem('{}', '{}');".format(key, value)
        )

    def get_local_storage_item(self, key):
        self.__check_scope()
        return self.execute_script(
            "return window.localStorage.getItem('{}');".format(key)
        )

    def remove_local_storage_item(self, key):
        self.__check_scope()
        self.execute_script(
            "window.localStorage.removeItem('{}');".format(key)
        )

    def clear_local_storage(self):
        self.__check_scope()
        self.execute_script("window.localStorage.clear();")

    def get_local_storage_keys(self):
        self.__check_scope()
        return self.execute_script(
            "var ls = window.localStorage, keys = []; "
            "for (var i = 0; i < ls.length; ++i) "
            "  keys[i] = ls.key(i); "
            "return keys;"
        )

    def get_local_storage_items(self):
        self.__check_scope()
        return self.execute_script(
            r"var ls = window.localStorage, items = {}; "
            "for (var i = 0, k; i < ls.length; ++i) "
            "  items[k = ls.key(i)] = ls.getItem(k); "
            "return items;"
        )

    # Application "Session Storage" controls

    def set_session_storage_item(self, key, value):
        self.__check_scope()
        self.execute_script(
            "window.sessionStorage.setItem('{}', '{}');".format(key, value)
        )

    def get_session_storage_item(self, key):
        self.__check_scope()
        return self.execute_script(
            "return window.sessionStorage.getItem('{}');".format(key)
        )

    def remove_session_storage_item(self, key):
        self.__check_scope()
        self.execute_script(
            "window.sessionStorage.removeItem('{}');".format(key)
        )

    def clear_session_storage(self):
        self.__check_scope()
        self.execute_script("window.sessionStorage.clear();")

    def get_session_storage_keys(self):
        self.__check_scope()
        return self.execute_script(
            "var ls = window.sessionStorage, keys = []; "
            "for (var i = 0; i < ls.length; ++i) "
            "  keys[i] = ls.key(i); "
            "return keys;"
        )

    def get_session_storage_items(self):
        self.__check_scope()
        return self.execute_script(
            r"var ls = window.sessionStorage, items = {}; "
            "for (var i = 0, k; i < ls.length; ++i) "
            "  items[k = ls.key(i)] = ls.getItem(k); "
            "return items;"
        )

    ############

    # Duplicates (Avoids name confusion when migrating from other frameworks.)

    def open_url(self, url):
        """ Same as self.open() """
        self.open(url)

    def visit(self, url):
        """ Same as self.open() """
        self.open(url)

    def visit_url(self, url):
        """ Same as self.open() """
        self.open(url)

    def goto(self, url):
        """ Same as self.open() """
        self.open(url)

    def go_to(self, url):
        """ Same as self.open() """
        self.open(url)

    def reload(self):
        """ Same as self.refresh_page() """
        self.refresh_page()

    def reload_page(self):
        """ Same as self.refresh_page() """
        self.refresh_page()

    def input(
        self, selector, text, by=By.CSS_SELECTOR, timeout=None, retry=False
    ):
        """ Same as self.update_text() """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.update_text(selector, text, by=by, timeout=timeout, retry=retry)

    def fill(
        self, selector, text, by=By.CSS_SELECTOR, timeout=None, retry=False
    ):
        """ Same as self.update_text() """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.update_text(selector, text, by=by, timeout=timeout, retry=retry)

    def write(
        self, selector, text, by=By.CSS_SELECTOR, timeout=None, retry=False
    ):
        """ Same as self.update_text() """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.update_text(selector, text, by=by, timeout=timeout, retry=retry)

    def send_keys(self, selector, text, by=By.CSS_SELECTOR, timeout=None):
        """ Same as self.add_text() """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        self.add_text(selector, text, by=by, timeout=timeout)

    def click_link(self, link_text, timeout=None):
        """ Same as self.click_link_text() """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.click_link_text(link_text, timeout=timeout)

    def click_partial_link(self, partial_link_text, timeout=None):
        """ Same as self.click_partial_link_text() """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.click_partial_link_text(partial_link_text, timeout=timeout)

    def wait_for_element_visible(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """ Same as self.wait_for_element() """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            return self.__wait_for_shadow_element_visible(selector)
        return page_actions.wait_for_element_visible(
            self.driver, selector, by, timeout
        )

    def wait_for_element_not_present(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """Same as self.wait_for_element_absent()
        Waits for an element to no longer appear in the HTML of a page.
        A hidden element still counts as appearing in the page HTML.
        If waiting for elements to be hidden instead of nonexistent,
        use wait_for_element_not_visible() instead.
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        return page_actions.wait_for_element_absent(
            self.driver, selector, by, timeout
        )

    def assert_element_not_present(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """Same as self.assert_element_absent()
        Will raise an exception if the element stays present.
        A hidden element counts as a present element, which fails this assert.
        If you want to assert that elements are hidden instead of nonexistent,
        use assert_element_not_visible() instead.
        (Note that hidden elements are still present in the HTML of the page.)
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.wait_for_element_absent(selector, by=by, timeout=timeout)
        return True

    def assert_no_broken_links(self, multithreaded=True):
        """ Same as self.assert_no_404_errors() """
        self.assert_no_404_errors(multithreaded=multithreaded)

    def wait(self, seconds):
        """ Same as self.sleep() - Some JS frameworks use this method name. """
        self.sleep(seconds)

    def block_ads(self):
        """ Same as self.ad_block() """
        self.ad_block()

    def _print(self, msg):
        """Same as Python's print(), but won't print during multithreaded runs
        because overlapping print() commands may lead to unexpected output.
        In most cases, the print() command won't print for multithreaded tests,
        but there are some exceptions, and this will take care of those.
        Here's an example of running tests multithreaded: "pytest -n=4".
        To force a print during multithreaded tests, use: "sys.stderr.write()".
        To print without the new-line character end, use: "sys.stdout.write()".
        """
        if not sb_config._multithreaded:
            print(msg)

    def start_tour(self, name=None, interval=0):
        self.play_tour(name=name, interval=interval)

    ############

    def add_css_link(self, css_link):
        self.__check_scope()
        js_utils.add_css_link(self.driver, css_link)

    def add_js_link(self, js_link):
        self.__check_scope()
        js_utils.add_js_link(self.driver, js_link)

    def add_css_style(self, css_style):
        self.__check_scope()
        js_utils.add_css_style(self.driver, css_style)

    def add_js_code_from_link(self, js_link):
        self.__check_scope()
        js_utils.add_js_code_from_link(self.driver, js_link)

    def add_js_code(self, js_code):
        self.__check_scope()
        js_utils.add_js_code(self.driver, js_code)

    def add_meta_tag(self, http_equiv=None, content=None):
        self.__check_scope()
        js_utils.add_meta_tag(
            self.driver, http_equiv=http_equiv, content=content
        )

    ############

    def create_presentation(
        self, name=None, theme="default", transition="default"
    ):
        """Creates a Reveal-JS presentation that you can add slides to.
        @Params
        name - If creating multiple presentations at the same time,
               use this to specify the name of the current presentation.
        theme - Set a theme with a unique style for the presentation.
                Valid themes: "serif" (default), "sky", "white", "black",
                              "simple", "league", "moon", "night",
                              "beige", "blood", and "solarized".
        transition - Set a transition between slides.
                     Valid transitions: "none" (default), "slide", "fade",
                                        "zoom", "convex", and "concave".
        """
        if not name:
            name = "default"
        if not theme or theme == "default":
            theme = "serif"
        valid_themes = [
            "serif",
            "white",
            "black",
            "beige",
            "simple",
            "sky",
            "league",
            "moon",
            "night",
            "blood",
            "solarized",
        ]
        theme = theme.lower()
        if theme not in valid_themes:
            raise Exception(
                "Theme {%s} not found! Valid themes: %s"
                % (theme, valid_themes)
            )
        if not transition or transition == "default":
            transition = "none"
        valid_transitions = [
            "none",
            "slide",
            "fade",
            "zoom",
            "convex",
            "concave",
        ]
        transition = transition.lower()
        if transition not in valid_transitions:
            raise Exception(
                "Transition {%s} not found! Valid transitions: %s"
                % (transition, valid_transitions)
            )

        reveal_theme_css = None
        if theme == "serif":
            reveal_theme_css = constants.Reveal.SERIF_MIN_CSS
        elif theme == "sky":
            reveal_theme_css = constants.Reveal.SKY_MIN_CSS
        elif theme == "white":
            reveal_theme_css = constants.Reveal.WHITE_MIN_CSS
        elif theme == "black":
            reveal_theme_css = constants.Reveal.BLACK_MIN_CSS
        elif theme == "simple":
            reveal_theme_css = constants.Reveal.SIMPLE_MIN_CSS
        elif theme == "league":
            reveal_theme_css = constants.Reveal.LEAGUE_MIN_CSS
        elif theme == "moon":
            reveal_theme_css = constants.Reveal.MOON_MIN_CSS
        elif theme == "night":
            reveal_theme_css = constants.Reveal.NIGHT_MIN_CSS
        elif theme == "beige":
            reveal_theme_css = constants.Reveal.BEIGE_MIN_CSS
        elif theme == "blood":
            reveal_theme_css = constants.Reveal.BLOOD_MIN_CSS
        elif theme == "solarized":
            reveal_theme_css = constants.Reveal.SOLARIZED_MIN_CSS
        else:
            # Use the default if unable to determine the theme
            reveal_theme_css = constants.Reveal.SERIF_MIN_CSS

        new_presentation = (
            "<html>\n"
            "<head>\n"
            '<meta charset="utf-8">\n'
            '<meta http-equiv="Content-Type" content="text/html">\n'
            '<meta name="viewport" content="shrink-to-fit=no">\n'
            '<link rel="stylesheet" href="%s">\n'
            '<link rel="stylesheet" href="%s">\n'
            "<style>\n"
            "pre{background-color:#fbe8d4;border-radius:8px;}\n"
            "div[flex_div]{height:68vh;margin:0;align-items:center;"
            "justify-content:center;}\n"
            "img[rounded]{border-radius:16px;max-width:64%%;}\n"
            "</style>\n"
            "</head>\n\n"
            "<body>\n"
            "<!-- Generated by SeleniumBase - https://seleniumbase.io -->\n"
            '<div class="reveal">\n'
            '<div class="slides">\n'
            % (constants.Reveal.MIN_CSS, reveal_theme_css)
        )

        self._presentation_slides[name] = []
        self._presentation_slides[name].append(new_presentation)
        self._presentation_transition[name] = transition

    def add_slide(
        self,
        content=None,
        image=None,
        code=None,
        iframe=None,
        content2=None,
        notes=None,
        transition=None,
        name=None,
    ):
        """Allows the user to add slides to a presentation.
        @Params
        content - The HTML content to display on the presentation slide.
        image - Attach an image (from a URL link) to the slide.
        code - Attach code of any programming language to the slide.
               Language-detection will be used to add syntax formatting.
        iframe - Attach an iFrame (from a URL link) to the slide.
        content2 - HTML content to display after adding an image or code.
        notes - Additional notes to include with the slide.
                ONLY SEEN if show_notes is set for the presentation.
        transition - Set a transition between slides. (overrides previous)
                     Valid transitions: "none" (default), "slide", "fade",
                                        "zoom", "convex", and "concave".
        name - If creating multiple presentations at the same time,
               use this to select the presentation to add slides to.
        """

        if not name:
            name = "default"
        if name not in self._presentation_slides:
            # Create a presentation if it doesn't already exist
            self.create_presentation(name=name)
        if not content:
            content = ""
        if not content2:
            content2 = ""
        if not notes:
            notes = ""
        if not transition:
            transition = self._presentation_transition[name]
        elif transition == "default":
            transition = "none"
        valid_transitions = [
            "none",
            "slide",
            "fade",
            "zoom",
            "convex",
            "concave",
        ]
        transition = transition.lower()
        if transition not in valid_transitions:
            raise Exception(
                "Transition {%s} not found! Valid transitions: %s"
                "" % (transition, valid_transitions)
            )
        add_line = ""
        if content.startswith("<"):
            add_line = "\n"
        html = '\n<section data-transition="%s">%s%s' % (
            transition,
            add_line,
            content,
        )
        if image:
            html += '\n<div flex_div><img rounded src="%s" /></div>' % image
        if code:
            html += "\n<div></div>"
            html += '\n<pre class="prettyprint">\n%s</pre>' % code
        if iframe:
            html += (
                "\n<div></div>"
                '\n<iframe src="%s" style="width:92%%;height:550px;" '
                'title="iframe content"></iframe>' % iframe
            )
        add_line = ""
        if content2.startswith("<"):
            add_line = "\n"
        if content2:
            html += "%s%s" % (add_line, content2)
        html += '\n<aside class="notes">%s</aside>' % notes
        html += "\n</section>\n"

        self._presentation_slides[name].append(html)

    def save_presentation(
        self, name=None, filename=None, show_notes=False, interval=0
    ):
        """Saves a Reveal-JS Presentation to a file for later use.
        @Params
        name - If creating multiple presentations at the same time,
               use this to select the one you wish to use.
        filename - The name of the HTML file that you wish to
                   save the presentation to. (filename must end in ".html")
        show_notes - When set to True, the Notes feature becomes enabled,
                     which allows presenters to see notes next to slides.
        interval - The delay time between autoplaying slides. (in seconds)
                   If set to 0 (default), autoplay is disabled.
        """

        if not name:
            name = "default"
        if not filename:
            filename = "my_presentation.html"
        if name not in self._presentation_slides:
            raise Exception("Presentation {%s} does not exist!" % name)
        if not filename.endswith(".html"):
            raise Exception('Presentation file must end in ".html"!')
        if not interval:
            interval = 0
        if interval == 0 and self.interval:
            interval = float(self.interval)
        if not type(interval) is int and not type(interval) is float:
            raise Exception('Expecting a numeric value for "interval"!')
        if interval < 0:
            raise Exception('The "interval" cannot be a negative number!')
        interval_ms = float(interval) * 1000.0

        show_notes_str = "false"
        if show_notes:
            show_notes_str = "true"

        the_html = ""
        for slide in self._presentation_slides[name]:
            the_html += slide

        the_html += (
            "\n</div>\n"
            "</div>\n"
            '<script src="%s"></script>\n'
            '<script src="%s"></script>\n'
            "<script>Reveal.initialize("
            "{showNotes: %s, slideNumber: true, progress: true, hash: false, "
            "autoSlide: %s,});"
            "</script>\n"
            "</body>\n"
            "</html>\n"
            % (
                constants.Reveal.MIN_JS,
                constants.PrettifyJS.RUN_PRETTIFY_JS,
                show_notes_str,
                interval_ms,
            )
        )

        # Remove duplicate ChartMaker library declarations
        chart_libs = """
            <script src="%s"></script>
            <script src="%s"></script>
            <script src="%s"></script>
            <script src="%s"></script>
            """ % (
            constants.HighCharts.HC_JS,
            constants.HighCharts.EXPORTING_JS,
            constants.HighCharts.EXPORT_DATA_JS,
            constants.HighCharts.ACCESSIBILITY_JS,
        )
        if the_html.count(chart_libs) > 1:
            chart_libs_comment = "<!-- HighCharts Libraries Imported -->"
            the_html = the_html.replace(chart_libs, chart_libs_comment)
            # Only need to import the HighCharts libraries once
            the_html = the_html.replace(chart_libs_comment, chart_libs, 1)

        saved_presentations_folder = constants.Presentations.SAVED_FOLDER
        if saved_presentations_folder.endswith("/"):
            saved_presentations_folder = saved_presentations_folder[:-1]
        if not os.path.exists(saved_presentations_folder):
            try:
                os.makedirs(saved_presentations_folder)
            except Exception:
                pass
        file_path = saved_presentations_folder + "/" + filename
        out_file = codecs.open(file_path, "w+", encoding="utf-8")
        out_file.writelines(the_html)
        out_file.close()
        print("\n>>> [%s] was saved!\n" % file_path)
        return file_path

    def begin_presentation(
        self, name=None, filename=None, show_notes=False, interval=0
    ):
        """Begin a Reveal-JS Presentation in the web browser.
        @Params
        name - If creating multiple presentations at the same time,
               use this to select the one you wish to use.
        filename - The name of the HTML file that you wish to
                   save the presentation to. (filename must end in ".html")
        show_notes - When set to True, the Notes feature becomes enabled,
                     which allows presenters to see notes next to slides.
        interval - The delay time between autoplaying slides. (in seconds)
                   If set to 0 (default), autoplay is disabled.
        """
        if self.headless or self.xvfb:
            return  # Presentations should not run in headless mode.
        if not name:
            name = "default"
        if not filename:
            filename = "my_presentation.html"
        if name not in self._presentation_slides:
            raise Exception("Presentation {%s} does not exist!" % name)
        if not filename.endswith(".html"):
            raise Exception('Presentation file must end in ".html"!')
        if not interval:
            interval = 0
        if interval == 0 and self.interval:
            interval = float(self.interval)
        if not type(interval) is int and not type(interval) is float:
            raise Exception('Expecting a numeric value for "interval"!')
        if interval < 0:
            raise Exception('The "interval" cannot be a negative number!')

        end_slide = (
            '\n<section data-transition="none">\n'
            '<p class="End_Presentation_Now"> </p>\n</section>\n'
        )
        self._presentation_slides[name].append(end_slide)
        file_path = self.save_presentation(
            name=name,
            filename=filename,
            show_notes=show_notes,
            interval=interval,
        )
        self._presentation_slides[name].pop()

        self.open_html_file(file_path)
        presentation_folder = constants.Presentations.SAVED_FOLDER
        try:
            while (
                len(self.driver.window_handles) > 0
                and presentation_folder in self.get_current_url()
            ):
                time.sleep(0.05)
                if self.is_element_visible(
                    "section.present p.End_Presentation_Now"
                ):
                    break
                time.sleep(0.05)
        except Exception:
            pass

    ############

    def create_pie_chart(
        self,
        chart_name=None,
        title=None,
        subtitle=None,
        data_name=None,
        unit=None,
        libs=True,
        labels=True,
        legend=True,
    ):
        """Creates a JavaScript pie chart using "HighCharts".
        @Params
        chart_name - If creating multiple charts,
                     use this to select which one.
        title - The title displayed for the chart.
        subtitle - The subtitle displayed for the chart.
        data_name - The series name. Useful for multi-series charts.
                    If no data_name, will default to using "Series 1".
        unit - The description label given to the chart's y-axis values.
        libs - The option to include Chart libraries (JS and CSS files).
               Should be set to True (default) for the first time creating
               a chart on a web page. If creating multiple charts on the
               same web page, you won't need to re-import the libraries
               when creating additional charts.
        labels - If True, displays labels on the chart for data points.
        legend - If True, displays the data point legend on the chart.
        """
        if not chart_name:
            chart_name = "default"
        if not data_name:
            data_name = ""
        style = "pie"
        self.__create_highchart(
            chart_name=chart_name,
            title=title,
            subtitle=subtitle,
            style=style,
            data_name=data_name,
            unit=unit,
            libs=libs,
            labels=labels,
            legend=legend,
        )

    def create_bar_chart(
        self,
        chart_name=None,
        title=None,
        subtitle=None,
        data_name=None,
        unit=None,
        libs=True,
        labels=True,
        legend=True,
    ):
        """Creates a JavaScript bar chart using "HighCharts".
        @Params
        chart_name - If creating multiple charts,
                     use this to select which one.
        title - The title displayed for the chart.
        subtitle - The subtitle displayed for the chart.
        data_name - The series name. Useful for multi-series charts.
                    If no data_name, will default to using "Series 1".
        unit - The description label given to the chart's y-axis values.
        libs - The option to include Chart libraries (JS and CSS files).
               Should be set to True (default) for the first time creating
               a chart on a web page. If creating multiple charts on the
               same web page, you won't need to re-import the libraries
               when creating additional charts.
        labels - If True, displays labels on the chart for data points.
        legend - If True, displays the data point legend on the chart.
        """
        if not chart_name:
            chart_name = "default"
        if not data_name:
            data_name = ""
        style = "bar"
        self.__create_highchart(
            chart_name=chart_name,
            title=title,
            subtitle=subtitle,
            style=style,
            data_name=data_name,
            unit=unit,
            libs=libs,
            labels=labels,
            legend=legend,
        )

    def create_column_chart(
        self,
        chart_name=None,
        title=None,
        subtitle=None,
        data_name=None,
        unit=None,
        libs=True,
        labels=True,
        legend=True,
    ):
        """Creates a JavaScript column chart using "HighCharts".
        @Params
        chart_name - If creating multiple charts,
                     use this to select which one.
        title - The title displayed for the chart.
        subtitle - The subtitle displayed for the chart.
        data_name - The series name. Useful for multi-series charts.
                    If no data_name, will default to using "Series 1".
        unit - The description label given to the chart's y-axis values.
        libs - The option to include Chart libraries (JS and CSS files).
               Should be set to True (default) for the first time creating
               a chart on a web page. If creating multiple charts on the
               same web page, you won't need to re-import the libraries
               when creating additional charts.
        labels - If True, displays labels on the chart for data points.
        legend - If True, displays the data point legend on the chart.
        """
        if not chart_name:
            chart_name = "default"
        if not data_name:
            data_name = ""
        style = "column"
        self.__create_highchart(
            chart_name=chart_name,
            title=title,
            subtitle=subtitle,
            style=style,
            data_name=data_name,
            unit=unit,
            libs=libs,
            labels=labels,
            legend=legend,
        )

    def create_line_chart(
        self,
        chart_name=None,
        title=None,
        subtitle=None,
        data_name=None,
        unit=None,
        zero=False,
        libs=True,
        labels=True,
        legend=True,
    ):
        """Creates a JavaScript line chart using "HighCharts".
        @Params
        chart_name - If creating multiple charts,
                     use this to select which one.
        title - The title displayed for the chart.
        subtitle - The subtitle displayed for the chart.
        data_name - The series name. Useful for multi-series charts.
                    If no data_name, will default to using "Series 1".
        unit - The description label given to the chart's y-axis values.
        zero - If True, the y-axis always starts at 0. (Default: False).
        libs - The option to include Chart libraries (JS and CSS files).
               Should be set to True (default) for the first time creating
               a chart on a web page. If creating multiple charts on the
               same web page, you won't need to re-import the libraries
               when creating additional charts.
        labels - If True, displays labels on the chart for data points.
        legend - If True, displays the data point legend on the chart.
        """
        if not chart_name:
            chart_name = "default"
        if not data_name:
            data_name = ""
        style = "line"
        self.__create_highchart(
            chart_name=chart_name,
            title=title,
            subtitle=subtitle,
            style=style,
            data_name=data_name,
            unit=unit,
            zero=zero,
            libs=libs,
            labels=labels,
            legend=legend,
        )

    def create_area_chart(
        self,
        chart_name=None,
        title=None,
        subtitle=None,
        data_name=None,
        unit=None,
        zero=False,
        libs=True,
        labels=True,
        legend=True,
    ):
        """Creates a JavaScript area chart using "HighCharts".
        @Params
        chart_name - If creating multiple charts,
                     use this to select which one.
        title - The title displayed for the chart.
        subtitle - The subtitle displayed for the chart.
        data_name - The series name. Useful for multi-series charts.
                    If no data_name, will default to using "Series 1".
        unit - The description label given to the chart's y-axis values.
        zero - If True, the y-axis always starts at 0. (Default: False).
        libs - The option to include Chart libraries (JS and CSS files).
               Should be set to True (default) for the first time creating
               a chart on a web page. If creating multiple charts on the
               same web page, you won't need to re-import the libraries
               when creating additional charts.
        labels - If True, displays labels on the chart for data points.
        legend - If True, displays the data point legend on the chart.
        """
        if not chart_name:
            chart_name = "default"
        if not data_name:
            data_name = ""
        style = "area"
        self.__create_highchart(
            chart_name=chart_name,
            title=title,
            subtitle=subtitle,
            style=style,
            data_name=data_name,
            unit=unit,
            zero=zero,
            libs=libs,
            labels=labels,
            legend=legend,
        )

    def __create_highchart(
        self,
        chart_name=None,
        title=None,
        subtitle=None,
        style=None,
        data_name=None,
        unit=None,
        zero=False,
        libs=True,
        labels=True,
        legend=True,
    ):
        """ Creates a JavaScript chart using the "HighCharts" library. """
        if not chart_name:
            chart_name = "default"
        if not title:
            title = ""
        if not subtitle:
            subtitle = ""
        if not style:
            style = "pie"
        if not data_name:
            data_name = "Series 1"
        if not unit:
            unit = "Values"
        if labels:
            labels = "true"
        else:
            labels = "false"
        if legend:
            legend = "true"
        else:
            legend = "false"
        title = title.replace("'", "\\'")
        subtitle = subtitle.replace("'", "\\'")
        unit = unit.replace("'", "\\'")
        self._chart_count += 1
        # If chart_libs format is changed, also change: save_presentation()
        chart_libs = """
            <script src="%s"></script>
            <script src="%s"></script>
            <script src="%s"></script>
            <script src="%s"></script>
            """ % (
            constants.HighCharts.HC_JS,
            constants.HighCharts.EXPORTING_JS,
            constants.HighCharts.EXPORT_DATA_JS,
            constants.HighCharts.ACCESSIBILITY_JS,
        )
        if not libs:
            chart_libs = ""
        chart_css = """
            <style>
            .highcharts-figure, .highcharts-data-table table {
                min-width: 320px;
                max-width: 660px;
                margin: 1em auto;
            }
            .highcharts-data-table table {
                font-family: Verdana, sans-serif;
                border-collapse: collapse;
                border: 1px solid #EBEBEB;
                margin: 10px auto;
                text-align: center;
                width: 100%;
                max-width: 500px;
            }
            .highcharts-data-table caption {
                padding: 1em 0;
                font-size: 1.2em;
                color: #555;
            }
            .highcharts-data-table th {
                font-weight: 600;
                padding: 0.5em;
            }
            .highcharts-data-table td, .highcharts-data-table th,
            .highcharts-data-table caption {
                padding: 0.5em;
            }
            .highcharts-data-table thead tr,
            .highcharts-data-table tr:nth-child(even) {
                background: #f8f8f8;
            }
            .highcharts-data-table tr:hover {
                background: #f1f7ff;
            }
            </style>
            """
        if not libs:
            chart_css = ""
        chart_description = ""
        chart_figure = """
            <figure class="highcharts-figure">
                <div id="chartcontainer_num_%s"></div>
                <p class="highcharts-description">%s</p>
            </figure>
            """ % (
            self._chart_count,
            chart_description,
        )
        min_zero = ""
        if zero:
            min_zero = "min: 0,"
        chart_init_1 = """
            <script>
            // Build the chart
            Highcharts.chart('chartcontainer_num_%s', {
            credits: {
                enabled: false
            },
            title: {
                text: '%s'
            },
            subtitle: {
                text: '%s'
            },
            xAxis: { },
            yAxis: {
                %s
                title: {
                    text: '%s',
                    style: {
                        fontSize: '14px'
                    }
                },
                labels: {
                    useHTML: true,
                    style: {
                        fontSize: '14px'
                    }
                }
            },
            chart: {
                renderTo: 'statusChart',
                plotBackgroundColor: null,
                plotBorderWidth: null,
                plotShadow: false,
                type: '%s'
            },
            """ % (
            self._chart_count,
            title,
            subtitle,
            min_zero,
            unit,
            style,
        )
        #  "{series.name}:"
        point_format = (
            r"<b>{point.y}</b><br />" r"<b>{point.percentage:.1f}%</b>"
        )
        if style != "pie":
            point_format = r"<b>{point.y}</b>"
        chart_init_2 = (
            """
            tooltip: {
                enabled: true,
                useHTML: true,
                style: {
                    padding: '6px',
                    fontSize: '14px'
                },
                backgroundColor: {
                    linearGradient: {
                        x1: 0,
                        y1: 0,
                        x2: 0,
                        y2: 1
                    },
                    stops: [
                        [0, 'rgba(255, 255, 255, 0.78)'],
                        [0.5, 'rgba(235, 235, 235, 0.76)'],
                        [1, 'rgba(244, 252, 255, 0.74)']
                    ]
                },
                hideDelay: 40,
                pointFormat: '%s'
            },
            """
            % point_format
        )
        chart_init_3 = """
            accessibility: {
                point: {
                    valueSuffix: '%%'
                }
            },
            plotOptions: {
                series: {
                    states: {
                        inactive: {
                            opacity: 0.85
                        }
                    }
                },
                pie: {
                    size: "95%%",
                    allowPointSelect: true,
                    animation: false,
                    cursor: 'pointer',
                    dataLabels: {
                        enabled: %s,
                        formatter: function() {
                          if (this.y > 0) {
                            return this.point.name + ': ' + this.point.y
                          }
                        }
                    },
                    states: {
                        hover: {
                            enabled: true
                        }
                    },
                    showInLegend: %s
                }
            },
            """ % (
            labels,
            legend,
        )
        if style != "pie":
            chart_init_3 = """
                allowPointSelect: true,
                cursor: 'pointer',
                legend: {
                    layout: 'vertical',
                    align: 'right',
                    verticalAlign: 'middle'
                },
                states: {
                    hover: {
                        enabled: true
                    }
                },
                plotOptions: {
                    series: {
                        dataLabels: {
                            enabled: %s
                        },
                        showInLegend: %s,
                        animation: false,
                        shadow: false,
                        lineWidth: 3,
                        fillOpacity: 0.5,
                        marker: {
                            enabled: true
                        }
                    }
                },
                """ % (
                labels,
                legend,
            )
        chart_init = chart_init_1 + chart_init_2 + chart_init_3
        color_by_point = "true"
        if style != "pie":
            color_by_point = "false"
        series = """
            series: [{
            name: '%s',
            colorByPoint: %s,
            data: [
            """ % (
            data_name,
            color_by_point,
        )
        new_chart = chart_libs + chart_css + chart_figure + chart_init + series
        self._chart_data[chart_name] = []
        self._chart_label[chart_name] = []
        self._chart_data[chart_name].append(new_chart)
        self._chart_first_series[chart_name] = True
        self._chart_series_count[chart_name] = 1

    def add_series_to_chart(self, data_name=None, chart_name=None):
        """Add a new data series to an existing chart.
        This allows charts to have multiple data sets.
        @Params
        data_name - Set the series name. Useful for multi-series charts.
        chart_name - If creating multiple charts,
                     use this to select which one.
        """
        if not chart_name:
            chart_name = "default"
        self._chart_series_count[chart_name] += 1
        if not data_name:
            data_name = "Series %s" % self._chart_series_count[chart_name]
        series = (
            """
            ]
            },
            {
            name: '%s',
            colorByPoint: false,
            data: [
            """
            % data_name
        )
        self._chart_data[chart_name].append(series)
        self._chart_first_series[chart_name] = False

    def add_data_point(self, label, value, color=None, chart_name=None):
        """Add a data point to a SeleniumBase-generated chart.
        @Params
        label - The label name for the data point.
        value - The numeric value of the data point.
        color - The HTML color of the data point.
                Can be an RGB color. Eg: "#55ACDC".
                Can also be a named color. Eg: "Teal".
        chart_name - If creating multiple charts,
                     use this to select which one.
        """
        if not chart_name:
            chart_name = "default"
        if chart_name not in self._chart_data:
            # Create a chart if it doesn't already exist
            self.create_pie_chart(chart_name=chart_name)
        if not value:
            value = 0
        if not type(value) is int and not type(value) is float:
            raise Exception('Expecting a numeric value for "value"!')
        if not color:
            color = ""
        label = label.replace("'", "\\'")
        color = color.replace("'", "\\'")
        data_point = """
            {
            name: '%s',
            y: %s,
            color: '%s'
            },
            """ % (
            label,
            value,
            color,
        )
        self._chart_data[chart_name].append(data_point)
        if self._chart_first_series[chart_name]:
            self._chart_label[chart_name].append(label)

    def save_chart(self, chart_name=None, filename=None, folder=None):
        """Saves a SeleniumBase-generated chart to a file for later use.
        @Params
        chart_name - If creating multiple charts at the same time,
                     use this to select the one you wish to use.
        filename - The name of the HTML file that you wish to
                   save the chart to. (filename must end in ".html")
        folder - The name of the folder where you wish to
                 save the HTML file. (Default: "./saved_charts/")
        """
        if not chart_name:
            chart_name = "default"
        if not filename:
            filename = "my_chart.html"
        if chart_name not in self._chart_data:
            raise Exception("Chart {%s} does not exist!" % chart_name)
        if not filename.endswith(".html"):
            raise Exception('Chart file must end in ".html"!')
        the_html = '<meta charset="utf-8">\n'
        the_html += '<meta http-equiv="Content-Type" content="text/html">\n'
        the_html += '<meta name="viewport" content="shrink-to-fit=no">\n'
        for chart_data_point in self._chart_data[chart_name]:
            the_html += chart_data_point
        the_html += """
            ]
                }]
            });
            </script>
            """
        axis = "xAxis: {\n"
        axis += "                labels: {\n"
        axis += "                    useHTML: true,\n"
        axis += "                    style: {\n"
        axis += "                        fontSize: '14px',\n"
        axis += "                    },\n"
        axis += "                },\n"
        axis += "            categories: ["
        for label in self._chart_label[chart_name]:
            axis += "'%s'," % label
        axis += "], crosshair: false},"
        the_html = the_html.replace("xAxis: { },", axis)
        if not folder:
            saved_charts_folder = constants.Charts.SAVED_FOLDER
        else:
            saved_charts_folder = folder
        if saved_charts_folder.endswith("/"):
            saved_charts_folder = saved_charts_folder[:-1]
        if not os.path.exists(saved_charts_folder):
            try:
                os.makedirs(saved_charts_folder)
            except Exception:
                pass
        file_path = saved_charts_folder + "/" + filename
        out_file = codecs.open(file_path, "w+", encoding="utf-8")
        out_file.writelines(the_html)
        out_file.close()
        print("\n>>> [%s] was saved!" % file_path)
        return file_path

    def display_chart(self, chart_name=None, filename=None, interval=0):
        """Displays a SeleniumBase-generated chart in the browser window.
        @Params
        chart_name - If creating multiple charts at the same time,
                     use this to select the one you wish to use.
        filename - The name of the HTML file that you wish to
                   save the chart to. (filename must end in ".html")
        interval - The delay time for auto-advancing charts. (in seconds)
                   If set to 0 (default), auto-advancing is disabled.
        """
        if self.headless or self.xvfb:
            interval = 1  # Race through chart if running in headless mode
        if not chart_name:
            chart_name = "default"
        if not filename:
            filename = "my_chart.html"
        if not interval:
            interval = 0
        if interval == 0 and self.interval:
            interval = float(self.interval)
        if not type(interval) is int and not type(interval) is float:
            raise Exception('Expecting a numeric value for "interval"!')
        if interval < 0:
            raise Exception('The "interval" cannot be a negative number!')
        if chart_name not in self._chart_data:
            raise Exception("Chart {%s} does not exist!" % chart_name)
        if not filename.endswith(".html"):
            raise Exception('Chart file must end in ".html"!')
        file_path = self.save_chart(chart_name=chart_name, filename=filename)
        self.open_html_file(file_path)
        chart_folder = constants.Charts.SAVED_FOLDER
        if interval == 0:
            try:
                print("\n*** Close the browser window to continue ***")
                # Will also continue if manually navigating to a new page
                while len(self.driver.window_handles) > 0 and (
                    chart_folder in self.get_current_url()
                ):
                    time.sleep(0.05)
            except Exception:
                pass
        else:
            try:
                start_ms = time.time() * 1000.0
                stop_ms = start_ms + (interval * 1000.0)
                for x in range(int(interval * 10)):
                    now_ms = time.time() * 1000.0
                    if now_ms >= stop_ms:
                        break
                    if len(self.driver.window_handles) == 0:
                        break
                    if chart_folder not in self.get_current_url():
                        break
                    time.sleep(0.1)
            except Exception:
                pass

    def extract_chart(self, chart_name=None):
        """Extracts the HTML from a SeleniumBase-generated chart.
        @Params
        chart_name - If creating multiple charts at the same time,
                     use this to select the one you wish to use.
        """
        if not chart_name:
            chart_name = "default"
        if chart_name not in self._chart_data:
            raise Exception("Chart {%s} does not exist!" % chart_name)
        the_html = ""
        for chart_data_point in self._chart_data[chart_name]:
            the_html += chart_data_point
        the_html += """
            ]
                }]
            });
            </script>
            """
        axis = "xAxis: {\n"
        axis += "                labels: {\n"
        axis += "                    useHTML: true,\n"
        axis += "                    style: {\n"
        axis += "                        fontSize: '14px',\n"
        axis += "                    },\n"
        axis += "                },\n"
        axis += "            categories: ["
        for label in self._chart_label[chart_name]:
            axis += "'%s'," % label
        axis += "], crosshair: false},"
        the_html = the_html.replace("xAxis: { },", axis)
        self._chart_xcount += 1
        the_html = the_html.replace(
            "chartcontainer_num_", "chartcontainer_%s_" % self._chart_xcount
        )
        return the_html

    ############

    def create_tour(self, name=None, theme=None):
        """Creates a tour for a website. By default, the Shepherd JavaScript
        Library is used with the Shepherd "Light" / "Arrows" theme.
        @Params
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        theme - Sets the default theme for the tour.
                Choose from "light"/"arrows", "dark", "default", "square",
                and "square-dark". ("arrows" is used if None is selected.)
                Alternatively, you may use a different JavaScript Library
                as the theme. Those include "IntroJS", "DriverJS",
                "Hopscotch", and "Bootstrap".
        """
        if not name:
            name = "default"

        if theme:
            if theme.lower() == "bootstrap":
                self.create_bootstrap_tour(name)
            elif theme.lower() == "hopscotch":
                self.create_hopscotch_tour(name)
            elif theme.lower() == "intro":
                self.create_introjs_tour(name)
            elif theme.lower() == "introjs":
                self.create_introjs_tour(name)
            elif theme.lower() == "driver":
                self.create_driverjs_tour(name)
            elif theme.lower() == "driverjs":
                self.create_driverjs_tour(name)
            elif theme.lower() == "shepherd":
                self.create_shepherd_tour(name, theme="light")
            elif theme.lower() == "light":
                self.create_shepherd_tour(name, theme="light")
            elif theme.lower() == "dark":
                self.create_shepherd_tour(name, theme="dark")
            elif theme.lower() == "arrows":
                self.create_shepherd_tour(name, theme="light")
            elif theme.lower() == "square":
                self.create_shepherd_tour(name, theme="square")
            elif theme.lower() == "square-dark":
                self.create_shepherd_tour(name, theme="square-dark")
            elif theme.lower() == "default":
                self.create_shepherd_tour(name, theme="default")
            else:
                self.create_shepherd_tour(name, theme)
        else:
            self.create_shepherd_tour(name, theme="light")

    def create_shepherd_tour(self, name=None, theme=None):
        """Creates a Shepherd JS website tour.
        @Params
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        theme - Sets the default theme for the tour.
                Choose from "light"/"arrows", "dark", "default", "square",
                and "square-dark". ("light" is used if None is selected.)
        """

        shepherd_theme = "shepherd-theme-arrows"
        if theme:
            if theme.lower() == "default":
                shepherd_theme = "shepherd-theme-default"
            elif theme.lower() == "dark":
                shepherd_theme = "shepherd-theme-dark"
            elif theme.lower() == "light":
                shepherd_theme = "shepherd-theme-arrows"
            elif theme.lower() == "arrows":
                shepherd_theme = "shepherd-theme-arrows"
            elif theme.lower() == "square":
                shepherd_theme = "shepherd-theme-square"
            elif theme.lower() == "square-dark":
                shepherd_theme = "shepherd-theme-square-dark"

        if not name:
            name = "default"

        new_tour = (
            """
            // Shepherd Tour
            var tour = new Shepherd.Tour({
                defaults: {
                    classes: '%s',
                    scrollTo: true
                }
            });
            var allButtons = {
                skip: {
                    text: "Skip",
                    action: tour.cancel,
                    classes: 'shepherd-button-secondary tour-button-left'
                },
                back: {
                    text: "Back",
                    action: tour.back,
                    classes: 'shepherd-button-secondary'
                },
                next: {
                    text: "Next",
                    action: tour.next,
                    classes: 'shepherd-button-primary tour-button-right'
                },
            };
            var firstStepButtons = [allButtons.skip, allButtons.next];
            var midTourButtons = [allButtons.back, allButtons.next];
            """
            % shepherd_theme
        )
        self._tour_steps[name] = []
        self._tour_steps[name].append(new_tour)

    def create_bootstrap_tour(self, name=None):
        """Creates a Bootstrap tour for a website.
        @Params
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        """
        if not name:
            name = "default"

        new_tour = """
            // Bootstrap Tour
            var tour = new Tour({
            container: 'body',
            animation: true,
            keyboard: true,
            orphan: true,
            smartPlacement: true,
            autoscroll: true,
            backdrop: true,
            backdropContainer: 'body',
            backdropPadding: 3,
            });
            tour.addSteps([
            """

        self._tour_steps[name] = []
        self._tour_steps[name].append(new_tour)

    def create_driverjs_tour(self, name=None):
        """Creates a DriverJS tour for a website.
        @Params
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        """
        if not name:
            name = "default"

        new_tour = """
            // DriverJS Tour
            var tour = new Driver({
                opacity: 0.24,  // Background opacity (0: no popover / overlay)
                padding: 6,    // Distance of element from around the edges
                allowClose: false, // Whether clicking on overlay should close
                overlayClickNext: false, // Move to next step on overlay click
                doneBtnText: 'Done', // Text that appears on the Done button
                closeBtnText: 'Close', // Text appearing on the Close button
                nextBtnText: 'Next', // Text that appears on the Next button
                prevBtnText: 'Previous', // Text appearing on Previous button
                showButtons: true, // This shows control buttons in the footer
                keyboardControl: true, // (escape to close, arrow keys to move)
                animate: true,   // Animate while changing highlighted element
            });
            tour.defineSteps([
            """

        self._tour_steps[name] = []
        self._tour_steps[name].append(new_tour)

    def create_hopscotch_tour(self, name=None):
        """Creates a Hopscotch tour for a website.
        @Params
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        """
        if not name:
            name = "default"

        new_tour = """
            // Hopscotch Tour
            var tour = {
            id: "hopscotch_tour",
            steps: [
            """

        self._tour_steps[name] = []
        self._tour_steps[name].append(new_tour)

    def create_introjs_tour(self, name=None):
        """Creates an IntroJS tour for a website.
        @Params
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        """
        if not hasattr(sb_config, "introjs_theme_color"):
            sb_config.introjs_theme_color = constants.TourColor.theme_color
        if not hasattr(sb_config, "introjs_hover_color"):
            sb_config.introjs_hover_color = constants.TourColor.hover_color
        if not name:
            name = "default"

        new_tour = """
            // IntroJS Tour
            function startIntro(){
            var intro = introJs();
            intro.setOptions({
            steps: [
            """

        self._tour_steps[name] = []
        self._tour_steps[name].append(new_tour)

    def set_introjs_colors(self, theme_color=None, hover_color=None):
        """Use this method to set the theme colors for IntroJS tours.
        Args must be hex color values that start with a "#" sign.
        If a color isn't specified, the color will reset to the default.
        The border color of buttons is set to the hover color.
        @Params
        theme_color - The color of buttons.
        hover_color - The color of buttons after hovering over them.
        """
        if not hasattr(sb_config, "introjs_theme_color"):
            sb_config.introjs_theme_color = constants.TourColor.theme_color
        if not hasattr(sb_config, "introjs_hover_color"):
            sb_config.introjs_hover_color = constants.TourColor.hover_color
        if theme_color:
            match = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', theme_color)
            if not match:
                raise Exception(
                    'Expecting a hex value color that starts with "#"!')
            sb_config.introjs_theme_color = theme_color
        else:
            sb_config.introjs_theme_color = constants.TourColor.theme_color
        if hover_color:
            match = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', hover_color)
            if not match:
                raise Exception(
                    'Expecting a hex value color that starts with "#"!')
            sb_config.introjs_hover_color = hover_color
        else:
            sb_config.introjs_hover_color = constants.TourColor.hover_color

    def add_tour_step(
        self,
        message,
        selector=None,
        name=None,
        title=None,
        theme=None,
        alignment=None,
        duration=None,
    ):
        """Allows the user to add tour steps for a website.
        @Params
        message - The message to display.
        selector - The CSS Selector of the Element to attach to.
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        title - Additional header text that appears above the message.
        theme - (Shepherd Tours ONLY) The styling of the tour step.
                Choose from "light"/"arrows", "dark", "default", "square",
                and "square-dark". ("arrows" is used if None is selected.)
        alignment - Choose from "top", "bottom", "left", and "right".
                    ("top" is default, except for Hopscotch and DriverJS).
        duration - (Bootstrap Tours ONLY) The amount of time, in seconds,
                   before automatically advancing to the next tour step.
        """
        if not selector:
            selector = "html"
        if page_utils.is_name_selector(selector):
            name = page_utils.get_name_from_selector(selector)
            selector = '[name="%s"]' % name
        if page_utils.is_xpath_selector(selector):
            selector = self.convert_to_css_selector(selector, By.XPATH)
        selector = self.__escape_quotes_if_needed(selector)

        if not name:
            name = "default"
        if name not in self._tour_steps:
            # By default, will create an IntroJS tour if no tours exist
            self.create_tour(name=name, theme="introjs")

        if not title:
            title = ""
        title = self.__escape_quotes_if_needed(title)

        if message:
            message = self.__escape_quotes_if_needed(message)
        else:
            message = ""

        if not alignment or alignment not in [
            "top",
            "bottom",
            "left",
            "right",
        ]:
            t_name = self._tour_steps[name][0]
            if "Hopscotch" not in t_name and "DriverJS" not in t_name:
                alignment = "top"
            else:
                alignment = "bottom"

        if "Bootstrap" in self._tour_steps[name][0]:
            self.__add_bootstrap_tour_step(
                message,
                selector=selector,
                name=name,
                title=title,
                alignment=alignment,
                duration=duration,
            )
        elif "DriverJS" in self._tour_steps[name][0]:
            self.__add_driverjs_tour_step(
                message,
                selector=selector,
                name=name,
                title=title,
                alignment=alignment,
            )
        elif "Hopscotch" in self._tour_steps[name][0]:
            self.__add_hopscotch_tour_step(
                message,
                selector=selector,
                name=name,
                title=title,
                alignment=alignment,
            )
        elif "IntroJS" in self._tour_steps[name][0]:
            self.__add_introjs_tour_step(
                message,
                selector=selector,
                name=name,
                title=title,
                alignment=alignment,
            )
        else:
            self.__add_shepherd_tour_step(
                message,
                selector=selector,
                name=name,
                title=title,
                theme=theme,
                alignment=alignment,
            )

    def __add_shepherd_tour_step(
        self,
        message,
        selector=None,
        name=None,
        title=None,
        theme=None,
        alignment=None,
    ):
        """Allows the user to add tour steps for a website.
        @Params
        message - The message to display.
        selector - The CSS Selector of the Element to attach to.
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        title - Additional header text that appears above the message.
        theme - (Shepherd Tours ONLY) The styling of the tour step.
                Choose from "light"/"arrows", "dark", "default", "square",
                and "square-dark". ("arrows" is used if None is selected.)
        alignment - Choose from "top", "bottom", "left", and "right".
                    ("top" is the default alignment).
        """
        if theme == "default":
            shepherd_theme = "shepherd-theme-default"
        elif theme == "dark":
            shepherd_theme = "shepherd-theme-dark"
        elif theme == "light":
            shepherd_theme = "shepherd-theme-arrows"
        elif theme == "arrows":
            shepherd_theme = "shepherd-theme-arrows"
        elif theme == "square":
            shepherd_theme = "shepherd-theme-square"
        elif theme == "square-dark":
            shepherd_theme = "shepherd-theme-square-dark"
        else:
            shepherd_base_theme = re.search(
                r"[\S\s]+classes: '([\S\s]+)',[\S\s]+",
                self._tour_steps[name][0],
            ).group(1)
            shepherd_theme = shepherd_base_theme

        shepherd_classes = shepherd_theme
        if selector == "html":
            shepherd_classes += " shepherd-orphan"
        buttons = "firstStepButtons"
        if len(self._tour_steps[name]) > 1:
            buttons = "midTourButtons"

        step = """tour.addStep('%s', {
                    title: '%s',
                    classes: '%s',
                    text: '%s',
                    attachTo: {element: '%s', on: '%s'},
                    buttons: %s,
                    advanceOn: '.docs-link click'
                });""" % (
            name,
            title,
            shepherd_classes,
            message,
            selector,
            alignment,
            buttons,
        )

        self._tour_steps[name].append(step)

    def __add_bootstrap_tour_step(
        self,
        message,
        selector=None,
        name=None,
        title=None,
        alignment=None,
        duration=None,
    ):
        """Allows the user to add tour steps for a website.
        @Params
        message - The message to display.
        selector - The CSS Selector of the Element to attach to.
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        title - Additional header text that appears above the message.
        alignment - Choose from "top", "bottom", "left", and "right".
                    ("top" is the default alignment).
        duration - (Bootstrap Tours ONLY) The amount of time, in seconds,
                   before automatically advancing to the next tour step.
        """
        if selector != "html":
            selector = self.__make_css_match_first_element_only(selector)
            element_row = "element: '%s'," % selector
        else:
            element_row = ""
        if not duration:
            duration = "0"
        else:
            duration = str(float(duration) * 1000.0)

        bd = "backdrop: true,"
        if selector == "html":
            bd = "backdrop: false,"

        step = """{
                %s
                title: '%s',
                content: '%s',
                orphan: true,
                autoscroll: true,
                %s
                placement: 'auto %s',
                smartPlacement: true,
                duration: %s,
                },""" % (
            element_row,
            title,
            message,
            bd,
            alignment,
            duration,
        )

        self._tour_steps[name].append(step)

    def __add_driverjs_tour_step(
        self, message, selector=None, name=None, title=None, alignment=None
    ):
        """Allows the user to add tour steps for a website.
        @Params
        message - The message to display.
        selector - The CSS Selector of the Element to attach to.
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        title - Additional header text that appears above the message.
        alignment - Choose from "top", "bottom", "left", and "right".
                    ("top" is the default alignment).
        """
        message = (
            '<font size="3" color="#33477B"><b>' + message + "</b></font>"
        )
        title_row = ""
        if not title:
            title_row = "title: '%s'," % message
            message = ""
        else:
            title_row = "title: '%s'," % title
        align_row = "position: '%s'," % alignment
        ani_row = "animate: true,"
        if not selector or selector == "html" or selector == "body":
            selector = "body"
            ani_row = "animate: false,"
            align_row = "position: '%s'," % "mid-center"
        element_row = "element: '%s'," % selector
        desc_row = "description: '%s'," % message

        step = """{
                %s
                %s
                popover: {
                  className: 'popover-class',
                  %s
                  %s
                  %s
                }
                },""" % (
            element_row,
            ani_row,
            title_row,
            desc_row,
            align_row,
        )

        self._tour_steps[name].append(step)

    def __add_hopscotch_tour_step(
        self, message, selector=None, name=None, title=None, alignment=None
    ):
        """Allows the user to add tour steps for a website.
        @Params
        message - The message to display.
        selector - The CSS Selector of the Element to attach to.
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        title - Additional header text that appears above the message.
        alignment - Choose from "top", "bottom", "left", and "right".
                    ("bottom" is the default alignment).
        """
        arrow_offset_row = None
        if not selector or selector == "html":
            selector = "head"
            alignment = "bottom"
            arrow_offset_row = "arrowOffset: '200',"
        else:
            arrow_offset_row = ""

        step = """{
                target: '%s',
                title: '%s',
                content: '%s',
                %s
                showPrevButton: 'true',
                scrollDuration: '550',
                placement: '%s'},
                """ % (
            selector,
            title,
            message,
            arrow_offset_row,
            alignment,
        )

        self._tour_steps[name].append(step)

    def __add_introjs_tour_step(
        self, message, selector=None, name=None, title=None, alignment=None
    ):
        """Allows the user to add tour steps for a website.
        @Params
        message - The message to display.
        selector - The CSS Selector of the Element to attach to.
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        title - Additional header text that appears above the message.
        alignment - Choose from "top", "bottom", "left", and "right".
                    ("top" is the default alignment).
        """
        if selector != "html":
            element_row = "element: '%s'," % selector
        else:
            element_row = ""

        if title:
            message = "<center><b>" + title + "</b></center><hr>" + message

        message = '<font size="3" color="#33477B">' + message + "</font>"

        step = """{%s
            intro: '%s',
            position: '%s'},""" % (
            element_row,
            message,
            alignment,
        )

        self._tour_steps[name].append(step)

    def play_tour(self, name=None, interval=0):
        """Plays a tour on the current website.
        @Params
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        interval - The delay time between autoplaying tour steps. (Seconds)
                   If set to 0 (default), the tour is fully manual control.
        """
        from seleniumbase.core import tour_helper

        if self.headless or self.xvfb:
            return  # Tours should not run in headless mode.

        self.wait_for_ready_state_complete()

        if not interval:
            interval = 0
        if interval == 0 and self.interval:
            interval = float(self.interval)

        if not name:
            name = "default"
        if name not in self._tour_steps:
            raise Exception("Tour {%s} does not exist!" % name)

        if "Bootstrap" in self._tour_steps[name][0]:
            tour_helper.play_bootstrap_tour(
                self.driver,
                self._tour_steps,
                self.browser,
                self.message_duration,
                name=name,
                interval=interval,
            )
        elif "DriverJS" in self._tour_steps[name][0]:
            tour_helper.play_driverjs_tour(
                self.driver,
                self._tour_steps,
                self.browser,
                self.message_duration,
                name=name,
                interval=interval,
            )
        elif "Hopscotch" in self._tour_steps[name][0]:
            tour_helper.play_hopscotch_tour(
                self.driver,
                self._tour_steps,
                self.browser,
                self.message_duration,
                name=name,
                interval=interval,
            )
        elif "IntroJS" in self._tour_steps[name][0]:
            tour_helper.play_introjs_tour(
                self.driver,
                self._tour_steps,
                self.browser,
                self.message_duration,
                name=name,
                interval=interval,
            )
        else:
            # "Shepherd"
            tour_helper.play_shepherd_tour(
                self.driver,
                self._tour_steps,
                self.message_duration,
                name=name,
                interval=interval,
            )

    def export_tour(self, name=None, filename="my_tour.js", url=None):
        """Exports a tour as a JS file.
        You can call self.export_tour() anywhere where you would
        normally use self.play_tour() to play a website tour.
        It will include necessary resources as well, such as jQuery.
        You'll be able to copy the tour directly into the Console of
        any web browser to play the tour outside of SeleniumBase runs.
        @Params
        name - If creating multiple tours at the same time,
               use this to select the tour you wish to add steps to.
        filename - The name of the JavaScript file that you wish to
                   save the tour to.
        url - The URL where the tour starts. If not specified, the URL
              of the current page will be used.
        """
        from seleniumbase.core import tour_helper

        if not url:
            url = self.get_current_url()
        tour_helper.export_tour(
            self._tour_steps, name=name, filename=filename, url=url
        )

    ############

    def activate_jquery_confirm(self):
        """ See https://craftpip.github.io/jquery-confirm/ for usage. """
        self.__check_scope()
        js_utils.activate_jquery_confirm(self.driver)
        self.wait_for_ready_state_complete()

    def set_jqc_theme(self, theme, color=None, width=None):
        """ Sets the default jquery-confirm theme and width (optional).
        Available themes: "bootstrap", "modern", "material", "supervan",
                          "light", "dark", and "seamless".
        Available colors: (This sets the BORDER color, NOT the button color.)
            "blue", "default", "green", "red", "purple", "orange", "dark".
        Width can be set using percent or pixels. Eg: "36.0%", "450px".
        """
        if not self.__changed_jqc_theme:
            self.__jqc_default_theme = constants.JqueryConfirm.DEFAULT_THEME
            self.__jqc_default_color = constants.JqueryConfirm.DEFAULT_COLOR
            self.__jqc_default_width = constants.JqueryConfirm.DEFAULT_WIDTH
        valid_themes = [
            "bootstrap",
            "modern",
            "material",
            "supervan",
            "light",
            "dark",
            "seamless",
        ]
        if theme.lower() not in valid_themes:
            raise Exception(
                "%s is not a valid jquery-confirm theme! "
                "Select from %s" % (theme.lower(), valid_themes)
            )
        constants.JqueryConfirm.DEFAULT_THEME = theme.lower()
        if color:
            valid_colors = [
                "blue",
                "default",
                "green",
                "red",
                "purple",
                "orange",
                "dark",
            ]
            if color.lower() not in valid_colors:
                raise Exception(
                    "%s is not a valid jquery-confirm border color! "
                    "Select from %s" % (color.lower(), valid_colors)
                )
            constants.JqueryConfirm.DEFAULT_COLOR = color.lower()
        if width:
            if type(width) is int or type(width) is float:
                # Convert to a string if a number is given
                width = str(width)
            if width.isnumeric():
                if int(width) <= 0:
                    raise Exception("Width must be set to a positive number!")
                elif int(width) <= 100:
                    width = str(width) + "%"
                else:
                    width = str(width) + "px"  # Use pixels if width is > 100
            if not width.endswith("%") and not width.endswith("px"):
                raise Exception(
                    "jqc width must end with %% for percent or px for pixels!"
                )
            value = None
            if width.endswith("%"):
                value = width[:-1]
            if width.endswith("px"):
                value = width[:-2]
            try:
                value = float(value)
            except Exception:
                raise Exception("%s is not a numeric value!" % value)
            if value <= 0:
                raise Exception("%s is not a positive number!" % value)
            constants.JqueryConfirm.DEFAULT_WIDTH = width

    def reset_jqc_theme(self):
        """ Resets the jqc theme settings to factory defaults. """
        if self.__changed_jqc_theme:
            constants.JqueryConfirm.DEFAULT_THEME = self.__jqc_default_theme
            constants.JqueryConfirm.DEFAULT_COLOR = self.__jqc_default_color
            constants.JqueryConfirm.DEFAULT_WIDTH = self.__jqc_default_width
            self.__changed_jqc_theme = False

    def get_jqc_button_input(self, message, buttons, options=None):
        """
        Pop up a jquery-confirm box and return the text of the button clicked.
        If running in headless mode, the last button text is returned.
        @Params
        message: The message to display in the jquery-confirm dialog.
        buttons: A list of tuples for text and color.
            Example: [("Yes!", "green"), ("No!", "red")]
            Available colors: blue, green, red, orange, purple, default, dark.
            A simple text string also works: "My Button". (Uses default color.)
        options: A list of tuples for options to set.
            Example: [("theme", "bootstrap"), ("width", "450px")]
            Available theme options: bootstrap, modern, material, supervan,
                                     light, dark, and seamless.
            Available colors: (For the BORDER color, NOT the button color.)
                "blue", "default", "green", "red", "purple", "orange", "dark".
            Example option for changing the border color: ("color", "default")
            Width can be set using percent or pixels. Eg: "36.0%", "450px".
        """
        from seleniumbase.core import jqc_helper

        if message and type(message) is not str:
            raise Exception('Expecting a string for arg: "message"!')
        if not type(buttons) is list and not type(buttons) is tuple:
            raise Exception('Expecting a list or tuple for arg: "button"!')
        if len(buttons) < 1:
            raise Exception('List "buttons" requires at least one button!')
        new_buttons = []
        for button in buttons:
            if (
                (type(button) is list or type(button) is tuple) and (
                 len(button) == 1)
            ):
                new_buttons.append(button[0])
            elif (
                (type(button) is list or type(button) is tuple) and (
                 len(button) > 1)
            ):
                new_buttons.append((button[0], str(button[1]).lower()))
            else:
                new_buttons.append((str(button), ""))
        buttons = new_buttons
        if options:
            for option in options:
                if not type(option) is list and not type(option) is tuple:
                    raise Exception('"options" should be a list of tuples!')
        if self.headless or self.xvfb:
            return buttons[-1][0]
        jqc_helper.jquery_confirm_button_dialog(
            self.driver, message, buttons, options
        )
        self.sleep(0.02)
        jf = "document.querySelector('.jconfirm-box').focus();"
        try:
            self.execute_script(jf)
        except Exception:
            pass
        waiting_for_response = True
        while waiting_for_response:
            self.sleep(0.05)
            jqc_open = self.execute_script(
                "return jconfirm.instances.length"
            )
            if str(jqc_open) == "0":
                break
        self.sleep(0.1)
        status = None
        try:
            status = self.execute_script("return $jqc_status")
        except Exception:
            status = self.execute_script(
                "return jconfirm.lastButtonText"
            )
        return status

    def get_jqc_text_input(self, message, button=None, options=None):
        """
        Pop up a jquery-confirm box and return the text submitted by the input.
        If running in headless mode, the text returned is "" by default.
        @Params
        message: The message to display in the jquery-confirm dialog.
        button: A 2-item list or tuple for text and color. Or just the text.
            Example: ["Submit", "blue"] -> (default button if not specified)
            Available colors: blue, green, red, orange, purple, default, dark.
            A simple text string also works: "My Button". (Uses default color.)
        options: A list of tuples for options to set.
            Example: [("theme", "bootstrap"), ("width", "450px")]
            Available theme options: bootstrap, modern, material, supervan,
                                     light, dark, and seamless.
            Available colors: (For the BORDER color, NOT the button color.)
                "blue", "default", "green", "red", "purple", "orange", "dark".
            Example option for changing the border color: ("color", "default")
            Width can be set using percent or pixels. Eg: "36.0%", "450px".
        """
        from seleniumbase.core import jqc_helper

        if message and type(message) is not str:
            raise Exception('Expecting a string for arg: "message"!')
        if button:
            if (
                (type(button) is list or type(button) is tuple) and (
                 len(button) == 1)
            ):
                button = (str(button[0]), "")
            elif (
                (type(button) is list or type(button) is tuple) and (
                 len(button) > 1)
            ):
                valid_colors = [
                    "blue",
                    "default",
                    "green",
                    "red",
                    "purple",
                    "orange",
                    "dark",
                ]
                detected_color = str(button[1]).lower()
                if str(button[1]).lower() not in valid_colors:
                    raise Exception(
                        "%s is an invalid jquery-confirm button color!\n"
                        "Select from %s" % (detected_color, valid_colors)
                    )
                button = (str(button[0]), str(button[1]).lower())
            else:
                button = (str(button), "")
        else:
            button = ("Submit", "blue")

        if options:
            for option in options:
                if not type(option) is list and not type(option) is tuple:
                    raise Exception('"options" should be a list of tuples!')
        if self.headless or self.xvfb:
            return ""
        jqc_helper.jquery_confirm_text_dialog(
            self.driver, message, button, options
        )
        self.sleep(0.02)
        jf = "document.querySelector('.jconfirm-box input.jqc_input').focus();"
        try:
            self.execute_script(jf)
        except Exception:
            pass
        waiting_for_response = True
        while waiting_for_response:
            self.sleep(0.05)
            jqc_open = self.execute_script(
                "return jconfirm.instances.length"
            )
            if str(jqc_open) == "0":
                break
        self.sleep(0.1)
        status = None
        try:
            status = self.execute_script("return $jqc_input")
        except Exception:
            status = self.execute_script(
                "return jconfirm.lastInputText"
            )
        return status

    def get_jqc_form_inputs(self, message, buttons, options=None):
        """
        Pop up a jquery-confirm box and return the input/button texts as tuple.
        If running in headless mode, returns the ("", buttons[-1][0]) tuple.
        @Params
        message: The message to display in the jquery-confirm dialog.
        buttons: A list of tuples for text and color.
            Example: [("Yes!", "green"), ("No!", "red")]
            Available colors: blue, green, red, orange, purple, default, dark.
            A simple text string also works: "My Button". (Uses default color.)
        options: A list of tuples for options to set.
            Example: [("theme", "bootstrap"), ("width", "450px")]
            Available theme options: bootstrap, modern, material, supervan,
                                     light, dark, and seamless.
            Available colors: (For the BORDER color, NOT the button color.)
                "blue", "default", "green", "red", "purple", "orange", "dark".
            Example option for changing the border color: ("color", "default")
            Width can be set using percent or pixels. Eg: "36.0%", "450px".
        """
        from seleniumbase.core import jqc_helper

        if message and type(message) is not str:
            raise Exception('Expecting a string for arg: "message"!')
        if not type(buttons) is list and not type(buttons) is tuple:
            raise Exception('Expecting a list or tuple for arg: "button"!')
        if len(buttons) < 1:
            raise Exception('List "buttons" requires at least one button!')
        new_buttons = []
        for button in buttons:
            if (
                (type(button) is list or type(button) is tuple) and (
                 len(button) == 1)
            ):
                new_buttons.append(button[0])
            elif (
                (type(button) is list or type(button) is tuple) and (
                 len(button) > 1)
            ):
                new_buttons.append((button[0], str(button[1]).lower()))
            else:
                new_buttons.append((str(button), ""))
        buttons = new_buttons
        if options:
            for option in options:
                if not type(option) is list and not type(option) is tuple:
                    raise Exception('"options" should be a list of tuples!')
        if self.headless or self.xvfb:
            return ("", buttons[-1][0])
        jqc_helper.jquery_confirm_full_dialog(
            self.driver, message, buttons, options
        )
        self.sleep(0.02)
        jf = "document.querySelector('.jconfirm-box input.jqc_input').focus();"
        try:
            self.execute_script(jf)
        except Exception:
            pass
        waiting_for_response = True
        while waiting_for_response:
            self.sleep(0.05)
            jqc_open = self.execute_script(
                "return jconfirm.instances.length"
            )
            if str(jqc_open) == "0":
                break
        self.sleep(0.1)
        text_status = None
        button_status = None
        try:
            text_status = self.execute_script("return $jqc_input")
            button_status = self.execute_script("return $jqc_status")
        except Exception:
            text_status = self.execute_script(
                "return jconfirm.lastInputText"
            )
            button_status = self.execute_script(
                "return jconfirm.lastButtonText"
            )
        return (text_status, button_status)

    ############

    def activate_messenger(self):
        self.__check_scope()
        js_utils.activate_messenger(self.driver)
        self.wait_for_ready_state_complete()

    def set_messenger_theme(
        self, theme="default", location="default", max_messages="default"
    ):
        """Sets a theme for posting messages.
        Themes: ["flat", "future", "block", "air", "ice"]
        Locations: ["top_left", "top_center", "top_right",
                    "bottom_left", "bottom_center", "bottom_right"]
        max_messages is the limit of concurrent messages to display.
        """
        self.__check_scope()
        if not theme:
            theme = "default"  # "flat"
        if not location:
            location = "default"  # "bottom_right"
        if not max_messages:
            max_messages = "default"  # "8"
        else:
            max_messages = str(max_messages)  # Value must be in string format
        js_utils.set_messenger_theme(
            self.driver,
            theme=theme,
            location=location,
            max_messages=max_messages,
        )

    def post_message(self, message, duration=None, pause=True, style="info"):
        """Post a message on the screen with Messenger.
        Arguments:
            message: The message to display.
            duration: The time until the message vanishes. (Default: 2.55s)
            pause: If True, the program waits until the message completes.
            style: "info", "success", or "error".

        You can also post messages by using =>
            self.execute_script('Messenger().post("My Message")')
        """
        self.__check_scope()
        if style not in ["info", "success", "error"]:
            style = "info"
        if not duration:
            if not self.message_duration:
                duration = settings.DEFAULT_MESSAGE_DURATION
            else:
                duration = self.message_duration
        try:
            js_utils.post_message(self.driver, message, duration, style=style)
        except Exception:
            print(" * %s message: %s" % (style.upper(), message))
        if pause:
            duration = float(duration) + 0.15
            time.sleep(float(duration))

    def post_message_and_highlight(
        self, message, selector, by=By.CSS_SELECTOR
    ):
        """Post a message on the screen and highlight an element.
        Arguments:
            message: The message to display.
            selector: The selector of the Element to highlight.
            by: The type of selector to search by. (Default: CSS Selector)
        """
        self.__check_scope()
        self.__highlight_with_assert_success(message, selector, by=by)

    def post_success_message(self, message, duration=None, pause=True):
        """Post a success message on the screen with Messenger.
        Arguments:
            message: The success message to display.
            duration: The time until the message vanishes. (Default: 2.55s)
            pause: If True, the program waits until the message completes.
        """
        self.__check_scope()
        if not duration:
            if not self.message_duration:
                duration = settings.DEFAULT_MESSAGE_DURATION
            else:
                duration = self.message_duration
        try:
            js_utils.post_message(
                self.driver, message, duration, style="success"
            )
        except Exception:
            print(" * SUCCESS message: %s" % message)
        if pause:
            duration = float(duration) + 0.15
            time.sleep(float(duration))

    def post_error_message(self, message, duration=None, pause=True):
        """Post an error message on the screen with Messenger.
        Arguments:
            message: The error message to display.
            duration: The time until the message vanishes. (Default: 2.55s)
            pause: If True, the program waits until the message completes.
        """
        self.__check_scope()
        if not duration:
            if not self.message_duration:
                duration = settings.DEFAULT_MESSAGE_DURATION
            else:
                duration = self.message_duration
        try:
            js_utils.post_message(
                self.driver, message, duration, style="error"
            )
        except Exception:
            print(" * ERROR message: %s" % message)
        if pause:
            duration = float(duration) + 0.15
            time.sleep(float(duration))

    ############

    def generate_referral(self, start_page, destination_page, selector=None):
        """This method opens the start_page, creates a referral link there,
        and clicks on that link, which goes to the destination_page.
        If a selector is given, clicks that on the destination_page,
        which can prevent an artificial rise in website bounce-rate.
        (This generates real traffic for testing analytics software.)"""
        self.__check_scope()
        if not page_utils.is_valid_url(destination_page):
            raise Exception(
                "Exception: destination_page {%s} is not a valid URL!"
                % destination_page
            )
        if start_page:
            if not page_utils.is_valid_url(start_page):
                raise Exception(
                    "Exception: start_page {%s} is not a valid URL! "
                    "(Use an empty string or None to start from current page.)"
                    % start_page
                )
            self.open(start_page)
            time.sleep(0.08)
            self.wait_for_ready_state_complete()
        referral_link = (
            """<body>"""
            """<a class='analytics referral test' href='%s' """
            """style='font-family: Arial,sans-serif; """
            """font-size: 30px; color: #18a2cd'>"""
            """Magic Link Button</a></body>""" % destination_page
        )
        self.execute_script(
            '''document.body.outerHTML = \"%s\"''' % referral_link
        )
        # Now click the generated button
        self.click("a.analytics.referral.test", timeout=2)
        time.sleep(0.15)
        if selector:
            self.click(selector)
            time.sleep(0.15)

    def generate_traffic(
        self, start_page, destination_page, loops=1, selector=None
    ):
        """Similar to generate_referral(), but can do multiple loops.
        If a selector is given, clicks that on the destination_page,
        which can prevent an artificial rise in website bounce-rate."""
        self.__check_scope()
        for loop in range(loops):
            self.generate_referral(
                start_page, destination_page, selector=selector
            )
            time.sleep(0.05)

    def generate_referral_chain(self, pages):
        """Use this method to chain the action of creating button links on
        one website page that will take you to the next page.
        (When you want to create a referral to a website for traffic
        generation without increasing the bounce rate, you'll want to visit
        at least one additional page on that site with a button click.)"""
        self.__check_scope()
        if not type(pages) is tuple and not type(pages) is list:
            raise Exception(
                "Exception: Expecting a list of website pages for chaining!"
            )
        if len(pages) < 2:
            raise Exception(
                "Exception: At least two website pages required for chaining!"
            )
        for page in pages:
            # Find out if any of the web pages are invalid before continuing
            if not page_utils.is_valid_url(page):
                raise Exception(
                    "Exception: Website page {%s} is not a valid URL!" % page
                )
        for page in pages:
            self.generate_referral(None, page)

    def generate_traffic_chain(self, pages, loops=1):
        """ Similar to generate_referral_chain(), but for multiple loops. """
        self.__check_scope()
        for loop in range(loops):
            self.generate_referral_chain(pages)
            time.sleep(0.05)

    ############

    def wait_for_element_present(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """Waits for an element to appear in the HTML of a page.
        The element does not need be visible (it may be hidden)."""
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            return self.__wait_for_shadow_element_present(selector)
        return page_actions.wait_for_element_present(
            self.driver, selector, by, timeout
        )

    def wait_for_element(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """Waits for an element to appear in the HTML of a page.
        The element must be visible (it cannot be hidden)."""
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            return self.__wait_for_shadow_element_visible(selector)
        return page_actions.wait_for_element_visible(
            self.driver, selector, by, timeout
        )

    def get_element(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """Same as wait_for_element_present() - returns the element.
        The element does not need be visible (it may be hidden)."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        return self.wait_for_element_present(selector, by=by, timeout=timeout)

    def assert_element_present(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """Similar to wait_for_element_present(), but returns nothing.
        Waits for an element to appear in the HTML of a page.
        The element does not need be visible (it may be hidden).
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        if type(selector) is list:
            self.assert_elements_present(selector, by=by, timeout=timeout)
            return True
        if self.__is_shadow_selector(selector):
            self.__assert_shadow_element_present(selector)
            return True
        self.wait_for_element_present(selector, by=by, timeout=timeout)
        if self.recorder_mode:
            url = self.get_current_url()
            if url and len(url) > 0:
                if ("http:") in url or ("https:") in url or ("file:") in url:
                    if self.get_session_storage_item("pause_recorder") == "no":
                        time_stamp = self.execute_script("return Date.now();")
                        action = ["as_ep", selector, "", time_stamp]
                        self.__extra_actions.append(action)
        return True

    def assert_elements_present(self, *args, **kwargs):
        """Similar to self.assert_element_present(),
            but can assert that multiple elements are present in the HTML.
        The input is a list of elements.
        Optional kwargs include "by" and "timeout" (used by all selectors).
        Raises an exception if any of the elements are not visible.
        Examples:
            self.assert_elements_present("head", "style", "script", "body")
            OR
            self.assert_elements_present(["head", "body", "h1", "h2"])
        """
        self.__check_scope()
        selectors = []
        timeout = None
        by = By.CSS_SELECTOR
        for kwarg in kwargs:
            if kwarg == "timeout":
                timeout = kwargs["timeout"]
            elif kwarg == "by":
                by = kwargs["by"]
            elif kwarg == "selector":
                selector = kwargs["selector"]
                if type(selector) is str:
                    selectors.append(selector)
                elif type(selector) is list:
                    selectors_list = selector
                    for selector in selectors_list:
                        if type(selector) is str:
                            selectors.append(selector)
            else:
                raise Exception('Unknown kwarg: "%s"!' % kwarg)
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        for arg in args:
            if type(arg) is list:
                for selector in arg:
                    if type(selector) is str:
                        selectors.append(selector)
            elif type(arg) is str:
                selectors.append(arg)
        for selector in selectors:
            if self.__is_shadow_selector(selector):
                self.__assert_shadow_element_visible(selector)
                continue
            self.wait_for_element_present(selector, by=by, timeout=timeout)
            continue
        return True

    def find_element(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """ Same as wait_for_element_visible() - returns the element """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.wait_for_element_visible(selector, by=by, timeout=timeout)

    def assert_element(self, selector, by=By.CSS_SELECTOR, timeout=None):
        """Similar to wait_for_element_visible(), but returns nothing.
        As above, will raise an exception if nothing can be found.
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        if type(selector) is list:
            self.assert_elements(selector, by=by, timeout=timeout)
            return True
        if self.__is_shadow_selector(selector):
            self.__assert_shadow_element_visible(selector)
            return True
        self.wait_for_element_visible(selector, by=by, timeout=timeout)
        if self.demo_mode:
            selector, by = self.__recalculate_selector(
                selector, by, xp_ok=False
            )
            a_t = "ASSERT"
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert(self._language)
            messenger_post = "%s %s: %s" % (a_t, by.upper(), selector)
            self.__highlight_with_assert_success(messenger_post, selector, by)
        if self.recorder_mode:
            url = self.get_current_url()
            if url and len(url) > 0:
                if ("http:") in url or ("https:") in url or ("file:") in url:
                    if self.get_session_storage_item("pause_recorder") == "no":
                        time_stamp = self.execute_script("return Date.now();")
                        action = ["as_el", selector, "", time_stamp]
                        self.__extra_actions.append(action)
        return True

    def assert_element_visible(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """Same as self.assert_element()
        As above, will raise an exception if nothing can be found."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.assert_element(selector, by=by, timeout=timeout)
        return True

    def assert_elements(self, *args, **kwargs):
        """Similar to self.assert_element(), but can assert multiple elements.
        The input is a list of elements.
        Optional kwargs include "by" and "timeout" (used by all selectors).
        Raises an exception if any of the elements are not visible.
        Examples:
            self.assert_elements("h1", "h2", "h3")
            OR
            self.assert_elements(["h1", "h2", "h3"])"""
        self.__check_scope()
        selectors = []
        timeout = None
        by = By.CSS_SELECTOR
        for kwarg in kwargs:
            if kwarg == "timeout":
                timeout = kwargs["timeout"]
            elif kwarg == "by":
                by = kwargs["by"]
            elif kwarg == "selector":
                selector = kwargs["selector"]
                if type(selector) is str:
                    selectors.append(selector)
                elif type(selector) is list:
                    selectors_list = selector
                    for selector in selectors_list:
                        if type(selector) is str:
                            selectors.append(selector)
            else:
                raise Exception('Unknown kwarg: "%s"!' % kwarg)
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        for arg in args:
            if type(arg) is list:
                for selector in arg:
                    if type(selector) is str:
                        selectors.append(selector)
            elif type(arg) is str:
                selectors.append(arg)
        for selector in selectors:
            if self.__is_shadow_selector(selector):
                self.__assert_shadow_element_visible(selector)
                continue
            self.wait_for_element_visible(selector, by=by, timeout=timeout)
            if self.demo_mode:
                selector, by = self.__recalculate_selector(selector, by)
                a_t = "ASSERT"
                if self._language != "English":
                    from seleniumbase.fixtures.words import SD

                    a_t = SD.translate_assert(self._language)
                messenger_post = "%s %s: %s" % (a_t, by.upper(), selector)
                self.__highlight_with_assert_success(
                    messenger_post, selector, by
                )
            continue
        return True

    def assert_elements_visible(self, *args, **kwargs):
        """Same as self.assert_elements()
        Raises an exception if any element cannot be found."""
        return self.assert_elements(*args, **kwargs)

    ############

    def wait_for_text_visible(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            return self.__wait_for_shadow_text_visible(text, selector)
        return page_actions.wait_for_text_visible(
            self.driver, text, selector, by, timeout
        )

    def wait_for_exact_text_visible(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            return self.__wait_for_exact_shadow_text_visible(text, selector)
        return page_actions.wait_for_exact_text_visible(
            self.driver, text, selector, by, timeout
        )

    def wait_for_text(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        """ The shorter version of wait_for_text_visible() """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.wait_for_text_visible(
            text, selector, by=by, timeout=timeout
        )

    def find_text(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        """ Same as wait_for_text_visible() - returns the element """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.wait_for_text_visible(
            text, selector, by=by, timeout=timeout
        )

    def assert_text_visible(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        """ Same as assert_text() """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.assert_text(text, selector, by=by, timeout=timeout)

    def assert_text(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        """Similar to wait_for_text_visible()
        Raises an exception if the element or the text is not found.
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            self.__assert_shadow_text_visible(text, selector)
            return True
        self.wait_for_text_visible(text, selector, by=by, timeout=timeout)
        if self.demo_mode:
            a_t = "ASSERT TEXT"
            i_n = "in"
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert_text(self._language)
                i_n = SD.translate_in(self._language)
            messenger_post = "%s: {%s} %s %s: %s" % (
                a_t,
                text,
                i_n,
                by.upper(),
                selector,
            )
            self.__highlight_with_assert_success(messenger_post, selector, by)
        if self.recorder_mode:
            url = self.get_current_url()
            if url and len(url) > 0:
                if ("http:") in url or ("https:") in url or ("file:") in url:
                    if self.get_session_storage_item("pause_recorder") == "no":
                        time_stamp = self.execute_script("return Date.now();")
                        action = ["as_te", text, selector, time_stamp]
                        self.__extra_actions.append(action)
        return True

    def assert_exact_text(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        """Similar to assert_text(), but the text must be exact, rather than
        exist as a subset of the full text.
        (Extra whitespace at the beginning or the end doesn't count.)
        Raises an exception if the element or the text is not found.
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        if self.__is_shadow_selector(selector):
            self.__assert_exact_shadow_text_visible(text, selector)
            return True
        self.wait_for_exact_text_visible(
            text, selector, by=by, timeout=timeout
        )
        if self.demo_mode:
            a_t = "ASSERT EXACT TEXT"
            i_n = "in"
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert_exact_text(self._language)
                i_n = SD.translate_in(self._language)
            messenger_post = "%s: {%s} %s %s: %s" % (
                a_t,
                text,
                i_n,
                by.upper(),
                selector,
            )
            self.__highlight_with_assert_success(messenger_post, selector, by)
        if self.recorder_mode:
            url = self.get_current_url()
            if url and len(url) > 0:
                if ("http:") in url or ("https:") in url or ("file:") in url:
                    if self.get_session_storage_item("pause_recorder") == "no":
                        time_stamp = self.execute_script("return Date.now();")
                        action = ["as_et", text, selector, time_stamp]
                        self.__extra_actions.append(action)
        return True

    ############

    def wait_for_link_text_present(self, link_text, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        start_ms = time.time() * 1000.0
        stop_ms = start_ms + (timeout * 1000.0)
        for x in range(int(timeout * 5)):
            shared_utils.check_if_time_limit_exceeded()
            try:
                if not self.is_link_text_present(link_text):
                    raise Exception(
                        "Link text {%s} was not found!" % link_text
                    )
                return
            except Exception:
                now_ms = time.time() * 1000.0
                if now_ms >= stop_ms:
                    break
                time.sleep(0.2)
        message = "Link text {%s} was not present after %s seconds!" % (
            link_text,
            timeout,
        )
        page_actions.timeout_exception("NoSuchElementException", message)

    def wait_for_partial_link_text_present(self, link_text, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        start_ms = time.time() * 1000.0
        stop_ms = start_ms + (timeout * 1000.0)
        for x in range(int(timeout * 5)):
            shared_utils.check_if_time_limit_exceeded()
            try:
                if not self.is_partial_link_text_present(link_text):
                    raise Exception(
                        "Partial Link text {%s} was not found!" % link_text
                    )
                return
            except Exception:
                now_ms = time.time() * 1000.0
                if now_ms >= stop_ms:
                    break
                time.sleep(0.2)
        message = (
            "Partial Link text {%s} was not present after %s seconds!"
            "" % (link_text, timeout)
        )
        page_actions.timeout_exception("NoSuchElementException", message)

    def wait_for_link_text_visible(self, link_text, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.wait_for_element_visible(
            link_text, by=By.LINK_TEXT, timeout=timeout
        )

    def wait_for_link_text(self, link_text, timeout=None):
        """ The shorter version of wait_for_link_text_visible() """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.wait_for_link_text_visible(link_text, timeout=timeout)

    def find_link_text(self, link_text, timeout=None):
        """ Same as wait_for_link_text_visible() - returns the element """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.wait_for_link_text_visible(link_text, timeout=timeout)

    def assert_link_text(self, link_text, timeout=None):
        """Similar to wait_for_link_text_visible(), but returns nothing.
        As above, will raise an exception if nothing can be found.
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.wait_for_link_text_visible(link_text, timeout=timeout)
        if self.demo_mode:
            a_t = "ASSERT LINK TEXT"
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert_link_text(self._language)
            messenger_post = "%s: {%s}" % (a_t, link_text)
            self.__highlight_with_assert_success(
                messenger_post, link_text, by=By.LINK_TEXT
            )
        if self.recorder_mode:
            url = self.get_current_url()
            if url and len(url) > 0:
                if ("http:") in url or ("https:") in url or ("file:") in url:
                    if self.get_session_storage_item("pause_recorder") == "no":
                        time_stamp = self.execute_script("return Date.now();")
                        action = ["as_lt", link_text, "", time_stamp]
                        self.__extra_actions.append(action)
        return True

    def wait_for_partial_link_text(self, partial_link_text, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.wait_for_element_visible(
            partial_link_text, by=By.PARTIAL_LINK_TEXT, timeout=timeout
        )

    def find_partial_link_text(self, partial_link_text, timeout=None):
        """ Same as wait_for_partial_link_text() - returns the element """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.wait_for_partial_link_text(
            partial_link_text, timeout=timeout
        )

    def assert_partial_link_text(self, partial_link_text, timeout=None):
        """Similar to wait_for_partial_link_text(), but returns nothing.
        As above, will raise an exception if nothing can be found.
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.wait_for_partial_link_text(partial_link_text, timeout=timeout)
        if self.demo_mode:
            a_t = "ASSERT PARTIAL LINK TEXT"
            if self._language != "English":
                from seleniumbase.fixtures.words import SD

                a_t = SD.translate_assert_link_text(self._language)
            messenger_post = "%s: {%s}" % (a_t, partial_link_text)
            self.__highlight_with_assert_success(
                messenger_post, partial_link_text, by=By.PARTIAL_LINK_TEXT
            )
        return True

    ############

    def wait_for_element_absent(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """Waits for an element to no longer appear in the HTML of a page.
        A hidden element counts as a present element, which fails this assert.
        If waiting for elements to be hidden instead of nonexistent,
        use wait_for_element_not_visible() instead.
        """
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        return page_actions.wait_for_element_absent(
            self.driver, selector, by, timeout
        )

    def assert_element_absent(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """Similar to wait_for_element_absent()
        As above, will raise an exception if the element stays present.
        A hidden element counts as a present element, which fails this assert.
        If you want to assert that elements are hidden instead of nonexistent,
        use assert_element_not_visible() instead.
        (Note that hidden elements are still present in the HTML of the page.)
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.wait_for_element_absent(selector, by=by, timeout=timeout)
        return True

    ############

    def wait_for_element_not_visible(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """Waits for an element to no longer be visible on a page.
        The element can be non-existent in the HTML or hidden on the page
        to qualify as not visible."""
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        return page_actions.wait_for_element_not_visible(
            self.driver, selector, by, timeout
        )

    def assert_element_not_visible(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """Similar to wait_for_element_not_visible()
        As above, will raise an exception if the element stays visible.
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.wait_for_element_not_visible(selector, by=by, timeout=timeout)
        if self.recorder_mode:
            url = self.get_current_url()
            if url and len(url) > 0:
                if ("http:") in url or ("https:") in url or ("file:") in url:
                    if self.get_session_storage_item("pause_recorder") == "no":
                        time_stamp = self.execute_script("return Date.now();")
                        action = ["asenv", selector, "", time_stamp]
                        self.__extra_actions.append(action)
        return True

    ############

    def wait_for_text_not_visible(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        return page_actions.wait_for_text_not_visible(
            self.driver, text, selector, by, timeout
        )

    def assert_text_not_visible(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        """Similar to wait_for_text_not_visible()
        Raises an exception if the text is still visible after timeout.
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.wait_for_text_not_visible(
            text, selector, by=by, timeout=timeout
        )

    ############

    def wait_for_attribute_not_present(
        self, selector, attribute, value=None, by=By.CSS_SELECTOR, timeout=None
    ):
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        selector, by = self.__recalculate_selector(selector, by)
        return page_actions.wait_for_attribute_not_present(
            self.driver, selector, attribute, value, by, timeout
        )

    def assert_attribute_not_present(
        self, selector, attribute, value=None, by=By.CSS_SELECTOR, timeout=None
    ):
        """Similar to wait_for_attribute_not_present()
        Raises an exception if the attribute is still present after timeout.
        Returns True if successful. Default timeout = SMALL_TIMEOUT."""
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return self.wait_for_attribute_not_present(
            selector, attribute, value=value, by=by, timeout=timeout
        )

    ############

    def wait_for_and_accept_alert(self, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return page_actions.wait_for_and_accept_alert(self.driver, timeout)

    def wait_for_and_dismiss_alert(self, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return page_actions.wait_for_and_dismiss_alert(self.driver, timeout)

    def wait_for_and_switch_to_alert(self, timeout=None):
        self.__check_scope()
        if not timeout:
            timeout = settings.LARGE_TIMEOUT
        if self.timeout_multiplier and timeout == settings.LARGE_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return page_actions.wait_for_and_switch_to_alert(self.driver, timeout)

    ############

    def accept_alert(self, timeout=None):
        """ Same as wait_for_and_accept_alert(), but smaller default T_O """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return page_actions.wait_for_and_accept_alert(self.driver, timeout)

    def dismiss_alert(self, timeout=None):
        """ Same as wait_for_and_dismiss_alert(), but smaller default T_O """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return page_actions.wait_for_and_dismiss_alert(self.driver, timeout)

    def switch_to_alert(self, timeout=None):
        """ Same as wait_for_and_switch_to_alert(), but smaller default T_O """
        self.__check_scope()
        if not timeout:
            timeout = settings.SMALL_TIMEOUT
        if self.timeout_multiplier and timeout == settings.SMALL_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        return page_actions.wait_for_and_switch_to_alert(self.driver, timeout)

    ############

    def __assert_eq(self, *args, **kwargs):
        """ Minified assert_equal() using only the list diff. """
        minified_exception = None
        try:
            self.assertEqual(*args, **kwargs)
        except Exception as e:
            str_e = str(e)
            minified_exception = "\nAssertionError:\n"
            lines = str_e.split("\n")
            countdown = 3
            countdown_on = False
            first_differing = False
            skip_lines = False
            for line in lines:
                if countdown_on:
                    if not skip_lines:
                        minified_exception += line + "\n"
                    countdown = countdown - 1
                    if countdown == 0:
                        countdown_on = False
                        skip_lines = False
                elif line.startswith("First differing"):
                    first_differing = True
                    countdown_on = True
                    countdown = 3
                    minified_exception += line + "\n"
                elif line.startswith("First list"):
                    countdown_on = True
                    countdown = 3
                    if not first_differing:
                        minified_exception += line + "\n"
                    else:
                        skip_lines = True
                elif line.startswith("F"):
                    countdown_on = True
                    countdown = 3
                    minified_exception += line + "\n"
                elif line.startswith("+") or line.startswith("-"):
                    minified_exception += line + "\n"
                elif line.startswith("?"):
                    minified_exception += line + "\n"
                elif line.strip().startswith("*"):
                    minified_exception += line + "\n"
        if minified_exception:
            raise Exception(minified_exception)

    def check_window(
        self, name="default", level=0, baseline=False, check_domain=True
    ):
        """***  Automated Visual Testing with SeleniumBase  ***

        The first time a test calls self.check_window() for a unique "name"
        parameter provided, it will set a visual baseline, meaning that it
        creates a folder, saves the URL to a file, saves the current window
        screenshot to a file, and creates the following three files
        with the listed data saved:
        tags_level1.txt  ->  HTML tags from the window
        tags_level2.txt  ->  HTML tags + attributes from the window
        tags_level3.txt  ->  HTML tags + attributes/values from the window

        Baseline folders are named based on the test name and the name
        parameter passed to self.check_window(). The same test can store
        multiple baseline folders.

        If the baseline is being set/reset, the "level" doesn't matter.

        After the first run of self.check_window(), it will compare the
        HTML tags of the latest window to the one from the initial run.
        Here's how the level system works:
        * level=0 ->
            DRY RUN ONLY - Will perform comparisons to the baseline (and
                           print out any differences that are found) but
                           won't fail the test even if differences exist.
        * level=1 ->
            HTML tags are compared to tags_level1.txt
        * level=2 ->
            HTML tags are compared to tags_level1.txt and
            HTML tags/attributes are compared to tags_level2.txt
        * level=3 ->
            HTML tags are compared to tags_level1.txt and
            HTML tags + attributes are compared to tags_level2.txt and
            HTML tags + attributes/values are compared to tags_level3.txt
        As shown, Level-3 is the most strict, Level-1 is the least strict.
        If the comparisons from the latest window to the existing baseline
        don't match, the current test will fail, except for Level-0 tests.

        You can reset the visual baseline on the command line by using:
            --visual_baseline
        As long as "--visual_baseline" is used on the command line while
        running tests, the self.check_window() method cannot fail because
        it will rebuild the visual baseline rather than comparing the html
        tags of the latest run to the existing baseline. If there are any
        expected layout changes to a website that you're testing, you'll
        need to reset the baseline to prevent unnecessary failures.

        self.check_window() will fail with "Page Domain Mismatch Failure"
        if the page domain doesn't match the domain of the baseline,
        unless "check_domain" is set to False when calling check_window().

        If you want to use self.check_window() to compare a web page to
        a later version of itself from within the same test run, you can
        add the parameter "baseline=True" to the first time you call
        self.check_window() in a test to use that as the baseline. This
        only makes sense if you're calling self.check_window() more than
        once with the same name parameter in the same test.

        Automated Visual Testing with self.check_window() is not very
        effective for websites that have dynamic content that changes
        the layout and structure of web pages. For those, you're much
        better off using regular SeleniumBase functional testing.

        Example usage:
            self.check_window(name="testing", level=0)
            self.check_window(name="xkcd_home", level=1)
            self.check_window(name="github_page", level=2)
            self.check_window(name="wikipedia_page", level=3)
        """
        self.wait_for_ready_state_complete()
        if level == "0":
            level = 0
        if level == "1":
            level = 1
        if level == "2":
            level = 2
        if level == "3":
            level = 3
        if level != 0 and level != 1 and level != 2 and level != 3:
            raise Exception('Parameter "level" must be set to 0, 1, 2, or 3!')

        if self.demo_mode:
            message = (
                "WARNING: Using check_window() from Demo Mode may lead "
                "to unexpected results caused by Demo Mode HTML changes."
            )
            logging.info(message)

        test_id = self.__get_display_id().split("::")[-1]

        if not name or len(name) < 1:
            name = "default"
        name = str(name)
        from seleniumbase.core import visual_helper

        visual_helper.visual_baseline_folder_setup()
        baseline_dir = constants.VisualBaseline.STORAGE_FOLDER
        visual_baseline_path = baseline_dir + "/" + test_id + "/" + name
        page_url_file = visual_baseline_path + "/page_url.txt"
        screenshot_file = visual_baseline_path + "/screenshot.png"
        level_1_file = visual_baseline_path + "/tags_level_1.txt"
        level_2_file = visual_baseline_path + "/tags_level_2.txt"
        level_3_file = visual_baseline_path + "/tags_level_3.txt"

        set_baseline = False
        if baseline or self.visual_baseline:
            set_baseline = True
        if not os.path.exists(visual_baseline_path):
            set_baseline = True
            try:
                os.makedirs(visual_baseline_path)
            except Exception:
                pass  # Only reachable during multi-threaded test runs
        if not os.path.exists(page_url_file):
            set_baseline = True
        if not os.path.exists(screenshot_file):
            set_baseline = True
        if not os.path.exists(level_1_file):
            set_baseline = True
        if not os.path.exists(level_2_file):
            set_baseline = True
        if not os.path.exists(level_3_file):
            set_baseline = True

        page_url = self.get_current_url()
        soup = self.get_beautiful_soup()
        html_tags = soup.body.find_all()
        level_1 = [[tag.name] for tag in html_tags]
        level_1 = json.loads(json.dumps(level_1))  # Tuples become lists
        level_2 = [[tag.name, sorted(tag.attrs.keys())] for tag in html_tags]
        level_2 = json.loads(json.dumps(level_2))  # Tuples become lists
        level_3 = [[tag.name, sorted(tag.attrs.items())] for tag in html_tags]
        level_3 = json.loads(json.dumps(level_3))  # Tuples become lists

        if set_baseline:
            self.save_screenshot("screenshot.png", visual_baseline_path)
            out_file = codecs.open(page_url_file, "w+", encoding="utf-8")
            out_file.writelines(page_url)
            out_file.close()
            out_file = codecs.open(level_1_file, "w+", encoding="utf-8")
            out_file.writelines(json.dumps(level_1))
            out_file.close()
            out_file = codecs.open(level_2_file, "w+", encoding="utf-8")
            out_file.writelines(json.dumps(level_2))
            out_file.close()
            out_file = codecs.open(level_3_file, "w+", encoding="utf-8")
            out_file.writelines(json.dumps(level_3))
            out_file.close()

        if not set_baseline:
            f = open(page_url_file, "r")
            page_url_data = f.read().strip()
            f.close()
            f = open(level_1_file, "r")
            level_1_data = json.loads(f.read())
            f.close()
            f = open(level_2_file, "r")
            level_2_data = json.loads(f.read())
            f.close()
            f = open(level_3_file, "r")
            level_3_data = json.loads(f.read())
            f.close()

            domain_fail = (
                "\n*\nPage Domain Mismatch Failure: "
                "Current Page Domain doesn't match the Page Domain of the "
                "Baseline! Can't compare two completely different sites! "
                "Run with --visual_baseline to reset the baseline!"
            )
            level_1_failure = (
                "\n*\n*** Exception: <Level 1> Visual Diff Failure:\n"
                "* HTML tags don't match the baseline!"
            )
            level_2_failure = (
                "\n*\n*** Exception: <Level 2> Visual Diff Failure:\n"
                "* HTML tag attribute names don't match the baseline!"
            )
            level_3_failure = (
                "\n*\n*** Exception: <Level 3> Visual Diff Failure:\n"
                "* HTML tag attribute values don't match the baseline!"
            )

            page_domain = self.get_domain_url(page_url)
            page_data_domain = self.get_domain_url(page_url_data)
            unittest.TestCase.maxDiff = 3200
            if level != 0 and check_domain:
                self.assertEqual(page_data_domain, page_domain, domain_fail)
            unittest.TestCase.maxDiff = 6400  # Use `None` for no limit
            if level == 3:
                self.__assert_eq(level_3_data, level_3, level_3_failure)
            unittest.TestCase.maxDiff = 3200
            if level == 2:
                self.__assert_eq(level_2_data, level_2, level_2_failure)
            if level == 1:
                self.__assert_eq(level_1_data, level_1, level_1_failure)
            unittest.TestCase.maxDiff = 6400  # Use `None` for no limit
            if level == 0:
                try:
                    unittest.TestCase.maxDiff = 3200
                    if check_domain:
                        self.assertEqual(
                            page_domain, page_data_domain, domain_fail
                        )
                    try:
                        self.__assert_eq(
                            level_1_data, level_1, level_1_failure
                        )
                    except Exception as e:
                        print(e)
                    try:
                        self.__assert_eq(
                            level_2_data, level_2, level_2_failure
                        )
                    except Exception as e:
                        print(e)
                    unittest.TestCase.maxDiff = 6400  # Use `None` for no limit
                    self.__assert_eq(level_3_data, level_3, level_3_failure)
                except Exception as e:
                    print(e)  # Level-0 Dry Run (Only print the differences)
            unittest.TestCase.maxDiff = None  # Reset unittest.TestCase.maxDiff

    ############

    def __get_new_timeout(self, timeout):
        """ When using --timeout_multiplier=#.# """
        import math

        self.__check_scope()
        try:
            timeout_multiplier = float(self.timeout_multiplier)
            if timeout_multiplier <= 0.5:
                timeout_multiplier = 0.5
            timeout = int(math.ceil(timeout_multiplier * timeout))
            return timeout
        except Exception:
            # Wrong data type for timeout_multiplier (expecting int or float)
            return timeout

    ############

    def __check_scope(self):
        if hasattr(self, "browser"):  # self.browser stores the type of browser
            return  # All good: setUp() already initialized variables in "self"
        else:
            from seleniumbase.common.exceptions import OutOfScopeException

            message = (
                "\n It looks like you are trying to call a SeleniumBase method"
                "\n from outside the scope of your test class's `self` object,"
                "\n which is initialized by calling BaseCase's setUp() method."
                "\n The `self` object is where all test variables are defined."
                "\n If you created a custom setUp() method (that overrided the"
                "\n the default one), make sure to call super().setUp() in it."
                "\n When using page objects, be sure to pass the `self` object"
                "\n from your test class into your page object methods so that"
                "\n they can call BaseCase class methods with all the required"
                "\n variables, which are initialized during the setUp() method"
                "\n that runs automatically before all tests called by pytest."
            )
            raise OutOfScopeException(message)

    ############

    def __get_exception_message(self):
        """This method extracts the message from an exception if there
        was an exception that occurred during the test, assuming
        that the exception was in a try/except block and not thrown."""
        exception_info = sys.exc_info()[1]
        if hasattr(exception_info, "msg"):
            exc_message = exception_info.msg
        elif hasattr(exception_info, "message"):
            exc_message = exception_info.message
        else:
            exc_message = sys.exc_info()
        return exc_message

    def __get_improved_exception_message(self):
        """If Chromedriver is out-of-date, make it clear!
        Given the high popularity of the following StackOverflow article:
        https://stackoverflow.com/questions/49162667/unknown-error-
                call-function-result-missing-value-for-selenium-send-keys-even
        ... the original error message was not helpful. Tell people directly.
        (Only expected when using driver.send_keys() with an old Chromedriver.)
        """
        exc_message = self.__get_exception_message()
        maybe_using_old_chromedriver = False
        if "unknown error: call function result missing" in exc_message:
            maybe_using_old_chromedriver = True
        if self.browser == "chrome" and maybe_using_old_chromedriver:
            update = (
                "Your version of ChromeDriver may be out-of-date! "
                "Please go to "
                "https://sites.google.com/a/chromium.org/chromedriver/ "
                "and download the latest version to your system PATH! "
                "Or use: ``seleniumbase install chromedriver`` . "
                "Original Exception Message: %s" % exc_message
            )
            exc_message = update
        return exc_message

    def __add_deferred_assert_failure(self):
        """ Add a deferred_assert failure to a list for future processing. """
        self.__check_scope()
        current_url = self.driver.current_url
        message = self.__get_exception_message()
        self.__deferred_assert_failures.append(
            "CHECK #%s: (%s)\n %s"
            % (self.__deferred_assert_count, current_url, message)
        )

    ############

    def deferred_assert_element(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """A non-terminating assertion for an element on a page.
        Failures will be saved until the process_deferred_asserts()
        method is called from inside a test, likely at the end of it."""
        self.__check_scope()
        if not timeout:
            timeout = settings.MINI_TIMEOUT
        if self.timeout_multiplier and timeout == settings.MINI_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.__deferred_assert_count += 1
        try:
            url = self.get_current_url()
            if url == self.__last_url_of_deferred_assert:
                timeout = 1
            else:
                self.__last_url_of_deferred_assert = url
        except Exception:
            pass
        try:
            self.wait_for_element_visible(selector, by=by, timeout=timeout)
            return True
        except Exception:
            self.__add_deferred_assert_failure()
            return False

    def deferred_assert_text(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        """A non-terminating assertion for text from an element on a page.
        Failures will be saved until the process_deferred_asserts()
        method is called from inside a test, likely at the end of it."""
        self.__check_scope()
        if not timeout:
            timeout = settings.MINI_TIMEOUT
        if self.timeout_multiplier and timeout == settings.MINI_TIMEOUT:
            timeout = self.__get_new_timeout(timeout)
        self.__deferred_assert_count += 1
        try:
            url = self.get_current_url()
            if url == self.__last_url_of_deferred_assert:
                timeout = 1
            else:
                self.__last_url_of_deferred_assert = url
        except Exception:
            pass
        try:
            self.wait_for_text_visible(text, selector, by=by, timeout=timeout)
            return True
        except Exception:
            self.__add_deferred_assert_failure()
            return False

    def process_deferred_asserts(self, print_only=False):
        """To be used with any test that uses deferred_asserts, which are
        non-terminating verifications that only raise exceptions
        after this method is called.
        This is useful for pages with multiple elements to be checked when
        you want to find as many bugs as possible in a single test run
        before having all the exceptions get raised simultaneously.
        Might be more useful if this method is called after processing all
        the deferred asserts on a single html page so that the failure
        screenshot matches the location of the deferred asserts.
        If "print_only" is set to True, the exception won't get raised."""
        if self.__deferred_assert_failures:
            exception_output = ""
            exception_output += "\n*** DEFERRED ASSERTION FAILURES FROM: "
            exception_output += "%s\n" % self.id()
            all_failing_checks = self.__deferred_assert_failures
            self.__deferred_assert_failures = []
            for tb in all_failing_checks:
                exception_output += "%s\n" % tb
            if print_only:
                print(exception_output)
            else:
                raise Exception(exception_output)

    ############

    # Alternate naming scheme for the "deferred_assert" methods.

    def delayed_assert_element(
        self, selector, by=By.CSS_SELECTOR, timeout=None
    ):
        """ Same as self.deferred_assert_element() """
        return self.deferred_assert_element(
            selector=selector, by=by, timeout=timeout
        )

    def delayed_assert_text(
        self, text, selector="html", by=By.CSS_SELECTOR, timeout=None
    ):
        """ Same as self.deferred_assert_text() """
        return self.deferred_assert_text(
            text=text, selector=selector, by=by, timeout=timeout
        )

    def process_delayed_asserts(self, print_only=False):
        """ Same as self.process_deferred_asserts() """
        self.process_deferred_asserts(print_only=print_only)

    ############

    def __js_click(self, selector, by=By.CSS_SELECTOR):
        """ Clicks an element using pure JS. Does not use jQuery. """
        selector, by = self.__recalculate_selector(selector, by)
        css_selector = self.convert_to_css_selector(selector, by=by)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        script = (
            """var simulateClick = function (elem) {
                   var evt = new MouseEvent('click', {
                       bubbles: true,
                       cancelable: true,
                       view: window
                   });
                   var canceled = !elem.dispatchEvent(evt);
               };
               var someLink = document.querySelector('%s');
               simulateClick(someLink);"""
            % css_selector
        )
        self.execute_script(script)

    def __js_click_all(self, selector, by=By.CSS_SELECTOR):
        """ Clicks all matching elements using pure JS. (No jQuery) """
        selector, by = self.__recalculate_selector(selector, by)
        css_selector = self.convert_to_css_selector(selector, by=by)
        css_selector = re.escape(css_selector)  # Add "\\" to special chars
        css_selector = self.__escape_quotes_if_needed(css_selector)
        script = (
            """var simulateClick = function (elem) {
                   var evt = new MouseEvent('click', {
                       bubbles: true,
                       cancelable: true,
                       view: window
                   });
                   var canceled = !elem.dispatchEvent(evt);
               };
               var $elements = document.querySelectorAll('%s');
               var index = 0, length = $elements.length;
               for(; index < length; index++){
               simulateClick($elements[index]);}"""
            % css_selector
        )
        self.execute_script(script)

    def __jquery_slow_scroll_to(self, selector, by=By.CSS_SELECTOR):
        selector, by = self.__recalculate_selector(selector, by)
        element = self.wait_for_element_present(
            selector, by=by, timeout=settings.SMALL_TIMEOUT
        )
        dist = js_utils.get_scroll_distance_to_element(self.driver, element)
        time_offset = 0
        try:
            if dist and abs(dist) > constants.Values.SSMD:
                time_offset = int(
                    float(abs(dist) - constants.Values.SSMD) / 12.5
                )
                if time_offset > 950:
                    time_offset = 950
        except Exception:
            time_offset = 0
        scroll_time_ms = 550 + time_offset
        sleep_time = 0.625 + (float(time_offset) / 1000.0)
        selector = self.convert_to_css_selector(selector, by=by)
        selector = self.__make_css_match_first_element_only(selector)
        scroll_script = (
            """jQuery([document.documentElement, document.body]).animate({"""
            """scrollTop: jQuery('%s').offset().top - 130}, %s);"""
            % (selector, scroll_time_ms)
        )
        if js_utils.is_jquery_activated(self.driver):
            self.execute_script(scroll_script)
        else:
            self.__slow_scroll_to_element(element)
        self.sleep(sleep_time)

    def __jquery_click(self, selector, by=By.CSS_SELECTOR):
        """ Clicks an element using jQuery. Different from using pure JS. """
        selector, by = self.__recalculate_selector(selector, by)
        self.wait_for_element_present(
            selector, by=by, timeout=settings.SMALL_TIMEOUT
        )
        selector = self.convert_to_css_selector(selector, by=by)
        selector = self.__make_css_match_first_element_only(selector)
        click_script = """jQuery('%s')[0].click();""" % selector
        self.safe_execute_script(click_script)

    def __get_href_from_link_text(self, link_text, hard_fail=True):
        href = self.get_link_attribute(link_text, "href", hard_fail)
        if not href:
            return None
        if href.startswith("//"):
            link = "http:" + href
        elif href.startswith("/"):
            url = self.driver.current_url
            domain_url = self.get_domain_url(url)
            link = domain_url + href
        else:
            link = href
        return link

    def __click_dropdown_link_text(self, link_text, link_css):
        """ When a link may be hidden under a dropdown menu, use this. """
        soup = self.get_beautiful_soup()
        drop_down_list = []
        for item in soup.select("li[class]"):
            drop_down_list.append(item)
        csstype = link_css.split("[")[1].split("=")[0]
        for item in drop_down_list:
            item_text_list = item.text.split("\n")
            if link_text in item_text_list and csstype in item.decode():
                dropdown_css = ""
                try:
                    for css_class in item["class"]:
                        dropdown_css += "."
                        dropdown_css += css_class
                except Exception:
                    continue
                dropdown_css = item.name + dropdown_css
                matching_dropdowns = self.find_visible_elements(dropdown_css)
                for dropdown in matching_dropdowns:
                    # The same class names might be used for multiple dropdowns
                    if dropdown.is_displayed():
                        try:
                            try:
                                page_actions.hover_element(
                                    self.driver,
                                    dropdown,
                                )
                            except Exception:
                                # If hovering fails, driver is likely outdated
                                # Time to go directly to the hidden link text
                                self.open(
                                    self.__get_href_from_link_text(link_text)
                                )
                                return True
                            page_actions.hover_element_and_click(
                                self.driver,
                                dropdown,
                                link_text,
                                click_by=By.LINK_TEXT,
                                timeout=0.12,
                            )
                            return True
                        except Exception:
                            pass

        return False

    def __get_href_from_partial_link_text(self, link_text, hard_fail=True):
        href = self.get_partial_link_text_attribute(
            link_text, "href", hard_fail
        )
        if not href:
            return None
        if href.startswith("//"):
            link = "http:" + href
        elif href.startswith("/"):
            url = self.driver.current_url
            domain_url = self.get_domain_url(url)
            link = domain_url + href
        else:
            link = href
        return link

    def __click_dropdown_partial_link_text(self, link_text, link_css):
        """ When a partial link may be hidden under a dropdown, use this. """
        soup = self.get_beautiful_soup()
        drop_down_list = []
        for item in soup.select("li[class]"):
            drop_down_list.append(item)
        csstype = link_css.split("[")[1].split("=")[0]
        for item in drop_down_list:
            item_text_list = item.text.split("\n")
            if link_text in item_text_list and csstype in item.decode():
                dropdown_css = ""
                try:
                    for css_class in item["class"]:
                        dropdown_css += "."
                        dropdown_css += css_class
                except Exception:
                    continue
                dropdown_css = item.name + dropdown_css
                matching_dropdowns = self.find_visible_elements(dropdown_css)
                for dropdown in matching_dropdowns:
                    # The same class names might be used for multiple dropdowns
                    if dropdown.is_displayed():
                        try:
                            try:
                                page_actions.hover_element(
                                    self.driver, dropdown
                                )
                            except Exception:
                                # If hovering fails, driver is likely outdated
                                # Time to go directly to the hidden link text
                                self.open(
                                    self.__get_href_from_partial_link_text(
                                        link_text
                                    )
                                )
                                return True
                            page_actions.hover_element_and_click(
                                self.driver,
                                dropdown,
                                link_text,
                                click_by=By.LINK_TEXT,
                                timeout=0.12,
                            )
                            return True
                        except Exception:
                            pass
        return False

    def __recalculate_selector(self, selector, by, xp_ok=True):
        """Use autodetection to return the correct selector with "by" updated.
        If "xp_ok" is False, don't call convert_css_to_xpath(), which is
        used to make the ":contains()" selector valid outside JS calls."""
        _type = type(selector)  # First make sure the selector is a string
        not_string = False
        if sys.version_info[0] < 3:
            if _type is not str and _type is not unicode:  # noqa: F821
                not_string = True
        else:
            if _type is not str:
                not_string = True
        if not_string:
            msg = "Expecting a selector of type: \"<class 'str'>\" (string)!"
            raise Exception('Invalid selector type: "%s"\n%s' % (_type, msg))
        if page_utils.is_xpath_selector(selector):
            by = By.XPATH
        if page_utils.is_link_text_selector(selector):
            selector = page_utils.get_link_text_from_selector(selector)
            by = By.LINK_TEXT
        if page_utils.is_partial_link_text_selector(selector):
            selector = page_utils.get_partial_link_text_from_selector(selector)
            by = By.PARTIAL_LINK_TEXT
        if page_utils.is_name_selector(selector):
            name = page_utils.get_name_from_selector(selector)
            selector = '[name="%s"]' % name
            by = By.CSS_SELECTOR
        if xp_ok:
            if ":contains(" in selector and by == By.CSS_SELECTOR:
                selector = self.convert_css_to_xpath(selector)
                by = By.XPATH
        return (selector, by)

    def __looks_like_a_page_url(self, url):
        """Returns True if the url parameter looks like a URL. This method
        is slightly more lenient than page_utils.is_valid_url(url) due to
        possible typos when calling self.get(url), which will try to
        navigate to the page if a URL is detected, but will instead call
        self.get_element(URL_AS_A_SELECTOR) if the input in not a URL."""
        if (
            url.startswith("http:")
            or url.startswith("https:")
            or url.startswith("://")
            or url.startswith("chrome:")
            or url.startswith("about:")
            or url.startswith("data:")
            or url.startswith("file:")
            or url.startswith("edge:")
            or url.startswith("opera:")
        ):
            return True
        else:
            return False

    def __make_css_match_first_element_only(self, selector):
        # Only get the first match
        return page_utils.make_css_match_first_element_only(selector)

    def __demo_mode_pause_if_active(self, tiny=False):
        if self.demo_mode:
            wait_time = settings.DEFAULT_DEMO_MODE_TIMEOUT
            if self.demo_sleep:
                wait_time = float(self.demo_sleep)
            if not tiny:
                time.sleep(wait_time)
            else:
                time.sleep(wait_time / 3.4)
        elif self.slow_mode:
            self.__slow_mode_pause_if_active()

    def __slow_mode_pause_if_active(self):
        if self.slow_mode:
            wait_time = settings.DEFAULT_DEMO_MODE_TIMEOUT
            if self.demo_sleep:
                wait_time = float(self.demo_sleep)
            time.sleep(wait_time)

    def __demo_mode_scroll_if_active(self, selector, by):
        if self.demo_mode:
            self.slow_scroll_to(selector, by=by)

    def __demo_mode_highlight_if_active(self, selector, by):
        if self.demo_mode:
            # Includes self.slow_scroll_to(selector, by=by) by default
            self.highlight(selector, by=by)
        elif self.slow_mode:
            # Just do the slow scroll part of the highlight() method
            time.sleep(0.08)
            selector, by = self.__recalculate_selector(selector, by)
            element = self.wait_for_element_visible(
                selector, by=by, timeout=settings.SMALL_TIMEOUT
            )
            try:
                scroll_distance = js_utils.get_scroll_distance_to_element(
                    self.driver, element
                )
                if abs(scroll_distance) > constants.Values.SSMD:
                    self.__jquery_slow_scroll_to(selector, by)
                else:
                    self.__slow_scroll_to_element(element)
            except (StaleElementReferenceException, ENI_Exception):
                self.wait_for_ready_state_complete()
                time.sleep(0.12)
                element = self.wait_for_element_visible(
                    selector, by=by, timeout=settings.SMALL_TIMEOUT
                )
                self.__slow_scroll_to_element(element)
            time.sleep(0.12)

    def __scroll_to_element(self, element, selector=None, by=By.CSS_SELECTOR):
        success = js_utils.scroll_to_element(self.driver, element)
        if not success and selector:
            self.wait_for_ready_state_complete()
            element = page_actions.wait_for_element_visible(
                self.driver, selector, by, timeout=settings.SMALL_TIMEOUT
            )
        self.__demo_mode_pause_if_active(tiny=True)

    def __slow_scroll_to_element(self, element):
        try:
            js_utils.slow_scroll_to_element(self.driver, element, self.browser)
        except Exception:
            # Scroll to the element instantly if the slow scroll fails
            js_utils.scroll_to_element(self.driver, element)

    def __highlight_with_assert_success(
        self, message, selector, by=By.CSS_SELECTOR
    ):
        selector, by = self.__recalculate_selector(selector, by, xp_ok=False)
        element = self.wait_for_element_visible(
            selector, by=by, timeout=settings.SMALL_TIMEOUT
        )
        try:
            scroll_distance = js_utils.get_scroll_distance_to_element(
                self.driver, element
            )
            if abs(scroll_distance) > constants.Values.SSMD:
                self.__jquery_slow_scroll_to(selector, by)
            else:
                self.__slow_scroll_to_element(element)
        except Exception:
            self.wait_for_ready_state_complete()
            time.sleep(0.12)
            element = self.wait_for_element_visible(
                selector, by=by, timeout=settings.SMALL_TIMEOUT
            )
            self.__slow_scroll_to_element(element)
        try:
            selector = self.convert_to_css_selector(selector, by=by)
        except Exception:
            # Don't highlight if can't convert to CSS_SELECTOR
            return

        o_bs = ""  # original_box_shadow
        try:
            style = element.get_attribute("style")
        except Exception:
            self.wait_for_ready_state_complete()
            time.sleep(0.12)
            element = self.wait_for_element_visible(
                selector, by=By.CSS_SELECTOR, timeout=settings.SMALL_TIMEOUT
            )
            style = element.get_attribute("style")
        if style:
            if "box-shadow: " in style:
                box_start = style.find("box-shadow: ")
                box_end = style.find(";", box_start) + 1
                original_box_shadow = style[box_start:box_end]
                o_bs = original_box_shadow

        if ":contains" not in selector and ":first" not in selector:
            selector = re.escape(selector)
            selector = self.__escape_quotes_if_needed(selector)
            self.__highlight_with_js_2(message, selector, o_bs)
        else:
            selector = self.__make_css_match_first_element_only(selector)
            selector = re.escape(selector)
            selector = self.__escape_quotes_if_needed(selector)
            try:
                self.__highlight_with_jquery_2(message, selector, o_bs)
            except Exception:
                pass  # JQuery probably couldn't load. Skip highlighting.
        time.sleep(0.065)

    def __highlight_with_js_2(self, message, selector, o_bs):
        js_utils.highlight_with_js_2(
            self.driver, message, selector, o_bs, self.message_duration
        )

    def __highlight_with_jquery_2(self, message, selector, o_bs):
        js_utils.highlight_with_jquery_2(
            self.driver, message, selector, o_bs, self.message_duration
        )

    ############

    # Deprecated Methods (Replace these if they're still in your code!)

    @decorators.deprecated(
        "jq_format() is deprecated. Use re.escape() instead!"
    )
    def jq_format(self, code):
        # DEPRECATED - re.escape() already performs the intended action!
        return js_utils._jq_format(code)

    ############

    def setUp(self, masterqa_mode=False):
        """
        Be careful if a subclass of BaseCase overrides setUp()
        You'll need to add the following line to the subclass setUp() method:
        super(SubClassOfBaseCase, self).setUp()
        """
        if not hasattr(self, "_using_sb_fixture") and self.__called_setup:
            # This test already called setUp()
            return
        self.__called_setup = True
        self.__called_teardown = False
        self.masterqa_mode = masterqa_mode
        self.is_pytest = None
        try:
            # This raises an exception if the test is not coming from pytest
            self.is_pytest = sb_config.is_pytest
        except Exception:
            # Not using pytest (probably nosetests)
            self.is_pytest = False
        if self.is_pytest:
            # pytest-specific code
            test_id = self.__get_test_id()
            self.test_id = test_id
            if hasattr(self, "_using_sb_fixture"):
                self.test_id = sb_config._test_id
            self.browser = sb_config.browser
            self.data = sb_config.data
            self.var1 = sb_config.var1
            self.var2 = sb_config.var2
            self.var3 = sb_config.var3
            self.slow_mode = sb_config.slow_mode
            self.demo_mode = sb_config.demo_mode
            self.demo_sleep = sb_config.demo_sleep
            self.highlights = sb_config.highlights
            self.time_limit = sb_config._time_limit
            sb_config.time_limit = sb_config._time_limit  # Reset between tests
            self.environment = sb_config.environment
            self.env = self.environment  # Add a shortened version
            self.with_selenium = sb_config.with_selenium  # Should be True
            self.headless = sb_config.headless
            self.headless_active = False
            self.headed = sb_config.headed
            self.xvfb = sb_config.xvfb
            self.locale_code = sb_config.locale_code
            self.interval = sb_config.interval
            self.start_page = sb_config.start_page
            self.log_path = sb_config.log_path
            self.with_testing_base = sb_config.with_testing_base
            self.with_basic_test_info = sb_config.with_basic_test_info
            self.with_screen_shots = sb_config.with_screen_shots
            self.with_page_source = sb_config.with_page_source
            self.with_db_reporting = sb_config.with_db_reporting
            self.with_s3_logging = sb_config.with_s3_logging
            self.protocol = sb_config.protocol
            self.servername = sb_config.servername
            self.port = sb_config.port
            self.proxy_string = sb_config.proxy_string
            self.user_agent = sb_config.user_agent
            self.mobile_emulator = sb_config.mobile_emulator
            self.device_metrics = sb_config.device_metrics
            self.cap_file = sb_config.cap_file
            self.cap_string = sb_config.cap_string
            self.settings_file = sb_config.settings_file
            self.database_env = sb_config.database_env
            self.message_duration = sb_config.message_duration
            self.js_checking_on = sb_config.js_checking_on
            self.ad_block_on = sb_config.ad_block_on
            self.block_images = sb_config.block_images
            self.chromium_arg = sb_config.chromium_arg
            self.firefox_arg = sb_config.firefox_arg
            self.firefox_pref = sb_config.firefox_pref
            self.verify_delay = sb_config.verify_delay
            self.recorder_mode = sb_config.recorder_mode
            self.recorder_ext = sb_config.recorder_mode
            self.disable_csp = sb_config.disable_csp
            self.disable_ws = sb_config.disable_ws
            self.enable_ws = sb_config.enable_ws
            if not self.disable_ws:
                self.enable_ws = True
            self.enable_sync = sb_config.enable_sync
            self.use_auto_ext = sb_config.use_auto_ext
            self.no_sandbox = sb_config.no_sandbox
            self.disable_gpu = sb_config.disable_gpu
            self.incognito = sb_config.incognito
            self.guest_mode = sb_config.guest_mode
            self.devtools = sb_config.devtools
            self.remote_debug = sb_config.remote_debug
            self._multithreaded = sb_config._multithreaded
            self._reuse_session = sb_config.reuse_session
            self._crumbs = sb_config.crumbs
            self.dashboard = sb_config.dashboard
            self._dash_initialized = sb_config._dashboard_initialized
            if self.dashboard and self._multithreaded:
                import fasteners

                self.dash_lock = fasteners.InterProcessLock(
                    constants.Dashboard.LOCKFILE
                )
            self.swiftshader = sb_config.swiftshader
            self.user_data_dir = sb_config.user_data_dir
            self.extension_zip = sb_config.extension_zip
            self.extension_dir = sb_config.extension_dir
            self.maximize_option = sb_config.maximize_option
            self.save_screenshot_after_test = sb_config.save_screenshot
            self.visual_baseline = sb_config.visual_baseline
            self.timeout_multiplier = sb_config.timeout_multiplier
            self.pytest_html_report = sb_config.pytest_html_report
            self.report_on = False
            if self.pytest_html_report:
                self.report_on = True
            self.use_grid = False
            if self.servername != "localhost":
                # Use Selenium Grid (Use --server="127.0.0.1" for a local Grid)
                self.use_grid = True
            if self.with_db_reporting:
                import getpass
                import uuid
                from seleniumbase.core.application_manager import (
                    ApplicationManager,
                )
                from seleniumbase.core.testcase_manager import (
                    ExecutionQueryPayload,
                )
                from seleniumbase.core.testcase_manager import (
                    TestcaseDataPayload,
                )
                from seleniumbase.core.testcase_manager import TestcaseManager

                self.execution_guid = str(uuid.uuid4())
                self.testcase_guid = None
                self.execution_start_time = 0
                self.case_start_time = 0
                self.application = None
                self.testcase_manager = None
                self.error_handled = False
                self.testcase_manager = TestcaseManager(self.database_env)
                #
                exec_payload = ExecutionQueryPayload()
                exec_payload.execution_start_time = int(time.time() * 1000)
                self.execution_start_time = exec_payload.execution_start_time
                exec_payload.guid = self.execution_guid
                exec_payload.username = getpass.getuser()
                self.testcase_manager.insert_execution_data(exec_payload)
                #
                data_payload = TestcaseDataPayload()
                self.testcase_guid = str(uuid.uuid4())
                data_payload.guid = self.testcase_guid
                data_payload.execution_guid = self.execution_guid
                if self.with_selenium:
                    data_payload.browser = self.browser
                else:
                    data_payload.browser = "N/A"
                data_payload.test_address = test_id
                application = ApplicationManager.generate_application_string(
                    self._testMethodName
                )
                data_payload.env = application.split(".")[0]
                data_payload.start_time = application.split(".")[1]
                data_payload.state = constants.State.UNTESTED
                self.__skip_reason = None
                self.testcase_manager.insert_testcase_data(data_payload)
                self.case_start_time = int(time.time() * 1000)
            if self.headless or self.xvfb:
                width = settings.HEADLESS_START_WIDTH
                height = settings.HEADLESS_START_HEIGHT
                try:
                    # from pyvirtualdisplay import Display  # Skip for own lib
                    from sbvirtualdisplay import Display

                    self.display = Display(visible=0, size=(width, height))
                    self.display.start()
                    self.headless_active = True
                except Exception:
                    # pyvirtualdisplay might not be necessary anymore because
                    # Chrome and Firefox now have built-in headless displays
                    pass
        else:
            # (Nosetests / Not Pytest)
            pass  # Setup performed in plugins

        # Verify that SeleniumBase is installed successfully
        if not hasattr(self, "browser"):
            raise Exception(
                'SeleniumBase plugins DID NOT load! * Please REINSTALL!\n'
                '*** Either install SeleniumBase in Dev Mode from a clone:\n'
                '    >>> "pip install -e ."     (Run in DIR with setup.py)\n'
                '*** Or install the latest SeleniumBase version from PyPI:\n'
                '    >>> "pip install -U seleniumbase"    (Run in any DIR)'
            )

        if not hasattr(sb_config, "_is_timeout_changed"):
            # Should only be reachable from pure Python runs
            sb_config._is_timeout_changed = False
            sb_config._SMALL_TIMEOUT = settings.SMALL_TIMEOUT
            sb_config._LARGE_TIMEOUT = settings.LARGE_TIMEOUT

        if sb_config._is_timeout_changed:
            if sb_config._SMALL_TIMEOUT and sb_config._LARGE_TIMEOUT:
                settings.SMALL_TIMEOUT = sb_config._SMALL_TIMEOUT
                settings.LARGE_TIMEOUT = sb_config._LARGE_TIMEOUT

        if not hasattr(sb_config, "_recorded_actions"):
            # Only filled when Recorder Mode is enabled
            sb_config._recorded_actions = {}

        if not hasattr(settings, "SWITCH_TO_NEW_TABS_ON_CLICK"):
            # If using an older settings file, set the new definitions manually
            settings.SWITCH_TO_NEW_TABS_ON_CLICK = True

        # Parse the settings file
        if self.settings_file:
            from seleniumbase.core import settings_parser

            settings_parser.set_settings(self.settings_file)

        # Mobile Emulator device metrics: CSS Width, CSS Height, & Pixel-Ratio
        if self.device_metrics:
            metrics_string = self.device_metrics
            metrics_string = metrics_string.replace(" ", "")
            metrics_list = metrics_string.split(",")
            exception_string = (
                "Invalid input for Mobile Emulator device metrics!\n"
                "Expecting a comma-separated string with three\n"
                "integer values for Width, Height, and Pixel-Ratio.\n"
                'Example: --metrics="411,731,3" '
            )
            if len(metrics_list) != 3:
                raise Exception(exception_string)
            try:
                self.__device_width = int(metrics_list[0])
                self.__device_height = int(metrics_list[1])
                self.__device_pixel_ratio = int(metrics_list[2])
                self.mobile_emulator = True
            except Exception:
                raise Exception(exception_string)
        if self.mobile_emulator:
            if not self.user_agent:
                # Use the Pixel 3 user agent by default if not specified
                self.user_agent = (
                    "Mozilla/5.0 (Linux; Android 9; Pixel 3 XL) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/76.0.3809.132 Mobile Safari/537.36"
                )

        # Dashboard pre-processing:
        if self.dashboard:
            if self._multithreaded:
                with self.dash_lock:
                    sb_config._sbase_detected = True
                    sb_config._only_unittest = False
                    if not self._dash_initialized:
                        sb_config._dashboard_initialized = True
                        self._dash_initialized = True
                        self.__process_dashboard(False, init=True)
            else:
                sb_config._sbase_detected = True
                sb_config._only_unittest = False
                if not self._dash_initialized:
                    sb_config._dashboard_initialized = True
                    self._dash_initialized = True
                    self.__process_dashboard(False, init=True)

        has_url = False
        if self._reuse_session:
            if not hasattr(sb_config, "shared_driver"):
                sb_config.shared_driver = None
            if sb_config.shared_driver:
                try:
                    self._default_driver = sb_config.shared_driver
                    self.driver = sb_config.shared_driver
                    self._drivers_list = [sb_config.shared_driver]
                    url = self.get_current_url()
                    if url is not None:
                        has_url = True
                    if len(self.driver.window_handles) > 1:
                        while len(self.driver.window_handles) > 1:
                            self.switch_to_window(
                                len(self.driver.window_handles) - 1
                            )
                            self.driver.close()
                        self.switch_to_window(0)
                    if self._crumbs:
                        self.driver.delete_all_cookies()
                except Exception:
                    pass
        if self._reuse_session and sb_config.shared_driver and has_url:
            if self.start_page and len(self.start_page) >= 4:
                if page_utils.is_valid_url(self.start_page):
                    self.open(self.start_page)
                else:
                    new_start_page = "http://" + self.start_page
                    if page_utils.is_valid_url(new_start_page):
                        self.open(new_start_page)
            elif self._crumbs:
                if self.get_current_url() != "data:,":
                    self.open("data:,")
            else:
                pass
        else:
            # Launch WebDriver for both Pytest and Nosetests
            self.driver = self.get_new_driver(
                browser=self.browser,
                headless=self.headless,
                locale_code=self.locale_code,
                protocol=self.protocol,
                servername=self.servername,
                port=self.port,
                proxy=self.proxy_string,
                agent=self.user_agent,
                switch_to=True,
                cap_file=self.cap_file,
                cap_string=self.cap_string,
                recorder_ext=self.recorder_ext,
                disable_csp=self.disable_csp,
                enable_ws=self.enable_ws,
                enable_sync=self.enable_sync,
                use_auto_ext=self.use_auto_ext,
                no_sandbox=self.no_sandbox,
                disable_gpu=self.disable_gpu,
                incognito=self.incognito,
                guest_mode=self.guest_mode,
                devtools=self.devtools,
                remote_debug=self.remote_debug,
                swiftshader=self.swiftshader,
                ad_block_on=self.ad_block_on,
                block_images=self.block_images,
                chromium_arg=self.chromium_arg,
                firefox_arg=self.firefox_arg,
                firefox_pref=self.firefox_pref,
                user_data_dir=self.user_data_dir,
                extension_zip=self.extension_zip,
                extension_dir=self.extension_dir,
                is_mobile=self.mobile_emulator,
                d_width=self.__device_width,
                d_height=self.__device_height,
                d_p_r=self.__device_pixel_ratio,
            )
            self._default_driver = self.driver
            if self._reuse_session:
                sb_config.shared_driver = self.driver

        if self.browser in ["firefox", "ie", "safari", "opera"]:
            # Only Chrome and Edge browsers have the mobile emulator.
            # Some actions such as hover-clicking are different on mobile.
            self.mobile_emulator = False
            # The Recorder Mode browser extension is only for Chrome/Edge.
            if self.recorder_mode:
                print('\n* The Recorder extension is for Chrome & Edge only!')
                self.recorder_mode = False

        # Configure the test time limit (if used).
        self.set_time_limit(self.time_limit)

        # Set the start time for the test (in ms).
        # Although the pytest clock starts before setUp() begins,
        # the time-limit clock starts at the end of the setUp() method.
        sb_config.start_time_ms = int(time.time() * 1000.0)
        if not self.__start_time_ms:
            # Call this once in case of multiple setUp() calls in the same test
            self.__start_time_ms = sb_config.start_time_ms

        # Set the JS start time for Recorder Mode if reusing the session.
        # Use this to skip saving recorded actions from previous tests.
        if self.recorder_mode and self._reuse_session:
            self.__js_start_time = self.execute_script("return Date.now();")

    def __set_last_page_screenshot(self):
        """self.__last_page_screenshot is only for pytest html report logs.
        self.__last_page_screenshot_png is for all screenshot log files."""
        if not self.__last_page_screenshot and (
            not self.__last_page_screenshot_png
        ):
            try:
                element = self.driver.find_element(
                    by=By.TAG_NAME, value="body"
                )
                if self.is_pytest and self.report_on:
                    self.__last_page_screenshot_png = (
                        self.driver.get_screenshot_as_png()
                    )
                    self.__last_page_screenshot = element.screenshot_as_base64
                else:
                    self.__last_page_screenshot_png = element.screenshot_as_png
            except Exception:
                if not self.__last_page_screenshot:
                    if self.is_pytest and self.report_on:
                        try:
                            self.__last_page_screenshot = (
                                self.driver.get_screenshot_as_base64()
                            )
                        except Exception:
                            self.__last_page_screenshot = (
                                constants.Warnings.SCREENSHOT_UNDEFINED
                            )
                if not self.__last_page_screenshot_png:
                    try:
                        self.__last_page_screenshot_png = (
                            self.driver.get_screenshot_as_png()
                        )
                    except Exception:
                        self.__last_page_screenshot_png = (
                            constants.Warnings.SCREENSHOT_UNDEFINED
                        )

    def __set_last_page_url(self):
        if not self.__last_page_url:
            try:
                self.__last_page_url = log_helper.get_last_page(self.driver)
            except Exception:
                self.__last_page_url = None

    def __set_last_page_source(self):
        if not self.__last_page_source:
            try:
                self.__last_page_source = (
                    log_helper.get_html_source_with_base_href(
                        self.driver, self.driver.page_source
                    )
                )
            except Exception:
                self.__last_page_source = (
                    constants.Warnings.PAGE_SOURCE_UNDEFINED
                )

    def __get_exception_info(self):
        exc_message = None
        if (
            sys.version_info[0] >= 3
            and hasattr(self, "_outcome")
            and (hasattr(self._outcome, "errors") and self._outcome.errors)
        ):
            try:
                exc_message = self._outcome.errors[0][1][1]
            except Exception:
                exc_message = "(Unknown Exception)"
        else:
            try:
                exc_message = sys.last_value
            except Exception:
                exc_message = "(Unknown Exception)"
        return str(exc_message)

    def __insert_test_result(self, state, err):
        from seleniumbase.core.testcase_manager import TestcaseDataPayload

        data_payload = TestcaseDataPayload()
        data_payload.runtime = int(time.time() * 1000) - self.case_start_time
        data_payload.guid = self.testcase_guid
        data_payload.execution_guid = self.execution_guid
        data_payload.state = state
        if err:
            import traceback

            tb_string = traceback.format_exc()
            if "Message: " in tb_string:
                data_payload.message = (
                    "Message: " + tb_string.split("Message: ")[-1]
                )
            elif "Exception: " in tb_string:
                data_payload.message = tb_string.split("Exception: ")[-1]
            elif "Error: " in tb_string:
                data_payload.message = tb_string.split("Error: ")[-1]
            else:
                data_payload.message = self.__get_exception_info()
        else:
            test_id = self.__get_test_id_2()
            if (
                self.is_pytest
                and test_id in sb_config._results.keys()
                and (sb_config._results[test_id] == "Skipped")
            ):
                if self.__skip_reason:
                    data_payload.message = "Skipped:   " + self.__skip_reason
                else:
                    data_payload.message = "Skipped:   (no reason given)"
        self.testcase_manager.update_testcase_data(data_payload)

    def __add_pytest_html_extra(self):
        if not self.__added_pytest_html_extra:
            try:
                if self.with_selenium:
                    if not self.__last_page_screenshot:
                        self.__set_last_page_screenshot()
                        self.__set_last_page_url()
                        self.__set_last_page_source()
                    if self.report_on:
                        extra_url = {}
                        extra_url["name"] = "URL"
                        extra_url["format"] = "url"
                        extra_url["content"] = self.get_current_url()
                        extra_url["mime_type"] = None
                        extra_url["extension"] = None
                        extra_image = {}
                        extra_image["name"] = "Screenshot"
                        extra_image["format"] = "image"
                        extra_image["content"] = self.__last_page_screenshot
                        extra_image["mime_type"] = "image/png"
                        extra_image["extension"] = "png"
                        self.__added_pytest_html_extra = True
                        if self.__last_page_screenshot != (
                            constants.Warnings.SCREENSHOT_UNDEFINED
                        ):
                            self._html_report_extra.append(extra_url)
                            self._html_report_extra.append(extra_image)
            except Exception:
                pass

    def __quit_all_drivers(self):
        if self._reuse_session and sb_config.shared_driver:
            if len(self._drivers_list) > 0:
                if self._drivers_list[0] != sb_config.shared_driver:
                    if sb_config.shared_driver in self._drivers_list:
                        self._drivers_list.remove(sb_config.shared_driver)
                    self._drivers_list.insert(0, sb_config.shared_driver)
                self._default_driver = self._drivers_list[0]
                self.switch_to_default_driver()
            if len(self._drivers_list) > 1:
                self._drivers_list = self._drivers_list[1:]
            else:
                self._drivers_list = []

        # Close all open browser windows
        self._drivers_list.reverse()  # Last In, First Out
        for driver in self._drivers_list:
            try:
                driver.quit()
            except AttributeError:
                pass
            except Exception:
                pass
        self.driver = None
        self._default_driver = None
        self._drivers_list = []

    def __has_exception(self):
        has_exception = False
        if hasattr(sys, "last_traceback") and sys.last_traceback is not None:
            has_exception = True
        elif sys.version_info[0] >= 3 and hasattr(self, "_outcome"):
            if hasattr(self._outcome, "errors") and self._outcome.errors:
                has_exception = True
        else:
            if sys.version_info[0] >= 3:
                has_exception = sys.exc_info()[1] is not None
            else:
                if not hasattr(self, "_using_sb_fixture_class") and (
                    not hasattr(self, "_using_sb_fixture_no_class")
                ):
                    has_exception = sys.exc_info()[1] is not None
                else:
                    has_exception = len(str(sys.exc_info()[1]).strip()) > 0
        if hasattr(self, "_using_sb_fixture") and self.__will_be_skipped:
            has_exception = False
        return has_exception

    def __get_test_id(self):
        """ The id used in various places such as the test log path. """
        test_id = "%s.%s.%s" % (
            self.__class__.__module__,
            self.__class__.__name__,
            self._testMethodName,
        )
        if self._sb_test_identifier and len(str(self._sb_test_identifier)) > 6:
            test_id = self._sb_test_identifier
        return test_id

    def __get_test_id_2(self):
        """ The id for SeleniumBase Dashboard entries. """
        if "PYTEST_CURRENT_TEST" in os.environ:
            return os.environ["PYTEST_CURRENT_TEST"].split(" ")[0]
        test_id = "%s.%s.%s" % (
            self.__class__.__module__.split(".")[-1],
            self.__class__.__name__,
            self._testMethodName,
        )
        if self._sb_test_identifier and len(str(self._sb_test_identifier)) > 6:
            test_id = self._sb_test_identifier
            if test_id.count(".") > 1:
                test_id = ".".join(test_id.split(".")[1:])
        return test_id

    def __get_display_id(self):
        """ The id for running a test from pytest. (Displayed on Dashboard) """
        if "PYTEST_CURRENT_TEST" in os.environ:
            return os.environ["PYTEST_CURRENT_TEST"].split(" ")[0]
        test_id = "%s.py::%s::%s" % (
            self.__class__.__module__.replace(".", "/"),
            self.__class__.__name__,
            self._testMethodName,
        )
        if self._sb_test_identifier and len(str(self._sb_test_identifier)) > 6:
            test_id = self._sb_test_identifier
            if hasattr(self, "_using_sb_fixture_class"):
                if test_id.count(".") >= 2:
                    parts = test_id.split(".")
                    full = parts[-3] + ".py::" + parts[-2] + "::" + parts[-1]
                    test_id = full
            elif hasattr(self, "_using_sb_fixture_no_class"):
                if test_id.count(".") >= 1:
                    parts = test_id.split(".")
                    full = parts[-2] + ".py::" + parts[-1]
                    test_id = full
        return test_id

    def __get_filename(self):
        """ The filename of the current SeleniumBase test. (NOT Path) """
        filename = None
        if "PYTEST_CURRENT_TEST" in os.environ:
            test_id = os.environ["PYTEST_CURRENT_TEST"].split(" ")[0]
            filename = test_id.split("::")[0].split("/")[-1]
        else:
            filename = self.__class__.__module__.split(".")[-1] + ".py"
        return filename

    def __create_log_path_as_needed(self, test_logpath):
        if not os.path.exists(test_logpath):
            try:
                os.makedirs(test_logpath)
            except Exception:
                pass  # Only reachable during multi-threaded runs

    def __process_dashboard(self, has_exception, init=False):
        """ SeleniumBase Dashboard Processing """
        existing_res = sb_config._results  # Used by multithreaded tests
        if self._multithreaded:
            abs_path = os.path.abspath(".")
            dash_json_loc = constants.Dashboard.DASH_JSON
            dash_jsonpath = os.path.join(abs_path, dash_json_loc)
            if not init and os.path.exists(dash_jsonpath):
                with open(dash_jsonpath, "r") as f:
                    dash_json = f.read().strip()
                dash_data, d_id, dash_rt, tlp, d_stats = json.loads(dash_json)
                num_passed, num_failed, num_skipped, num_untested = d_stats
                sb_config._results = dash_data
                sb_config._display_id = d_id
                sb_config._duration = dash_rt  # Dashboard Run Time
                sb_config._d_t_log_path = tlp  # Test Log Path
                sb_config.item_count_passed = num_passed
                sb_config.item_count_failed = num_failed
                sb_config.item_count_skipped = num_skipped
                sb_config.item_count_untested = num_untested
        if len(sb_config._extra_dash_entries) > 0:
            # First take care of existing entries from non-SeleniumBase tests
            for test_id in sb_config._extra_dash_entries:
                if test_id in sb_config._results.keys():
                    if sb_config._results[test_id] == "Skipped":
                        sb_config.item_count_skipped += 1
                        sb_config.item_count_untested -= 1
                    elif sb_config._results[test_id] == "Failed":
                        sb_config.item_count_failed += 1
                        sb_config.item_count_untested -= 1
                    elif sb_config._results[test_id] == "Passed":
                        sb_config.item_count_passed += 1
                        sb_config.item_count_untested -= 1
                    else:  # Mark "Skipped" if unknown
                        sb_config.item_count_skipped += 1
                        sb_config.item_count_untested -= 1
            sb_config._extra_dash_entries = []  # Reset the list to empty
        # Process new entries
        log_dir = self.log_path
        ft_id = self.__get_test_id()  # Full test id with path to log files
        test_id = self.__get_test_id_2()  # The test id used by the DashBoard
        dud = "seleniumbase/plugins/pytest_plugin.py::BaseClass::base_method"
        dud2 = "pytest_plugin.BaseClass.base_method"
        if hasattr(self, "_using_sb_fixture") and self.__will_be_skipped:
            test_id = sb_config._test_id
        if not init:
            duration_ms = int(time.time() * 1000) - self.__start_time_ms
            duration = float(duration_ms) / 1000.0
            duration = "{:.2f}".format(duration)
            sb_config._duration[test_id] = duration
            if (
                has_exception
                or self.save_screenshot_after_test
                or self.__screenshot_count > 0
                or self.__will_be_skipped
            ):
                sb_config._d_t_log_path[test_id] = os.path.join(log_dir, ft_id)
            else:
                sb_config._d_t_log_path[test_id] = None
            if test_id not in sb_config._display_id.keys():
                sb_config._display_id[test_id] = self.__get_display_id()
            if sb_config._display_id[test_id] == dud:
                return
            if (
                hasattr(self, "_using_sb_fixture")
                and test_id not in sb_config._results.keys()
            ):
                if test_id.count(".") > 1:
                    alt_test_id = ".".join(test_id.split(".")[1:])
                    if alt_test_id in sb_config._results.keys():
                        sb_config._results.pop(alt_test_id)
                elif test_id.count(".") == 1:
                    alt_test_id = sb_config._display_id[test_id]
                    alt_test_id = alt_test_id.replace(".py::", ".")
                    alt_test_id = alt_test_id.replace("::", ".")
                    if alt_test_id in sb_config._results.keys():
                        sb_config._results.pop(alt_test_id)
            if test_id in sb_config._results.keys() and (
                sb_config._results[test_id] == "Skipped"
            ):
                if self.__passed_then_skipped:
                    # Multiple calls of setUp() and tearDown() in the same test
                    sb_config.item_count_passed -= 1
                    sb_config.item_count_untested += 1
                    self.__passed_then_skipped = False
                sb_config._results[test_id] = "Skipped"
                sb_config.item_count_skipped += 1
                sb_config.item_count_untested -= 1
            elif (
                self._multithreaded
                and test_id in existing_res.keys()
                and existing_res[test_id] == "Skipped"
            ):
                sb_config._results[test_id] = "Skipped"
                sb_config.item_count_skipped += 1
                sb_config.item_count_untested -= 1
            elif has_exception:
                if test_id not in sb_config._results.keys():
                    sb_config._results[test_id] = "Failed"
                    sb_config.item_count_failed += 1
                    sb_config.item_count_untested -= 1
                elif not sb_config._results[test_id] == "Failed":
                    # tearDown() was called more than once in the test
                    if sb_config._results[test_id] == "Passed":
                        # Passed earlier, but last run failed
                        sb_config._results[test_id] = "Failed"
                        sb_config.item_count_failed += 1
                        sb_config.item_count_passed -= 1
                    else:
                        sb_config._results[test_id] = "Failed"
                        sb_config.item_count_failed += 1
                        sb_config.item_count_untested -= 1
                else:
                    # pytest-rerunfailures caused a duplicate failure
                    sb_config._results[test_id] = "Failed"
            else:
                if (
                    test_id in sb_config._results.keys()
                    and sb_config._results[test_id] == "Failed"
                ):
                    # pytest-rerunfailures reran a test that failed
                    sb_config._d_t_log_path[test_id] = os.path.join(
                        log_dir, ft_id
                    )
                    sb_config.item_count_failed -= 1
                    sb_config.item_count_untested += 1
                elif (
                    test_id in sb_config._results.keys()
                    and sb_config._results[test_id] == "Passed"
                ):
                    # tearDown() was called more than once in the test
                    sb_config.item_count_passed -= 1
                    sb_config.item_count_untested += 1
                sb_config._results[test_id] = "Passed"
                sb_config.item_count_passed += 1
                sb_config.item_count_untested -= 1
        else:
            pass  # Only initialize the Dashboard on the first processing
        num_passed = sb_config.item_count_passed
        num_failed = sb_config.item_count_failed
        num_skipped = sb_config.item_count_skipped
        num_untested = sb_config.item_count_untested
        self.create_pie_chart(title=constants.Dashboard.TITLE)
        self.add_data_point("Passed", num_passed, color="#84d474")
        self.add_data_point("Untested", num_untested, color="#eaeaea")
        self.add_data_point("Skipped", num_skipped, color="#efd8b4")
        self.add_data_point("Failed", num_failed, color="#f17476")
        style = (
            '<link rel="stylesheet" charset="utf-8" '
            'href="%s">' % constants.Dashboard.STYLE_CSS
        )
        auto_refresh_html = ""
        if num_untested > 0:
            # Refresh every X seconds when waiting for more test results
            auto_refresh_html = constants.Dashboard.META_REFRESH_HTML
        else:
            # The tests are complete
            if sb_config._using_html_report:
                # Add the pie chart to the pytest html report
                sb_config._saved_dashboard_pie = self.extract_chart()
                if self._multithreaded:
                    abs_path = os.path.abspath(".")
                    dash_pie = json.dumps(sb_config._saved_dashboard_pie)
                    dash_pie_loc = constants.Dashboard.DASH_PIE
                    pie_path = os.path.join(abs_path, dash_pie_loc)
                    pie_file = codecs.open(pie_path, "w+", encoding="utf-8")
                    pie_file.writelines(dash_pie)
                    pie_file.close()
        head = (
            '<head><meta charset="utf-8">'
            '<meta name="viewport" content="shrink-to-fit=no">'
            '<link rel="shortcut icon" href="%s">'
            "%s"
            "<title>Dashboard</title>"
            "%s</head>"
            % (constants.Dashboard.DASH_PIE_PNG_1, auto_refresh_html, style)
        )
        table_html = (
            "<div></div>"
            '<table border="1px solid #e6e6e6;" width="100%;" padding: 5px;'
            ' font-size="12px;" text-align="left;" id="results-table">'
            '<thead id="results-table-head">'
            '<tr style="background-color: #F7F7FD;">'
            '<th col="result">Result</th><th col="name">Test</th>'
            '<th col="duration">Duration</th><th col="links">Links</th>'
            "</tr></thead>"
        )
        the_failed = []
        the_skipped = []
        the_passed_hl = []  # Passed and has logs
        the_passed_nl = []  # Passed and no logs
        the_untested = []
        if dud2 in sb_config._results.keys():
            sb_config._results.pop(dud2)
        for key in sb_config._results.keys():
            t_res = sb_config._results[key]
            t_dur = sb_config._duration[key]
            t_d_id = sb_config._display_id[key]
            t_l_path = sb_config._d_t_log_path[key]
            res_low = t_res.lower()
            if sb_config._results[key] == "Failed":
                if not sb_config._d_t_log_path[key]:
                    sb_config._d_t_log_path[key] = os.path.join(log_dir, ft_id)
                the_failed.append([res_low, t_res, t_d_id, t_dur, t_l_path])
            elif sb_config._results[key] == "Skipped":
                the_skipped.append([res_low, t_res, t_d_id, t_dur, t_l_path])
            elif sb_config._results[key] == "Passed" and t_l_path:
                the_passed_hl.append([res_low, t_res, t_d_id, t_dur, t_l_path])
            elif sb_config._results[key] == "Passed" and not t_l_path:
                the_passed_nl.append([res_low, t_res, t_d_id, t_dur, t_l_path])
            elif sb_config._results[key] == "Untested":
                the_untested.append([res_low, t_res, t_d_id, t_dur, t_l_path])
        for row in the_failed:
            row = (
                '<tbody class="%s results-table-row">'
                '<tr style="background-color: #FFF8F8;">'
                '<td class="col-result">%s</td><td>%s</td><td>%s</td>'
                '<td><a href="%s">Logs</a> / <a href="%s/">Data</a>'
                "</td></tr></tbody>"
                "" % (row[0], row[1], row[2], row[3], log_dir, row[4])
            )
            table_html += row
        for row in the_skipped:
            if not row[4]:
                row = (
                    '<tbody class="%s results-table-row">'
                    '<tr style="background-color: #FEFEF9;">'
                    '<td class="col-result">%s</td><td>%s</td><td>%s</td>'
                    "<td>-</td></tr></tbody>"
                    % (row[0], row[1], row[2], row[3])
                )
            else:
                row = (
                    '<tbody class="%s results-table-row">'
                    '<tr style="background-color: #FEFEF9;">'
                    '<td class="col-result">%s</td><td>%s</td><td>%s</td>'
                    '<td><a href="%s">Logs</a> / <a href="%s/">Data</a>'
                    "</td></tr></tbody>"
                    "" % (row[0], row[1], row[2], row[3], log_dir, row[4])
                )
            table_html += row
        for row in the_passed_hl:
            # Passed and has logs
            row = (
                '<tbody class="%s results-table-row">'
                '<tr style="background-color: #F8FFF8;">'
                '<td class="col-result">%s</td><td>%s</td><td>%s</td>'
                '<td><a href="%s">Logs</a> / <a href="%s/">Data</a>'
                "</td></tr></tbody>"
                "" % (row[0], row[1], row[2], row[3], log_dir, row[4])
            )
            table_html += row
        for row in the_passed_nl:
            # Passed and no logs
            row = (
                '<tbody class="%s results-table-row">'
                '<tr style="background-color: #F8FFF8;">'
                '<td class="col-result">%s</td><td>%s</td><td>%s</td>'
                "<td>-</td></tr></tbody>" % (row[0], row[1], row[2], row[3])
            )
            table_html += row
        for row in the_untested:
            row = (
                '<tbody class="%s results-table-row"><tr>'
                '<td class="col-result">%s</td><td>%s</td><td>%s</td>'
                "<td>-</td></tr></tbody>" % (row[0], row[1], row[2], row[3])
            )
            table_html += row
        table_html += "</table>"
        add_more = "<br /><b>Last updated:</b> "
        timestamp, the_date, the_time = log_helper.get_master_time()
        last_updated = "%s at %s" % (the_date, the_time)
        add_more = add_more + "%s" % last_updated
        status = "<p></p><div><b>Status:</b> Awaiting results..."
        status += " (Refresh the page for updates)"
        if num_untested == 0:
            status = "<p></p><div><b>Status:</b> Test Run Complete:"
            if num_failed == 0:
                if num_passed > 0:
                    if num_skipped == 0:
                        status += " <b>Success!</b> (All tests passed)"
                    else:
                        status += " <b>Success!</b> (No failing tests)"
                else:
                    status += " All tests were skipped!"
            else:
                latest_logs_dir = "latest_logs/"
                log_msg = "See latest logs for details"
                if num_failed == 1:
                    status += (
                        " <b>1 test failed!</b> --- "
                        '(<b><a href="%s">%s</a></b>)'
                        "" % (latest_logs_dir, log_msg)
                    )
                else:
                    status += (
                        " <b>%s tests failed!</b> --- "
                        '(<b><a href="%s">%s</a></b>)'
                        "" % (num_failed, latest_logs_dir, log_msg)
                    )
        status += "</div><p></p>"
        add_more = add_more + status
        gen_by = (
            '<p><div>Generated by: <b><a href="https://seleniumbase.io/">'
            "SeleniumBase</a></b></div></p><p></p>"
        )
        add_more = add_more + gen_by
        # Have dashboard auto-refresh on updates when using an http server
        refresh_line = (
            '<script type="text/javascript" src="%s">'
            "</script>" % constants.Dashboard.LIVE_JS
        )
        if num_untested == 0 and sb_config._using_html_report:
            sb_config._dash_final_summary = status
        add_more = add_more + refresh_line
        the_html = (
            '<html lang="en">'
            + head
            + self.extract_chart()
            + table_html
            + add_more
        )
        abs_path = os.path.abspath(".")
        file_path = os.path.join(abs_path, "dashboard.html")
        out_file = codecs.open(file_path, "w+", encoding="utf-8")
        out_file.writelines(the_html)
        out_file.close()
        sb_config._dash_html = the_html
        if self._multithreaded:
            d_stats = (num_passed, num_failed, num_skipped, num_untested)
            _results = sb_config._results
            _display_id = sb_config._display_id
            _rt = sb_config._duration  # Run Time (RT)
            _tlp = sb_config._d_t_log_path  # Test Log Path (TLP)
            dash_json = json.dumps((_results, _display_id, _rt, _tlp, d_stats))
            dash_json_loc = constants.Dashboard.DASH_JSON
            dash_jsonpath = os.path.join(abs_path, dash_json_loc)
            dash_json_file = codecs.open(dash_jsonpath, "w+", encoding="utf-8")
            dash_json_file.writelines(dash_json)
            dash_json_file.close()

    def has_exception(self):
        """(This method should ONLY be used in custom tearDown() methods.)
        This method returns True if the test failed or raised an exception.
        This is useful for performing additional steps in your tearDown()
        method (based on whether or not the test passed or failed).
        Example use cases:
            * Performing cleanup steps if a test didn't complete.
            * Sending test data and/or results to a dashboard service.
        """
        return self.__has_exception()

    def save_teardown_screenshot(self):
        """(Should ONLY be used at the start of custom tearDown() methods.)
        This method takes a screenshot of the current web page for a
        failing test (or when running your tests with --save-screenshot).
        That way your tearDown() method can navigate away from the last
        page where the test failed, and still get the correct screenshot
        before performing tearDown() steps on other pages. If this method
        is not included in your custom tearDown() method, a screenshot
        will still be taken after the last step of your tearDown(), where
        you should be calling "super(SubClassOfBaseCase, self).tearDown()"
        """
        try:
            self.__check_scope()
        except Exception:
            return
        if self.__has_exception() or self.save_screenshot_after_test:
            test_id = self.__get_test_id()
            test_logpath = self.log_path + "/" + test_id
            self.__create_log_path_as_needed(test_logpath)
            self.__set_last_page_screenshot()
            self.__set_last_page_url()
            self.__set_last_page_source()
            if self.is_pytest:
                self.__add_pytest_html_extra()

    def tearDown(self):
        """
        Be careful if a subclass of BaseCase overrides setUp()
        You'll need to add the following line to the subclass's tearDown():
        super(SubClassOfBaseCase, self).tearDown()
        """
        if not hasattr(self, "_using_sb_fixture") and self.__called_teardown:
            # This test already called tearDown()
            return
        if self.recorder_mode:
            self.__process_recorded_actions()
        self.__called_teardown = True
        self.__called_setup = False
        try:
            is_pytest = self.is_pytest  # This fails if overriding setUp()
            if is_pytest:
                with_selenium = self.with_selenium
        except Exception:
            sub_class_name = (
                str(self.__class__.__bases__[0]).split(".")[-1].split("'")[0]
            )
            sub_file_name = str(self.__class__.__bases__[0]).split(".")[-2]
            sub_file_name = sub_file_name + ".py"
            class_name = str(self.__class__).split(".")[-1].split("'")[0]
            file_name = str(self.__class__).split(".")[-2] + ".py"
            class_name_used = sub_class_name
            file_name_used = sub_file_name
            if sub_class_name == "BaseCase":
                class_name_used = class_name
                file_name_used = file_name
            fix_setup = "super(%s, self).setUp()" % class_name_used
            fix_teardown = "super(%s, self).tearDown()" % class_name_used
            message = (
                "You're overriding SeleniumBase's BaseCase setUp() "
                "method with your own setUp() method, which breaks "
                "SeleniumBase. You can fix this by going to your "
                "%s class located in your %s file and adding the "
                "following line of code AT THE BEGINNING of your "
                "setUp() method:\n%s\n\nAlso make sure "
                "you have added the following line of code AT THE "
                "END of your tearDown() method:\n%s\n"
                % (class_name_used, file_name_used, fix_setup, fix_teardown)
            )
            raise Exception(message)
        # *** Start tearDown() officially ***
        self.__slow_mode_pause_if_active()
        has_exception = self.__has_exception()
        if self.__overrided_default_timeouts:
            # Reset default timeouts in case there are more tests
            # These were changed in set_default_timeout()
            if sb_config._SMALL_TIMEOUT and sb_config._LARGE_TIMEOUT:
                settings.SMALL_TIMEOUT = sb_config._SMALL_TIMEOUT
                settings.LARGE_TIMEOUT = sb_config._LARGE_TIMEOUT
                sb_config._is_timeout_changed = False
                self.__overrided_default_timeouts = False
        if self.__deferred_assert_failures:
            print(
                "\nWhen using self.deferred_assert_*() methods in your tests, "
                "remember to call self.process_deferred_asserts() afterwards. "
                "Now calling in tearDown()...\nFailures Detected:"
            )
            if not has_exception:
                self.process_deferred_asserts()
            else:
                self.process_deferred_asserts(print_only=True)
        if self.is_pytest:
            # pytest-specific code
            test_id = self.__get_test_id()
            if with_selenium:
                # Save a screenshot if logging is on when an exception occurs
                if has_exception:
                    self.__add_pytest_html_extra()
                    sb_config._has_exception = True
                if (
                    self.with_testing_base
                    and not has_exception
                    and self.save_screenshot_after_test
                ):
                    test_logpath = self.log_path + "/" + test_id
                    self.__create_log_path_as_needed(test_logpath)
                    if not self.__last_page_screenshot_png:
                        self.__set_last_page_screenshot()
                        self.__set_last_page_url()
                        self.__set_last_page_source()
                    log_helper.log_screenshot(
                        test_logpath,
                        self.driver,
                        self.__last_page_screenshot_png,
                    )
                    self.__add_pytest_html_extra()
                if self.with_testing_base and has_exception:
                    test_logpath = self.log_path + "/" + test_id
                    self.__create_log_path_as_needed(test_logpath)
                    if (
                        not self.with_screen_shots
                        and not self.with_basic_test_info
                        and not self.with_page_source
                    ):
                        # Log everything if nothing specified (if testing_base)
                        if not self.__last_page_screenshot_png:
                            self.__set_last_page_screenshot()
                            self.__set_last_page_url()
                            self.__set_last_page_source()
                        log_helper.log_screenshot(
                            test_logpath,
                            self.driver,
                            self.__last_page_screenshot_png,
                        )
                        log_helper.log_test_failure_data(
                            self,
                            test_logpath,
                            self.driver,
                            self.browser,
                            self.__last_page_url,
                        )
                        log_helper.log_page_source(
                            test_logpath, self.driver, self.__last_page_source
                        )
                    else:
                        if self.with_screen_shots:
                            if not self.__last_page_screenshot_png:
                                self.__set_last_page_screenshot()
                                self.__set_last_page_url()
                                self.__set_last_page_source()
                            log_helper.log_screenshot(
                                test_logpath,
                                self.driver,
                                self.__last_page_screenshot_png,
                            )
                        if self.with_basic_test_info:
                            log_helper.log_test_failure_data(
                                self,
                                test_logpath,
                                self.driver,
                                self.browser,
                                self.__last_page_url,
                            )
                        if self.with_page_source:
                            log_helper.log_page_source(
                                test_logpath,
                                self.driver,
                                self.__last_page_source,
                            )
                if self.dashboard:
                    if self._multithreaded:
                        with self.dash_lock:
                            self.__process_dashboard(has_exception)
                    else:
                        self.__process_dashboard(has_exception)
                # (Pytest) Finally close all open browser windows
                self.__quit_all_drivers()
            if self.headless or self.xvfb:
                if self.headless_active:
                    try:
                        self.display.stop()
                    except AttributeError:
                        pass
                    except Exception:
                        pass
                    self.display = None
            if self.with_db_reporting:
                if has_exception:
                    self.__insert_test_result(constants.State.FAILED, True)
                else:
                    test_id = self.__get_test_id_2()
                    if test_id in sb_config._results.keys() and (
                        sb_config._results[test_id] == "Skipped"
                    ):
                        self.__insert_test_result(
                            constants.State.SKIPPED, False
                        )
                    else:
                        self.__insert_test_result(
                            constants.State.PASSED, False
                        )
                runtime = int(time.time() * 1000) - self.execution_start_time
                self.testcase_manager.update_execution_data(
                    self.execution_guid, runtime
                )
            if self.with_s3_logging and has_exception:
                """ If enabled, upload logs to S3 during test exceptions. """
                import uuid
                from seleniumbase.core.s3_manager import S3LoggingBucket

                s3_bucket = S3LoggingBucket()
                guid = str(uuid.uuid4().hex)
                path = "%s/%s" % (self.log_path, test_id)
                uploaded_files = []
                for logfile in os.listdir(path):
                    logfile_name = "%s/%s/%s" % (
                        guid,
                        test_id,
                        logfile.split(path)[-1],
                    )
                    s3_bucket.upload_file(
                        logfile_name, "%s/%s" % (path, logfile)
                    )
                    uploaded_files.append(logfile_name)
                s3_bucket.save_uploaded_file_names(uploaded_files)
                index_file = s3_bucket.upload_index_file(test_id, guid)
                print("\n\n*** Log files uploaded: ***\n%s\n" % index_file)
                logging.info(
                    "\n\n*** Log files uploaded: ***\n%s\n" % index_file
                )
                if self.with_db_reporting:
                    from seleniumbase.core.testcase_manager import (
                        TestcaseDataPayload,
                    )
                    from seleniumbase.core.testcase_manager import (
                        TestcaseManager,
                    )

                    self.testcase_manager = TestcaseManager(self.database_env)
                    data_payload = TestcaseDataPayload()
                    data_payload.guid = self.testcase_guid
                    data_payload.logURL = index_file
                    self.testcase_manager.update_testcase_log_url(data_payload)
        else:
            # (Nosetests)
            if has_exception:
                test_id = self.__get_test_id()
                test_logpath = self.log_path + "/" + test_id
                self.__create_log_path_as_needed(test_logpath)
                log_helper.log_test_failure_data(
                    self,
                    test_logpath,
                    self.driver,
                    self.browser,
                    self.__last_page_url,
                )
                if len(self._drivers_list) > 0:
                    if not self.__last_page_screenshot_png:
                        self.__set_last_page_screenshot()
                        self.__set_last_page_url()
                        self.__set_last_page_source()
                    log_helper.log_screenshot(
                        test_logpath,
                        self.driver,
                        self.__last_page_screenshot_png,
                    )
                    log_helper.log_page_source(
                        test_logpath, self.driver, self.__last_page_source
                    )
            elif self.save_screenshot_after_test:
                test_id = self.__get_test_id()
                test_logpath = self.log_path + "/" + test_id
                self.__create_log_path_as_needed(test_logpath)
                if not self.__last_page_screenshot_png:
                    self.__set_last_page_screenshot()
                    self.__set_last_page_url()
                    self.__set_last_page_source()
                log_helper.log_screenshot(
                    test_logpath, self.driver, self.__last_page_screenshot_png
                )
            if self.report_on:
                self._last_page_screenshot = self.__last_page_screenshot_png
                try:
                    self._last_page_url = self.get_current_url()
                except Exception:
                    self._last_page_url = "(Error: Unknown URL)"
            # Finally close all open browser windows
            self.__quit_all_drivers()
