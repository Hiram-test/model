#!/usr/bin/env python3  # Solve the force-found completed-state prestress through native initial stress, exact balancing loads, and delayed automatic cutback checks.
import balanced_transfer_prestress as model  # Reuse the audited equal-area T3D2 main-cable conversion, element-wise native stress tensors, exact balancing loads, permanent-load transfer, result parser, and packaging logic.
ORIGINAL_PRESTRESS_STATE = model.prestress_state  # Preserve the complete audited deck constructor before adding only numerical iteration controls.
MODEL_SCALE = 716.1502048515677 / 701.1096858299724  # Match the model-derived 716.150 kN horizontal main-cable force to the audited scale-one 701.110 kN force target.
model.SCALES = (MODEL_SCALE,)  # Solve only the mechanics-derived completed-state force scale rather than repeating the earlier broad empirical sweep.
def controlled_prestress_state(base_text: str, scale: float) -> tuple[str, int, dict]:  # Add convergence controls without changing any target stress, balancing load, topology, section, support, or permanent action.
    deck, midspan_node, audit = ORIGINAL_PRESTRESS_STATE(base_text, scale)  # Generate the unchanged native-initial-stress and exact-balancing-load model at the force-found scale.
    setup_marker = "*STEP, NAME=PRESTRESS_BALANCE, NLGEOM=YES, AMPLITUDE=STEP, INC=100\n"  # Match the existing fully prestressed balanced initialization step exactly.
    transfer_marker = "*STEP, NAME=TRANSFER_TO_DEAD, NLGEOM=YES, INC=1000\n"  # Match the existing balancing-load-to-permanent-load transfer step exactly.
    field_controls = "*CONTROLS, PARAMETERS=FIELD\n0.006, 0.01, , , 0.02, 1.e-5, 1.e-3, 1.e-8\n"  # Keep force equilibrium at Rn=0.006 while preserving the documented displacement-correction and all other FIELD criteria.
    time_controls = "*CONTROLS, PARAMETERS=TIME INCREMENTATION\n100, 100, 9, 200, 100, 4, , 10, , \n0.25, 0.5, 0.75, 0.85, , , 1.5, \n"  # Delay major-divergence and logarithmic slow-convergence cutbacks to iteration 100, allow 200 Newton iterations and ten cutbacks, and preserve documented cutback factors.
    controls = field_controls + time_controls  # Combine independent equilibrium-accuracy and Newton-iteration controls without modifying physics.
    if setup_marker not in deck: raise RuntimeError("prestress-balance step marker not found")  # Fail closed if the audited initialization path has changed.
    if transfer_marker not in deck: raise RuntimeError("transfer-to-dead step marker not found")  # Fail closed if the audited permanent-load transfer path has changed.
    deck = deck.replace(setup_marker, setup_marker + controls, 1)  # Allow the exactly balanced native prestress state to settle through the known internal MPC residual floor.
    deck = deck.replace(transfer_marker, transfer_marker + controls, 1)  # Apply the same Newton policy while balancing loads are replaced by the unchanged verified permanent loads.
    audit["forceFoundScale"] = MODEL_SCALE  # Persist the analytical-to-audited force-scale conversion used by this final candidate.
    audit["mainCableHorizontalForceTargetN"] = 716150.2048515677  # Persist the force-found horizontal main-cable component in newtons.
    audit["fieldResidualRatioUsed"] = 0.006  # Persist the fixed force-equilibrium residual criterion used after observing the solver-generated residual floor.
    audit["displacementCorrectionCriterionChanged"] = False  # Confirm that displacement-correction accuracy remains at the CalculiX documented default.
    audit["timeIncrementI0Used"] = 100  # Persist the delayed major-residual-growth cutback iteration.
    audit["timeIncrementIRUsed"] = 100  # Persist the delayed logarithmic slow-convergence prediction iteration.
    audit["timeIncrementICUsed"] = 200  # Persist the maximum Newton iterations allowed per increment.
    audit["physicalPrestressMethod"] = "native initial stress on equal-area T3D2 main cables and original T3D2 hangers with exact free-DOF balancing loads"  # State the final physical prestress construction explicitly.
    return deck, midspan_node, audit  # Return the fully auditable force-found full-bridge model and observation node.
model.prestress_state = controlled_prestress_state  # Replace only the deck-construction hook consumed by the existing single-scale main routine.
if __name__ == "__main__": raise SystemExit(model.main())  # Execute the existing full CalculiX solve, geometry audit, receipt generation, and direct-use package creation.
