from pathlib import Path  # Use deterministic filesystem paths for the immutable PR9 baseline and generated prestress-reference comparison models.
import importlib.util  # Load the already-audited native prestress constructor exported by the workflow without duplicating force-model logic.
import json  # Persist the exact comparison contract and prestress metadata beside the generated solver decks.
import sys  # Receive the validated baseline, audited module directory, and output directory from GitHub Actions.
if len(sys.argv) != 4:  # Require one immutable baseline, one audited module directory, and one explicit generated-model directory.
    raise SystemExit('usage: prestress_reference_perturbation.py BASELINE_INP NATIVE_MODULE_DIR OUTPUT_DIR')  # Stop clearly when workflow invocation is incomplete.
base_path = Path(sys.argv[1]).resolve()  # Resolve the already-solved PR9 LC01 mother-model input deck.
module_dir = Path(sys.argv[2]).resolve()  # Resolve the temporary directory containing the audited native prestress modules.
out_dir = Path(sys.argv[3]).resolve()  # Resolve the isolated directory for low- and design-prestress reference models.
out_dir.mkdir(parents=True, exist_ok=True)  # Create the generated-model directory before writing solver inputs.
sys.path.insert(0, str(module_dir))  # Make the audited prestress modules importable without copying their source into this experimental implementation.
spec = importlib.util.spec_from_file_location('balanced_transfer_prestress', module_dir / 'balanced_transfer_prestress.py')  # Build an explicit import specification for the audited native stress and balancing-load constructor.
if spec is None or spec.loader is None:  # Refuse to proceed if Python cannot load the audited prestress implementation.
    raise RuntimeError('cannot load audited balanced-transfer prestress module')  # Stop before generating an ambiguous finite-element deck.
balanced = importlib.util.module_from_spec(spec)  # Create the module object exposing the audited completed-state prestress constructor.
spec.loader.exec_module(balanced)  # Execute the audited definitions without invoking their guarded nonlinear calibration main function.
base_text = base_path.read_text(encoding='ascii')  # Load the exact validated L2 mother model once so both comparison states share identical non-prestress content.
MIDSPAN_NODE = 291  # Use the frozen bridge-deck centerline midspan monitor node from the validated PR9 model.
TEST_LOAD_N = -1000.0  # Apply one identical downward one-kilonewton perturbation after each prestressed reference state is initialized.
SCALES = {'LOW': 0.5, 'DESIGN': 1.0214524479201714}  # Compare two positive prestress states so both equal-area T3D2 cable systems possess geometric stiffness.
def build_reference(scale: float) -> tuple[str, dict]:  # Build a two-step model: balanced linear prestress reference followed by second-order static perturbation.
    nonlinear_deck, midspan_node, audit = balanced.prestress_state(base_text, scale)  # Reuse the audited equal-area T3D2 main-cable conversion, elementwise initial stress, and exact free-DOF balancing loads.
    if midspan_node != MIDSPAN_NODE:  # Require the audited force model to identify the same frozen bridge midspan monitor.
        raise RuntimeError(f'unexpected midspan node {midspan_node}')  # Stop rather than compare responses at inconsistent physical locations.
    prefix, remainder = nonlinear_deck.split('*STEP, NAME=PRESTRESS_BALANCE', 1)  # Preserve the complete model definition and initial-stress field while isolating the generated balancing step.
    setup_body, _unused_transfer = remainder.split('*END STEP\n', 1)  # Keep only the exact initial balancing CLOAD step and discard the known-failing nonlinear transfer-to-dead-load path.
    setup = '*STEP, NAME=PRESTRESS_REFERENCE, AMPLITUDE=STEP\n' + setup_body.split('\n', 1)[1] + '*END STEP\n'  # Recast the same exact balancing-load step as geometrically linear static so it can establish the prestressed base stress field without finite-rotation KNOT updates.
    setup = setup.replace('*STATIC\n1.0, 1.0\n', '*STATIC\n1.0, 1.0\n', 1)  # Preserve the one-step linear equilibrium solve explicitly while documenting that no nonlinear increment controls are introduced.
    perturbation = '*STEP, PERTURBATION\n*STATIC\n*CLOAD\n' + f'{MIDSPAN_NODE}, 3, {TEST_LOAD_N:.12g}\n' + '*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*NODE PRINT, NSET=MONITOR, FREQUENCY=1\nU, RF\n*EL PRINT, ELSET=MAIN_CABLES, FREQUENCY=1\nS, E\n*EL PRINT, ELSET=HANGERS, FREQUENCY=1\nS, E\n*NODE FILE, FREQUENCY=1\nU, RF\n*EL FILE, FREQUENCY=1\nS, E\n*END STEP\n'  # Ask CalculiX for a second-order static increment about the converged prestressed base stress field while avoiding the NLGEOM Newton path.
    deck = prefix + setup + perturbation  # Assemble the complete prestressed-reference and perturbation model.
    return deck, audit  # Return both solver input text and exact mechanics-derived prestress/balancing-load audit metadata.
summary = {'baseline': str(base_path), 'midspanNode': MIDSPAN_NODE, 'testLoadN': TEST_LOAD_N, 'analysisPath': 'LINEAR PRESTRESS_REFERENCE then STEP PERTURBATION + STATIC', 'mainCableHorizontalForceAtDesignScaleN': 716150.2048515677, 'cases': {}}  # Initialize the model-generation receipt independently of solver output.
for label, scale in SCALES.items():  # Generate the low- and design-prestress models using the same topology and external perturbation.
    deck, audit = build_reference(scale)  # Construct one balanced prestress reference and second-order perturbation deck.
    stem = f'ZQ_REF_{label}'  # Create a deterministic short CalculiX basename for this prestress level.
    (out_dir / f'{stem}.inp').write_text(deck, encoding='ascii')  # Persist the exact solver input for this comparison state.
    summary['cases'][label] = {'scale': scale, 'stem': stem, 'stressAssignments': len(audit['stressAssignments']), 'balancingLoadComponentCount': audit['balancingLoadComponentCount'], 'balancingLoadVectorNormN': audit['balancingLoadVectorNormN'], 'mainCableRepresentation': audit['mainCableRepresentationAfter']}  # Record the load-bearing construction metadata for this state.
(out_dir / 'generation_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')  # Persist the complete generation receipt beside both solver decks.
print(json.dumps(summary, indent=2))  # Mirror the exact comparison contract into the GitHub Actions log.
