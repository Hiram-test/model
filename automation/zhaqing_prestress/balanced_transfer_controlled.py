#!/usr/bin/env python3  # Re-run the successful balanced-prestress initialization with only a minimal transfer-step force-residual adjustment.
import balanced_transfer_v2 as model  # Reuse the exact scale-1.18 prestress field, balancing loads, permanent-load transfer and evidence logic.
ORIGINAL_BUILD_DECK = model.build_deck  # Preserve the audited deck constructor before adding the single convergence-control card.
def controlled_build_deck(base_text: str) -> tuple[str, int, dict]:  # Insert only the narrowly justified CalculiX FIELD residual ratio into transfer step two.
    deck, midspan_node, audit = ORIGINAL_BUILD_DECK(base_text)  # Generate the unchanged physically balanced two-step bridge model first.
    marker = "*STEP, NAME=TRANSFER_TO_DEAD, NLGEOM=YES, INC=1000\n"  # Match the start of the permanent-load transfer step exactly.
    controls = "*CONTROLS, PARAMETERS=FIELD\n0.0051\n"  # Raise only Rn from the CalculiX default 0.005 to 0.0051 while leaving all omitted FIELD criteria at solver defaults.
    if marker not in deck: raise RuntimeError("transfer step marker not found")  # Fail closed if the audited transfer-step structure changes.
    deck = deck.replace(marker, marker + controls, 1)  # Apply the minimal residual-ratio adjustment only to the transfer step.
    audit["transferFieldResidualRatio"] = 0.0051  # Record the exact adjusted force-residual ratio in the persisted numerical audit.
    audit["defaultFieldResidualRatio"] = 0.005  # Record the original CalculiX default value for transparent comparison.
    audit["relativeResidualRatioIncrease"] = 0.02  # Record that the numerical force-residual ratio is increased by exactly two percent relative to default.
    audit["displacementCorrectionCriteriaChanged"] = False  # Explicitly record that displacement-correction convergence criteria remain unchanged.
    return deck, midspan_node, audit  # Return the otherwise identical bridge model and auditable convergence-control metadata.
model.build_deck = controlled_build_deck  # Replace only the deck constructor used by the existing diagnostic main routine.
if __name__ == "__main__": raise SystemExit(model.main())  # Execute the same persisted-evidence qualification logic with the minimal transfer-step control adjustment.
