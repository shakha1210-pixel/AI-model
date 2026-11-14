from workspace.adapters.base import (
    GenerationRequest,
    GenerationResult,
    ModelMessage,
    ProviderAdapter,
    ProviderAdapterError,
    StreamEvent,
    Usage,
)


def test_generation_request_and_result_are_provider_neutral():
    request = GenerationRequest(
        model="example-model",
        messages=[ModelMessage(role="user", content="Hello")],
        temperature=0.2,
        max_tokens=128,
    )
    result = GenerationResult(
        text="Hi",
        model=request.model,
        provider="example",
        usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
    )

    assert request.messages[0].content == "Hello"
    assert result.text == "Hi"
    assert result.usage.total_tokens == 2


def test_stream_event_supports_delta_and_terminal_event():
    delta = StreamEvent(text_delta="Hello")
    final = StreamEvent(finish_reason="stop", is_final=True)

    assert delta.text_delta == "Hello"
    assert not delta.is_final
    assert final.is_final
    assert final.finish_reason == "stop"


def test_provider_adapter_error_exposes_safe_diagnostics():
    error = ProviderAdapterError(
        "Provider request failed", provider="example", status_code=429, retryable=True
    )

    assert str(error) == "Provider request failed"
    assert error.provider == "example"
    assert error.status_code == 429
    assert error.retryable


def test_contract_is_runtime_checkable_protocol():
    assert getattr(ProviderAdapter, "_is_runtime_protocol", False)
