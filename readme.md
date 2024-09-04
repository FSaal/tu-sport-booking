# Slot Booking Automation Program

This program automatically checks available booking slots on the TU-Berlin Tennisplatzbuchung-Einzeltermin webpage and, based on the user's desired slot preferences, opens the booking page and fills in all necessary information for the user. The user only needs to click "verbindlich anmelden" to finalize the booking.

## Features

- Automatically checks available slots on the specified webpage and displays them in the terminal.
- Opens the booking page for the desired slot (if available) and fills in the user's information.
- Retries automatically if the desired slot is not available.
- Configurable via a JSON file to adjust preferences for desired booking day, time, and user details.

## Requirements

- Python 3.x
- Playwright (for browser automation)
- Requests (for fetching the webpage data)
- JSON configuration file

## Installation

1. **Get the repository:**
    Ask Felix to send it to you

2. **Install the required Python packages:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright and set up the browser:**
   ```bash
   playwright install
   ```

## Configuration

You need to modify the `form_data.json` file to include your personal information, preferences for the booking day, time, and other details. Below is the structure of the configuration file:

### `form_data.json`

```json
{
    "person1": {
        "gender": "female",
        "first_name": "Evelyn",
        "last_name": "Müller",
        "address": "Musterstraße 12",
        "city": "Berlin",
        "postal_code": "10117",
        "status": "TU-Alumni",
        "student_number": "-",
        "email": "ev.muell@gmail.com",
        "phone": "017423456789",
        "birthdate": "15.07.1990"
    },
    "person2": {
        "gender": "male",
        "first_name": "Lukas",
        "last_name": "Schmidt",
        "address": "Musterstraße 12",
        "city": "Berlin",
        "postal_code": "10117",
        "status": "S-TU",
        "student_number": "456789",
        "email": "lu.schmidt@gmail.com",
        "phone": "017423456789",
        "birthdate": "18.01.2006"
    },
    "banking": {
        "iban": "DE89370400400432013000",
        "bic": "GENODEF1P01"
    },
    "slots_overview_url": "https://www.tu-sport.de/sportprogramm/kurse/?tx_dwzeh_courses%5Baction%5D=show&tx_dwzeh_courses%5BsportsDescription%5D=768&cHash=302c5e58dded9777b08d1305c1398488",
    "desired_day": "Mittwoch",
    "desired_start_time": 14,
    "double_booking": false,
    "request_refresh_interval_s": 100,
    "review_time_s": 10
}
```

### Explanation of JSON Fields

- **person1** and **person2**: Personal details for the two users.
  - **gender**: male or female, otherwise "keine Angabe" will be selected
  - Only the following **status**es are supported currently:
    | Status                                       | JSON format |
    | -------------------------------------------- | ----------- |
    | Student*in der Technische Universität Berlin | S-TU        |
    | registrierte Alumni der TU Berlin            | TU-Alumni   |
    | Externe*r                                    | extern      |
  - **student_number**: Only necessary, if **status** is set to student. Otherwise write "" or "-".
- **banking**: IBAN and BIC details for payment.
- **slots_overview_url**: URL of the page that displays the available slots.
- **desired_day**: The day (in german) on which you want to book a slot (e.g., "Mittwoch"). 
- **desired_start_time**: Desired start time in 24-hour format (e.g., `14` for 2 PM). Must be between 8 and 22.
- **desired_duration**: The time the session should last. Defaults to 1 hour. NOT IMPLEMENTED.
- **double_booking**: Set to `true` if you want to book two slots simultaneously. NOT IMPLEMENTED.
- **request_refresh_interval_s**: How often (in seconds) the program checks for new slots.
- **review_time_s**: The amount of time (in seconds) given to the user to review the pre-filled form before submitting. Set to 0, to immediately book. **Attention**: After the review time is up, the booking is executed and can not be reversed!

## Usage

1. **Update `form_data.json`** with your details and preferences.

2. **Run the program:**
   ```bash
   python slot_booking.py
   ```

3. The program will start checking the available slots at the specified interval. When a desired slot becomes available, it will automatically:
   - Open the booking page.
   - Fill in all personal and payment information.
   - Allow you to review the pre-filled information before you confirm the booking.

## Notes

- Ensure your personal information is correctly formatted in the JSON file.
- The program will notify you when it's ready to confirm the booking, giving you enough time to check the details.
- You can update the refresh interval to check for slots more frequently or less frequently, depending on your preference.

## Troubleshooting

If you encounter issues:

1. **Missing or outdated dependencies**: Ensure you've installed all required libraries with `pip install -r requirements.txt`.
2. **Playwright browser issues**: Try reinstalling the Playwright browsers:
   ```bash
   playwright install
   ```
3. **Configuration errors**: Double-check the `form_data.json` for any incorrect or missing fields.
