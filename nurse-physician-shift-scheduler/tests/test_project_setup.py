import sys

import ortools
from ortools.sat.python import cp_model

import nurse_scheduler


def test_python_version_is_supported():
    assert sys.version_info >= (3, 10)


def test_ortools_is_installed():
    assert ortools.__version__


def test_cp_sat_model_can_be_created():
    model = cp_model.CpModel()
    assert model is not None


def test_scheduler_package_can_be_imported():
    assert nurse_scheduler is not None
