#!/usr/bin/env python3  # Build the constitutive suspension prestress in a linear equilibrium step before the nonlinear permanent-load transfer.
import balanced_thermal_transfer as model  # Reuse the audited element-specific contraction field, exact balancing loads and verified permanent-load transfer logic.
ORIGINAL_BUILD_DECK = model.build_deck  # Preserve the audited constitutive-prestress deck constructor before changing only the prestress-build procedure.
def linear_build_deck(base_text: str) -> tuple[str, int, dict]:  # Replace only the prestress-build step with a linear static equilibrium at the frozen completed geometry.
    deck, midspan_node, audit = ORIGINAL_BUILD_DECK(base_text)  # Generate the unchanged two-step constitutive-prestress bridge model first.
    old_step = "*STEP, NAME=BUILD_PRESTRESS, NLGEOM=YES, INC=1000\n*STATIC\n0.01, 1.0, 1.E-8, 0.02\n"  # Match the original nonlinear prestress-build procedure exactly.
    new_step = "*INITIAL CONDITIONS, TYPE=TEMPERATURE\nPRETENSION_NODES, 0.\n*STEP, NAME=BUILD_PRESTRESS\n*STATIC\n1.0, 1.0\n"  # Define the required zero thermal reference and solve the proportional contraction-plus-balancing-load state linearly at the frozen geometry.
    if old_step not in deck:  # Require the audited prestress-build step before making the isolated procedural substitution.
        raise RuntimeError("nonlinear prestress-build step marker not found")  # Fail closed if the source model changes unexpectedly.
    deck = deck.replace(old_step, new_step, 1)  # Change only the prestress-build solution procedure while preserving every target force, temperature and balancing load value.
    audit["initialTemperatureC"] = 0.0  # Record the explicit zero thermal reference state required by CalculiX.
    audit["prestressBuildGeometryNonlinear"] = False  # Record that the exactly balanced prestress construction is solved at the frozen completed geometry.
    audit["prestressBuildStaticIncrement"] = [1.0, 1.0]  # Record that the linear proportional prestress state is obtained in one static equilibrium solve.
    audit["transferGeometryNonlinear"] = True  # Record that geometric nonlinearity remains active during balancing-load removal and verified permanent-load application.
    audit["prestressTargetsChanged"] = False  # Record that no cable or hanger prestress target has changed relative to the audited scale-1.18 construction.
    audit["verifiedPermanentLoadsChanged"] = False  # Record that no verified PR9 permanent load has changed.
    return deck, midspan_node, audit  # Return the otherwise identical bridge model and updated procedural audit metadata.
model.build_deck = linear_build_deck  # Replace only the constructor used by the existing persisted-evidence main routine.
if __name__ == "__main__":  # Execute the diagnostic only when this file is invoked as the workflow entry point.
    raise SystemExit(model.main())  # Propagate the same nonlinear final-state qualification status after the linear prestress-build correction.
