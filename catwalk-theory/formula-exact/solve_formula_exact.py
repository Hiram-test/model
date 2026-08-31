import numpy as np  # Import numerical arrays for matrix assembly.
from scipy.linalg import eigh  # Import the symmetric generalized eigensolver.

B = 42.90  # Set the centerline spacing between the two catwalks in metres.
y_floor = np.array([-2.67,-2.41,-2.15,-1.89,-1.63,-1.37,-1.11,-0.85,0.85,1.11,1.37,1.63,1.89,2.15,2.41,2.67])  # Set the sixteen physical load-bearing cable offsets in metres.
L = 2286.642  # Set the main-span saddle-to-saddle horizontal length in metres.
f = 227.300  # Set the main-span sag in metres.
E_cable = 120e9  # Set the cable tangent Young modulus in pascals.
A_floor = 1400.42e-6  # Set the ordinary floor-cable metallic area in square metres.
mu_floor = 12.038  # Set the floor-cable line mass in kilograms per metre.
E_steel = 206e9  # Set the structural-steel Young modulus in pascals.
A_eq_cross = 116.93 / 7850.0 / 5.60  # Recover the large-crossbeam equivalent steel area directly from its measured mass, density and effective length.
EA_eq_cross = E_steel * A_eq_cross  # Compute the finite transverse-member axial rigidity from physical member data.
EA_passage = E_steel * 0.0030  # Set the transverse-passage equivalent axial rigidity from its explicit equivalent area.
Nseg = 80  # Set the longitudinal discretization count used only for matrix evaluation.

x = np.linspace(0.0, L, Nseg + 1)  # Create the longitudinal stations.
z = 4.0 * f * (x / L) * (1.0 - x / L)  # Create the prescribed equilibrium parabola.
w_one = mu_floor * 9.80665  # Compute one physical floor-cable self weight per horizontal metre.
H_one = w_one * L * L / (8.0 * f)  # Recover one physical floor-cable horizontal prestress from static equilibrium.

nc_side = len(y_floor)  # Count the sixteen floor cables in one catwalk.
nc = 2 * nc_side  # Count the thirty-two independent floor cables in the double catwalk.
node_count = nc * (Nseg + 1)  # Count all independent physical cable nodes.
ndof = 3 * node_count  # Count all translational degrees of freedom.
K = np.zeros((ndof, ndof))  # Allocate the global tangent stiffness matrix.
M = np.zeros((ndof, ndof))  # Allocate the global consistent mass matrix.

def dofs(cable, station):  # Return the three translation indices of one physical cable node.
    base = 3 * (cable * (Nseg + 1) + station)  # Compute the first global degree index.
    return np.array([base, base + 1, base + 2], dtype=int)  # Return x, y and z translation indices.

for c in range(nc):  # Loop over all thirty-two independent physical load-bearing cables.
    for j in range(Nseg):  # Loop over every longitudinal cable segment.
        dx = x[j + 1] - x[j]  # Compute the horizontal chord increment.
        dz = z[j + 1] - z[j]  # Compute the vertical chord increment.
        d = np.array([dx, 0.0, -dz])  # Form the current three-dimensional cable chord.
        ell = np.linalg.norm(d)  # Compute the current chord length.
        n = d / ell  # Compute the current chord unit vector.
        nn = np.outer(n, n)  # Form the axial projection tensor.
        A3 = (E_cable * A_floor / ell) * nn + (H_one / ell) * (np.eye(3) - nn)  # Evaluate the exact material-plus-geometric tangent operator.
        ke = np.block([[A3, -A3], [-A3, A3]])  # Form the two-node six-by-six tangent stiffness matrix.
        me = (mu_floor * ell / 6.0) * np.block([[2.0*np.eye(3), np.eye(3)], [np.eye(3), 2.0*np.eye(3)]])  # Form the two-node six-by-six consistent mass matrix.
        ids = np.r_[dofs(c, j), dofs(c, j + 1)]  # Collect the six global element indices.
        K[np.ix_(ids, ids)] += ke  # Assemble the cable tangent stiffness.
        M[np.ix_(ids, ids)] += me  # Assemble the cable consistent mass.

cross_stations = np.unique(np.rint(np.linspace(1, Nseg - 1, 71)).astype(int))  # Map the seventy-one physical frame stations to the longitudinal mesh.
for side in range(2):  # Loop over the two catwalks independently.
    offset = side * nc_side  # Compute the physical cable index offset of this catwalk.
    for j in cross_stations:  # Loop only over actual frame stations rather than every numerical station.
        for i in range(nc_side - 1):  # Loop over every neighboring pair of physical load-bearing cables.
            dy = abs(y_floor[i + 1] - y_floor[i])  # Compute the actual transverse spacing between the two cables.
            k_ax = EA_eq_cross / dy  # Compute the finite member stiffness directly from EA over the physical member length.
            a = dofs(offset + i, j)  # Get the first physical cable node degrees.
            b = dofs(offset + i + 1, j)  # Get the neighboring physical cable node degrees.
            K[a[1], a[1]] += k_ax  # Add the first transverse axial diagonal term.
            K[b[1], b[1]] += k_ax  # Add the second transverse axial diagonal term.
            K[a[1], b[1]] -= k_ax  # Add the first transverse axial coupling term.
            K[b[1], a[1]] -= k_ax  # Add the symmetric transverse axial coupling term.

passage_stations = np.unique(np.rint(np.linspace(5, Nseg - 5, 21)).astype(int))  # Map the twenty-one transverse passages to the longitudinal mesh.
k_pass = EA_passage / B  # Compute one passage axial stiffness directly from equivalent EA over span.
for j in passage_stations:  # Loop over every transverse passage station.
    for i in range(nc_side):  # Distribute the centreline passage action over the sixteen physical cable nodes without a rigid-section degree.
        a = dofs(i, j)  # Get the upstream physical cable node degrees.
        b = dofs(nc_side + i, j)  # Get the downstream physical cable node degrees.
        share = k_pass / nc_side  # Compute the equal physical-node share of passage stiffness.
        K[a[1], a[1]] += share  # Add the upstream lateral diagonal term.
        K[b[1], b[1]] += share  # Add the downstream lateral diagonal term.
        K[a[1], b[1]] -= share  # Add the upstream-downstream coupling term.
        K[b[1], a[1]] -= share  # Add the symmetric coupling term.

fixed = []  # Initialize the constrained degree list.
for c in range(nc):  # Loop over all physical cables.
    fixed.extend(dofs(c, 0).tolist())  # Constrain the first end translations.
    fixed.extend(dofs(c, Nseg).tolist())  # Constrain the second end translations.
fixed = np.unique(np.array(fixed, dtype=int))  # Remove duplicate constrained indices.
free = np.setdiff1d(np.arange(ndof), fixed)  # Build the free degree index set.
Kf = K[np.ix_(free, free)]  # Extract the constrained tangent stiffness matrix.
Mf = M[np.ix_(free, free)]  # Extract the constrained mass matrix.
vals, vecs = eigh(Kf, Mf, subset_by_index=[0, 119])  # Compute the lowest one hundred twenty generalized eigenpairs.
freq = np.sqrt(np.maximum(vals, 0.0)) / (2.0 * np.pi)  # Convert generalized eigenvalues to hertz.

rows = []  # Initialize the physical mode records.
denom = float(np.dot(y_floor, y_floor))  # Compute the exact least-squares twist denominator of the sixteen-cable section.
for r in range(len(freq)):  # Loop over every computed eigenpair.
    full = np.zeros(ndof)  # Allocate the full constrained eigenvector.
    full[free] = vecs[:, r]  # Restore the free components.
    theta_u = []  # Initialize upstream physical twist history.
    theta_d = []  # Initialize downstream physical twist history.
    vert_u = []  # Initialize upstream mean vertical history.
    vert_d = []  # Initialize downstream mean vertical history.
    lat_u = []  # Initialize upstream mean lateral history.
    lat_d = []  # Initialize downstream mean lateral history.
    for j in range(Nseg + 1):  # Loop over all longitudinal stations.
        zu = np.array([full[dofs(i, j)[2]] for i in range(nc_side)])  # Collect upstream vertical cable displacements.
        zd = np.array([full[dofs(nc_side + i, j)[2]] for i in range(nc_side)])  # Collect downstream vertical cable displacements.
        yu = np.array([full[dofs(i, j)[1]] for i in range(nc_side)])  # Collect upstream lateral cable displacements.
        yd = np.array([full[dofs(nc_side + i, j)[1]] for i in range(nc_side)])  # Collect downstream lateral cable displacements.
        theta_u.append(float(np.dot(y_floor, zu - zu.mean()) / denom))  # Project upstream cable differences onto section twist.
        theta_d.append(float(np.dot(y_floor, zd - zd.mean()) / denom))  # Project downstream cable differences onto section twist.
        vert_u.append(float(zu.mean()))  # Store upstream mean vertical motion.
        vert_d.append(float(zd.mean()))  # Store downstream mean vertical motion.
        lat_u.append(float(yu.mean()))  # Store upstream mean lateral motion.
        lat_d.append(float(yd.mean()))  # Store downstream mean lateral motion.
    theta_u = np.array(theta_u)  # Convert upstream twist history to an array.
    theta_d = np.array(theta_d)  # Convert downstream twist history to an array.
    vert_u = np.array(vert_u)  # Convert upstream vertical history to an array.
    vert_d = np.array(vert_d)  # Convert downstream vertical history to an array.
    lat_u = np.array(lat_u)  # Convert upstream lateral history to an array.
    lat_d = np.array(lat_d)  # Convert downstream lateral history to an array.
    et = float(np.dot(theta_u, theta_u) + np.dot(theta_d, theta_d))  # Compute physical twist projection energy.
    ev = float(np.dot(vert_u, vert_u) + np.dot(vert_d, vert_d))  # Compute mean vertical projection energy.
    el = float(np.dot(lat_u, lat_u) + np.dot(lat_d, lat_d))  # Compute mean lateral projection energy.
    normalized = np.array([et / (et + ev + el + 1e-30), ev / (et + ev + el + 1e-30), el / (et + ev + el + 1e-30)])  # Normalize the three projection energies.
    family = ['T','V','L'][int(np.argmax(normalized))]  # Assign the dominant physical family.
    common = theta_u + theta_d if family == 'T' else (vert_u + vert_d if family == 'V' else lat_u + lat_d)  # Build the common two-catwalk field.
    differential = theta_u - theta_d if family == 'T' else (vert_u - vert_d if family == 'V' else lat_u - lat_d)  # Build the differential two-catwalk field.
    use = common if np.dot(common, common) >= np.dot(differential, differential) else differential  # Select the dominant two-catwalk combination.
    ud = 'SAME' if np.dot(common, common) >= np.dot(differential, differential) else 'DIFF'  # Record the common or differential relation.
    parity_corr = float(np.dot(use, use[::-1]) / (np.dot(use, use) + 1e-30))  # Compute midpoint-reflection parity.
    parity = 'S' if parity_corr >= 0.0 else 'A'  # Assign symmetric or antisymmetric parity.
    basis_scores = []  # Initialize longitudinal sine projection scores.
    for norder in range(1, 9):  # Test the first eight longitudinal orders.
        basis = np.sin(norder * np.pi * x / L)  # Build the current sine basis.
        basis_scores.append(abs(float(np.dot(use, basis))) / (np.linalg.norm(use) * np.linalg.norm(basis) + 1e-30))  # Compute the normalized projection.
    order = int(np.argmax(basis_scores) + 1)  # Select the dominant longitudinal order.
    rows.append((r + 1, float(freq[r]), family, ud, order, parity, float(normalized[0]), float(normalized[1]), float(normalized[2])))  # Store the complete physical classification record.

def pick(family, parity, rank):  # Select a ranked physical family member without target-frequency matching.
    candidates = sorted([row for row in rows if row[2] == family and row[5] == parity], key=lambda row: row[1])  # Filter and sort only by computed frequency.
    return candidates[rank - 1] if len(candidates) >= rank else None  # Return the requested family rank.

labels = {  # Define the physics-only requested modal labels.
    'LS1': pick('L','S',1),  # Select first symmetric lateral mode.
    'VA1': pick('V','A',1),  # Select first antisymmetric vertical mode.
    'LA1': pick('L','A',1),  # Select first antisymmetric lateral mode.
    'TA1': pick('T','A',1),  # Select first antisymmetric twist mode.
    'VS1': pick('V','S',1),  # Select first symmetric vertical mode.
    'LS2': pick('L','S',2),  # Select second symmetric lateral mode.
    'TS1': pick('T','S',1),  # Select first symmetric twist mode.
    'VA2': pick('V','A',2),  # Select second antisymmetric vertical mode.
    'LA2': pick('L','A',2),  # Select second antisymmetric lateral