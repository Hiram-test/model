# C20 both-end pin failure

- MAPDL ERROR: node 2027671 UX = 6.30e9 mm > NCNV 1e6. Node is a passage chord at (3887593, 24860, 88733), not a post node.
- ERR also: extremely large pivot ratio / rigid-body motion.
- Pin CERIG equations are kinematically correct (UX_s = UX_m + 87.5 ROTY_m, UY_s = UY_m - 87.5 ROTX_m, ROTY free).
- Cause: 568 pins = both top and bottom of every post release ROTY. Each portal becomes a linear parallelogram mechanism in the XZ plane. First equilibrium iteration has no bending stiffness about Y, so the gates/passages run away in UX.
- Next: pin only the top (上横梁铰接); keep bottom ALL (抱箍更接近刚接). That is 284 pins, 284 welded bottoms.
