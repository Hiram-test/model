#!/usr/bin/env python3  # Execute a narrow residual-minimization sweep using the audited element-wise generator.
import elementwise_prestress as model  # Reuse the exact element-wise force construction, solver parser and evidence writer.
model.SCALES = (1.14, 1.16, 1.18, 1.20, 1.22, 1.24, 1.26)  # Resolve the residual-envelope minimum around the coarse 1.1-to-1.2 transition.
if __name__ == "__main__":  # Run the fine sweep only when invoked as the workflow entry point.
    raise SystemExit(model.main())  # Propagate the same clean-equilibrium gate while preserving all failed-trial residual evidence.
