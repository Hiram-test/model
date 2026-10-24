from pathlib import Path  # Resolve the existing native executable without changing its machine instructions.
import hashlib  # Record both executable identities and the exact bounded repair.
import json  # Publish a reproducible precision-only transformation receipt.
ROOT = Path(__file__).resolve().parents[3]  # Locate this isolated workspace.
source = ROOT / 'solver-runtime/root/usr/bin/ccx'  # Read the original CalculiX 2.21 binary.
target = source.with_name('ccx-precision-v2')  # Preserve the original executable for controlled comparisons.
old = b'(i10,1p,3(1x,e13.6))'  # Identify the original three-component nodal print FORMAT constant.
new = b'(i9,1p,3(1x,e24.16))'  # Emit sixteen decimals with whitespace separation and nine-digit integer IDs.
data = source.read_bytes()  # Capture the exact source executable bytes.
assert hashlib.sha256(data).hexdigest() == '6adaabf5bf0382fc2bfd692b984320ed375dba777f7dc8297562f818043faa1b' and data.count(b'(i10,1p,6(1x,e13.6))') == 1 and len(old) == len(new) and data.count(old) == 1  # Refuse an ambiguous or address-changing binary modification.
offset = data.index(old)  # Record the exact changed read-only data location.
patched = data.replace(old, new).replace(b'(i10,1p,6(1x,e13.6))', b'(i9,1p,6(1x,e24.16))')  # Change only the Fortran output format, never solver arithmetic or criteria.
assert len(patched) == len(data)  # Preserve every executable section and address.
target.write_bytes(patched)  # Save the explicitly named output-precision variant.
target.chmod(0o755)  # Make the isolated native binary executable.
wrapper = ROOT / 'solver-runtime/ccx-precision-v2'  # Publish a distinct solver entry for provenance.
wrapper.write_text((ROOT / 'solver-runtime/ccx').read_text().replace('/usr/bin/ccx ', '/usr/bin/ccx-precision-v2 '))  # Reuse only the established dependency environment.
wrapper.chmod(0o755)  # Permit explicit invocation by the existing runner.
receipt = {'original_sha256': hashlib.sha256(data).hexdigest(), 'precision_sha256': hashlib.sha256(patched).hexdigest(), 'offset': offset, 'displacement_offset': data.index(b'(i10,1p,6(1x,e13.6))'), 'displacement_format': '(i9,1p,6(1x,e24.16))', 'before': old.decode(), 'after': new.decode(), 'machine_instructions_changed': False, 'integer_id_limit': 999999999, 'convergence_tolerances_changed': False}  # Disclose the exact implementation and its integer-width boundary.
(ROOT / 'solver-runtime/precision-repair-v2.json').write_text(json.dumps(receipt, indent=2) + '\n')  # Persist independent reproducibility evidence.
print(json.dumps(receipt))  # Report only the bounded precision repair identity.
