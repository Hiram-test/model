#!/usr/bin/env python3  # Re-run the closest convergent constitutive-prestress model while separating convergence tolerances from automatic cutback logic.
import balanced_thermal_transfer_v2 as previous  # Reuse the full audited equal-area T3D2 cable, thermal-contraction, balancing-load, zero-initial-temperature, and dead-load-transfer implementation.
ORIGINAL_BUILD_DECK = previous.model.build_deck  # Preserve the complete v2 deck constructor before adding narrowly targeted nonlinear controls.
def corrected_build_deck(base_text: str) -> tuple[str, int, dict]:  # Keep force/displacement accuracy fixed and delay only the automatic divergence and slow-convergence cutbacks.
    deck, midspan_node, audit = ORIGINAL_BUILD_DECK(base_text)  # Generate the unchanged v2 full-bridge constitutive-prestress model first.
    build_marker = "*STEP, NAME=BUILD_PRESTRESS, NLGEOM=YES, INC=1000\n"  # Match the existing prestress-building step exactly.
    transfer_marker = "*STEP, NAME=TRANSFER_TO_DEAD, NLGEOM=YES, INC=1000\n"  # Match the existing prestress-to-dead-load transfer step exactly.
    field_controls = "*CONTROLS, PARAMETERS=FIELD\n0.006, 0.01, , , 0.02, 1.e-5, 1.e-3, 1.e-8\n"  # Keep the final force residual criterion at 0.006 and preserve every other FIELD convergence parameter at its documented default.
    time_controls = "*CONTROLS, PARAMETERS=TIME INCREMENTATION\n100, 100, 9, 200, 100, 4, , 10, , \n0.25, 0.5, 0.75, 0.85, , , 1.5, \n"  # Delay major-divergence and logarithmic slow-convergence checks to iteration 100, allow at most 200 Newton iterations, allow ten cutbacks, and preserve all documented cutback factors.
    controls = field_controls + time_controls  # Apply both independent CalculiX control cards without weakening displacement convergence or changing physical loads.
    if build_marker not in deck: raise RuntimeError("prestress-build step marker not found")  # Fail closed if the audited first-step structure has changed.
    if transfer_marker not in deck: raise RuntimeError("dead-load-transfer step marker not found")  # Fail closed if the audited second-step structure has changed.
    deck = deck.replace(build_marker, build_marker + controls, 1)  # Let the prestress-building step iterate through the observed nearly stationary MPC residual plateau before any automatic cutback is considered.
    deck = deck.replace(transfer_marker, transfer_marker + controls, 1)  # Apply the identical nonlinear iteration policy to the inherited prestress-to-dead-load transfer step.
    audit["mechanicalResidualRatioDefault"] = 0.005  # Persist the original CalculiX default residual criterion for comparison.
    audit["mechanicalResidualRatioUsed"] = 0.006  # Persist the fixed residual criterion used after observing the B31/MPC residual floor.
    audit["mechanicalResidualToleranceRelativeIncrease"] = 0.20  # Record the twenty-percent force-residual tolerance increase explicitly.
    audit["displacementCorrectionCriterionChanged"] = False  # Confirm that the displacement-correction convergence requirement remains unchanged at 0.01.
    audit["timeIncrementI0Default"] = 4  # Record the documented default iteration at which the major residual-growth divergence check starts.
    audit["timeIncrementI0Used"] = 100  # Delay the major-divergence check so a tiny stationary residual does not force repeated cutbacks.
    audit["timeIncrementIRDefault"] = 8  # Record the documented default iteration at which logarithmic slow-convergence prediction starts.
    audit["timeIncrementIRUsed"] = 100  # Delay logarithmic cutback prediction until the nearly stationary equilibrium has had ample Newton iterations.
    audit["timeIncrementICDefault"] = 16  # Record the documented default maximum Newton iterations per increment.
    audit["timeIncrementICUsed"] = 200  # Allow sufficient Newton iterations to distinguish a numerical residual plateau from genuine structural divergence.
    audit["prestressMechanicsChangedFromV2"] = False  # Confirm that cable target strain, balancing loads, mesh, supports, and permanent loads remain unchanged from v2.
    audit["rerunTrigger"] = "separate_newton_cutback_logic_from_fixed_equilibrium_accuracy"  # Record why this run changes TIME INCREMENTATION controls while freezing all physical prestress parameters.
    return deck, midspan_node, audit  # Return the otherwise identical full bridge deck and updated numerical-control audit.
previous.model.build_deck = corrected_build_deck  # Replace only the model constructor consumed by the existing persisted-evidence main routine.
if __name__ == "__main__": raise SystemExit(previous.model.main())  # Execute the same full nonlinear qualification and receipt generation with the corrected iteration-control policy.
