from pathlib import Path  # Locate the pinned native executable and immutable evidence.
import hashlib  # Identify every source and resulting native binary.
import json  # Persist an auditable output-only transformation receipt.
import struct  # Inspect ELF sections without relying on external binary tools.
import tarfile  # Read the exact pinned CalculiX printing routines.
ROOT = Path(__file__).resolve().parents[3]  # Resolve the workspace containing the native runtime.
REPO = Path(__file__).resolve().parents[2]  # Resolve repository evidence independently of the current directory.
source = ROOT / 'solver-runtime/root/usr/bin/ccx'  # Keep the original executable unchanged.
target = source.with_name('ccx-complex-precision-v3')  # Give the precision variant a distinct executable identity.
data = source.read_bytes()  # Inspect the exact original native solver bytes.
assert hashlib.sha256(data).hexdigest() == '6adaabf5bf0382fc2bfd692b984320ed375dba777f7dc8297562f818043faa1b'  # Reject a different or already modified solver.
assert data[:6] == b'\x7fELF\x02\x01'  # Require the known little-endian ELF64 layout.
header = struct.unpack_from('<16sHHIQQQIHHHHHH', data, 0)  # Decode the standard ELF64 header.
sections = [struct.unpack_from('<IIQQQQIIQQ', data, header[6] + index * header[11]) for index in range(header[12])]  # Decode every section descriptor.
names_section = sections[header[13]]  # Find the section-name string table.
names = data[names_section[4]:names_section[4] + names_section[5]]  # Read only the declared section-name bytes.
section_names = [names[item[0]:].split(b'\0', 1)[0].decode() for item in sections]  # Resolve names for changed-region checks.
formats = ['(i10,1p,3(1x,e13.6))', '(i10,1p,6(1x,e13.6))', '(i10,1x,1p,e13.6)', '(i10,1x,i3,1p,3(1x,e13.6))', '(i10,1x,i3,1p,6(1x,e13.6))', '(i10,1x,i3,1p,99(1x,e13.6))']  # Cover native nodal vectors, temperature, IP flux, stress, and material state.
patched = data  # Apply fixed-length substitutions to a separate immutable byte value.
changes = []  # Retain exact before/after constants and offsets.
for value in formats:  # Restrict edits to six explicitly identified printing constants.
    old = value.encode()  # Encode the exact original Fortran FORMAT text.
    new = value.replace('i10', 'i9', 1).replace('e13.6', 'e24.16').encode()  # Trade one integer-width character for an extra exponent-format digit.
    assert len(old) == len(new) and data.count(old) == 1  # Refuse address changes and ambiguous replacements.
    offset = data.index(old)  # Locate the unique original constant.
    owners = [(name, section) for name, section in zip(section_names, sections) if section[4] <= offset and offset + len(old) <= section[4] + section[5]]  # Find its complete containing section.
    assert len(owners) == 1 and owners[0][0] == '.rodata' and not owners[0][1][2] & 4  # Restrict every edit to nonexecutable read-only data.
    patched = patched[:offset] + new + patched[offset + len(old):]  # Preserve binary length and every address.
    changes.append({'offset': offset, 'section': owners[0][0], 'before': value, 'after': new.decode()})  # Record the bounded output change.
assert len(patched) == len(data)  # Confirm the complete executable size is unchanged.
executable_sections = []  # Record independent checks on every executable section.
for name, section in zip(section_names, sections):  # Inspect machine instructions directly rather than relying on format intent.
    if section[2] & 4:  # Select sections carrying the ELF executable-instructions flag.
        before = data[section[4]:section[4] + section[5]]  # Capture original instruction bytes.
        after = patched[section[4]:section[4] + section[5]]  # Capture corresponding precision-variant bytes.
        assert before == after  # Reject any machine-instruction change.
        executable_sections.append({'name': name, 'bytes': len(before), 'sha256': hashlib.sha256(before).hexdigest()})  # Persist exact unchanged machine-code identities.
archive = REPO / 'build/completion-audit-20261024/source/ccx_2.21.src.tar.bz2'  # Use the pinned official source downloaded during the earlier audit.
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '52a20ef7216c6e2de75eae460539915640e3140ec4a2f631a9301e01eda605ad'  # Verify source provenance before attributing printing formats.
routines = {}  # Preserve printing-routine identities and line numbers.
with tarfile.open(archive, 'r:bz2') as bundle:  # Read source without extracting or modifying the archive.
    for name in ('printoutnode.f', 'printoutint.f'):  # Cover the native routines responsible for the patched fields.
        payload = bundle.extractfile('./CalculiX/ccx_2.21/src/' + name).read()  # Read the exact member bytes.
        routines[name] = {'sha256': hashlib.sha256(payload).hexdigest(), 'matching_lines': [{'line': number, 'text': line.strip()} for number, line in enumerate(payload.decode().splitlines(), 1) if any(value in line for value in formats)]}  # Tie each output format to native source evidence.
target.write_bytes(patched)  # Create the distinct precision-only native executable.
target.chmod(0o755)  # Permit the existing native runner to invoke the variant.
wrapper = ROOT / 'solver-runtime/ccx-complex-precision-v3'  # Keep the v2 launcher available for controlled comparisons.
wrapper.write_text((ROOT / 'solver-runtime/ccx-precision-v2').read_text().replace('/usr/bin/ccx-precision-v2 ', '/usr/bin/ccx-complex-precision-v3 '))  # Reuse the established dependency environment without changing solver arguments.
wrapper.chmod(0o755)  # Make the explicit variant launcher executable.
receipt = {'original_sha256': hashlib.sha256(data).hexdigest(), 'precision_sha256': hashlib.sha256(patched).hexdigest(), 'source_archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'changes': changes, 'executable_sections': executable_sections, 'printing_routines': routines, 'machine_instructions_changed': False, 'convergence_tolerances_changed': False, 'integer_id_limit': 999999999, 'wrapper': str(wrapper), 'scope': 'DAT output precision only; native arithmetic and FRD output unchanged'}  # Disclose provenance and limits without claiming solver-method changes.
evidence = REPO / 'build/complex-nonlinear-20261024/audit/precision_v3'  # Keep reproducible evidence with the current scientific campaign.
evidence.mkdir(parents=True, exist_ok=True)  # Prepare the dedicated audit directory.
for path in (ROOT / 'solver-runtime/precision-repair-v3.json', evidence / 'precision_repair.json'):  # Retain runtime and campaign copies of the same receipt.
    path.write_text(json.dumps(receipt, indent=2) + '\n')  # Persist exact JSON with stable readable formatting.
print(json.dumps({'wrapper': str(wrapper), 'precision_sha256': receipt['precision_sha256'], 'changed_formats': len(changes), 'unchanged_executable_sections': len(executable_sections)}))  # Report compact verification metadata.
