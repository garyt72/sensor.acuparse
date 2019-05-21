---
layout: page
title: "Acuparse"
description: "Instructions on how to integrate Acuparse Weather within Home Assistant."
date: 2019-05-21
sidebar: true
comments: false
sharing: true
footer: true
logo: false
ha_category:
  - Weather
ha_release: 0.93
ha_iot_class: Cloud Polling
redirect_from:
 - /components/sensor.acuparse/
---

The `Acuparse` platform allows you to use [Acuparse](https://www.acuparse.com/) as a source for current weather information.

<p class='note'>
This will require access to an Acuparse instance in order 

Please consider this when using the following information.
</p>

{% linkable_title Configuration %}

To add Acuparse to your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sensor:
- platform: acuparse
  hostname: YOUR_ACUPARSE_SERVER_HOSTNAME
  monitored_conditions:
   - temp
   - feels
   - relh
```

{% configuration %}
hostname:
  description: The hostname for the acuparse instance.
  required: true
  type: string
monitored_conditions:
  description: Conditions to display in the frontend. The following conditions can be monitored.
  required: true
  type: list
  default: symbol
  keys:
    temp:
      description: Current temperature
    temp_trend:
      description: Temperature trend
    feels:
      description: Current feels like temperature
    dewpt:
      description: Dew point
    temp_high:
      description: Today's high temperature
    temp_high_time:
      description: When today's high temperature occurred
    temp_low
      description: Today's low temperature
    temp_low_time
      description: When today's low temperature occurred
    temp_avg
      description: Today's average temperature
    relh
      description: Current relative humidity
    relh_trend
      description: Relative humidity trend
    pressure_inhg
      description: Current atmospheric pressure measured in inhg
    pressure_kpa
      description: Current atmospheric pressure measured in kpa
    pressure_trend
      description: Atmospheric pressure trend
    wind_mph
      description: Wind speed in mph
    wind_kmh
      description: Wind speed in kph
    wind_dir
      description: Wind direction indicated by cardinal direction (S, SW, WSW, etc)
    wind_deg
      description: Wind direction measured in degrees
    wind_deg_peak
      description: Today's peak wind speed direction measured in degrees
    wind_dir_peak
      description: Today's peak wind speed direction by cardinal direction  (S, SW, WSW, etc)
    wind_peak_time
      description: When today's peak wind happened
    wind_mph_peak
      description: Today's peak wind speed in mph
    wind_kmh_peak
      description: Today's peak wind speed in kph
    rain_rate_in
      description: Current rain rate measured in inches per hour 
    rain_rate_mm
      description: Current rain rate measured in millimeters per hour
    rain_total_in_today
      description: Today's total rain fall measured in inches
    rain_total_mm_today
      description: Today's total rain fall measured in millimeters
    moon_age
      description: The age of the current moon, measured in days
    moon_phase
      description: The current phase of the moon
    moon_next_new
      description: When the next new moon will occur
    moon_next_full
      description: When the next full moon will occur
    moon_last_new
      description: When the last new moon occurred
    moon_last_full
      description: When the last full moon occurred
    moon_distance
      description: Moon's current disance from earth in kilometers
    moon_illumination
      description: Percent of moon that is illuminated.
    ??_temp_max
      description: High temperature
    ??_temp_min
      description: Low temperature
    ??_temp_max_when
      description: When the high temperature occurred
    ??_temp_min_when
      description: When the low temperature occurred
    ??_wind_max_mph
      description: Maximum wind speed in mph
    ??_wind_max_kmh
      description: Maximum wind speed in kph
    ??_wind_max_dir
      description: Maximum wind direction indicated by cardinal direction (S, SW, WSW, etc)
    ??_wind_max_when
      description: When the maximum wind speed when was recorded
    ??_pressure_max_inhg
      description: Maximum atmospheric pressure measured in inhg
    ??_pressure_min_inhg
      description: Minimum atmospheric pressure measured in inhg
    ??_pressure_max_kpa
      description: Maximum atmospheric pressure measured in kpa
    ??_pressure_min_kpa
      description: Minimum atmospheric pressure measured in kpa
    ??_pressure_max_when
      description: When the maximum atmospheric pressure was recorded
    ??_pressure_min_when
      description: When the minimum atmospheric pressure was recorded
    ??_relh_max
      description: Maximum relative humidity
    ??_relh_min
      description: Minimum relative humidity
    ??_relh_max_when
      description: When the maximum relative humidity was recorded
    ??_relh_min_when
      description: When the minimum relative humidity was recorded
    ??_rain_rate_in_max
      description: Maximum rate rate recorded measured in inches per hour
    ??_rain_rate_mm_max
      description: Maximum rate rate recorded measured in millimeters per hour
    ??_rain_rate_max_when
      description: when the maximum rate rate was recorded 
    ??_rain_in_total
      description: Total rain recorded measured in inches 
    ??_rain_mm_total
      description: Total rain recorded measured in millimeters 
    at_rain_total_since
      description: When Acuparse first started recording rain fall for the at_rain_??_total sensors.
    {% endconfiguration %}

All the conditions listed above will be updated every 5 minutes.

### {% linkable_title Historical data %}

Monitored conditions above starting with ?? are available for multiple historical time periods, as specified by the prefix ?? in the definitions.  Replace the ?? with one of the following values to include the specified data for that time period:
      y  = yesterday's historical values   Note: the three _when are not available for yesterday
      tw = this week's historical values
      lw = last week's historical values
      tm = this month's historical values
      lm = last month's historical values
      ty = this year's historical values
      at = all time historical values
        

### {% linkable_title Weather overview %}

configuration.yaml:
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

Card defintion to display the above entities:
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

<p class='note warning'>
Note: While the platform is called “acuparse” the sensors will show up in Home Assistant as “apwx” (eg: sensor.apwx_temp).
</p>
