"""Exercise the production HTTP boundary without credentials or an external call."""
import io
from urllib.error import URLError

import pytest

from provider_directory_truth_layer import mapping_model
from provider_directory_truth_layer.fhir_acquisition import NoRedirect


class Response(io.BytesIO):
    def __init__(self, body, code=200):
        super().__init__(body)
        self.code = code
        self.headers = {'x-request-id': 'controlled-provider-request'}


def install(monkeypatch, response):
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            if isinstance(response, Exception):
                raise response
            return response
    def factory(*handlers):
        assert any(isinstance(handler, NoRedirect) for handler in handlers)
        return Opener()
    monkeypatch.setattr(mapping_model, 'build_opener', factory)
    return calls


def test_fixed_destination_single_post_and_key_is_header_only(monkeypatch):
    calls = install(monkeypatch, Response(b'controlled response'))
    result = mapping_model.invoke(b'{"input":"synthetic"}', 'synthetic-secret')
    request, timeout = calls[0]
    assert len(calls) == 1 and request.full_url == 'https://api.openai.com/v1/responses'
    assert request.get_method() == 'POST' and timeout == 10
    assert request.get_header('Authorization') == 'Bearer synthetic-secret'
    assert b'synthetic-secret' not in request.data
    assert result['body'] == b'controlled response' and 'synthetic-secret' not in str(result)


@pytest.mark.parametrize('status', [401, 403])
def test_authentication_body_is_not_retained(monkeypatch, status):
    install(monkeypatch, Response(b'Key fragment should never be exported', status))
    result = mapping_model.invoke(b'{}', 'synthetic-secret')
    assert result['body'] == b'' and result['status'] == status
    assert 'Key fragment' not in str(result)


def test_oversized_response_retains_only_labeled_prefix(monkeypatch):
    install(monkeypatch, Response(b'x' * (mapping_model.LIMITS['response_bytes'] + 1)))
    result = mapping_model.invoke(b'{}', 'synthetic-secret')
    assert len(result['body']) == mapping_model.LIMITS['response_bytes']
    assert 'prefix only' in result['error'] and result['truncated']


def test_connection_failure_has_no_hidden_retry_or_exception_secret(monkeypatch):
    calls = install(monkeypatch, URLError('Do not persist this synthetic-secret exception'))
    result = mapping_model.invoke(b'{}', 'synthetic-secret')
    assert len(calls) == 1 and result['status'] is None
    assert result['body'] == b'' and 'synthetic-secret' not in str(result)


def test_redirect_is_not_followed(monkeypatch):
    calls = install(monkeypatch, Response(b'Redirect retained for diagnosis', 302))
    result = mapping_model.invoke(b'{}', 'synthetic-secret')
    assert result['status'] == 302 and len(calls) == 1


def test_active_read_deadline_returns_failure_without_reading_later_body(monkeypatch):
    from types import SimpleNamespace
    ticks = iter([0, 31])
    monkeypatch.setattr(mapping_model, 'time', SimpleNamespace(monotonic=lambda: next(ticks)))
    calls = install(monkeypatch, Response(b'Body beyond deadline'))
    result = mapping_model.invoke(b'{}', 'synthetic-secret')
    assert result['error'] and result['body'] == b'' and len(calls) == 1


def test_partial_read_is_labeled_truncated_even_below_byte_cap(monkeypatch):
    from http.client import IncompleteRead
    class Partial(Response):
        def read(self, _size):
            raise IncompleteRead(b'Exact partial bytes', 999)
    install(monkeypatch, Partial(b''))
    result = mapping_model.invoke(b'{}', 'synthetic-secret')
    assert result['body'] == b'Exact partial bytes' and result['truncated']
    assert 'Incomplete' in result['error']
