"""Exercise optional-model test discovery in fresh processes, without Torch."""

import json
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
DISCOVER = textwrap.dedent("""\
    import builtins
    import importlib.abc
    import io
    import json
    import sys
    import unittest

    class TorchImportFailure(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "torch":
                raise getattr(builtins, sys.argv[1])(
                    "TEST-ONLY Torch import failure", name=sys.argv[2])

    sys.meta_path.insert(0, TorchImportFailure())
    if sys.argv[3] == "pytest":
        import pytest
        raise SystemExit(pytest.main(["-q", "-rs", "tests/test_contact_model.py"]))

    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_contact_model.py", top_level_dir=".")
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output).run(suite)
    print(json.dumps(dict(testsRun=result.testsRun, skipped=len(result.skipped),
                          errors=len(result.errors), failures=len(result.failures),
                          successful=result.wasSuccessful(), output=output.getvalue())))
""")


class OptionalDependencyDiscoveryTests(unittest.TestCase):
    def discover(self, error_type="ModuleNotFoundError", name="torch", runner="unittest"):
        result = subprocess.run(
            [sys.executable, "-c", DISCOVER, error_type, name, runner],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        return result

    def test_absent_torch_is_a_unittest_skip_instead_of_an_import_error(self):
        result = self.discover()
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertTrue(summary["successful"], summary["output"])
        self.assertEqual((summary["testsRun"], summary["skipped"],
                          summary["errors"], summary["failures"]), (1, 1, 0, 0))

    def test_absent_torch_is_also_a_pytest_skip(self):
        result = self.discover(runner="pytest")
        # This invocation selects only the optional module, so pytest reports
        # no collected tests after the module skip (its documented exit code 5).
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("1 skipped", result.stdout)
        self.assertIn("optional PyTorch test dependencies are not installed", result.stdout)

    def test_broken_torch_imports_are_errors_instead_of_skips(self):
        for error_type, name in (("ModuleNotFoundError", "torch._C"),
                                 ("ModuleNotFoundError", "torch_dependency"),
                                 ("ImportError", "torch")):
            with self.subTest(error_type=error_type, name=name):
                result = self.discover(error_type, name)
                self.assertEqual(result.returncode, 0, result.stderr)
                summary = json.loads(result.stdout)
                self.assertFalse(summary["successful"], summary["output"])
                self.assertEqual((summary["errors"], summary["skipped"]), (1, 0))
                self.assertIn("TEST-ONLY Torch import failure", summary["output"])


if __name__ == "__main__":
    unittest.main()
