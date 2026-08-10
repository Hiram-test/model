#!/usr/bin/env python3  # Add the CalculiX-required zero thermal initial state without changing the audited constitutive-prestress mechanics.
import balanced_thermal_transfer as model  # Reuse the complete element-specific contraction, balancing-load and permanent-load transfer implementation.
ORIGINAL_BUILD_DECK = model.build_deck  # Preserve the audited constitutive-prestress deck constructor before the syntax-only correction.
def corrected_build_deck(base_text: str) -> tuple[str, int, dict]:  # Insert only the required thermal initial condition before the first mechanical step.
    deck, midspan_node, audit = ORIGINAL_BUILD_DECK(base_text)  # Generate the unchanged two-step constitutive-prestress model first.
    marker = "*STEP, NAME=BUILD_PRESTRESS, NLGEOM=YES, INC=1000\n"  # Match the start of the prestress-building step exactly.
    initial = "*INITIAL CONDITIONS, TYPE=TEMPERATURE\nPRETENSION_NODES, 0.\n"  # Define zero initial temperature so subsequent mechanical-step temperature loading has a valid reference state.
    if marker not in deck: raise RuntimeError("prestress-build step marker not found")  # Fail closed if the audited step structure changes.
    deck = deck.replace(marker, initial + marker, 1)  # Insert the syntax-required zero thermal state without modifying any force, strain, mesh or support value.
    audit["initialTemperatureC"] = 0.0  # Record the explicit zero reference temperature in the persisted audit.
    return deck, midspan_node, audit  # Return the otherwise identical bridge model and updated audit metadata.
model.build_deck = corrected_build_deck  # Replace only the model constructor used by the existing persisted-evidence main routine.
if __name__ == "__main__": raise SystemExit(model.main())  # Execute the same nonlinear qualification logic after the syntax-only thermal initialization correction.
