import claims_fraud


def test_package_imports_successfully():
    assert claims_fraud is not None


def test_initial_package_version():
    assert claims_fraud.__version__ == "0.1.0"
