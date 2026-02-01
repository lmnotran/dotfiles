#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# This script creates a Google Calendar event link from a date and flight number.

__doc__ = """
Usage:
    gcal.py <date> <flight_iata>
    gcal.py <date> <flight_iata> <origin_iata> <destination_iata> <departure_time> <arrival_time>
    gcal.py (-h | --help)

Arguments:
    <date>              The date of the flight in YYYY-MM-DD format.
    <flight_iata>       The IATA flight number (e.g., AA1234).
    <origin_iata>       The IATA code of the departure airport (e.g., LAX).
    <destination_iata>  The IATA code of the arrival airport (e.g., JFK).
    <departure_time>    The scheduled departure time in 24-hour format (e.g., 1500).
    <arrival_time>      The scheduled arrival time in 24-hour format (e.g., 1700).

Options:
    -h --help       Show this help message and exit
"""

# Used to get flight information
import requests
import datetime
from zoneinfo import ZoneInfo
import pprint
import airportsdata

# Used to create Google Calendar event link
import sys
from urllib.parse import urlencode
from docopt import docopt
import os

aviationstack_api_key = os.environ.get("AVIATIONSTACK_API_KEY", "")

def get_tzone_info(airport_code: str) -> ZoneInfo:
    '''
    Returns the timezone of the airport.
    Args:
        airport_code (str): The IATA code of the airport.
    Returns:
        ZoneInfo: The timezone of the airport.
    '''
    airports = airportsdata.load("IATA")

    if airport_code not in airports:
        print(f"Error: Airport '{airport_code}' not found.")
        sys.exit(1)

    return ZoneInfo(airports[airport_code].get("tz"))

# =============================================================================================

class FlightDetails:
    def __init__(self, data) -> None:
        self.flight_date = data.get("flight_date")
        self.flight_status = data.get("flight_status")
        self.departure = data.get("departure", {})
        self.arrival = data.get("arrival", {})
        self.airline = data.get("airline", {})
        self.flight = data.get("flight", {})
        self.aircraft = data.get("aircraft", {})
        self.live = data.get("live", {})

        # Convert all time strings to datetime objects
        for key in ["departure", "arrival"]:
            if key in data:
                for time_key in ["estimated", "actual", "scheduled"]:
                    if time_key in data[key]:
                        time_value = data[key][time_key]
                        if isinstance(time_value, str):
                            # Convert the string to a datetime object
                            data[key][time_key] = datetime.datetime.strptime(time_value, "%Y-%m-%dT%H:%M:%S%z")
                        elif isinstance(time_value, datetime.datetime):
                            # If it's already a datetime object, just keep it
                            continue

    def get_departure_time(self) -> datetime.datetime:
        '''
        Returns the scheduled departure time in local time.
        '''
        return self.departure.get("scheduled", self.departure.get("actual"))

    def get_arrival_time(self) -> datetime.datetime:
        '''
        Returns the scheduled arrival time in local time.
        '''
        return self.arrival.get("scheduled", self.arrival.get("actual"))

    def get_departure_airport(self) -> str:
        return self.departure.get("airport")

    def get_departure_airport_iata(self) -> str:
        return self.departure.get("iata")

    def get_arrival_airport_iata(self) -> str:
        return self.arrival.get("iata")

    def get_flight_iata(self) -> str:
        return self.flight.get("iata")

    def get_origin_timezone(self) -> ZoneInfo:
        '''
        Returns the timezone of the departure airport.
        '''
        departure_airport = self.get_departure_airport_iata()
        if departure_airport:
            return get_tzone_info(departure_airport)
        else:
            print("Error: Departure airport IATA code not found.")
            sys.exit(1)
    def get_destination_timezone(self) -> ZoneInfo:
        '''
        Returns the timezone of the arrival airport.
        '''
        arrival_airport = self.get_arrival_airport_iata()
        if arrival_airport:
            return get_tzone_info(arrival_airport)
        else:
            print("Error: Arrival airport IATA code not found.")
            sys.exit(1)


def get_flight_details_aviationstack(flight_iata: str) -> FlightDetails:
    '''
    Fetches flight details from aviationstack website.

    Because of the API limitations, we can only get flight details for 3 days in the future from the current date.
    Use the date most in the future as it is probably closest to the scheduled time without any delays.

    Args:
        flight_iata (str): The IATA flight number. e.g., "AA1234".
        date (datetime): The date of the flight.
    Returns:
        FlightDetails: An object containing flight details.
    '''
    date = datetime.datetime.now().date()

    # Request details
    request = {
        "access_key": aviationstack_api_key,
        "flight_iata": flight_iata,
        "flight_dates": date.strftime("%Y-%m-%d"),
    }

    # Construct the URL for the API request
    base_url = "http://api.aviationstack.com/v1/flights"
    url = f"{base_url}?{urlencode(request)}"

    # Make the API request
    print(f"Fetching flight details from: {url}")
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code != 200:
        print(f"Error: Unable to fetch flight details. Status code: {response.status_code}")
        sys.exit(1)

    # Parse the JSON response
    data = response.json()
    # pprint.pprint(data)

    # Check if the response contains flight data
    if not data.get("data"):
        print("Error: No flight data found.")
        sys.exit(1)

    # Extract the first flight data
    flight_data = data["data"][0]

    # Create an FlightDetails object
    flight_response = FlightDetails(flight_data)

    return flight_response
# =============================================================================================

def create_event_link(flight_date: datetime.datetime, flight_details: FlightDetails) -> str:
    '''
    Creates a Google Calendar event link.
    Args:
        flight_date (datetime): The date of the event in YYYY-MM-DD format.
        flight_details (FlightDetails): An object containing flight details.
    Returns:
        str: The Google Calendar event link.
    '''

    # Get flight times and set the date in start_time and end_time to the flight_date
    start_time = flight_details.get_departure_time().replace(year=flight_date.year, month=flight_date.month, day=flight_date.day)
    end_time = flight_details.get_arrival_time().replace(year=flight_date.year, month=flight_date.month, day=flight_date.day)

    # Format the datetime objects to strings.
    # For the end time, convert it to the timezone of the origin airport.
    # This is because Google Calendar requires the start and end times to be in the same timezone.
    origin_timezone = flight_details.get_origin_timezone()
    start_datetime_str = start_time.strftime("%Y%m%dT%H%M%S")
    end_datetime_str = end_time.astimezone(origin_timezone).strftime("%Y%m%dT%H%M%S")

    # Get timezone of origin airport
    timezone = flight_details.get_origin_timezone().key

    departure_iata = flight_details.get_departure_airport_iata()
    arrival_iata = flight_details.get_arrival_airport_iata()
    flight_iata = flight_details.get_flight_iata()

    # Event details
    event_details = {
        "action": "TEMPLATE",
        "text": f"{departure_iata}✈️{arrival_iata} - {flight_iata}",
        "location": f"{flight_details.get_departure_airport()} Airport",
        "dates": f"{start_datetime_str}/{end_datetime_str}",
        "ctz": timezone,
    }

    # Generate the Google Calendar event link
    base_url = "https://www.google.com/calendar/render"
    event_link = f"{base_url}?{urlencode(event_details)}"
    return event_link

def main():
    if __doc__ is None:
        print("Error: __doc__ string is missing or not defined.")
        sys.exit(1)

    args = docopt(__doc__)

    # Parse command line arguments
    date = args["<date>"]
    flight_iata = args["<flight_iata>"]
    origin_iata = args["<origin_iata>"] if args["<origin_iata>"] else None
    destination_iata = args["<destination_iata>"] if args["<destination_iata>"] else None
    departure_time = datetime.datetime.strptime(args["<departure_time>"], "%H%M") if args["<departure_time>"] else None
    arrival_time = datetime.datetime.strptime(args["<arrival_time>"], "%H%M") if args["<arrival_time>"] else None

    # Get flight details
    global flight_details
    if origin_iata and destination_iata and departure_time and arrival_time:

        # Set the date and timezones for the departure and arrival times
        departure_time = datetime.datetime(
            year=int(date.split("-")[0]),
            month=int(date.split("-")[1]),
            day=int(date.split("-")[2]),
            hour=departure_time.hour,
            minute=departure_time.minute,
            tzinfo=get_tzone_info(origin_iata),
        )
        arrival_time = datetime.datetime(
            year=int(date.split("-")[0]),
            month=int(date.split("-")[1]),
            day=int(date.split("-")[2]),
            hour=arrival_time.hour,
            minute=arrival_time.minute,
            tzinfo=get_tzone_info(destination_iata),
        )

        print("Creating event link with manually specified details.")
        # Create a FlightDetails object with manually specified details
        flight_details = FlightDetails({
            "flight_date": date,
            "departure": {
                "airport": origin_iata,
                "iata": origin_iata,
                "scheduled": departure_time,
                "timezone": get_tzone_info(origin_iata),
            },
            "arrival": {
                "iata": destination_iata,
                "scheduled": arrival_time,
                "timezone": get_tzone_info(destination_iata),
            },
            "flight": {
                "iata": flight_iata,
            },
        })
    else:
        print("Fetching flight details from aviationstack.")
        flight_details = get_flight_details_aviationstack(flight_iata)

    flight_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    event_link = create_event_link(flight_date, flight_details)

    print()
    print("Google Calendar Event Link:")
    print(event_link)

if __name__ == "__main__":
    main()

