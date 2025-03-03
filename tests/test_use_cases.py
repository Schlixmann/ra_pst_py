from use_cases import EvalPipeline

import unittest

class UseCaseTest(unittest.TestCase):
    def test_generator(self):
        ep = EvalPipeline()
        release_times = ep.generate_release_times(5, 5)
        print(release_times)
        print(sum(release_times) / len(release_times))
