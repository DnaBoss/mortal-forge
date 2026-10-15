import unittest
from write_guard import verdict

class GodotObservation(unittest.TestCase):
    def decide(self, command):
        return verdict({"cwd":"/tmp","tool_input":{"cmd":command}})[0]
    def test_observed_combination_refused(self):
        self.assertEqual(self.decide("ps -eo pid,comm | rg 'godot|ollama'; localai code task"),"godot-model-observation")
        self.assertEqual(self.decide("pgrep -x godot4\nlocalai review task"),"godot-model-observation")
    def test_observation_alone_allowed(self):
        self.assertIsNone(self.decide("ps -eo pid,comm | rg 'godot|ollama'"))
    def test_model_alone_and_unrelated_process_query_allowed(self):
        self.assertIsNone(self.decide("localai code task"))
        self.assertIsNone(self.decide("ps -eo pid,comm | rg redis; localai review task"))
    def test_quoted_discussion_is_not_an_observation(self):
        self.assertIsNone(self.decide("echo 'ps godot; localai code task'"))

if __name__=="__main__": unittest.main()
