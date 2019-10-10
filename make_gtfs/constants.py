"""
Constants used throughout the package.
"""
import pandas as pd
import pytz
import pycountry


#: Character to separate different chunks within an ID
SEP = '-'

#: Meters to buffer trip paths to find stops
BUFFER = 10

# ProtoFeed table and field reference
PROTOFEED_REF = pd.DataFrame(
    [
        ['frequencies', True, 'route_short_name', True, 'str'],
        ['frequencies', True, 'route_long_name', True, 'str'],
        ['frequencies', True, 'route_type', True, 'int'],
        ['frequencies', True, 'service_window_id', True, 'str'],
        ['frequencies', True, 'direction', True, 'int'],
        ['frequencies', True, 'frequency', True, 'int'],
        ['frequencies', True, 'speed', True, 'float'],
        ['frequencies', True, 'shape_id', True, 'str'],
        ['meta', True, 'agency_name', True, 'str'],
        ['meta', True, 'agency_url', True, 'str'],
        ['meta', True, 'agency_timezone', True, 'str'],
        ['meta', True, 'start_date', True, 'str'],
        ['meta', True, 'end_date', True, 'str'],
        ['meta', True, 'default_route_speed', True, 'float'],
        ['service_windows', True, 'service_window_id', True, 'str'],
        ['service_windows', True, 'start_time', True, 'str'],
        ['service_windows', True, 'end_time', True, 'str'],
        ['service_windows', True, 'monday', True, 'int'],
        ['service_windows', True, 'tuesday', True, 'int'],
        ['service_windows', True, 'wednesday', True, 'int'],
        ['service_windows', True, 'thursday', True, 'int'],
        ['service_windows', True, 'friday', True, 'int'],
        ['service_windows', True, 'saturday', True, 'int'],
        ['service_windows', True, 'sunday', True, 'int'],
        ['shapes', True, 'shape_id', True, 'str'],
        ['shapes', True, 'geometry', True, 'LineString'],
        ['stops', False, 'stop_id', True, 'str'],
        ['stops', False, 'stop_code', False, 'str'],
        ['stops', False, 'stop_name', True, 'str'],
        ['stops', False, 'stop_desc', False, 'str'],
        ['stops', False, 'stop_lat', True, 'float'],
        ['stops', False, 'stop_lon', True, 'float'],
        ['stops', False, 'zone_id', False, 'str'],
        ['stops', False, 'stop_url', False, 'str'],
        ['stops', False, 'location_type', False, 'int'],
        ['stops', False, 'parent_station', False, 'str'],
        ['stops', False, 'stop_timezone', False, 'str'],
        ['stops', True, 'wheelchair_boarding', False, 'int'],
    ],
    columns=['table', 'table_required', 'column', 'column_required', 'dtype'],
    )

#:
PROTOFEED_ATTRS = [
    'frequencies',
    'meta',
    'service_windows',
    'shapes',
    'shapes_extra',
    'stops',
    ]

# Country name by country alpha-2 code
COUNTRY_BY_ALPHA2 = {
    country.alpha_2: country.name
    for country in pycountry.countries
    }

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
LHT_COUNTRIES = set([
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

# Traffic side by timezone
TRAFFIC_BY_TIMEZONE = {}
for timezone, country in COUNTRY_BY_TIMEZONE.items():
    if country in LHT_COUNTRIES:
        traffic = 'left'
    else:
        traffic = 'right'
    TRAFFIC_BY_TIMEZONE[timezone] = traffic
