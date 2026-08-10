#!/usr/bin/env python3  # Execute the audited controlled equilibrium with a fixed conservative maximum increment.
import controlled_equilibrium as model  # Reuse the complete scale-1.18 prestress construction, FIELD controls and physical-node audit.
model.INITIAL_INCREMENT = 0.005  # Start each completed-state ramp at one two-hundredth of the full permanent-load/prestress state.
model.MAX_INCREMENT = 0.005  # Prevent CalculiX automatic growth beyond the increment size already observed to satisfy the unchanged residual criterion.
if __name__ == "__main__":  # Run only when invoked as the dedicated conservative workflow entry point.
    raise SystemExit(model.main())  # Propagate the same controlled-equilibrium qualification gate without changing any other numerical setting.
