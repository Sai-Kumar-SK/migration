import unittest
import validate_setup

class TestValidateSetup(unittest.TestCase):
    def test_templates_exist(self):
        ok = validate_setup.check_templates()
        self.assertTrue(ok)

if __name__ == '__main__':
    unittest.main()