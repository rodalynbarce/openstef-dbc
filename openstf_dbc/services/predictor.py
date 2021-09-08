# SPDX-FileCopyrightText: 2021 2017-2021 Alliander N.V. <korte.termijn.prognoses@alliander.com>
#
# SPDX-License-Identifier: MPL-2.0

import warnings
from enum import Enum
from typing import List, Optional, Tuple, Union

import pandas as pd
from openstf_dbc.data_interface import _DataInterface
from openstf_dbc.services.weather import Weather
from openstf_dbc.utils.utils import get_datetime_index


class PredictorGroups(Enum):
    MARKET_DATA = "market_data"
    WEATHER_DATA = "weather_data"
    LOAD_PROFILES = "load_profiles"


class Predictor:
    def get_predictors(
        self,
        datetime_start,
        datetime_end,
        forecast_resolution: Optional[str] = None,
        location: Union[str, Tuple[float, float]] = None,
        predictor_groups: Union[List[PredictorGroups], List[str], None] = None,
    ):
        """Get predictors.

        Get predictors for a given datetime range. Optionally predictor groups can be
        selected. If the WEATHER_DATA group is included a location is required.

        Args:
            location (Union[str, Tuple[float, float]], optional): Location (for weather data).
                Defaults to None.
            predictor_groups (Optional[List[str]], optional): The groups of predictors
                to include (see the PredictorGroups enum for allowed values). When set to
                None or not given all predictor groups will be returned. Defaults to None.

        Returns:
            pd.DataFrame: Requested predictors with timezone aware datetime index.
        """
        if predictor_groups is None:
            predictor_groups = [p for p in PredictorGroups]

        # convert strings to enums if required
        predictor_groups = [PredictorGroups(p) for p in predictor_groups]

        if PredictorGroups.WEATHER_DATA in predictor_groups and location is None:
            raise ValueError(
                "Need to provide a location when weather data predictors are requested."
            )

        predictors = pd.DataFrame(
            index=pd.date_range(
                start=datetime_start,
                end=datetime_end,
                freq=forecast_resolution,
                tz="UTC",
            )
        )

        if PredictorGroups.WEATHER_DATA in predictor_groups:
            weather_data_predictors = self.get_weather_data(
                datetime_start,
                datetime_end,
                location=location,
                forecast_resolution=forecast_resolution,
            )
            predictors = pd.concat([predictors, weather_data_predictors], axis=1)

        if PredictorGroups.MARKET_DATA in predictor_groups:
            market_data_predictors = self.get_market_data(
                datetime_start, datetime_end, forecast_resolution=forecast_resolution
            )
            predictors = pd.concat([predictors, market_data_predictors], axis=1)

        if PredictorGroups.LOAD_PROFILES in predictor_groups:
            load_profiles_predictors = self.get_load_profiles(
                datetime_start, datetime_end, forecast_resolution=forecast_resolution
            )
            predictors = pd.concat([predictors, load_profiles_predictors], axis=1)

        return predictors

    def get_market_data(self, datetime_start, datetime_end, forecast_resolution=None):
        electricity_price = self.get_electricity_price(
            datetime_start, datetime_end, forecast_resolution
        )
        gas_price = self.get_gas_price(
            datetime_start, datetime_end, forecast_resolution
        )

        if electricity_price.empty is False and gas_price.empty is True:
            return electricity_price

        if electricity_price.empty is True and gas_price.empty is False:
            return gas_price

        if electricity_price.empty is True and gas_price.empty is True:
            return pd.DataFrame(
                index=get_datetime_index(
                    datetime_start, datetime_end, forecast_resolution
                )
            )

        return pd.concat([electricity_price, gas_price], axis=1)

    def get_electricity_price(
        self, datetime_start, datetime_end, forecast_resolution=None
    ):
        query = 'SELECT "Price" FROM "forecast_latest".."marketprices" \
        WHERE "Name" = \'APX\' AND time >= \'{}\' AND time <= \'{}\''.format(
            datetime_start, datetime_end
        )

        electricity_price = _DataInterface.get_instance().exec_influx_query(query)

        electricity_price = electricity_price["marketprices"]

        electricity_price.rename(columns=dict(Price="APX"), inplace=True)

        if forecast_resolution and electricity_price.empty is False:
            electricity_price = electricity_price.resample(forecast_resolution).ffill()

        return electricity_price

    def get_gas_price(self, datetime_start, datetime_end, forecast_resolution=None):
        query = "SELECT datetime, price FROM marketprices WHERE name = 'gasPrice' \
                    AND datetime BETWEEN '{start}' AND '{end}' ORDER BY datetime asc".format(
            start=str(datetime_start), end=str(datetime_end)
        )

        gas_price = _DataInterface.get_instance().exec_sql_query(query)
        gas_price.rename(columns={"price": "Elba"}, inplace=True)

        if forecast_resolution and gas_price.empty is False:
            gas_price = gas_price.resample(forecast_resolution).ffill()

        return gas_price

    def get_load_profiles(self, datetime_start, datetime_end, forecast_resolution=None):
        """Get load profiles.

            Get the TDCV (Typical Domestic Consumption Values) load profiles from the
            database for a given range.

            NEDU supplies the SJV (Standaard Jaarverbruik) load profiles for
            The Netherlands. For more information see:
            https://www.nedu.nl/documenten/verbruiksprofielen/

        Returns:
            pandas.DataFrame: TDCV load profiles (if available)

        """
        # select all fields which start with 'sjv'
        # (there is also a 'year_created' tag in this measurement)
        database = "realised"
        measurement = "sjv"
        query = f"""
            SELECT /^sjv/ FROM "{database}".."{measurement}"
            WHERE time >= '{datetime_start}' AND time <= '{datetime_end}'
        """

        load_profiles = _DataInterface.get_instance().exec_influx_query(query)

        load_profiles = load_profiles[measurement]

        if forecast_resolution and load_profiles.empty is False:
            load_profiles = load_profiles.resample(forecast_resolution).interpolate(
                limit=3
            )

        return load_profiles

    def get_weather_data(
        self, datetime_start, datetime_end, location, forecast_resolution=None
    ):
        # Get weather data
        weather_params = [
            "clouds",
            "radiation",
            "temp",
            "winddeg",
            "windspeed",
            "windspeed_100m",
            "pressure",
            "humidity",
            "rain",
            "mxlD",
            "snowDepth",
            "clearSky_ulf",
            "clearSky_dlf",
            "ssrunoff",
        ]
        weather_data = Weather().get_weather_data(
            location,
            weather_params,
            datetime_start,
            datetime_end,
            source="optimum",
        )

        # Post process weather data
        # This might not be required anymore?
        if "source_1" in list(weather_data):
            weather_data["source"] = weather_data.source_1
            weather_data = weather_data.drop("source_1", axis=1)

        if "source" in list(weather_data):
            del weather_data["source"]

        if "input_city_1" in list(weather_data):
            del weather_data["input_city_1"]
        elif "input_city" in list(weather_data):
            del weather_data["input_city"]

        if forecast_resolution and weather_data.empty is False:
            weather_data = weather_data.resample(forecast_resolution).interpolate(
                limit=11
            )  # 11 as GFS data has data every 3 hours

        return weather_data
