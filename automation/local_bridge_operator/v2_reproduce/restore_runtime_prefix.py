import argparse,hashlib,json,os,shutil # Materialize only the private runtime prefix, never system libraries.
from pathlib import Path # Keep restoration paths explicit and auditable.
HERE=Path(__file__).resolve().parent;ORIGINAL=Path('/workspace/scratch/500ec816102b/solver-runtime') # The unchanged wrapper contains this exact absolute prefix.
parser=argparse.ArgumentParser();parser.add_argument('--destination',required=True);args=parser.parse_args();destination=Path(args.destination) # Require the operator to name the isolated restoration destination.
assert destination==ORIGINAL,'A different prefix needs a separately identified configuration and new execution lock; this utility does not rewrite the original wrapper' # Do not imply that relocation preserves the frozen execution identity.
assert not destination.exists(),'Refuse to overwrite an existing runtime; restore in an empty isolated environment' # Protect the active installation and all user files.
manifest=json.loads((HERE/'runtime_manifest.json').read_text());payload=HERE/'runtime_prefix';assert payload.is_dir() # Read the authenticated archive manifest and its private-prefix subtree.
def digest(path): # Verify copied bytes without executing any solver or library.
    h=hashlib.sha256() # Use the same content identifier as the packaging receipt.
    with path.open('rb') as stream: # Bound temporary memory during verification.
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block) # Stream full source bytes.
    return h.hexdigest() # Return the complete SHA256 digest.
expected=[item for item in manifest['files'] if item['archive_path'].startswith('runtime_prefix/')] # System snapshots and licenses are not installation inputs.
assert all(digest(HERE/item['archive_path'])==item['sha256'] for item in expected) # Verify the extracted payload before creating the destination.
destination.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(payload,destination) # Copy only the private prefix into the explicitly empty isolated path.
for alias in manifest['private_prefix_symlinks']: # Recreate only the original recorded private-prefix aliases.
    target=destination/alias['relative_path'];assert not target.exists() and not target.is_symlink();target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(alias['link_target']) # Preserve original alias semantics without replacing any existing path.
assert all(digest(destination/Path(item['archive_path']).relative_to('runtime_prefix'))==item['sha256'] for item in expected) # Verify all restored regular-file bytes.
assert all(digest(destination/alias['relative_path'])==alias['target_sha256'] for alias in manifest['private_prefix_symlinks']) # Verify that every restored alias resolves to its expected target bytes.
print(json.dumps({'status':'PRIVATE_PREFIX_BYTES_RESTORED','destination':str(destination),'solver_calls':0,'system_libraries_installed':False,'host_ABI_compatibility_verified':False},indent=2)) # Restoration alone is not a numerical replay or an ABI compatibility certification.
