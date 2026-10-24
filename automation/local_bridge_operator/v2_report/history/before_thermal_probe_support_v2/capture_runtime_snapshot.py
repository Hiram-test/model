import hashlib, importlib.metadata, json, platform, sys, time  # Record the actually observed research runtime without importing Torch or invoking any native solver.
from pathlib import Path  # Read only fixed installed executable identities and write one report provenance snapshot.
ROOT = Path('/dev/shm/bridge_complex_v2_20261025/report')  # Keep this observation distinct from original per-process training receipts.
def reference(path):  # Identify installed executable bytes without executing them.
    path = Path(path)  # Normalize the explicitly declared executable path.
    with path.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()  # Hash the whole wrapper or actual ELF binary.
    return {'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size}  # Preserve exact local identities for reproducibility.
def main():  # Observe the current shared scientific environment, not retrospectively invent a launch-time receipt.
    output = ROOT / 'runtime_observation.json'; packages = {}  # Keep missing distributions explicit instead of guessing versions.
    for name in ('torch', 'numpy', 'scipy', 'matplotlib'):  # Record the installed libraries used by training, numerical validation and statistical plotting.
        try: packages[name] = importlib.metadata.version(name)  # Read installed distribution metadata without loading heavy native modules.
        except importlib.metadata.PackageNotFoundError: packages[name] = None  # An unavailable package remains visibly unavailable.
    value = {'schema': 'bridge.v2.report.runtime.observation.v1', 'observed_epoch_seconds': time.time(), 'scope': 'Current shared research environment observed during report-generator preparation; not a replacement for original per-process launch receipts.', 'python': {'version': sys.version, 'executable': reference(sys.executable)}, 'platform': platform.platform(), 'packages': packages, 'native_solver_wrapper': reference('/workspace/scratch/500ec816102b/solver-runtime/ccx-precision-v2'), 'native_solver_binary': reference('/workspace/scratch/500ec816102b/solver-runtime/root/usr/bin/ccx-precision-v2'), 'native_solver_executed': False, 'dependencies_installed_or_changed': False}  # Preserve the exact observed boundary and avoid a clone-only reproducibility claim.
    if output.exists(): raise FileExistsError(output)  # Never silently overwrite an earlier runtime observation.
    output.write_text(json.dumps(value, indent=2) + '\n'); print(json.dumps({'path': str(output), 'sha256': reference(output)['sha256'], 'packages': packages}))  # Publish a small explicit runtime receipt without training or solver work.
if __name__ == '__main__': main()  # Importing this helper does not write an observation automatically.
