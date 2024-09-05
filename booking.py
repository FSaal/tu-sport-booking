import json
import re
import time
from collections import defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import Playwright, sync_playwright


class Person:
    """Class to represent a person with basic personal details."""

    def __init__(
        self,
        gender: str,
        first_name: str,
        last_name: str,
        address: str,
        city: str,
        postal_code: str,
        status: str,
        student_number: str,
        email: str,
        phone: str,
        birthdate: str,
    ):
        """Initialize the person."""
        self.gender = gender
        self.first_name = first_name
        self.last_name = last_name
        self.address = address
        self.city = city
        self.postal_code = postal_code
        self.status = status
        self.student_number = student_number
        self.email = email
        self.phone = phone
        self.birthdate = birthdate

    def __repr__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class BankAccount:
    """Class to represent a bank account with IBAN and BIC details."""

    def __init__(self, iban, bic):
        self.iban = iban
        self.bic = bic


class FormFiller:
    """Class to fill personal details into web form using Playwright."""

    def __init__(self, page):
        self.page = page

    def fill_personal_details(self, person: Person, index: int | None = None) -> None:
        """Fill personal details for a given person into the corresponding form fields."""
        # Name of input elements on the booking page have no index for the first person
        if index is None:
            index = ""

        # Check correct gender radio button
        gender_mapping = {"male": "maennlich", "female": "weiblich"}
        # If gender is unknown use ska --> keine Angabe
        mapped_gender = gender_mapping.get(person.gender.lower(), "ska")
        self.page.locator(f'input[name="Geschlecht{index}"][id="{mapped_gender}"]').check()

        # Fill form fields
        self.page.locator(f'input[name="Vorname{index}"]').fill(person.first_name)
        self.page.locator(f'input[name="Name{index}"]').fill(person.last_name)
        self.page.locator(f'input[name="Strasse{index}"]').fill(person.address)
        self.page.locator(f'input[name="Ort{index}"]').fill(f"{person.postal_code} {person.city}")
        self.page.locator(f'select[name="Statusorig{index}"]').select_option(person.status)
        self.page.locator(f'input[name="Matnr{index}"]').fill(person.student_number)
        self.page.locator(f'input[name="Mail{index}"]').fill(person.email)
        self.page.locator(f'input[name="Tel{index}"]').fill(person.phone)

        # Fill birthdate if visible (only necessary on some booking sites)
        if self.page.locator(f'input[name="Geburtsdatum{index}"]').is_visible():
            self.page.locator(f'input[name="Geburtsdatum{index}"]').fill(person.birthdate)


class BookingManager:
    def __init__(self):
        self.person1 = None
        self.person2 = None
        self.bank_details = None
        self.slots_overview_url = None
        self.desired_day = None
        self.desired_start_time = None
        self.desired_duration_h = None
        self.double_booking = None
        self.request_refresh_interval_s = None
        self.review_time_s = None

    def validate_input_data(self, day: str, time: int, refresh_interval: int, review_time: int) -> None:
        """Check if the input data is valid. Raise an error if not."""
        errors = []

        valid_days = {
            "Montag",
            "Dienstag",
            "Mittwoch",
            "Donnerstag",
            "Freitag",
            "Samstag",
            "Sonntag",
        }
        if day not in valid_days:
            errors.append(f"Invalid day: {day}. Must be one of {', '.join(valid_days)}")

        if not isinstance(time, int) or not (8 <= time <= 22):
            errors.append(f"Invalid start time: {time}. Must be an integer between 8 and 22.")

        if not isinstance(refresh_interval, int) or refresh_interval <= 0:
            errors.append(f"Invalid refresh interval: {refresh_interval}. Must be a positive integer.")

        if not isinstance(review_time, int) or review_time < 0:
            errors.append(f"Invalid review time: {review_time}. Must be a non-negative integer.")

        return errors

    def validate_personal_details(self, person: Person) -> None:
        """Check if the personal details are valid. Raise an error if not."""
        errors = []

        if not person.first_name.isalpha():
            errors.append(
                f"Invalid first name: {person.first_name}. First name should only contain alphabetic characters."
            )

        if not person.last_name.isalpha():
            errors.append(
                f"Invalid last name: {person.last_name}. Last name should only contain alphabetic characters."
            )

        if not (person.postal_code.isdigit() and len(person.postal_code) == 5):
            errors.append(f"Invalid postal code: {person.postal_code}. It must be a 5-digit number.")

        # TODO: Verify address

        if not re.fullmatch(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", person.email):
            errors.append(f"Invalid email address: {person.email}")

        valid_status = {
            "S-TU": "Student",
            "TU-Alumni": "Registered Alumni",
            "extern": "External",
        }
        if person.status not in valid_status:
            errors.append(
                f"Invalid status: {person.status}. Must be one of {', '.join([f'{json_status} ({status})' for json_status, status in valid_status.items()])}."
            )

        if not person.phone.replace(" ", "").replace("+", "").isdigit():
            errors.append(f"Invalid phone number: {person.phone}. It must contain only digits.")

        if not re.fullmatch(r"^\d{2}\.\d{2}\.\d{4}$", person.birthdate):
            errors.append(f"Invalid birthdate format: {person.birthdate}. It should be in the format dd.mm.yyyy.")

        return errors

    def validate_config(self) -> None:
        """Validate the loaded configuration data."""
        errors = []
        errors.extend(
            self.validate_input_data(
                self.desired_day, self.desired_start_time, self.request_refresh_interval_s, self.review_time_s
            )
        )
        errors.extend(self.validate_personal_details(self.person1))
        errors.extend(self.validate_personal_details(self.person2))

        if errors:
            print("WARNING - Some configuration errors were found:")
            print("\n".join(errors))
            ignore = input("Continue anyway? (y/n): ").strip().lower()
            if ignore != "y":
                raise ValueError("\n".join(errors))

    def load_config(self, config_file_path: str | Path) -> None:
        """Load the configuration data from a JSON file and verify, that they are valid."""
        with open(config_file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        self.person1 = Person(**data["person1"])
        self.person2 = Person(**data["person2"])
        self.bank_details = BankAccount(**data["banking"])
        self.slots_overview_url = data["slots_overview_url"]
        # Capitalize it, in case it was forgotten in the JSON
        self.desired_day = data["desired_day"].capitalize()
        self.desired_start_time = data["desired_start_time"]
        self.desired_duration_h = data["desired_duration_h"]
        self.double_booking = data["double_booking"]
        self.request_refresh_interval_s = data["request_refresh_interval_s"]
        self.review_time_s = data["review_time_s"]

        self.validate_config()

    def fetch_available_slots(self, url: str | Path) -> dict:
        """Collect available time slots, with their field number and booking link."""
        # Fetch the HTML content
        response = requests.get(url, timeout=10)

        # Check if site is reachable
        if response.status_code != 200:
            print(f"Request failed with status code {response.status_code}")
            raise ConnectionError

        day_slots = defaultdict(dict)
        html_content = BeautifulSoup(response.content, "html.parser")

        # Find table containing the time slots
        table_body = html_content.find("div", class_="table-body-group")
        if not table_body:
            # Possible, if no time slots are available
            raise ValueError("Could not find table containing time slots.")
        
        # First day is not inside the table body group and must manually initialized
        day_name = "Montag"
        for day in table_body.find_all("div", class_="table-row"):
            if day.find_all("div", class_="table-head column-1"):
                # Row contains day name
                day_name = day.find("div", class_="table-head column-1").text.strip()
            elif day.find_all("div", class_="date bookable"):
                # Row contains time slots for one day
                available_slots = day.find_all("div", class_="date bookable")
                print(f"Available slots on {day_name}: {len(available_slots)}")
                
                time_slots = defaultdict(dict)
                for time_slot in available_slots:
                    link_tag = time_slot.find("a")
                    if not link_tag:
                        continue
                    
                    # Extract time, field number and booking link
                    # Time is written in bold and hence inside a strong tag
                    time_slot = link_tag.find("strong", class_="time").text
                    # Omit "Feld" and only extract number
                    field = str(link_tag.find("span", class_="detail").text[-1])
                    booking_link = link_tag.get("href")
                    time_slots[time_slot][field] = booking_link

                for time_slot in time_slots:
                    # If there are multiple fields for one time slot, print them in one line
                    print(f"{time_slot} (field {" & ".join([field for field in time_slots[time_slot]])})")
                    day_slots[day_name][time_slot] = time_slots[time_slot]

        return day_slots

    def generate_time_slot(self, hour: int) -> str:
        """Convert starting hour to time format used for the booking.
        E.g. 8 --> 08:00-09:00"""
        return f"{hour:02d}:00-{(hour+1):02d}:00"

    def get_booking_link(self, slots: dict, day: int, start_time: int) -> str:
        """Retrieve booking link for desired time slot.
        If no slot is available for that time, raise an error."""
        # Get first available pitch (if there are multiple)
        time = self.generate_time_slot(start_time)
        try:
            # Get first dictionary entry
            first_pitch = next(iter(slots[day][time]))
        except KeyError:
            # Slot is not available
            raise ValueError(f"No slot available on {day} at {time}\n")
        return slots[day][time][first_pitch]

    def monitor_slots(
        self,
        url: str,
        day: str,
        start_time: int,
        refresh_interval_s: int,
        review_time_s: int,
    ):
        """Periodically check what slots are available. If the desired slot is available, open the booking page.

        Args:
            url (str): Some link
            day (str): Name of the day (in german) to look for (e.g. Montag)
            start_time (int): Start time in 24h format (e.g. 15 for 3pm)
            refresh_interval_s (int): Time to wait in seconds before sending new request.
            review_time_s (int): Time to wait in seconds, after which the booking will be confirmed.
        """
        while True:
            self.attempt_booking(url, day, start_time, review_time_s)
            t0 = time.time()
            while True:
                elapsed_time = time.time() - t0
                remaining_time = refresh_interval_s - elapsed_time
                if remaining_time <= 0:
                    # Exit loop and fetch again
                    break
                print(f"Trying again in {remaining_time:.0f} seconds", end="\r")
                time.sleep(1)

    def fill_form(self, playwright: Playwright, booking_url: str | Path, review_time_s: int) -> None:
        """Fill out the booking form and submit it after review time is over."""
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # First page - Contains only one radio button to confirm date and time
        page.goto(booking_url)
        # Select first available date (there is never more than one, since new appointments are only released 1 week prior)
        page.get_by_role("radio").check()
        page.get_by_role("button", name="weiter zur Buchung").click()

        # Second page - Actual booking site where data must be entered
        # Personal details
        form_filler = FormFiller(page)
        form_filler.fill_personal_details(self.person1)
        form_filler.fill_personal_details(self.person2, 2)
        # Payment details
        page.locator('input[name="iban"]').fill(self.bank_details.iban)
        page.locator('input[name="bic"]').fill(self.bank_details.bic)
        page.locator('input[name="BuchBed"]').check()
        page.get_by_role("button", name="verbindlich anmelden").click()
        
        # Third page - Confirmation
        # Checkbox to confirm that data is correct and banking account has enough balance
        page.get_by_role("checkbox").check()

        # Confirm booking after review time is over
        t0 = time.time()
        while True:
            elapsed_time = time.time() - t0
            if elapsed_time > review_time_s:
                break
            print(
                f"Booking will be performed in {int(review_time_s - elapsed_time):03d} seconds",
                end="\r",
            )
            time.sleep(1)
        page.get_by_role("button", name="kostenpflichtig buchen").click()
        # Keep page open to let user see booking confirmation
        time.sleep(10)
        context.close()
        browser.close()

    def attempt_booking(self, slots_url: str, day: str, start_time: int, review_time_s: int) -> None:
        """Get available slots and book slot, if the desired slot is available."""
        slots = self.fetch_available_slots(slots_url)
        booking_url = self.get_booking_link(slots, day, start_time)
        with sync_playwright() as playwright:
            self.fill_form(playwright, booking_url, review_time_s)


if __name__ == "__main__":
    booking = BookingManager()
    booking.load_config("form_data.json")
    booking.monitor_slots(
        booking.slots_overview_url,
        booking.desired_day,
        booking.desired_start_time,
        booking.request_refresh_interval_s,
        booking.review_time_s,
    )
