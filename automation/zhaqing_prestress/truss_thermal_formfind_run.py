#!/usr/bin/env python3  # Execute the audited direct truss-cable form-finding model with the shared CalculiX solver helper bound explicitly.
import truss_thermal_formfind as model  # Reuse the unchanged direct nonlinear form-finding generator, scale sweep and evidence logic.
model.source.solve_trial = model.source.core.solve_trial  # Bind the solver call to the audited shared prestress-isolation helper without altering any bridge modeling parameter.
RUN_CONTRACT = "isolated-final-formfind-v1"  # Record a harmless workflow-trigger contract string without changing any bridge or solver parameter.
if __name__ == "__main__":  # Execute only when this wrapper is invoked as the workflow entry point.
    raise SystemExit(model.main())  # Propagate the unchanged direct form-finding qualification status to GitHub Actions.
