from treasury_rag.text import remove_report_boilerplate


def test_remove_report_boilerplate_preserves_substantive_text() -> None:
    text = (
        "HM Treasury Annual Report & Accounts 2025–26 "
        "ACCOUNTABILITY REPORT FINANCIAL REVIEW PERFORMANCE REPORT "
        "FINANCIAL STATEMENTS ANNEXES TRUST STATEMENT "
        "HM Treasury Group liabilities were £180.8bn."
    )

    cleaned = remove_report_boilerplate(text)

    assert "ACCOUNTABILITY REPORT" not in cleaned
    assert "Annual Report" not in cleaned
    assert cleaned == "HM Treasury Group liabilities were £180.8bn."

