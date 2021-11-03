# SPDX-FileCopyrightText: 2021 2017-2021 Alliander N.V. <korte.termijn.prognoses@alliander.com>
#
# SPDX-License-Identifier: MPL-2.0

# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch
from openstf_dbc.data.featuresets import FEATURESET_NAMES
from pydantic import ValidationError
import pandas as pd
from openstf_dbc.services.prediction_job import (
    PredictionJobRetriever,
    PredictionJobDataClass,
)
from openstf_dbc.services.model_specifications import ModelSpecificationRetriever

prediction_job = {
    "id": 307,
    "name": "Neerijnen",
    "forecast_type": "demand",
    "model": "xgb",
    "model_type_group": "default",
    "horizon_minutes": 2880,
    "resolution_minutes": 15,
    "train_components": 1,
    "external_id": None,
    "lat": 51.8336647,
    "lon": 5.2137814,
    "sid": "LC_Neerijnen",
    "created": pd.Timestamp("2019-04-05 12:08:23"),
}


@patch("openstf_dbc.services.prediction_job._DataInterface")
class TestPredictionJob(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.service = PredictionJobRetriever()
        self.modelspecs = ModelSpecificationRetriever()

    def test_get_prediction_job_result_size_is_zero(self, data_interface_mock):
        data_interface_mock.get_instance.return_value.exec_sql_query.return_value = (
            pd.DataFrame()
        )

        with self.assertRaises(ValueError):
            self.service.get_prediction_job(pid=307)

    def test_get_prediction_jobs_result_size_is_zero(self, data_interface_mock):

        self.service.get_prediction_jobs()

    def test_get_prediction_jobs_wind_result_size_is_zero(self, data_interface_mock):
        self.service.get_prediction_jobs_wind()

    def test_get_prediction_jobs_solar_result_size_is_zero(self, data_interface_mock):
        self.service.get_prediction_jobs_solar()

    def test_build_get_prediction_jobs_query(self, *args, **kwargs):
        kwargs = {
            "pid": 123,
            "model_type": "xgb",
            "is_active": 1,
            "only_ato": True,
            "external_id": "e179c450-30cc-4fb8-a9c8-1cd6feee2cbd",
            "limit": 999,
        }
        query = PredictionJobRetriever.build_get_prediction_jobs_query(**kwargs)
        for key, value in kwargs.items():
            if key == "only_ato":
                self.assertTrue("ATO" in query)
                continue
            self.assertTrue(str(value) in query)

    def test_get_featureset(self, data_interface_mock):
        for name in FEATURESET_NAMES:
            featureset = self.modelspecs.get_featureset(name)
            if name == "N":
                self.assertEqual(featureset, None)
            else:
                self.assertEqual(type(featureset), list)

    def test_get_featureset_wrong_name(self, data_interface_mock):
        with self.assertRaises(KeyError):
            self.modelspecs.get_featureset("wrong_name")

    def test_dataclass(self, data_interface_mock):
        pj_dataclass = PredictionJobDataClass(**prediction_job)
        self.assertIsInstance(pj_dataclass, PredictionJobDataClass)

    def test_create_prediction_job_object(self, data_interface_mock):
        pj = self.service._create_prediction_job_object(prediction_job)
        self.assertEqual(pj.__getitem__("id"), prediction_job["id"])
        pj.__setitem__("id", 50)
        self.assertEqual(pj.__getitem__("id"), 50)

        with self.assertRaises(AttributeError):
            pj.__setitem__("non_existing", "can't")

    def test_create_prediction_job_object_missing_attribute(self, data_interface_mock):
        pj_dict = prediction_job.copy()
        pj_dict.pop("forecast_type")
        with self.assertRaises(AttributeError):
            self.service._create_prediction_job_object(pj_dict)


if __name__ == "__main__":
    unittest.main()
