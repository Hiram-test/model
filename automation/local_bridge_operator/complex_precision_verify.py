from pathlib import Path  # Resolve native input and output evidence.
import hashlib  # Compare immutable native input and result bytes.
import json  # Store independently reproducible precision verification results.
import os  # Explicitly bound solver thread usage.
import re  # Parse numeric DAT fields independently of the production adapters.
import subprocess  # Execute the real native solvers synchronously.
import time  # Record actual native computation duration.
ROOT = Path(__file__).resolve().parents[3]  # Locate the isolated native runtime.
REPO = Path(__file__).resolve().parents[2]  # Locate versioned campaign inputs.
AUDIT = REPO / 'build/complex-nonlinear-20261024/audit'  # Keep all checks beside existing scientific evidence.
OUTPUT = AUDIT / 'precision_v3/native_equivalence_v2'  # Preserve the earlier strict whole-file comparison including its differing timestamps.
OUTPUT.mkdir(parents=True, exist_ok=True)  # Prepare a distinct verification revision without overwriting failed evidence.
heat = (AUDIT / 'heat_benchmark/nx010_dt0.00100/heat.inp').read_text()  # Reuse the independent analytic transient-conduction benchmark.
heat = heat.replace('*END STEP', '*NODE FILE,FREQUENCY=999999\nNT\n*EL PRINT,ELSET=BODY,FREQUENCY=999999\nHFL\n*END STEP')  # Add identical observation requests to both binaries without changing physical equations.
patch = (AUDIT / 'quadratic_native_patch_v3/patch.inp').read_text()  # Reuse a native nonuniform quadratic mechanical patch.
inputs = {'heat': heat, 'patch': patch}  # Test temperature, heat flux, displacement, force, and stress printing.
solvers = {'v2': ROOT / 'solver-runtime/ccx-precision-v2', 'v3': ROOT / 'solver-runtime/ccx-complex-precision-v3'}  # Compare only the isolated precision variants.
environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', CCX_NPROC_RESULTS='1', CCX_NPROC_EQUATION_SOLVER='1')  # Bound each native comparison to one CPU thread.
records = []  # Preserve execution and result evidence for both physical tests.
for case, input_text in inputs.items():  # Run each unchanged physical input under both binary variants.
    runs = {}  # Collect the two native observations without mixing jobs.
    for version, solver in solvers.items():  # Execute the original printing and upgraded printing sequentially.
        folder = OUTPUT / (case + '_' + version)  # Isolate every solver's native files.
        folder.mkdir(parents=True, exist_ok=True)  # Prepare the dedicated native working directory.
        (folder / (case + '.inp')).write_text(input_text)  # Use byte-identical input decks for the comparison.
        start = time.perf_counter()  # Measure actual native wall time.
        completed = subprocess.run([str(solver), case], cwd=folder, env=environment, capture_output=True, timeout=180)  # Wait for the real solver and fail on an unbounded run.
        elapsed = time.perf_counter() - start  # Preserve native runtime without reporting it as neural training time.
        (folder / 'solver.log').write_bytes(completed.stdout + completed.stderr)  # Retain complete native diagnostics.
        assert completed.returncode == 0 and b'Job finished' in completed.stdout  # Require actual native completion.
        dat = (folder / (case + '.dat')).read_text()  # Read native high-precision or original-precision scalar output.
        frd = (folder / (case + '.frd')).read_bytes()  # Retain unchanged native field output for bitwise comparison.
        numeric_rows = [line.split() for line in dat.splitlines() if re.match(r'^\s*\d+\s', line)]  # Extract native data rows without assuming a specific field width.
        values = [[float(token.replace('D', 'E')) for token in row] for row in numeric_rows]  # Parse native whitespace-separated values exactly as consumers do.
        runs[version] = {'elapsed_seconds': elapsed, 'input_sha256': hashlib.sha256(input_text.encode()).hexdigest(), 'dat_sha256': hashlib.sha256(dat.encode()).hexdigest(), 'frd_sha256': hashlib.sha256(frd).hexdigest(), 'frd': frd, 'values': values, 'tokens': numeric_rows, 'folder': str(folder.relative_to(REPO))}  # Keep both field values and native evidence identities.
    assert len(runs['v2']['values']) == len(runs['v3']['values']) > 0  # Require identical observed entity and frame counts.
    bounded = True  # Verify every printed scalar against its original decimal-rounding interval.
    maximum_ratio = 0.0  # Quantify the tightest original-precision interval comparison.
    for old_row, new_row, old_tokens in zip(runs['v2']['values'], runs['v3']['values'], runs['v2']['tokens']):  # Compare each native row and its original printed precision.
        assert len(old_row) == len(new_row)  # Refuse silently missing or merged DAT columns.
        for old, new, token in zip(old_row, new_row, old_tokens):  # Check integer identities and physical values separately.
            if 'E' not in token.upper() and '.' not in token:  # Preserve exact node and integration-point identifiers.
                assert old == new  # Output precision must never alter entity identity.
                continue  # Advance to the next native scalar.
            mantissa, exponent = re.split('[EeDd]', token) if re.search('[EeDd]', token) else (token, '0')  # Read the original token's decimal quantization.
            decimals = len(mantissa.split('.')[-1]) if '.' in mantissa else 0  # Count explicitly printed decimal places.
            tolerance = 0.50001 * 10.0 ** (int(exponent) - decimals) + abs(new) * 2e-15 + 1e-300  # Allow only original rounding and floating parsing roundoff.
            ratio = abs(old - new) / tolerance  # Normalize discrepancy to the justified print interval.
            maximum_ratio = max(maximum_ratio, ratio)  # Preserve the largest independent interval check.
            bounded = bounded and ratio <= 1.0  # Fail on any numerical discrepancy beyond printing precision.
    assert bounded  # Verify that the output-only transformation did not change native numerical results.
    frd_identical = runs['v2']['frd'] == runs['v3']['frd']  # Record whether metadata timestamps also happen to match.
    frd_payloads = {version: b'\n'.join(line for line in run['frd'].splitlines() if not line.startswith((b'    1UDATE ', b'    1UTIME '))) for version, run in runs.items()}  # Exclude only documented wall-clock date and time metadata.
    assert frd_payloads['v2'] == frd_payloads['v3']  # Require every geometry, field, result time, and remaining metadata byte to match.
    records.append({'case': case, 'native_frd_whole_file_identical': frd_identical, 'native_frd_payload_bitwise_identical': True, 'excluded_frd_metadata': ['1UDATE', '1UTIME'], 'payload_sha256': hashlib.sha256(frd_payloads['v3']).hexdigest(), 'all_dat_values_inside_original_rounding': bounded, 'maximum_rounding_interval_ratio': maximum_ratio, 'observed_numeric_rows': len(runs['v2']['values']), 'runs': {version: {key: value for key, value in run.items() if key not in ('frd', 'values', 'tokens')} for version, run in runs.items()}})  # Keep compact reproducible verification evidence.
receipt = {'status': 'PASS', 'scope': 'same input, unchanged native arithmetic and FRD fields; improved DAT precision', 'cases': records}  # State the bounded validation conclusion.
(OUTPUT / 'native_precision_equivalence.json').write_text(json.dumps(receipt, indent=2) + '\n')  # Persist the comparison for final independent review.
print(json.dumps(receipt))  # Return the native verification result without large solver logs.
