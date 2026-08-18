import json
from core.optimizer.optimizer import serialize_instance  # Ensure proper imports
from concurrent.futures import ThreadPoolExecutor

# Mock data
mock_data = {
    "start_date": "2025-01-01",
    "end_date": "2025-01-07",
    "teams": ["Team A", "Team B"],
    "uncheckWhiteSolutionConstraints": [],
    "uncheckOrangeSolutionConstraints": [],
}

mock_solutions_primary = [
    [{"team_idx": 0, "events": []}, {"team_idx": 1, "events": []}],
    [{"team_idx": 0, "events": []}, {"team_idx": 1, "events": []}],
    [{"team_idx": 0, "events": []}, {"team_idx": 1, "events": []}],
    [{"team_idx": 0, "events": []}, {"team_idx": 1, "events": []}],
]

mock_solutions_secondary = [
    [{"team_idx": 0, "events": []}, {"team_idx": 1, "events": []}],
    [{"team_idx": 0, "events": []}, {"team_idx": 1, "events": []}],
    [{"team_idx": 0, "events": []}, {"team_idx": 1, "events": []}],
    [{"team_idx": 0, "events": []}, {"team_idx": 1, "events": []}],
]


def test_thread_pool_executor():
    lambda_url = "http://localhost:4000/optimizer/teams"  # Replace with your endpoint for testing

    def mock_call_lambda_url(url, payload):
        print(f"Calling {url} with payload:")
        print(json.dumps(payload, indent=2))
        return {"results": [{"team_idx": payload["team_idx"], "status": "success"}]}

    # Using mock data
    data = mock_data
    team_idx = 1
    team = "Team B"

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                mock_call_lambda_url,
                lambda_url,
                {
                    "data": data.copy(),
                    "team_idx": team_idx,
                    "team": team,
                    "solutions_primary": serialize_instance([
                        mock_solutions_primary[0][team_idx],
                        mock_solutions_primary[1][team_idx],
                        mock_solutions_primary[2][team_idx],
                        mock_solutions_primary[3][team_idx],
                    ]),
                    "solutions_secondary": serialize_instance([
                        mock_solutions_secondary[0][team_idx],
                        mock_solutions_secondary[1][team_idx],
                        mock_solutions_secondary[2][team_idx],
                        mock_solutions_secondary[3][team_idx],
                    ]),
                },
            )
        ]

        results = [future.result() for future in futures]
        print("ThreadPoolExecutor Results:", results)


# Add this main block
if __name__ == "__main__":
    test_thread_pool_executor()
