#!/usr/bin/env python3  # Initialize the constitutive suspension prestress as a fully balanced thermal state while keeping NLGEOM active in every mechanical step.
import balanced_thermal_transfer as model  # Reuse the audited element-specific contraction field, exact balancing loads and verified permanent-load transfer logic.
ORIGINAL_BUILD_DECK = model.build_deck  # Preserve the audited constitutive-prestress deck constructor before changing only how the prestress state enters step one.
def initial_state_build_deck(base_text: str) -> tuple[str, int, dict]:  # Replace the prestress ramp with a full initial thermal state and full exact balancing load in the first NLGEOM equilibrium step.
    deck, midspan_node, audit = ORIGINAL_BUILD_DECK(base_text)  # Generate the unchanged constitutive-prestress target field and permanent-load transfer model first.
    old_block = "*STEP, NAME=BUILD_PRESTRESS, NLGEOM=YES, INC=1000\n*STATIC\n0.01, 1.0, 1.E-8, 0.02\n*TEMPERATURE\nPRETENSION_NODES, -1.18\n*CLOAD\n"  # Match the original proportional prestress-building procedure exactly.
    new_block = "*INITIAL CONDITIONS, TYPE=TEMPERATURE\nPRETENSION_NODES, -1.18\n*STEP, NAME=BUILD_PRESTRESS, NLGEOM=YES, AMPLITUDE=STEP, INC=200\n*STATIC\n1.0, 1.0\n*CLOAD\n"  # Start from the full constitutive contraction and apply the exact opposite balancing loads immediately in the first nonlinear equilibrium state.
    if old_block not in deck:  # Require the audited prestress-build block before making the isolated initialization substitution.
        raise RuntimeError("constitutive prestress-build block not found")  # Fail closed if the source model changes unexpectedly.
    deck = deck.replace(old_block, new_block, 1)  # Change only the entry path to the same target prestress and balancing-load state.
    audit["initialTemperatureC"] = -1.18  # Record that the full target constitutive contraction exists from the initial mechanical state.
    audit["prestressBuildGeometryNonlinear"] = True  # Record that geometric nonlinearity remains active from the first mechanical equilibrium onward.
    audit["prestressBuildAmplitude"] = "STEP"  # Record that the exact balancing loads are fully present from the first Newton iteration.
    audit["prestressRampUsed"] = False  # Record that no incremental temperature ramp is used to build the target prestress.
    audit["prestressTargetsChanged"] = False  # Record that cable and hanger target forces remain identical to the audited scale-1.18 construction.
    audit["verifiedPermanentLoadsChanged"] = False  # Record that the verified PR9 permanent loads remain unchanged.
    return deck, midspan_node, audit  # Return the otherwise identical all-NLGEOM bridge model and updated initialization audit metadata.
model.build_deck = initial_state_build_deck  # Replace only the constructor used by the existing persisted-evidence main routine.
if __name__ == "__main__":  # Execute the diagnostic only when this file is invoked as the workflow entry point.
    raise SystemExit(model.main())  # Propagate the same final-state qualification status after the balanced initial thermal-state correction.
