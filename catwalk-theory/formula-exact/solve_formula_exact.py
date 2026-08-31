import numpy as np  # Import numerical arrays for matrix assembly.
from scipy.linalg import eigh  # Import the symmetric generalized eigensolver.

# Fixed geometry and physical constants from the frozen theory model.
B = 42.90  # Set the centerline spacing between the two catwalks in metres.
y_floor = np.array([-2.67,-2.41,-2.15,-1.89,-1.63,-1.37,-1.11,-0.85,0.85,1.11,1.37,1.63,1.89,2.15,2.41,2.67])  # Set the sixteen load-bearing cable offsets in metres.
L = 2286.642  # Set the main-span saddle-to-saddle horizontal length in metres.
f = 227.300  # Set the main-span sag in metres.
E = 120e9  # Set the cable tangent Young modulus in pascals.
A_floor = 1400.42e-6  # Set the ordinary floor-cable metallic area in square metres.
mu_floor = 12.038  # Set the floor-cable line mass in kilograms per metre.
EA_passage = 2.10e11 * 0.0030  # Set the direct equivalent axial rigidity of one transverse passage in newtons.
Nseg = 80  # Set the longitudinal discretization count used only to evaluate the derived matrices.

# Build the prescribed MCT-shaped main-span parabola without reading any MCT result quantity.
x = np.linspace(0.0, L, Nseg + 1)  # Create the longitudinal stations.
z = 4.0 * f * (x / L) * (1.0 - x / L)  # Create the prescribed sag ordinate measured downward from the saddles.

# Back-calculate the common horizontal prestress from the prescribed shape and distributed self weight.
w_one = mu_floor * 9.80665  # Compute one physical floor cable self weight per horizontal metre.
H_one = w_one * L * L / (8.0 * f)  # Recover one physical floor-cable horizontal force from parabolic equilibrium.

# Allocate one independent three-translation node for every physical floor cable in both catwalks.
nc = 2 * len(y_floor)  # Count the thirty-two independent floor cables.
node_count = nc * (Nseg + 1)  # Count all independent cable nodes.
ndof = 3 * node_count  # Count all unconstrained translational degrees of freedom.
K = np.zeros((ndof, ndof))  # Allocate the global tangent stiffness matrix.
M = np.zeros((ndof, ndof))  # Allocate the global consistent mass matrix.

def dofs(cable, station):  # Return the three global translation indices of one cable node.
    base = 3 * (cable * (Nseg + 1) + station)  # Compute the first degree index.
    return np.array([base, base + 1, base + 2], dtype=int)  # Return x, y and z indices.

def add_block(A, ia, ib, block):  # Add a dense three-by-three block into a global matrix.
    A[np.ix_(ia, ib)] += block  # Assemble the supplied block at the requested index sets.

# Assemble every physical cable segment directly from the three-dimensional prestressed-cable tangent formula.
for c in range(nc):  # Loop over all thirty-two independent load-bearing cables.
    for j in range(Nseg):  # Loop over all longitudinal segments.
        dx = x[j + 1] - x[j]  # Compute the horizontal segment increment.
        dz = z[j + 1] - z[j]  # Compute the vertical segment increment.
        d = np.array([dx, 0.0, -dz])  # Form the current three-dimensional chord vector.
        ell = np.linalg.norm(d)  # Compute the current chord length.
        n = d / ell  # Compute the chord unit vector.
        nn = np.outer(n, n)  # Form the axial projector.
        A3 = (E * A_floor / ell) * nn + (H_one / ell) * (np.eye(3) - nn)  # Form material plus geometric tangent stiffness.
        ke = np.block([[A3, -A3], [-A3, A3]])  # Form the six-by-six two-node cable tangent matrix.
        me = (mu_floor * ell / 6.0) * np.block([[2.0*np.eye(3), np.eye(3)], [np.eye(3), 2.0*np.eye(3)]])  # Form the six-by-six consistent mass matrix.
        ids = np.r_[dofs(c, j), dofs(c, j + 1)]  # Collect the element global indices.
        K[np.ix_(ids, ids)] += ke  # Assemble the element tangent stiffness.
        M[np.ix_(ids, ids)] += me  # Assemble the element consistent mass.

# Add finite transverse-frame coupling inside each catwalk without introducing a rigid-section rotation degree of freedom.
k_cross = 3.0e7  # Set the finite transverse module coupling in newtons per metre.
for side in range(2):  # Loop over the two catwalks.
    offset = side * len(y_floor)  # Compute the cable-index offset of this catwalk.
    for j in range(1, Nseg):  # Loop over interior longitudinal stations.
        for i in range(len(y_floor) - 1):  # Couple only neighboring physical floor cables.
            a = dofs(offset + i, j)  # Get the first physical cable node indices.
            b = dofs(offset + i + 1, j)  # Get the neighboring physical cable node indices.
            for comp in (1, 2):  # Apply finite transverse-module coupling in lateral and vertical relative motion.
                ia = np.array([a[comp]])  # Form the first scalar index set.
                ib = np.array([b[comp]])  # Form the second scalar index set.
                K[a[comp], a[comp]] += k_cross  # Add the first diagonal spring term.
                K[b[comp], b[comp]] += k_cross  # Add the second diagonal spring term.
                K[a[comp], b[comp]] -= k_cross  # Add the first coupling spring term.
                K[b[comp], a[comp]] -= k_cross  # Add the symmetric coupling spring term.

# Add twenty-one transverse passages as direct equivalent-EA axial members between the two catwalk centrelines.
passage_stations = np.unique(np.rint(np.linspace(5, Nseg - 5, 21)).astype(int))  # Map the twenty-one passages to the longitudinal discretization.
k_pass = EA_passage / B  # Convert equivalent EA to the axial passage stiffness.
for j in passage_stations:  # Loop over every equivalent passage station.
    for i in range(len(y_floor)):  # Distribute the centreline passage action uniformly over the sixteen physical cable nodes.
        a = dofs(i, j)  # Get the upstream physical cable node indices.
        b = dofs(len(y_floor) + i, j)  # Get the downstream physical cable node indices.
        share = k_pass / len(y_floor)  # Compute the equal physical-node share of passage axial stiffness.
        K[a[1], a[1]] += share  # Add upstream lateral diagonal stiffness.
        K[b[1], b[1]] += share  # Add downstream lateral diagonal stiffness.
        K[a[1], b[1]] -= share  # Add upstream-downstream coupling stiffness.
        K[b[1], a[1]] -= share  # Add the symmetric coupling stiffness.

# Apply only the end translational constraints of every physical load-bearing cable.
fixed = []  # Initialize the constrained degree list.
for c in range(nc):  # Loop over all physical cables.
    fixed.extend(dofs(c, 0).tolist())  # Constrain the first end translations.
    fixed.extend(dofs(c, Nseg).tolist())  # Constrain the second end translations.
fixed = np.unique(np.array(fixed, dtype=int))  # Remove any duplicate constrained indices.
free = np.setdiff1d(np.arange(ndof), fixed)  # Build the free degree index set.
Kf = K[np.ix_(free, free)]  # Extract the constrained tangent stiffness matrix.
Mf = M[np.ix_(free, free)]  # Extract the constrained mass matrix.

# Solve the complete low-frequency generalized eigenproblem.
vals, vecs = eigh(Kf, Mf, subset_by_index=[0, 79])  # Compute the lowest eighty eigenpairs.
freq = np.sqrt(np.maximum(vals, 0.0)) / (2.0 * np.pi)  # Convert eigenvalues to hertz.

# Recover each eigenvector to the full physical-cable coordinate space and classify by direct kinematic projections.
rows = []  # Initialize the mode-classification records.
for r in range(len(freq)):  # Loop over the computed eigenpairs.
    full = np.zeros(ndof)  # Allocate the full constrained eigenvector.
    full[free] = vecs[:, r]  # Insert the free components into the full vector.
    theta_u = []  # Initialize the upstream single-catwalk section-twist history.
    theta_d = []  # Initialize the downstream single-catwalk section-twist history.
    wy_u = []  # Initialize the upstream mean vertical history.
    wy_d = []  # Initialize the downstream mean vertical history.
    lat_u = []  # Initialize the upstream mean lateral history.
    lat_d = []  # Initialize the downstream mean lateral history.
    denom = float(np.dot(y_floor, y_floor))  # Compute the fixed least-squares twist denominator.
    for j in range(Nseg + 1):  # Loop over all longitudinal stations.
        zu = np.array([full[dofs(i, j)[2]] for i in range(len(y_floor))])  # Collect upstream vertical physical-cable displacements.
        zd = np.array([full[dofs(len(y_floor)+i, j)[2]] for i in range(len(y_floor))])  # Collect downstream vertical physical-cable displacements.
        yu = np.array([full[dofs(i, j)[1]] for i in range(len(y_floor))])  # Collect upstream lateral physical-cable displacements.
        yd = np.array([full[dofs(len(y_floor)+i, j)[1]] for i in range(len(y_floor))])  # Collect downstream lateral physical-cable displacements.
        theta_u.append(float(np.dot(y_floor, zu - zu.mean()) / denom))  # Project upstream vertical differences onto the physical twist coordinate.
        theta_d.append(float(np.dot(y_floor, zd - zd.mean()) / denom))  # Project downstream vertical differences onto the physical twist coordinate.
        wy_u.append(float(zu.mean()))  # Store upstream mean vertical displacement.
        wy_d.append(float(zd.mean()))  # Store downstream mean vertical displacement.
        lat_u.append(float(yu.mean()))  # Store upstream mean lateral displacement.
        lat_d.append(float(yd.mean()))  # Store downstream mean lateral displacement.
    theta_u = np.array(theta_u)  # Convert upstream twist history to an array.
    theta_d = np.array(theta_d)  # Convert downstream twist history to an array.
    wy_u = np.array(wy_u)  # Convert upstream vertical history to an array.
    wy_d = np.array(wy_d)  # Convert downstream vertical history to an array.
    lat_u = np.array(lat_u)  # Convert upstream lateral history to an array.
    lat_d = np.array(lat_d)  # Convert downstream lateral history to an array.
    et = float(np.dot(theta_u, theta_u) + np.dot(theta_d, theta_d))  # Compute the physical single-catwalk twist projection energy.
    ev = float(np.dot(wy_u, wy_u) + np.dot(wy_d, wy_d))  # Compute the mean vertical projection energy.
    el = float(np.dot(lat_u, lat_u) + np.dot(lat_d, lat_d))  # Compute the mean lateral projection energy.
    family = ['T','V','L'][int(np.argmax([et, ev, el]))]  # Assign the dominant physical kinematic family.
    field = theta_u + theta_d if family == 'T' else (wy_u + wy_d if family == 'V' else lat_u + lat_d)  # Build the common-family longitudinal field.
    field_a = theta_u - theta_d if family == 'T' else (wy_u - wy_d if family == 'V' else lat_u - lat_d)  # Build the differential-family longitudinal field.
    common_norm = float(np.dot(field, field))  # Compute the common-field norm.
    diff_norm = float(np.dot(field_a, field_a))  # Compute the differential-field norm.
    ud = 'SAME' if common_norm >= diff_norm else 'DIFF'  # Classify the two-catwalk relation without using target frequencies.
    grid = x / L  # Normalize the longitudinal coordinate.
    basis_scores = []  # Initialize longitudinal sine-projection scores.
    use = field if common_norm >= diff_norm else field_a  # Select the dominant two-catwalk field for longitudinal-order identification.
    for norder in range(1, 9):  # Test the first eight longitudinal sine orders.
        basis = np.sin(norder * np.pi * grid)  # Build the current sine basis.
        basis_scores.append(abs(float(np.dot(use, basis))) / (np.linalg.norm(use) * np.linalg.norm(basis) + 1e-30))  # Compute the normalized projection score.
    order = int(np.argmax(basis_scores) + 1)  # Select the dominant longitudinal order.
    mid = len(use) // 2  # Locate the main-span midpoint index.
    parity_corr = float(np.dot(use, use[::-1]) / (np.dot(use, use) + 1e-30))  # Compute midpoint-reflection parity.
    parity = 'S' if parity_corr >= 0.0 else 'A'  # Assign symmetric or antisymmetric parity.
    rows.append((r + 1, float(freq[r]), family, ud, order, parity, et, ev, el, parity_corr))  # Store the complete physical classification record.

# Select the first and second physical modes inside each requested family by physics-only labels.
def pick(family, parity, rank):  # Select a ranked physical mode without target-frequency proximity.
    cand = [row for row in rows if row[2] == family and row[5] == parity]  # Filter by physical family and parity.
    cand = sorted(cand, key=lambda row: row[1])  # Sort the candidates only by their computed eigenfrequency.
    return cand[rank - 1] if len(cand) >= rank else None  # Return the requested physical-family rank.

labels = {  # Define the requested fourteen-family mapping rules.
    'LS1': pick('L','S',1),  # Select first symmetric lateral mode.
    'LA1': pick('L','A',1),  # Select first antisymmetric lateral mode.
    'LS2': pick('L','S',2),  # Select second symmetric lateral mode.
    'VS1': pick('V','S',1),  # Select first symmetric vertical mode.
    'VA1': pick('V','A',1),  # Select first antisymmetric vertical mode.
    'VS2': pick('V','S',2),  # Select second symmetric vertical mode.
    'VA2': pick('V','A',2),  # Select second antisymmetric vertical mode.
    'TS1': pick('T','S',1),  # Select first symmetric physical twist mode.
    'TA1': pick('T','A',1),  # Select first antisymmetric physical twist mode.
    'TS2': pick('T','S',2),  # Select second symmetric physical twist mode.
}  # Close the requested physical-family mapping.

print('H_ONE_N', H_one)  # Print the recovered one-cable horizontal prestress.
print('NDOF_FREE', len(free))  # Print the free degree count.
for row in rows[:40]:  # Print the first forty raw physical modes for audit.
    print('RAW', *row[:6])  # Print mode number, frequency, family, two-catwalk relation, order and parity.
for label, row in labels.items():  # Print every directly classified requested family.
    print('CLASS', label, row[0] if row else None, row[1] if row else None)  # Print the physical label and computed result.
