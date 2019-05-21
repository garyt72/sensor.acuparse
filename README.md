# sensor.acuparse

_Custom component to get weather data from your [Acuparse](https://acuparse.com) server for [Home Assistant](https://www.home-assistant.io/)._

## Installation
1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `acuparse`.
4. Download _all_ the files from the `custom_components/acuparse/` directory (folder) in this repository.
5. Place the files you downloaded in the new `acuparse` directory (folder) you created.
6. Add a sensor `- platform: acuparse` to your HA configuration.

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/acuparse/__init__.py
custom_components/acuparse/sensor.py
custom_components/acuparse/manifest.json
```

## Configuration
key | type | description
:--- | :--- | :---
**platform (Required)** | string | `acuparse`
**hostname (Required)** | string | The hostname or ip address for the Acuparse server.
**monitored_conditions (Required)** | list | Defines sensors to monitor, see below.

### Current conditions
monitored_condition | description
:--- | :---
temp | Current temperature
temp_trend | Temperature trend
feels | Current feels like temperature
dewpt | Dew point
temp_high | Today's high temperature
temp_high_time | When today's high temperature occurred
temp_low | Today's low temperature
temp_low_time | When today's low temperature occurred
temp_avg | Today's average temperature
relh | Current relative humidity
relh_trend | Relative humidity trend
pressure_inhg | Current atmospheric pressure measured in inhg
pressure_kpa | Current atmospheric pressure measured in kpa
pressure_trend | Atmospheric pressure trend
wind_mph | Wind speed in mph
wind_kmh | Wind speed in kph
wind_dir | Wind direction indicated by cardinal direction (S, SW, WSW, etc)
wind_deg | Wind direction measured in degrees
wind_deg_peak | Today's peak wind speed direction measured in degrees
wind_dir_peak | Today's peak wind speed direction by cardinal direction  (S, SW, WSW, etc)
wind_peak_time | When today's peak wind happened
wind_mph_peak | Today's peak wind speed in mph
wind_kmh_peak | Today's peak wind speed in kph
rain_rate_in | Current rain rate measured in inches per hour
rain_rate_mm | Current rain rate measured in millimeters per hour
rain_total_in_today | Today's total rain fall measured in inches
rain_total_mm_today | Today's total rain fall measured in millimeters
moon_age | The age of the current moon, measured in days
moon_phase | The current phase of the moon
moon_next_new | When the next new moon will occur
moon_next_full | When the next full moon will occur
moon_last_new | When the last new moon occurred
moon_last_full | When the last full moon occurred
moon_distance | Moon's current disance from earth in kilometers
moon_illumination | Percent of moon that is illuminated.
**??**_temp_max | High temperature 
**??**_temp_min | Low temperature
**??**_temp_max_when | When the high temperature occurred
**??**_temp_min_when | When the low temperature occurred
**??**_wind_max_mph | Maximum wind speed in mph
**??**_wind_max_kmh | Maximum wind speed in kph
**??**_wind_max_dir | Maximum wind direction indicated by cardinal direction (S, SW, WSW, etc)
**??**_wind_max_when | When the maximum wind speed when was recorded
**??**_pressure_max_inhg | Maximum atmospheric pressure measured in inhg
**??**_pressure_min_inhg | Minimum atmospheric pressure measured in inhg
**??**_pressure_max_kpa | Maximum atmospheric pressure measured in kpa
**??**_pressure_min_kpa | Minimum atmospheric pressure measured in kpa
**??**_pressure_max_when | When the maximum atmospheric pressure was recorded
**??**_pressure_min_when | When the minimum atmospheric pressure was recorded
**??**_relh_max | Maximum relative humidity
**??**_relh_min | Minimum relative humidity
**??**_relh_max_when | When the maximum relative humidity was recorded
**??**_relh_min_when | When the minimum relative humidity was recorded
**??**_rain_rate_in_max | Maximum rate rate recorded measured in inches per hour
**??**_rain_rate_mm_max | Maximum rate rate recorded measured in millimeters per hour
**??**_rain_rate_max_when | when the maximum rate rate was recorded
**??**_rain_in_total | Total rain recorded measured in inches
**??**_rain_mm_total | Total rain recorded measured in millimeters
at_rain_total_since | When Acuparse first started recording rain fall for the at_rain_??_total sensors.

### Note
Monitored conditions above starting with ?? are available for multiple historical time periods, as specified by the prefix ?? in the definitions.  Replace the ?? with one of the following values to include the specified data for that time period:

prefix | description
:--- | :---
y  | yesterday's historical values   Note: the three \_when are not available for yesterday
tw | this week's historical values
lw | last week's historical values
tm | this month's historical values
lm | last month's historical values
ty | this year's historical values
at | all time historical values


## Example
**Configuration:**

#### configuration.yaml:
```yaml
sensor:
  - platform: acuparse
    api_key: YOUR_API_KEY
    monitored_conditions:
      - temp
      - feels
      - relh
      - wind_mph
```

#### Card defintion to display the above entities:
```yaml
cards:
  type: entities
  title: Weather overview
  show_header_toggle: false
  entities:
    - entity: sensor.apwx_temp
    - entity: sensor.apwx_feels
    - entity: sensor.apwx_relh
    - entity: sensor.apwx_wind_mph
```



## Changelog


# Note: 
While the platform is called “acuparse” the sensors will show up in Home Assistant as “apwx” (eg: sensor.apwx_temp).
