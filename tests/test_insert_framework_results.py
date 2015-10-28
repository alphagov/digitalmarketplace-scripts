import pytest

from dmscripts.insert_framework_results import insert_result, insert_results
from mock import mock, call
from dmutils.apiclient.errors import HTTPError


@pytest.fixture
def mock_data_client():
    return mock.Mock()


def test_insert_result(mock_data_client):
    mock_data_client.set_framework_result.return_value = {'on_framework': True}

    assert insert_result(mock_data_client, 123456, 'g-cloud-7', True, 'user') == 'OK: 123456\n'
    mock_data_client.set_framework_result.assert_called_with(123456, 'g-cloud-7', True, 'user')


def test_insert_results(mock_data_client):
    out_mock = mock.Mock()
    insert_results(mock_data_client, out_mock, 'g-cloud-7', 'tests/fixtures/framework_results.csv', 'user')

    mock_data_client.set_framework_result.assert_has_calls([
        call(123, 'g-cloud-7', True, 'user'),
        call(234, 'g-cloud-7', False, 'user'),
        call(345, 'g-cloud-7', True, 'user'),
        call(456, 'g-cloud-7', False, 'user'),
        call(678, 'g-cloud-7', True, 'user')
        ], any_order=False
    )

    out_mock.write.assert_has_calls([
        call("OK: 123\n"),
        call("OK: 234\n"),
        call("OK: 345\n"),
        call("OK: 456\n"),
        call("Error: Result must be 'pass' or 'fail', not 'yes'; Bad line: 5\n"),
        call("Error: invalid literal for int() with base 10: 'Company Name'; Bad line: 6\n"),
        call("OK: 678\n")
        ], any_order=False
    )


def test_http_error_handling(mock_data_client):
    mock_data_client.set_framework_result.side_effect = HTTPError()

    result = insert_result(mock_data_client, 123456, 'g-cloud-7', True, 'user')
    assert result == 'Error inserting result for 123456 (True): Request failed (status: 503)\n'