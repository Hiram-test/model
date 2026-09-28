import importlib.util  # Load the existing commented calibration implementation without copying or diverging its solver logic.
import sys  # Forward the validated baseline and output directory arguments to the imported calibration entry point.
from pathlib import Path  # Resolve the sibling calibration module deterministically on the GitHub Actions runner.
module_path = Path(__file__).with_name('prestress_l2_calibrate.py')  # Locate the full L2 completed-state calibration implementation beside this diagnostic wrapper.
spec = importlib.util.spec_from_file_location('zhaqing_prestress_calibration', module_path)  # Build an import specification from the exact branch file being tested.
if spec is None or spec.loader is None:  # Refuse to run when Python cannot construct a loader for the calibration module.
    raise SystemExit('cannot load prestress calibration module')  # Exit explicitly instead of silently running a different implementation.
module = importlib.util.module_from_spec(spec)  # Create the module object that will hold the imported calibration functions and constants.
spec.loader.exec_module(module)  # Execute the calibration module definitions without invoking its guarded command-line main block.
module.SCALES = [0.0, 1.0]  # Restrict this diagnostic pass to the zero-prestress control and the analytical main-cable prestress estimate.
raise SystemExit(module.main())  # Run the unchanged calibration workflow with the two diagnostic scales and propagate its numerical status.
