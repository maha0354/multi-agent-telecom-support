from app.checks import extract_numbers, next_after_agent, normalize_status, unsupported_numbers


class TestNextAfterAgent:
    def test_useful_result_moves_to_next_agent(self):
        assert next_after_agent("plan", "ok", ["analyst"], [], 0) == "analyst"

    def test_valid_empty_result_does_not_replan(self):
        assert next_after_agent("plan", "ok_empty", ["analyst"], [], 0) == "analyst"

    def test_last_agent_goes_to_verifier(self):
        assert next_after_agent("plan", "ok", [], [], 0) == "verifier"

    def test_no_info_triggers_one_replan(self):
        assert next_after_agent("plan", "no_relevant_info", ["analyst"], [], 0) == "router"
        assert next_after_agent("plan", "error", [], [], 0) == "router"

    def test_replan_limit_falls_through_to_plan(self):
        assert next_after_agent("plan", "no_relevant_info", ["analyst"], [], 1) == "analyst"
        assert next_after_agent("plan", "error", [], [], 1) == "verifier"

    def test_retry_phase_goes_back_to_verifier(self):
        assert next_after_agent("retry", "ok", ["analyst"], [], 0) == "verifier"

    def test_retry_phase_runs_queued_retries_first(self):
        assert next_after_agent("retry", "ok", [], ["analyst"], 0) == "analyst"


class TestNormalizeStatus:
    def test_ok_without_claims_is_no_info(self):
        assert normalize_status("ok", 0, any_tool_error=False) == "no_relevant_info"

    def test_ok_without_claims_after_tool_error_is_error(self):
        assert normalize_status("ok", 0, any_tool_error=True) == "error"

    def test_ok_with_claims_unchanged(self):
        assert normalize_status("ok_empty", 1, any_tool_error=False) == "ok_empty"


class TestNumbers:
    def test_formats_normalize(self):
        assert extract_numbers("€68.96, 68,96 or 774 SEK; 1,234 total") == {68.96, 774.0, 1234.0}

    def test_list_markers_ignored(self):
        assert extract_numbers("1. Restart\n2) Check APN") == set()

    def test_identifiers_ignored_but_attached_units_kept(self):
        assert extract_numbers("customer C-1001 used 6GB") == {6.0}

    def test_supported_reply_passes(self):
        claims = ["Zone 4 pay-as-you-go costs 129 SEK per GB.", "6 GB costs 774 SEK."]
        reply = "In Zone 4 data costs 129 SEK/GB, so 6 GB would be 774.00 SEK."
        assert unsupported_numbers(reply, claims) == set()

    def test_changed_number_is_caught(self):
        assert unsupported_numbers("That costs 744 SEK.", ["It costs 774 SEK."]) == {744.0}

    def test_responder_arithmetic_is_caught(self):
        claims = ["The pass costs 399 SEK.", "Pay-as-you-go would cost 774 SEK."]
        assert unsupported_numbers("You save 375 SEK.", claims) == {375.0}
