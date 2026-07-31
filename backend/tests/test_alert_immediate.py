from finance_agent.graph.master import _build_alert_message

FROM_ADDRESS = "agent@example.com"
TO_ADDRESS = "user@example.com"


def test_alert_message_contains_statement_and_failure_reason():
    message = _build_alert_message(
        [{"statement_id": "abc-123", "failure_reason": "unreadable_pdf"}],
        from_address=FROM_ADDRESS,
        to_address=TO_ADDRESS,
    )

    assert message["From"] == FROM_ADDRESS
    assert message["To"] == TO_ADDRESS
    assert "błąd weryfikacji" in message["Subject"]
    body = message.get_content()
    assert "abc-123" in body
    assert "unreadable_pdf" in body


def test_alert_message_lists_multiple_failed_statements():
    message = _build_alert_message(
        [
            {"statement_id": "stmt-1", "failure_reason": "unreadable_pdf"},
            {"statement_id": "stmt-2", "failure_reason": "balance_mismatch"},
        ],
        from_address=FROM_ADDRESS,
        to_address=TO_ADDRESS,
    )

    body = message.get_content()
    assert "stmt-1" in body
    assert "unreadable_pdf" in body
    assert "stmt-2" in body
    assert "balance_mismatch" in body
