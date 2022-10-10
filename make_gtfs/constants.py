"""
Constants used throughout the package.
"""
import pytz
import pycountry


WGS84 = "EPSG:4326"

#: Character to separate different chunks within an ID
SEP = "-"

#: Meters to buffer trip paths to find stops
BUFFER = 10

#: Meters to offset stops from route shapes
STOP_OFFSET = 5

# Country name by country alpha-2 code
COUNTRY_BY_ALPHA2 = {country.alpha_2: country.name for country in pycountry.countries}

# Country alpha-2 code by timezone
ALPHA2_BY_TIMEZONE = {
    timezone: alpha2
    for alpha2, timezones in pytz.country_timezones.items()
    for timezone in timezones
}

# Country name by timezone
COUNTRY_BY_TIMEZONE = {
    timezone: COUNTRY_BY_ALPHA2[alpha2]
    for timezone, alpha2 in ALPHA2_BY_TIMEZONE.items()
}

# Country names with left hand traffic
LHT_COUNTRIES = set(
    [
        "Antigua and Barbuda",
        "Australia",
        "Bahamas",
        "Bangladesh",
        "Barbados",
        "Bhutan",
        "Botswana",
        "Brunei",
        "Cyprus",
        "Dominica",
        "East Timor",
        "Fiji",
        "Grenada",
        "Guyana",
        "Hong Kong",
        "India",
        "Indonesia",
        "Ireland",
        "Jamaica",
        "Japan",
        "Kenya",
        "Kiribati",
        "Lesotho",
        "Macau",
        "Malawi",
        "Malaysia",
        "Maldives",
        "Malta",
        "Mauritius",
        "Mozambique",
        "Namibia",
        "Nauru",
        "Nepal",
        "New Zealand",
        "Niue",
        "Northern Cyprus",
        "Pakistan",
        "Papua New Guinea",
        "Saint Kitts and Nevis",
        "Saint Lucia",
        "Saint Vincent and the Grenadines",
        "Samoa",
        "Seychelles",
        "Singapore",
        "Solomon Islands",
        "South Africa",
        "Sri Lanka",
        "Suriname",
        "Swaziland",
        "Tanzania",
        "Thailand",
        "Tonga",
        "Trinidad and Tobago",
        "Tuvalu",
        "Uganda",
        "United Kingdom",
        "Zambia",
        "Zimbabwe",
    ]
)

# Traffic side by timezone
TRAFFIC_BY_TIMEZONE = {}
for timezone, country in COUNTRY_BY_TIMEZONE.items():
    if country in LHT_COUNTRIES:
        traffic = "left"
    else:
        traffic = "right"
    TRAFFIC_BY_TIMEZONE[timezone] = traffic
