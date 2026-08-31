import numpy as np  # Import numerical arrays for matrix assembly.
from scipy.linalg import eigh  # Import the symmetric generalized eigensolver.
B = 42.90  # Set the centerline spacing between catwalks in metres.
y_floor = np.array([-2.67,-2.41,-2.15,-1.89,-1.63,-1.37,-1.11,-0.85,0.85,1.11,1.37,1.63,1.89,2.15,2.41,2.67])  # Set sixteen physical cable offsets.
L = 2286.642  # Set main-span saddle spacing in metres.
f = 227.300  # Set main-span sag in metres.
E_cable = 120e9  # Set cable tangent modulus in pascals.
A_floor = 1400.42e-6  # Set one floor-cable metallic area in square metres.
mu_floor = 12.038  # Set one floor-cable line mass in kilograms per metre.
E_steel = 206e9  # Set structural-steel modulus in pascals.
A_eq_cross = 116.93 / 7850.0 / 5.60  # Recover crossbeam equivalent area from measured mass, density and length.
EA_eq_cross = E_steel * A_eq_cross  # Compute crossbeam equivalent axial rigidity.
EA_passage = E_steel * 0.0030  # Compute passage equivalent axial rigidity from its explicit equivalent area.
Nseg = 80  # Set longitudinal numerical subdivisions.
x = np.linspace(0.0, L, Nseg + 1)  # Create longitudinal stations.
z = 4.0 * f * (x / L) * (1.0 - x / L)  # Create prescribed equilibrium parabola.
w_one = mu_floor * 9.80665  # Compute one cable self weight per horizontal metre.
H_one = w_one * L * L / (8.0 * f)  # Recover one cable horizontal prestress from static equilibrium.
nc_side = len(y_floor)  # Count physical floor cables per catwalk.
nc = 2 * nc_side  # Count physical floor cables in both catwalks.
node_count = nc * (Nseg + 1)  # Count independent cable nodes.
ndof = 3 * node_count  # Count translational degrees of freedom.
K = np.zeros((ndof, ndof))  # Allocate global tangent stiffness.
M = np.zeros((ndof, ndof))  # Allocate global consistent mass.
def dofs(cable, station):  # Return three translation indices of one cable node.
    base = 3 * (cable * (Nseg + 1) + station)  # Compute first global index.
    return np.array([base, base + 1, base + 2], dtype=int)  # Return x, y and z indices.
for c in range(nc):  # Loop over all physical floor cables.
    for j in range(Nseg):  # Loop over longitudinal cable segments.
        d = np.array([x[j + 1] - x[j], 0.0, -(z[j + 1] - z[j])])  # Form current chord vector.
        ell = np.linalg.norm(d)  # Compute current chord length.
        n = d / ell  # Compute chord unit vector.
        nn = np.outer(n, n)  # Form axial projector.
        A3 = (E_cable * A_floor / ell) * nn + (H_one / ell) * (np.eye(3) - nn)  # Evaluate material plus geometric tangent operator.
        ke = np.block([[A3, -A3], [-A3, A3]])  # Form six-by-six cable tangent matrix.
        me = (mu_floor * ell / 6.0) * np.block([[2.0*np.eye(3), np.eye(3)], [np.eye(3), 2.0*np.eye(3)]])  # Form six-by-six cable consistent mass.
        ids = np.r_[dofs(c, j), dofs(c, j + 1)]  # Collect element indices.
        K[np.ix_(ids, ids)] += ke  # Assemble cable tangent stiffness.
        M[np.ix_(ids, ids)] += me  # Assemble cable consistent mass.
cross_stations = np.unique(np.rint(np.linspace(1, Nseg - 1, 71)).astype(int))  # Map seventy-one physical frame stations.
for side in range(2):  # Loop over both catwalks.
    offset = side * nc_side  # Compute cable-index offset.
    for j in cross_stations:  # Loop over physical frame stations only.
        for i in range(nc_side - 1):  # Loop over neighboring physical cables.
            dy = abs(y_floor[i + 1] - y_floor[i])  # Compute physical transverse spacing.
            k_ax = EA_eq_cross / dy  # Compute finite transverse-member stiffness directly from EA/L.
            a = dofs(offset + i, j)  # Get first cable node indices.
            b = dofs(offset + i + 1, j)  # Get neighboring cable node indices.
            K[a[1], a[1]] += k_ax  # Add first lateral diagonal term.
            K[b[1], b[1]] += k_ax  # Add second lateral diagonal term.
            K[a[1], b[1]] -= k_ax  # Add lateral coupling term.
            K[b[1], a[1]] -= k_ax  # Add symmetric lateral coupling term.
passage_stations = np.unique(np.rint(np.linspace(5, Nseg - 5, 21)).astype(int))  # Map twenty-one passage stations.
k_pass = EA_passage / B  # Compute one passage axial stiffness from EA/L.
for j in passage_stations:  # Loop over passage stations.
    for i in range(nc_side):  # Distribute passage action over sixteen independent cable nodes.
        a = dofs(i, j)  # Get upstream node indices.
        b = dofs(nc_side + i, j)  # Get downstream node indices.
        share = k_pass / nc_side  # Compute one physical-node stiffness share.
        K[a[1], a[1]] += share  # Add upstream diagonal term.
        K[b[1], b[1]] += share  # Add downstream diagonal term.
        K[a[1], b[1]] -= share  # Add coupling term.
        K[b[1], a[1]] -= share  # Add symmetric coupling term.
fixed = []  # Initialize constrained degree list.
for c in range(nc):  # Loop over all physical cables.
    fixed.extend(dofs(c, 0).tolist())  # Constrain first-end translations.
    fixed.extend(dofs(c, Nseg).tolist())  # Constrain second-end translations.
fixed = np.unique(np.array(fixed, dtype=int))  # Remove duplicate constraints.
free = np.setdiff1d(np.arange(ndof), fixed)  # Build free degree set.
Kf = K[np.ix_(free, free)]  # Extract constrained stiffness.
Mf = M[np.ix_(free, free)]  # Extract constrained mass.
vals, vecs = eigh(Kf, Mf, subset_by_index=[0, 119])  # Solve lowest one hundred twenty eigenpairs.
freq = np.sqrt(np.maximum(vals, 0.0)) / (2.0 * np.pi)  # Convert eigenvalues to hertz.
rows = []  # Initialize physical mode records.
denom = float(np.dot(y_floor, y_floor))  # Compute least-squares twist denominator.
for r in range(len(freq)):  # Loop over computed modes.
    full = np.zeros(ndof)  # Allocate full constrained eigenvector.
    full[free] = vecs[:, r]  # Restore free components.
    theta_u, theta_d, vert_u, vert_d, lat_u, lat_d = [], [], [], [], [], []  # Initialize physical section histories.
    for j in range(Nseg + 1):  # Loop over longitudinal stations.
        zu = np.array([full[dofs(i, j)[2]] for i in range(nc_side)])  # Collect upstream vertical cable motions.
        zd = np.array([full[dofs(nc_side + i, j)[2]] for i in range(nc_side)])  # Collect downstream vertical cable motions.
        yu = np.array([full[dofs(i, j)[1]] for i in range(nc_side)])  # Collect upstream lateral cable motions.
        yd = np.array([full[dofs(nc_side + i, j)[1]] for i in range(nc_side)])  # Collect downstream lateral cable motions.
        theta_u.append(float(np.dot(y_floor, zu - zu.mean()) / denom))  # Project upstream motion onto physical section twist.
        theta_d.append(float(np.dot(y_floor, zd - zd.mean()) / denom))  # Project downstream motion onto physical section twist.
        vert_u.append(float(zu.mean()))  # Store upstream mean vertical motion.
        vert_d.append(float(zd.mean()))  # Store downstream mean vertical motion.
        lat_u.append(float(yu.mean()))  # Store upstream mean lateral motion.
        lat_d.append(float(yd.mean()))  # Store downstream mean lateral motion.
    theta_u, theta_d = np.array(theta_u), np.array(theta_d)  # Convert twist histories to arrays.
    vert_u, vert_d = np.array(vert_u), np.array(vert_d)  # Convert vertical histories to arrays.
    lat_u, lat_d = np.array(lat_u), np.array(lat_d)  # Convert lateral histories to arrays.
    et = float(np.dot(theta_u, theta_u) + np.dot(theta_d, theta_d))  # Compute twist projection energy.
    ev = float(np.dot(vert_u, vert_u) + np.dot(vert_d, vert_d))  # Compute vertical projection energy.
    el = float(np.dot(lat_u, lat_u) + np.dot(lat_d, lat_d))  # Compute lateral projection energy.
    energy = np.array([et, ev, el]) / (et + ev + el + 1e-30)  # Normalize projection energies.
    family = ['T','V','L'][int(np.argmax(energy))]  # Assign dominant physical family.
    common = theta_u + theta_d if family == 'T' else (vert_u + vert_d if family == 'V' else lat_u + lat_d)  # Build common two-catwalk field.
    differential = theta_u - theta_d if family == 'T' else (vert_u - vert_d if family == 'V' else lat_u - lat_d)  # Build differential two-catwalk field.
    same = np.dot(common, common) >= np.dot(differential, differential)  # Determine common or differential dominance.
    use = common if same else differential  # Select dominant two-catwalk field.
    ud = 'SAME' if same else 'DIFF'  # Record common or differential relation.
    parity_corr = float(np.dot(use, use[::-1]) / (np.dot(use, use) + 1e-30))  # Compute midpoint-reflection parity.
    parity = 'S' if parity_corr >= 0.0 else 'A'  # Assign symmetric or antisymmetric parity.
    scores = []  # Initialize longitudinal sine scores.
    for norder in range(1, 9):  # Test first eight longitudinal orders.
        basis = np.sin(norder * np.pi * x / L)  # Build sine basis.
        scores.append(abs(float(np.dot(use, basis))) / (np.linalg.norm(use) * np.linalg.norm(basis) + 1e-30))  # Compute normalized projection score.
    order = int(np.argmax(scores) + 1)  # Select dominant longitudinal order.
    rows.append((r + 1, float(freq[r]), family, ud, order, parity, float(energy[0]), float(energy[1]), float(energy[2])))  # Store physical classification record.
def pick(family, parity, rank):  # Select ranked physical family member without target-frequency matching.
    candidates = sorted([row for row in rows if row[2] == family and row[5] == parity], key=lambda row: row[1])  # Filter and sort computed candidates.
    return candidates[rank - 1] if len(candidates) >= rank else None  # Return requested physical rank.
labels = {  # Define requested physics-only modal labels.
    'LS1': pick('L','S',1),  # Select first symmetric lateral mode.
    'VA1': pick('V','A',1),  # Select first antisymmetric vertical mode.
    'LA1': pick('L','A',1),  # Select first antisymmetric lateral mode.
    'TA1': pick('T','A',1),  # Select first antisymmetric twist mode.
    'VS1': pick('V','S',1),  # Select first symmetric vertical mode.
    'LS2': pick('L','S',2),  # Select second symmetric lateral mode.
    'TS1': pick('T','S',1),  # Select first symmetric twist mode.
    'VA2': pick('V','A',2),  # Select second antisymmetric vertical mode.
    'LA2': pick('L','A',2),  # Select second antisymmetric lateral mode.
    'TS2': pick('T','S',2),  # Select second symmetric twist mode.
    'VS2': pick('V','S',2),  # Select second symmetric vertical mode.
}  # Close requested modal-label mapping.
print('H_ONE_N', H_one)  # Print recovered one-cable horizontal prestress.
print('EA_EQ_CROSS_N', EA_eq_cross)  # Print derived transverse-member equivalent EA.
print('K_PASS_NPM', k_pass)  # Print derived passage axial stiffness.
print('NDOF_FREE', len(free))  # Print free degree count.
for row in rows[:50]:  # Print first fifty raw modes for audit.
    print('RAW', *row)  # Print complete raw physical classification.
for label, row in labels.items():  # Print every requested classified mode.
    print('CLASS', label, row[0] if row else None, row[1] if row else None)  # Print physical label, numerical order and frequency.
print('frequency_reproduced', False)  # This parabola toy is not attach reproduction.
print('not_attach_ta1', True)  # Family label TA1 is not attach TA1.
print('not_formula_exact', True)  # eigh of an 80-segment parabola is not a closed-form exact solution.
