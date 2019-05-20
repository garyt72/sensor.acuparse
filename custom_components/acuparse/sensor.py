"""
Support for Acuparse weather service.

beta version based on wunderground component from Home Assistant.
"""
import asyncio
from datetime import timedelta
import logging
import re

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.components import sensor
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_MONITORED_CONDITIONS, TEMP_FAHRENHEIT, TEMP_CELSIUS, LENGTH_INCHES, ATTR_ATTRIBUTION)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_RESOURCE = 'http://{}/data?json'
_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by Acuparse"
CONF_HOSTNAME = 'hostname'
CONF_DEBUG = 'debug'
CONF_REFRESH_SECONDS = 'refresh_seconds'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

# Helper classes for declaring sensor configurations

class SensorConfig:
	"""Acuparse Sensor Configuration.

	defines basic HA properties of the weather sensor and
	stores callbacks that can parse sensor values out of
	the json data received from Acuparse.
	"""

	def __init__(self, section, friendly_name, feature, value,
				 unit_of_measurement=None, entity_picture=None,
				 icon="mdi:gauge", device_state_attributes=None):
		"""Constructor.

		Args:
			friendly_name (string|func): Friendly name
			feature (string): Acuparse item
			value callback that extracts desired value from AcuparseData object
			unit_of_measurement (string): unit of measurement
			entity_picture (string): value or callback returning URL of entity picture
			icon (string): icon name or URL
			device_state_attributes (dict): dictionary of attributes,
				or callable that returns it
		"""
		if section == 'yesterday':
			friendly_name = friendly_name + " Yesterday"
		elif section == 'this_week':
			friendly_name = friendly_name + " This Week"
		elif section == 'this_month':
			friendly_name = friendly_name + " This Month"
		elif section == 'last_month':
			friendly_name = friendly_name + " Last Month"
		elif section == 'this_year':
			friendly_name = friendly_name + " This Year"
		elif section == 'all_time':
			friendly_name = friendly_name + " All Time"
		
		self.friendly_name = friendly_name
		self.unit_of_measurement = unit_of_measurement
		self.feature = feature
		self.value = value
		self.icon = icon
		self.device_state_attributes = device_state_attributes or {}
		self.entity_picture = entity_picture


class AcuparseConditionsSensorConfig(SensorConfig):
	"""Helper for defining sensor configurations for current conditions."""

	def __init__(self, section, friendly_name, field, icon="mdi:gauge", unit_of_measurement=None):
		"""Constructor.

		Args:
			friendly_name (string|func): Friendly name of sensor
			field (string): Field name in the "current_observation" dictionary.
			icon (string): icon name or URL, if None sensor will use current weather symbol
			unit_of_measurement (string): unit of measurement
		"""
		
		super().__init__(
			section,
			friendly_name,
			"conditions",
			value=lambda wu: wu.data[section][field],
			icon=icon,
			unit_of_measurement=unit_of_measurement,
			entity_picture=lambda wu: wu.data[section]['icon_url'] if icon is None else None,
			device_state_attributes={'date': lambda wu: wu.data[section]['timestamp'] }
		)


# Declaration of supported Acuparse sensors
# Declaration of supported Acuparse sensors
# (see above helper classes for argument explanation)

SENSOR_TYPES = {
	'temp':                AcuparseConditionsSensorConfig('current', 'Temp',                  'tempF',              'mdi:thermometer',   TEMP_FAHRENHEIT),
	'temp_trend':          AcuparseConditionsSensorConfig('current', 'Temp',                  'tempF_trend',        'mdi:thermometer',   'trend'),
	'feels':               AcuparseConditionsSensorConfig('current', 'Temp Feels Like',       'feelsF',             'mdi:thermometer',   TEMP_FAHRENHEIT),
	'dewpt':               AcuparseConditionsSensorConfig('current', 'Dewpoint',              'dewptF',             'mdi:water',         TEMP_FAHRENHEIT),
	'temp_high':           AcuparseConditionsSensorConfig('current', 'Temp High ',            'tempF_high',         'mdi:thermometer',   TEMP_FAHRENHEIT),
	'temp_high_time':      AcuparseConditionsSensorConfig('current', 'Temp High Time',        'high_temp_recorded', 'mdi:thermometer',   'time'),
	'temp_low':            AcuparseConditionsSensorConfig('current', 'Temp Low',              'tempF_low',          'mdi:thermometer',   TEMP_FAHRENHEIT),
	'temp_low_time':       AcuparseConditionsSensorConfig('current', 'Temp Low Time',         'low_temp_recorded',  'mdi:thermometer',   'time'),
	'temp_avg':            AcuparseConditionsSensorConfig('current', 'Temp Average',          'tempF_avg',          'mdi:thermometer',   TEMP_FAHRENHEIT),
	'relh':                AcuparseConditionsSensorConfig('current', 'Relative Humidity',     'relH',               'mdi:water',         '%'),
	'relh_trend':          AcuparseConditionsSensorConfig('current', 'Relative Humidity',     'relH_trend',         'mdi:water',         'trend'),
	'pressure_inhg':       AcuparseConditionsSensorConfig('current', 'Pressure',              'pressure_inHg',      'mdi:gauge',         'inHg'),
	'pressure_kpa':        AcuparseConditionsSensorConfig('current', 'Pressure',              'pressure_kPa',       'mdi:gauge',         'kPa'),
	'pressure_trend':      AcuparseConditionsSensorConfig('current', 'Pressure',              'inHg_trend',         'mdi:gauge',         'trend'),
	'wind_mph':            AcuparseConditionsSensorConfig('current', 'Wind',                  'windSmph',           'mdi:weather-windy', 'mph'),
	'wind_kmh':            AcuparseConditionsSensorConfig('current', 'Wind',                  'windSkmh',           'mdi:weather-windy', 'kph'),
	'wind_dir':            AcuparseConditionsSensorConfig('current', 'Wind',                  'windDIR',            'mdi:weather-windy', 'direction'),
	'wind_deg':            AcuparseConditionsSensorConfig('current', 'Wind',                  'windDEG',            'mdi:weather-windy', 'degrees'),
	'wind_deg_avg2':       AcuparseConditionsSensorConfig('current', 'Wind Avg 2',            'windDEG_avg2',       'mdi:weather-windy', 'degrees'),
	'wind_dir_avg2':       AcuparseConditionsSensorConfig('current', 'Wind Avg 2',            'windDIR_avg2',       'mdi:weather-windy', 'direction'),
	'wind_mph_avg2':       AcuparseConditionsSensorConfig('current', 'Wind Avg 2',            'windSmph_avg2',      'mdi:weather-windy', 'mph'),
	'wind_kmh_avg2':       AcuparseConditionsSensorConfig('current', 'Wind Avg 2',            'windSkmh_avg2',      'mdi:weather-windy', 'kph'),
	'wind_deg_avg10':      AcuparseConditionsSensorConfig('current', 'Wind Avg 10',           'windDEG_avg10',      'mdi:weather-windy', 'degrees'),
	'wind_mph_avg10':      AcuparseConditionsSensorConfig('current', 'Wind Avg 10',           'windSmph_avg10',     'mdi:weather-windy', 'mph'),
	'wind_kmh_avg10':      AcuparseConditionsSensorConfig('current', 'Wind Avg 10',           'windSkmh_avg10',     'mdi:weather-windy', 'kph'),
	'wind_deg_peak':       AcuparseConditionsSensorConfig('current', 'Wind Max',              'windDEG_peak',       'mdi:weather-windy', 'degrees'),
	'wind_dir_peak':       AcuparseConditionsSensorConfig('current', 'Wind Max',              'windDIR_peak',       'mdi:weather-windy', 'direction'),
	'wind_peak_time':      AcuparseConditionsSensorConfig('current', 'Wind Max',              'wind_recorded_peak', 'mdi:weather-windy', 'time'),
	'wind_mph_peak':       AcuparseConditionsSensorConfig('current', 'Wind Max',              'windSmph_peak',      'mdi:weather-windy', 'mph'),
	'wind_kmh_peak':       AcuparseConditionsSensorConfig('current', 'Wind Max',              'windSkmh_peak',      'mdi:weather-windy', 'kph'),
	'wind_mph_max5':       AcuparseConditionsSensorConfig('current', 'Wind Max 5',            'windSmph_max5',      'mdi:weather-windy', 'mph'),
	'wind_kmh_max5':       AcuparseConditionsSensorConfig('current', 'Wind Max 5',            'windSkmh_max5',      'mdi:weather-windy', 'kph'),
	'rain_rate_in':        AcuparseConditionsSensorConfig('current', 'Rain Rate',             'rainIN',             'mdi:umbrella',      'in/hr'),
	'rain_rate_mm':        AcuparseConditionsSensorConfig('current', 'Rain Rate',             'rainMM',             'mdi:umbrella',      'mm/hr'),
	'rain_total_in_today': AcuparseConditionsSensorConfig('current', 'Rain Total',            'rainTotalIN_today',  'mdi:umbrella',      LENGTH_INCHES),
	'rain_total_mm_today': AcuparseConditionsSensorConfig('current', 'Rain Total',            'rainTotalMM_today',  'mdi:umbrella',      'mm'),
	
	'y_temp_max':          AcuparseConditionsSensorConfig('yesterday', 'Temp High',          'tempF_high',                  'mdi:thermometer',   TEMP_FAHRENHEIT),
	'y_temp_min':          AcuparseConditionsSensorConfig('yesterday', 'Temp Low',           'tempF_low',                   'mdi:thermometer',   TEMP_FAHRENHEIT),
	'y_temp_max_when':     AcuparseConditionsSensorConfig('yesterday', 'Temp High',          'tempF_high_recorded',         'mdi:thermometer',   'time'),
	'y_temp_min_when':     AcuparseConditionsSensorConfig('yesterday', 'Temp Low',           'tempF_low_recorded',          'mdi:thermometer',   'time'),
	'y_wind_max_mph':      AcuparseConditionsSensorConfig('yesterday', 'Wind Max',           'windS_mph_high',              'mdi:weather-windy', 'mph'),
	'y_wind_max_kmh':      AcuparseConditionsSensorConfig('yesterday', 'Wind Max',           'windS_kmh_high',              'mdi:weather-windy', 'kph'),
	'y_wind_max_dir':      AcuparseConditionsSensorConfig('yesterday', 'Wind Max',           'windDIR',                     'mdi:weather-windy', 'direction'),
	'y_wind_max_when':     AcuparseConditionsSensorConfig('yesterday', 'Wind Max',           'windS_mph_high_recorded',     'mdi:weather-windy', 'time'),
	'y_pressure_max_inhg': AcuparseConditionsSensorConfig('yesterday', 'Pressure High',      'pressure_inHg_high',          'mdi:gauge',         'inHg'),
	'y_pressure_min_inhg': AcuparseConditionsSensorConfig('yesterday', 'Pressure Low',       'pressure_inHg_low',           'mdi:gauge',         'inHg'),
	'y_pressure_max_kpa':  AcuparseConditionsSensorConfig('yesterday', 'Pressure High',      'pressure_kPa_high',           'mdi:gauge',         'kPa'),
	'y_pressure_min_kpa':  AcuparseConditionsSensorConfig('yesterday', 'Pressure Low',       'pressure_kPa_low',            'mdi:gauge',         'kPa'),
	'y_pressure_max_when': AcuparseConditionsSensorConfig('yesterday', 'Pressure High',      'pressure_inHg_high_recorded', 'mdi:gauge',         'time'),
	'y_pressure_min_when': AcuparseConditionsSensorConfig('yesterday', 'Pressure Low',       'pressure_inHg_low_recorded',  'mdi:gauge',         'time'),
	'y_relh_max':          AcuparseConditionsSensorConfig('yesterday', 'Humidity High',      'relH_high',                   'mdi:water',         '%'),
	'y_relh_min':          AcuparseConditionsSensorConfig('yesterday', 'Humidity Low',       'relH_low',                    'mdi:water',         '%'),
	'y_relh_max_when':     AcuparseConditionsSensorConfig('yesterday', 'Humidity High',      'relH_high_recorded',          'mdi:water',         'time'),
	'y_relh_min_when':     AcuparseConditionsSensorConfig('yesterday', 'Humidity Low',       'relH_low_recorded',           'mdi:water',         'time'),
	'y_rain_in_total':     AcuparseConditionsSensorConfig('yesterday', 'Rain Total',         'rainfall_IN_total',           'mdi:umbrella',      LENGTH_INCHES),
	'y_rain_mm_total':     AcuparseConditionsSensorConfig('yesterday', 'Rain Total',         'rainfall_MM_total',           'mdi:umbrella',      'mm'),

	'tw_temp_max':           AcuparseConditionsSensorConfig('this_week', 'Temp High',          'tempF_high',                  'mdi:thermometer',   TEMP_FAHRENHEIT),
	'tw_temp_min':           AcuparseConditionsSensorConfig('this_week', 'Temp Low',           'tempF_low',                   'mdi:thermometer',   TEMP_FAHRENHEIT),
	'tw_temp_max_when':      AcuparseConditionsSensorConfig('this_week', 'Temp High',          'tempF_high_recorded',         'mdi:thermometer',   'time'),
	'tw_temp_min_when':      AcuparseConditionsSensorConfig('this_week', 'Temp Low',           'tempF_low_recorded',          'mdi:thermometer',   'time'),
	'tw_wind_max_mph':       AcuparseConditionsSensorConfig('this_week', 'Wind Max',           'windS_mph_high',              'mdi:weather-windy', 'mph'),
	'tw_wind_max_kmh':       AcuparseConditionsSensorConfig('this_week', 'Wind Max',           'windS_kmh_high',              'mdi:weather-windy', 'kph'),
	'tw_wind_max_dir':       AcuparseConditionsSensorConfig('this_week', 'Wind Max',           'windDIR',                     'mdi:weather-windy', 'direction'),
	'tw_wind_max_when':      AcuparseConditionsSensorConfig('this_week', 'Wind Max',           'windS_mph_high_recorded',     'mdi:weather-windy', 'time'),
	'tw_pressure_max_inhg':  AcuparseConditionsSensorConfig('this_week', 'Pressure High',      'pressure_inHg_high',          'mdi:gauge',         'inHg'),
	'tw_pressure_min_inhg':  AcuparseConditionsSensorConfig('this_week', 'Pressure Low',       'pressure_inHg_low',           'mdi:gauge',         'inHg'),
	'tw_pressure_max_kpa':   AcuparseConditionsSensorConfig('this_week', 'Pressure High',      'pressure_kPa_high',           'mdi:gauge',         'kPa'),
	'tw_pressure_min_kpa':   AcuparseConditionsSensorConfig('this_week', 'Pressure Low',       'pressure_kPa_low',            'mdi:gauge',         'kPa'),
	'tw_pressure_max_when':  AcuparseConditionsSensorConfig('this_week', 'Pressure High',      'pressure_inHg_high_recorded', 'mdi:gauge',         'time'),
	'tw_pressure_min_when':  AcuparseConditionsSensorConfig('this_week', 'Pressure Low',       'pressure_inHg_low_recorded',  'mdi:gauge',         'time'),
	'tw_relh_max':           AcuparseConditionsSensorConfig('this_week', 'Humidity High',      'relH_high',                   'mdi:water',         '%'),
	'tw_relh_min':           AcuparseConditionsSensorConfig('this_week', 'Humidity Low',       'relH_low',                    'mdi:water',         '%'),
	'tw_relh_max_when':      AcuparseConditionsSensorConfig('this_week', 'Humidity High',      'relH_high_recorded',          'mdi:water',         'time'),
	'tw_relh_min_when':      AcuparseConditionsSensorConfig('this_week', 'Humidity Low',       'relH_low_recorded',           'mdi:water',         'time'),
	'tw_rain_rate_in_max':   AcuparseConditionsSensorConfig('this_week', 'Rain Rate Max',      'rainfall_IN_most',            'mdi:umbrella',      'in/hr'),
	'tw_rain_rate_mm_max':   AcuparseConditionsSensorConfig('this_week', 'Rain Rate Max',      'rainfall_MM_most',            'mdi:umbrella',      'mm/hr'),
	'tw_rain_rate_max_when': AcuparseConditionsSensorConfig('this_week', 'Rain Rate Max',      'rainfall_IN_most_recorded',   'mdi:umbrella',      'time'),
	'tw_rain_in_total':      AcuparseConditionsSensorConfig('this_week', 'Rain Total',         'rainfall_IN_total',           'mdi:umbrella',      LENGTH_INCHES),
	'tw_rain_mm_total':      AcuparseConditionsSensorConfig('this_week', 'Rain Total',         'rainfall_MM_total',           'mdi:umbrella',      'mm'),

	'tm_temp_max':           AcuparseConditionsSensorConfig('this_month', 'Temp High',          'tempF_high',                  'mdi:thermometer',   TEMP_FAHRENHEIT),
	'tm_temp_min':           AcuparseConditionsSensorConfig('this_month', 'Temp Low',           'tempF_low',                   'mdi:thermometer',   TEMP_FAHRENHEIT),
	'tm_temp_max_when':      AcuparseConditionsSensorConfig('this_month', 'Temp High',          'tempF_high_recorded',         'mdi:thermometer',   'time'),
	'tm_temp_min_when':      AcuparseConditionsSensorConfig('this_month', 'Temp Low',           'tempF_low_recorded',          'mdi:thermometer',   'time'),
	'tm_wind_max_mph':       AcuparseConditionsSensorConfig('this_month', 'Wind Max',           'windS_mph_high',              'mdi:weather-windy', 'mph'),
	'tm_wind_max_kmh':       AcuparseConditionsSensorConfig('this_month', 'Wind Max',           'windS_kmh_high',              'mdi:weather-windy', 'kph'),
	'tm_wind_max_dir':       AcuparseConditionsSensorConfig('this_month', 'Wind Max',           'windDIR',                     'mdi:weather-windy', 'direction'),
	'tm_wind_max_when':      AcuparseConditionsSensorConfig('this_month', 'Wind Max',           'windS_mph_high_recorded',     'mdi:weather-windy', 'time'),
	'tm_pressure_max_inhg':  AcuparseConditionsSensorConfig('this_month', 'Pressure High',      'pressure_inHg_high',          'mdi:gauge',         'inHg'),
	'tm_pressure_min_inhg':  AcuparseConditionsSensorConfig('this_month', 'Pressure Low',       'pressure_inHg_low',           'mdi:gauge',         'inHg'),
	'tm_pressure_max_kpa':   AcuparseConditionsSensorConfig('this_month', 'Pressure High',      'pressure_kPa_high',           'mdi:gauge',         'kPa'),
	'tm_pressure_min_kpa':   AcuparseConditionsSensorConfig('this_month', 'Pressure Low',       'pressure_kPa_low',            'mdi:gauge',         'kPa'),
	'tm_pressure_max_when':  AcuparseConditionsSensorConfig('this_month', 'Pressure High',      'pressure_inHg_high_recorded', 'mdi:gauge',         'time'),
	'tm_pressure_min_when':  AcuparseConditionsSensorConfig('this_month', 'Pressure Low',       'pressure_inHg_low_recorded',  'mdi:gauge',         'time'),
	'tm_relh_max':           AcuparseConditionsSensorConfig('this_month', 'Humidity High',      'relH_high',                   'mdi:water',         '%'),
	'tm_relh_min':           AcuparseConditionsSensorConfig('this_month', 'Humidity Low',       'relH_low',                    'mdi:water',         '%'),
	'tm_relh_max_when':      AcuparseConditionsSensorConfig('this_month', 'Humidity High',      'relH_high_recorded',          'mdi:water',         'time'),
	'tm_relh_min_when':      AcuparseConditionsSensorConfig('this_month', 'Humidity Low',       'relH_low_recorded',           'mdi:water',         'time'),
	'tm_rain_rate_in_max':   AcuparseConditionsSensorConfig('this_month', 'Rain Rate Max',      'rainfall_IN_most',            'mdi:umbrella',      'in/hr'),
	'tm_rain_rate_mm_max':   AcuparseConditionsSensorConfig('this_month', 'Rain Rate Max',      'rainfall_MM_most',            'mdi:umbrella',      'mm/hr'),
	'tm_rain_rate_max_when': AcuparseConditionsSensorConfig('this_month', 'Rain Rate Max',      'rainfall_IN_most_recorded',   'mdi:umbrella',      'time'),
	'tm_rain_in_total':      AcuparseConditionsSensorConfig('this_month', 'Rain Total',         'rainfall_IN_total',           'mdi:umbrella',      LENGTH_INCHES),
	'tm_rain_mm_total':      AcuparseConditionsSensorConfig('this_month', 'Rain Total',         'rainfall_MM_total',           'mdi:umbrella',      'mm'),

	'lm_temp_max':           AcuparseConditionsSensorConfig('last_month', 'Temp High',          'tempF_high',                  'mdi:thermometer',   TEMP_FAHRENHEIT),
	'lm_temp_min':           AcuparseConditionsSensorConfig('last_month', 'Temp Low',           'tempF_low',                   'mdi:thermometer',   TEMP_FAHRENHEIT),
	'lm_temp_max_when':      AcuparseConditionsSensorConfig('last_month', 'Temp High',          'tempF_high_recorded',         'mdi:thermometer',   'time'),
	'lm_temp_min_when':      AcuparseConditionsSensorConfig('last_month', 'Temp Low',           'tempF_low_recorded',          'mdi:thermometer',   'time'),
	'lm_wind_max_mph':       AcuparseConditionsSensorConfig('last_month', 'Wind Max',           'windS_mph_high',              'mdi:weather-windy', 'mph'),
	'lm_wind_max_kmh':       AcuparseConditionsSensorConfig('last_month', 'Wind Max',           'windS_kmh_high',              'mdi:weather-windy', 'kph'),
	'lm_wind_max_dir':       AcuparseConditionsSensorConfig('last_month', 'Wind Max',           'windDIR',                     'mdi:weather-windy', 'direction'),
	'lm_wind_max_when':      AcuparseConditionsSensorConfig('last_month', 'Wind Max',           'windS_mph_high_recorded',     'mdi:weather-windy', 'time'),
	'lm_pressure_max_inhg':  AcuparseConditionsSensorConfig('last_month', 'Pressure High',      'pressure_inHg_high',          'mdi:gauge',         'inHg'),
	'lm_pressure_min_inhg':  AcuparseConditionsSensorConfig('last_month', 'Pressure Low',       'pressure_inHg_low',           'mdi:gauge',         'inHg'),
	'lm_pressure_max_kpa':   AcuparseConditionsSensorConfig('last_month', 'Pressure High',      'pressure_kPa_high',           'mdi:gauge',         'kPa'),
	'lm_pressure_min_kpa':   AcuparseConditionsSensorConfig('last_month', 'Pressure Low',       'pressure_kPa_low',            'mdi:gauge',         'kPa'),
	'lm_pressure_max_when':  AcuparseConditionsSensorConfig('last_month', 'Pressure High',      'pressure_inHg_high_recorded', 'mdi:gauge',         'time'),
	'lm_pressure_min_when':  AcuparseConditionsSensorConfig('last_month', 'Pressure Low',       'pressure_inHg_low_recorded',  'mdi:gauge',         'time'),
	'lm_relh_max':           AcuparseConditionsSensorConfig('last_month', 'Humidity High',      'relH_high',                   'mdi:water',         '%'),
	'lm_relh_min':           AcuparseConditionsSensorConfig('last_month', 'Humidity Low',       'relH_low',                    'mdi:water',         '%'),
	'lm_relh_max_when':      AcuparseConditionsSensorConfig('last_month', 'Humidity High',      'relH_high_recorded',          'mdi:water',         'time'),
	'lm_relh_min_when':      AcuparseConditionsSensorConfig('last_month', 'Humidity Low',       'relH_low_recorded',           'mdi:water',         'time'),
	'lm_rain_rate_in_max':   AcuparseConditionsSensorConfig('last_month', 'Rain Rate Max',      'rainfall_IN_most',            'mdi:umbrella',      'in/hr'),
	'lm_rain_rate_mm_max':   AcuparseConditionsSensorConfig('last_month', 'Rain Rate Max',      'rainfall_MM_most',            'mdi:umbrella',      'mm/hr'),
	'lm_rain_rate_max_when': AcuparseConditionsSensorConfig('last_month', 'Rain Rate Max',      'rainfall_IN_most_recorded',   'mdi:umbrella',      'time'),
	'lm_rain_in_total':      AcuparseConditionsSensorConfig('last_month', 'Rain Total',         'rainfall_IN_total',           'mdi:umbrella',      LENGTH_INCHES),
	'lm_rain_mm_total':      AcuparseConditionsSensorConfig('last_month', 'Rain Total',         'rainfall_MM_total',           'mdi:umbrella',      'mm'),

	'ty_temp_max':           AcuparseConditionsSensorConfig('this_year', 'Temp High',          'tempF_high',                  'mdi:thermometer',   TEMP_FAHRENHEIT),
	'ty_temp_min':           AcuparseConditionsSensorConfig('this_year', 'Temp Low',           'tempF_low',                   'mdi:thermometer',   TEMP_FAHRENHEIT),
	'ty_temp_max_when':      AcuparseConditionsSensorConfig('this_year', 'Temp High',          'tempF_high_recorded',         'mdi:thermometer',   'time'),
	'ty_temp_min_when':      AcuparseConditionsSensorConfig('this_year', 'Temp Low',           'tempF_low_recorded',          'mdi:thermometer',   'time'),
	'ty_wind_max_mph':       AcuparseConditionsSensorConfig('this_year', 'Wind Max',           'windS_mph_high',              'mdi:weather-windy', 'mph'),
	'ty_wind_max_kmh':       AcuparseConditionsSensorConfig('this_year', 'Wind Max',           'windS_kmh_high',              'mdi:weather-windy', 'kph'),
	'ty_wind_max_dir':       AcuparseConditionsSensorConfig('this_year', 'Wind Max',           'windDIR',                     'mdi:weather-windy', 'direction'),
	'ty_wind_max_when':      AcuparseConditionsSensorConfig('this_year', 'Wind Max',           'windS_mph_high_recorded',     'mdi:weather-windy', 'time'),
	'ty_pressure_max_inhg':  AcuparseConditionsSensorConfig('this_year', 'Pressure High',      'pressure_inHg_high',          'mdi:gauge',         'inHg'),
	'ty_pressure_min_inhg':  AcuparseConditionsSensorConfig('this_year', 'Pressure Low',       'pressure_inHg_low',           'mdi:gauge',         'inHg'),
	'ty_pressure_max_kpa':   AcuparseConditionsSensorConfig('this_year', 'Pressure High',      'pressure_kPa_high',           'mdi:gauge',         'kPa'),
	'ty_pressure_min_kpa':   AcuparseConditionsSensorConfig('this_year', 'Pressure Low',       'pressure_kPa_low',            'mdi:gauge',         'kPa'),
	'ty_pressure_max_when':  AcuparseConditionsSensorConfig('this_year', 'Pressure High',      'pressure_inHg_high_recorded', 'mdi:gauge',         'time'),
	'ty_pressure_min_when':  AcuparseConditionsSensorConfig('this_year', 'Pressure Low',       'pressure_inHg_low_recorded',  'mdi:gauge',         'time'),
	'ty_relh_max':           AcuparseConditionsSensorConfig('this_year', 'Humidity High',      'relH_high',                   'mdi:water',         '%'),
	'ty_relh_min':           AcuparseConditionsSensorConfig('this_year', 'Humidity Low',       'relH_low',                    'mdi:water',         '%'),
	'ty_relh_max_when':      AcuparseConditionsSensorConfig('this_year', 'Humidity High',      'relH_high_recorded',          'mdi:water',         'time'),
	'ty_relh_min_when':      AcuparseConditionsSensorConfig('this_year', 'Humidity Low',       'relH_low_recorded',           'mdi:water',         'time'),
	'ty_rain_rate_in_max':   AcuparseConditionsSensorConfig('this_year', 'Rain Rate Max',      'rainfall_IN_most',            'mdi:umbrella',      'in/hr'),
	'ty_rain_rate_mm_max':   AcuparseConditionsSensorConfig('this_year', 'Rain Rate Max',      'rainfall_MM_most',            'mdi:umbrella',      'mm/hr'),
	'ty_rain_rate_max_when': AcuparseConditionsSensorConfig('this_year', 'Rain Rate Max',      'rainfall_IN_most_recorded',   'mdi:umbrella',      'time'),
	'ty_rain_in_total':      AcuparseConditionsSensorConfig('this_year', 'Rain Total',         'rainfall_IN_total',           'mdi:umbrella',      LENGTH_INCHES),
	'ty_rain_mm_total':      AcuparseConditionsSensorConfig('this_year', 'Rain Total',         'rainfall_MM_total',           'mdi:umbrella',      'mm'),

	'at_temp_max':           AcuparseConditionsSensorConfig('all_time', 'Temp High',          'tempF_high',                  'mdi:thermometer',   TEMP_FAHRENHEIT),
	'at_temp_min':           AcuparseConditionsSensorConfig('all_time', 'Temp Low',           'tempF_low',                   'mdi:thermometer',   TEMP_FAHRENHEIT),
	'at_temp_max_when':      AcuparseConditionsSensorConfig('all_time', 'Temp High',          'tempF_high_recorded',         'mdi:thermometer',   'time'),
	'at_temp_min_when':      AcuparseConditionsSensorConfig('all_time', 'Temp Low',           'tempF_low_recorded',          'mdi:thermometer',   'time'),
	'at_wind_max_mph':       AcuparseConditionsSensorConfig('all_time', 'Wind Max',           'windS_mph_high',              'mdi:weather-windy', 'mph'),
	'at_wind_max_kmh':       AcuparseConditionsSensorConfig('all_time', 'Wind Max',           'windS_kmh_high',              'mdi:weather-windy', 'kph'),
	'at_wind_max_dir':       AcuparseConditionsSensorConfig('all_time', 'Wind Max',           'windDIR',                     'mdi:weather-windy', 'direction'),
	'at_wind_max_when':      AcuparseConditionsSensorConfig('all_time', 'Wind Max',           'windS_mph_high_recorded',     'mdi:weather-windy', 'time'),
	'at_pressure_max_inhg':  AcuparseConditionsSensorConfig('all_time', 'Pressure High',      'pressure_inHg_high',          'mdi:gauge',         'inHg'),
	'at_pressure_min_inhg':  AcuparseConditionsSensorConfig('all_time', 'Pressure Low',       'pressure_inHg_low',           'mdi:gauge',         'inHg'),
	'at_pressure_max_kpa':   AcuparseConditionsSensorConfig('all_time', 'Pressure High',      'pressure_kPa_high',           'mdi:gauge',         'kPa'),
	'at_pressure_min_kpa':   AcuparseConditionsSensorConfig('all_time', 'Pressure Low',       'pressure_kPa_low',            'mdi:gauge',         'kPa'),
	'at_pressure_max_when':  AcuparseConditionsSensorConfig('all_time', 'Pressure High',      'pressure_inHg_high_recorded', 'mdi:gauge',         'time'),
	'at_pressure_min_when':  AcuparseConditionsSensorConfig('all_time', 'Pressure Low',       'pressure_inHg_low_recorded',  'mdi:gauge',         'time'),
	'at_relh_max':           AcuparseConditionsSensorConfig('all_time', 'Humidity High',      'relH_high',                   'mdi:water',         '%'),
	'at_relh_min':           AcuparseConditionsSensorConfig('all_time', 'Humidity Low',       'relH_low',                    'mdi:water',         '%'),
	'at_relh_max_when':      AcuparseConditionsSensorConfig('all_time', 'Humidity High',      'relH_high_recorded',          'mdi:water',         'time'),
	'at_relh_min_when':      AcuparseConditionsSensorConfig('all_time', 'Humidity Low',       'relH_low_recorded',           'mdi:water',         'time'),
	'at_rain_rate_in_max':   AcuparseConditionsSensorConfig('all_time', 'Rain Rate Max',      'rainfall_IN_most',            'mdi:umbrella',      'in/hr'),
	'at_rain_rate_mm_max':   AcuparseConditionsSensorConfig('all_time', 'Rain Rate Max',      'rainfall_MM_most',            'mdi:umbrella',      'mm/hr'),
	'at_rain_rate_max_when': AcuparseConditionsSensorConfig('all_time', 'Rain Rate Max',      'rainfall_IN_most_recorded',   'mdi:umbrella',      'time'),
	'at_rain_in_total':      AcuparseConditionsSensorConfig('all_time', 'Rain Total',         'rainfall_IN_total',           'mdi:umbrella',      LENGTH_INCHES),
	'at_rain_mm_total':      AcuparseConditionsSensorConfig('all_time', 'Rain Total',         'rainfall_MM_total',           'mdi:umbrella',      'mm'),
	'at_rain_total_since':   AcuparseConditionsSensorConfig('all_time', 'Rain Total',         'rainfall_IN_total_since',     'mdi:umbrella',      'date'),
	
	'moon_age':              AcuparseConditionsSensorConfig('moon',     'Moon Age',           'age',                         'mdi:weather-night', 'time'),
	'moon_phase':            AcuparseConditionsSensorConfig('moon',     'Moon Phase',         'stage',                       None,                ''),
	'moon_next_new':         AcuparseConditionsSensorConfig('moon',     'Next New Moon',      'next_new',                    'mdi:weather-night', 'date'),
	'moon_next_full':        AcuparseConditionsSensorConfig('moon',     'Next Full Moon',     'next_full',                   'mdi:weather-night', 'date'),
	'moon_last_new':         AcuparseConditionsSensorConfig('moon',     'Last New Moon',      'last_new',                    'mdi:weather-night', 'date'),
	'moon_last_full':        AcuparseConditionsSensorConfig('moon',     'Last Full Moon',     'last_full',                   'mdi:weather-night', 'date'),
	'moon_distance':         AcuparseConditionsSensorConfig('moon',     'Moon Distance',      'distance',                    'mdi:weather-night', 'miles'),
	'moon_illumination':     AcuparseConditionsSensorConfig('moon',     'Moon Illumination',  'illumination',                'mdi:weather-night', '%'),

}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
	vol.Required(CONF_HOSTNAME): cv.string,
	vol.Optional(CONF_DEBUG, default='false'): cv.string,
	vol.Optional(CONF_REFRESH_SECONDS, default=60): cv.string,
	vol.Required(CONF_MONITORED_CONDITIONS):
		vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_TYPES)])
})


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None):
	"""Set up the Acuparse sensor."""
	latitude = config.get(hass.config.latitude)
	longitude = config.get(hass.config.longitude)
	hostname = config.get(CONF_HOSTNAME)
	refresh_rate = timedelta(seconds=int(config.get(CONF_REFRESH_SECONDS)))
	debug = config.get(CONF_DEBUG)
	
	_LOGGER.warning("refresh_rate %s", refresh_rate)
	
	rest = AcuparseData(hass, hostname, refresh_rate)
	sensors = []
	UNIQUE_COUNTER = 0
	for variable in config[CONF_MONITORED_CONDITIONS]:
		UNIQUE_COUNTER += 1
		unique_id_base = "apwx.{}".format(hostname)
		sensors.append(AcuparseSensor(hass, rest, variable, unique_id_base))

	await rest.async_update()
	if not rest.data:
		raise PlatformNotReady

	async_add_entities(sensors, True)


class AcuparseSensor(Entity):
	"""Implementing the Acuparse sensor."""

	def __init__(self, hass: HomeAssistantType, rest, condition, unique_id_base: str):
		"""Initialize the sensor."""
		self.rest = rest
		self._condition = condition
		self._state = None
		self._attributes = {ATTR_ATTRIBUTION: CONF_ATTRIBUTION,}
		self._icon = None
		self._entity_picture = None
		self._unit_of_measurement = self._cfg_expand("unit_of_measurement")
		self.rest.request_feature(SENSOR_TYPES[condition].feature)
		# This is only the suggested entity id, it might get changed by
		# the entity registry later.
		self.entity_id = sensor.ENTITY_ID_FORMAT.format('apwx_' + condition)
		self._unique_id = "{}.{}".format(unique_id_base, condition)

	def _cfg_expand(self, what, default=None):
		"""Parse and return sensor data."""
		cfg = SENSOR_TYPES[self._condition]
		val = getattr(cfg, what)
		if not callable(val):
			return val
		try:
			val = val(self.rest)
		except (KeyError, IndexError, TypeError, ValueError) as err:
			_LOGGER.warning("Failed to expand cfg from Acuparse API."
							" Condition: %s Attr: %s Error: %s",
							self._condition, what, repr(err))
			val = default

		return val

	def _update_attrs(self):
		"""Parse and update device state attributes."""
		attrs = self._cfg_expand("device_state_attributes", {})

		for (attr, callback) in attrs.items():
			if callable(callback):
				try:
					self._attributes[attr] = callback(self.rest)
				except (KeyError, IndexError, TypeError, ValueError) as err:
					_LOGGER.warning("Failed to update attrs from Acuparse API."
									" Condition: %s Attr: %s Error: %s",
									self._condition, attr, repr(err))
			else:
				self._attributes[attr] = callback

	@property
	def name(self):
		"""Return the name of the sensor."""
		return self._cfg_expand("friendly_name")

	@property
	def state(self):
		"""Return the state of the sensor."""
		return self._state

	@property
	def device_state_attributes(self):
		"""Return the state attributes."""
		return self._attributes

	@property
	def icon(self):
		"""Return icon."""
		return self._icon

	@property
	def entity_picture(self):
		"""Return the entity picture."""
		return self._entity_picture

	@property
	def unit_of_measurement(self):
		"""Return the units of measurement."""
		return self._unit_of_measurement

	async def async_update(self):
		"""Update current conditions."""
		await self.rest.async_update()

		if not self.rest.data:
			# no data, return
			return

		self._state = self._cfg_expand("value")
		self._update_attrs()
		self._icon = self._cfg_expand("icon", super().icon)
		url = self._cfg_expand("entity_picture")
		if isinstance(url, str):
			self._entity_picture = re.sub(r'^http://', 'https://',
										  url, flags=re.IGNORECASE)

	@property
	def unique_id(self) -> str:
		"""Return a unique ID."""
		return self._unique_id


class AcuparseData:
	"""Get data from Acuparse."""

	REFRESH_RATE = timedelta(seconds=60)

	def __init__(self, hass, hostname, refresh_rate):
		"""Initialize the data object."""
		self._hass = hass
		self._hostname = hostname
		global REFRESH_RATE
		REFRESH_RATE = refresh_rate
		_LOGGER.warning("RREFRESH_RATE %s", REFRESH_RATE)
		self._features = set()
		self.data = None
		self._session = async_get_clientsession(self._hass)

	def request_feature(self, feature):
		"""Register feature to be fetched from WU API."""
		self._features.add(feature)

	def _build_url(self, baseurl=_RESOURCE):
		url = baseurl.format(self._hostname)
		return url
	
	def format_time(self, string):
		parts = string.split(":")
		hours = int(parts[0])
		minutes = parts[1]
		
		if (hours == 0):
			hours = 12
			ampm = " AM"
		elif (hours) < 12:
			ampm = " AM"
		elif (hours) == 12:
			ampm = " PM"
		else:
			hours = hours - 12
			ampm = " PM"
		
		return "{}:{}{}".format(hours, minutes, ampm)

	@Throttle(MIN_TIME_BETWEEN_UPDATES)
	async def async_update(self):
		"""Get the latest data from Acuparse."""
		try:
			with async_timeout.timeout(10, loop=self._hass.loop):
				response = await self._session.get(self._build_url())
			result = await response.json(content_type='text/html')
			
			if result['current']['feelsF'] == 0:
				_LOGGER.info("Feels like = 0 : setting to current temp")
				result['current']['feelsF'] = result['current']['tempF']
				result['current']['feelsC'] = result['current']['tempC']
				
			result['current']['high_temp_recorded'] = self.format_time(result['current']['high_temp_recorded'])
			result['current']['low_temp_recorded'] = self.format_time(result['current']['low_temp_recorded'])
				
			self.data = result
		except ValueError as err:
			_LOGGER.error("Check Acuparse API %s", err.args)
		except (asyncio.TimeoutError) as err:
			_LOGGER.error("Timeout Error fetching Acuparse data: %s", repr(err))
		except (aiohttp.ClientError) as err:
			_LOGGER.error("Client Error fetching Acuparse data: %s", repr(err))
