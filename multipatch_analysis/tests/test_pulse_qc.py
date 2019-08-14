import os, glob, pickle
import pytest
import neuroanalysis
from ..qc import PulseResponseQCTestCase
from ..ui.pulse_response_qc 

path = os.path.join(os.path.dirname(multipatch_analysis.__file__), '..', 'test_data', 'pulse_response_qc', '*.pkl')
pulse_response_files = sorted(glob.glob(path))

test_ui = None

@pytest.mark.parametrize('test_file', pulse_response_files)
def test_pulse_response_qc(request, test_file):
    global test_ui
    audit = request.config.getoption('audit')
    if audit and test_ui is None:
        test_ui = PulseResponseQCTestUi()

    print("test:", test_file)
    tc = PulseResponseQCTestCase()
    tc.load_file(test_file)
    if audit:
        tc.audit_test(test_ui)
    else:
        tc.run_test()