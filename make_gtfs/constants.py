import pytz
import pycountry


#: Character to separate different chunks within an ID
SEP = '-'

#: Meters to buffer trip paths to find stops
BUFFER = 10

#: Country name by country alpha-2 code
country_by_alpha2 = {
    country.alpha_2: country.name
    for country in pycountry.countries
}

#: Country alpha-2 code by timezone
alpha2_by_timezone = {
    timezone: alpha2
    for alpha2, timezones in pytz.country_timezones.items()
    for timezone in timezones
}

#: Country name by timezone
country_by_timezone = {
    timezone: country_by_alpha2[alpha2]
    for timezone, alpha2 in alpha2_by_timezone.items()
}

#: Country names with left hand traffic
lht_countries = set([
    'Antigua and Barbuda',
    'Australia',
    'Bahamas',
    'Bangladesh',
    'Barbados',
    'Bhutan',
    'Botswana',
    'Brunei',
    'Cyprus',
    'Dominica',
    'East Timor',
    'Fiji',
    'Grenada',
    'Guyana',
    'Hong Kong',
    'India',
    'Indonesia',
    'Ireland',
    'Jamaica',
    'Japan',
    'Kenya',
    'Kiribati',
    'Lesotho',
    'Macau',
    'Malawi',
    'Malaysia',
    'Maldives',
    'Malta',
    'Mauritius',
    'Mozambique',
    'Namibia',
    'Nauru',
    'Nepal',
    'New Zealand',
    'Niue',
    'Northern Cyprus',
    'Pakistan',
    'Papua New Guinea',
    'Saint Kitts and Nevis',
    'Saint Lucia',
    'Saint Vincent and the Grenadines',
    'Samoa',
    'Seychelles',
    'Singapore',
    'Solomon Islands',
    'South Africa',
    'Sri Lanka',
    'Suriname',
    'Swaziland',
    'Tanzania',
    'Thailand',
    'Tonga',
    'Trinidad and Tobago',
    'Tuvalu',
    'Uganda',
    'United Kingdom',
    'Zambia',
    'Zimbabwe',
])

#: Traffic side by timezone
traffic_by_timezone = {}
for timezone, country in country_by_timezone.items():
    if country in lht_countries:
        traffic = 'left'
    else:
        traffic = 'right'
    traffic_by_timezone[timezone] = traffic
