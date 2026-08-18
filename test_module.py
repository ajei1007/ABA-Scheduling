import unittest
from solution_checker import convert_in_out
from testing import test_1_input, output


class TestEfficiencyMethods(unittest.TestCase):
    def setUp(self):
        self.test_results = {}

    def tearDown(self):
        # Print the test results at the end of each test
        for test_name, result in self.test_results.items():
            if result:
                print(f"{test_name} SUCCESS")
            else:
                print(f"{test_name} FAILED")

    def test_efficiency(self):
        try:
            res = convert_in_out(test_1_input, output)
            self.assertGreaterEqual(res["efficiency"], 95.0)
            self.test_results["test_efficiency"] = True
        except Exception as e:
            self.test_results["test_efficiency"] = False
            print(f"TEST [1] FAILED: {e}\n{res}")


if __name__ == '__main__':
    unittest.main()
