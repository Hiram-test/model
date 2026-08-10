from pathlib import Path  # Use deterministic filesystem paths for the immutable baseline and generated perturbation decks.
import importlib.util  # Load the already-audited native prestress modules exported by the workflow without duplicating their mechanics logic.
import json  # Persist the exact prestress scales and generated-model provenance beside the numerical comparison.
import sys  # Receive the validated PR9 baseline, exported native-module directory, and output directory from the workflow.
if len(sys.argv) != 4:  # Require one immutable baseline, one audited module directory, and one explicit generated-model directory.
    raise SystemExit('usage: perturbation_prestress_test.py BASELINE_INP NATIVE_MODULE_DIR OUTPUT_DIR')  # Stop explicitly when workflow invocation is incomplete.
base_path = Path(sys.argv[1]).resolve()  # Resolve the already-solved PR9 LC01 mother-model input deck.
module_dir = Path(sys.argv[2]).resolve()  # Resolve the temporary directory containing audited native prestress modules from the existing solver branch.
out_dir = Path(sys.argv[3]).resolve()  # Resolve the isolated directory for the zero-stress and prestressed perturbation decks.
out_dir.mkdir(parents=True, exist_ok=True)  # Create the generated-model directory before writing any solver inputs.
sys.path.insert(0, str(module_dir))  # Make the audited prestress modules importable without copying their source into this experimental script.
spec = importlib.util.spec_from_file_location('balanced_transfer_prestress', module_dir / 'balanced_transfer_prestress.py')  # Build an explicit import specification for the audited balanced-transfer prestress constructor.
if spec is None or spec.loader is None:  # Refuse to proceed if Python cannot load the audited native prestress implementation.
    raise RuntimeError('cannot load audited balanced-transfer prestress module')  # Stop before generating any ambiguous finite-element deck.
balanced = importlib.util.module_from_spec(spec)  # Create the module object that will expose the audited prestress-state constructor.
spec.loader.exec_module(balanced)  # Execute the audited module definitions without invoking its guarded command-line calibration main function.
base_text = base_path.read_text(encoding='ascii')  # Load the exact validated L2 mother deck once so both comparison models share identical non-prestress content.
PRESTRESS_SCALE = 1.0214524479201714  # Use the previously force-found native prestress scale corresponding to approximately 716.15 kN main-cable horizontal force.
TEST_LOAD_N = -1000.0  # Apply the same small downward one-kilonewton perturbation at validated bridge midspan in both comparison models.
MIDSPAN_NODE = 291  # Use the validated bridge-deck centerline midspan node already employed throughout PR9 response checks.
def perturbation_deck(scale: float) -> tuple[str, dict]:  # Build one prestress-linearized static deck from the audited native stress construction.
    full_deck, midspan_node, audit = balanced.prestress_state(base_text, scale)  # Reuse the audited B31-to-equal-area-T3D2 cable conversion and elementwise main-cable/hanger native initial stresses.
    if midspan_node != MIDSPAN_NODE:  # Require the audited mechanics module to identify the same frozen bridge midspan node.
        raise RuntimeError(f'unexpected midspan node {midspan_node}')  # Stop rather than silently comparing different response locations.
    prefix = full_deck.split('*STEP, NAME=PRESTRESS_BALANCE', 1)[0]  # Keep only the complete model definition and native initial-stress field while discarding the known-failing NLGEOM equilibrium steps.
    step = '*STEP, PERTURBATION\n*STATIC\n*CLOAD\n' + f'{MIDSPAN_NODE}, 3, {TEST_LOAD_N:.12g}\n' + '*NODE PRINT, NSET=PRESTRESS_CALIBRATION, FREQUENCY=1\nU, RF\n*NODE PRINT, NSET=MONITOR, FREQUENCY=1\nU, RF\n*EL PRINT, ELSET=MAIN_CABLES, FREQUENCY=1\nS, E\n*EL PRINT, ELSET=HANGERS, FREQUENCY=1\nS, E\n*NODE FILE, FREQUENCY=1\nU, RF\n*EL FILE, FREQUENCY=1\nS, E\n*END STEP\n'  # Request CalculiX second-order perturbation static response about the supplied initial-stress state without invoking finite-rotation Newton updates.
    deck = prefix + step  # Assemble the complete prestress-linearized finite-element input deck.
    return deck, audit  # Return both solver text and the exact mechanics-derived initial-stress audit used to create it.
zero_deck, zero_audit = perturbation_deck(0.0)  # Build the zero-initial-stress control using the same equal-area T3D2 main-cable topology as the prestressed model.
prestress_deck, prestress_audit = perturbation_deck(PRESTRESS_SCALE)  # Build the force-found initial-stress model using the exact same topology and perturbation load.
(out_dir / 'ZQ_PERT_ZERO.inp').write_text(zero_deck, encoding='ascii')  # Persist the zero-stress second-order static control input.
(out_dir / 'ZQ_PERT_PRESTRESS.inp').write_text(prestress_deck, encoding='ascii')  # Persist the force-found prestressed second-order static input.
provenance = {'baseline': str(base_path), 'prestressScale': PRESTRESS_SCALE, 'mainCableHorizontalForceTargetN': 716150.2048515677, 'testLoadNode': MIDSPAN_NODE, 'testLoadDof': 3, 'testLoadN': TEST_LOAD_N, 'zeroStressAssignments': len(zero_audit['stressAssignments']), 'prestressAssignments': len(prestress_audit['stressAssignments']), 'mainCableRepresentation': prestress_audit['mainCableRepresentationAfter'], 'analysis': 'STEP PERTURBATION plus STATIC second-order incremental response'}  # Record the exact comparison contract independently of the numerical solver output.
(out_dir / 'generation_summary.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')  # Persist the complete generation receipt for audit and later mother-model handoff.
print(json.dumps(provenance, indent=2))  # Mirror the same deterministic generation receipt into the GitHub Actions log.
