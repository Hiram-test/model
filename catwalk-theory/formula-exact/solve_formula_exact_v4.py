from __future__ import annotations  # Enable stable type annotations.
import csv  # Write auditable modal tables.
import json  # Write machine-readable calculation results.
import math  # Evaluate section and geometric formulas.
from pathlib import Path  # Manage deterministic output paths.
import numpy as np  # Assemble local and global matrices.
from scipy.sparse import lil_matrix  # Assemble the sparse global matrices.
from scipy.sparse.linalg import eigsh  # Solve the symmetric generalized eigenproblem.
OUT = Path(__file__).resolve().parent / "results_v4"  # Define the isolated v4 result directory.
OUT.mkdir(parents=True, exist_ok=True)  # Create the result directory.
G = 9.80665  # Set gravitational acceleration in metres per second squared.
E_ROPE = 120.0e9  # Set the working rope tangent modulus in pascals.
E_STEEL = 206.0e9  # Set structural-steel Young modulus in pascals.
RHO_STEEL = 7850.0  # Set structural-steel density in kilograms per cubic metre.
A_ROPE = 1400.42e-6  # Set one ordinary rope metallic area in square metres.
MU_ROPE = 12.038  # Set one phi-50 rope line mass in kilograms per metre.
Q_FLOOR = 2766.0  # Set one catwalk lower-system dead load in newtons per horizontal metre.
B_CAT = 42.90  # Set the two-catwalk centreline spacing in metres.
L_MAIN = 2286.642  # Set the main-span saddle-to-saddle horizontal length in metres.
F_MAIN = 227.300  # Set the prescribed main-span sag in metres.
H_PORTAL = 8.0  # Set the representative portal height in metres.
M_PORTAL_BODY = 1123.0  # Set one portal body mass without bottom beam in kilograms.
M_BOTTOM_BEAM = 306.98  # Set one portal bottom-beam mass in kilograms.
M_TOP_BEAM = 211.0  # Set one portal top-beam mass in kilograms.
M_PASSAGE = 10130.0  # Set one complete transverse-passage mass in kilograms.
NSEG = 80  # Set the longitudinal numerical subdivision count.
FLOOR_Y = np.array([-2.67, -2.41, -2.15, -1.89, -1.63, -1.37, -1.11, -0.85, 0.85, 1.11, 1.37, 1.63, 1.89, 2.15, 2.41, 2.67])  # Retain all sixteen floor-rope offsets.
GANTRY_Y = np.array([-2.21, -1.95, -1.69, 1.69, 1.95, 2.21])  # Retain all six gantry-rope offsets.
CAT_CENTRES = np.array([-B_CAT / 2.0, B_CAT / 2.0])  # Place both catwalk centrelines.
PASSAGE_GLOBAL_X = np.array([838.0, 1009.0, 1180.0, 1351.0, 1504.0, 1657.0, 1810.0, 1963.0, 2116.0, 2269.0, 2440.0, 2611.0, 2782.0])  # Retain the thirteen actual main-span passage stations.
X_SADDLE_N = 666.679  # Set the north main-span saddle global coordinate in metres.
def square_tube_inertia(area: float, outer: float) -> float:  # Recover a square-tube inertia from area and outer depth.
    inner = math.sqrt(max(outer * outer - area, 1.0e-16))  # Recover the equivalent inner depth.
    return (outer**4 - inner**4) / 12.0  # Return the centroidal second moment of area.
def pipe_area(diameter: float, thickness: float) -> float:  # Evaluate a circular hollow-section area.
    return math.pi * (diameter**2 - (diameter - 2.0 * thickness) ** 2) / 4.0  # Return the exact tube area.
def beam_condensed(y: np.ndarray, flexural_rigidity: float) -> np.ndarray:  # Condense Euler-beam rotations and retain vertical port translations.
    count = len(y)  # Count the physical beam connection points.
    full = np.zeros((2 * count, 2 * count))  # Allocate the vertical-displacement and rotation matrix.
    for element in range(count - 1):  # Traverse every transverse beam segment.
        length = float(y[element + 1] - y[element])  # Evaluate the segment length.
        local = flexural_rigidity / length**3 * np.array([[12.0, 6.0 * length, -12.0, 6.0 * length], [6.0 * length, 4.0 * length**2, -6.0 * length, 2.0 * length**2], [-12.0, -6.0 * length, 12.0, -6.0 * length], [6.0 * length, 2.0 * length**2, -6.0 * length, 4.0 * length**2]])  # Form the Euler element stiffness.
        indices = np.array([2 * element, 2 * element + 1, 2 * element + 2, 2 * element + 3])  # Address both segment nodes.
        full[np.ix_(indices, indices)] += local  # Assemble the local beam stiffness.
    translations = np.arange(0, 2 * count, 2)  # Address all retained vertical translations.
    rotations = np.arange(1, 2 * count, 2)  # Address all internal beam rotations.
    ktt = full[np.ix_(translations, translations)]  # Extract the translation block.
    ktr = full[np.ix_(translations, rotations)]  # Extract the translation-rotation block.
    krr = full[np.ix_(rotations, rotations)]  # Extract the internal rotation block.
    return ktt - ktr @ np.linalg.solve(krr, ktr.T)  # Return the statically condensed objective stiffness.
def frame_element(area: float, inertia: float, y1: float, z1: float, y2: float, z2: float) -> np.ndarray:  # Form one two-dimensional Euler frame element.
    dy = y2 - y1  # Evaluate the transverse coordinate increment.
    dz = z2 - z1  # Evaluate the vertical coordinate increment.
    length = math.hypot(dy, dz)  # Evaluate the member length.
    cosine = dy / length  # Evaluate the local-axis cosine.
    sine = dz / length  # Evaluate the local-axis sine.
    axial = E_STEEL * area / length  # Evaluate the member axial stiffness.
    bending = E_STEEL * inertia  # Evaluate the member flexural rigidity.
    local = np.array([[axial, 0.0, 0.0, -axial, 0.0, 0.0], [0.0, 12.0 * bending / length**3, 6.0 * bending / length**2, 0.0, -12.0 * bending / length**3, 6.0 * bending / length**2], [0.0, 6.0 * bending / length**2, 4.0 * bending / length, 0.0, -6.0 * bending / length**2, 2.0 * bending / length], [-axial, 0.0, 0.0, axial, 0.0, 0.0], [0.0, -12.0 * bending / length**3, -6.0 * bending / length**2, 0.0, 12.0 * bending / length**3, -6.0 * bending / length**2], [0.0, 6.0 * bending / length**2, 2.0 * bending / length, 0.0, -6.0 * bending / length**2, 4.0 * bending / length]])  # Form the local frame matrix.
    rotation = np.array([[cosine, sine, 0.0], [-sine, cosine, 0.0], [0.0, 0.0, 1.0]])  # Form the node coordinate rotation.
    transform = np.zeros((6, 6))  # Allocate the two-node transformation.
    transform[:3, :3] = rotation  # Insert the first-node transformation.
    transform[3:, 3:] = rotation  # Insert the second-node transformation.
    return transform.T @ local @ transform  # Return the frame stiffness in transverse-vertical coordinates.
def portal_matrix() -> np.ndarray:  # Condense one complete 16-floor-port and 6-gantry-port frame.
    coordinates = [(float(value), 0.0) for value in FLOOR_Y] + [(float(value), H_PORTAL) for value in GANTRY_Y]  # Define all twenty-two physical port coordinates.
    count = len(coordinates)  # Count the portal nodes.
    full = np.zeros((3 * count, 3 * count))  # Allocate two translations and one internal rotation per portal node.
    area_bottom = M_BOTTOM_BEAM / (RHO_STEEL * 5.60)  # Recover the bottom-beam equivalent area from mass conservation.
    inertia_bottom = square_tube_inertia(area_bottom, 0.16)  # Recover its equivalent flexural inertia.
    area_top = M_TOP_BEAM / (RHO_STEEL * 7.46)  # Recover the top-beam equivalent area from mass conservation.
    inertia_top = (0.16**4 - (0.16 - 2.0 * 0.006) ** 4) / 12.0  # Use the documented 160-by-160-by-6 top-beam inertia.
    column_mass = M_PORTAL_BODY - M_TOP_BEAM  # Isolate the two-column mass package.
    column_length = math.hypot(FLOOR_Y[0] - GANTRY_Y[0], H_PORTAL)  # Evaluate one inclined column length.
    area_column = column_mass / (2.0 * RHO_STEEL * column_length)  # Recover the two-column equivalent area.
    inertia_column = square_tube_inertia(area_column, 0.16)  # Recover the equivalent column flexural inertia.
    members: list[tuple[int, int, float, float]] = []  # Initialize the portal member list.
    members += [(index, index + 1, area_bottom, inertia_bottom) for index in range(15)]  # Add all bottom-beam segments.
    members += [(16 + index, 17 + index, area_top, inertia_top) for index in range(5)]  # Add all top-beam segments.
    members += [(0, 16, area_column, inertia_column), (15, 21, area_column, inertia_column)]  # Add both portal columns.
    for node_i, node_j, area, inertia in members:  # Traverse every portal member.
        stiffness = frame_element(area, inertia, *coordinates[node_i], *coordinates[node_j])  # Evaluate its global frame matrix.
        indices = np.r_[np.arange(3 * node_i, 3 * node_i + 3), np.arange(3 * node_j, 3 * node_j + 3)]  # Address both member nodes.
        full[np.ix_(indices, indices)] += stiffness  # Assemble the member matrix.
    translations = np.array([3 * node + component for node in range(count) for component in (0, 1)])  # Retain all physical y-z port translations.
    rotations = np.array([3 * node + 2 for node in range(count)])  # Mark all frame rotations as internal.
    ktt = full[np.ix_(translations, translations)]  # Extract the retained translation block.
    ktr = full[np.ix_(translations, rotations)]  # Extract the coupling block.
    krr = full[np.ix_(rotations, rotations)]  # Extract the internal rotation block.
    return ktt - ktr @ np.linalg.solve(krr, ktr.T)  # Return the condensed forty-four-port stiffness.
def passage_port_matrix() -> np.ndarray:  # Condense the six-panel transverse passage to four y-z endpoint ports.
    panel_lengths = np.array([7.435, 9.540, 9.540, 6.165, 9.540, 7.435])  # Retain the documented six-module length sequence.
    stations = np.r_[0.0, np.cumsum(panel_lengths)]  # Form the seven module-boundary stations.
    height = 1.70  # Set the documented passage truss depth in metres.
    count = len(stations)  # Count the nodes on one chord.
    coordinates = [(float(value), 0.0) for value in stations] + [(float(value), height) for value in stations]  # Define bottom and top chord nodes.
    full = np.zeros((2 * len(coordinates), 2 * len(coordinates)))  # Allocate the two-dimensional truss stiffness.
    area_chord = 2.0 * pipe_area(0.152, 0.006)  # Combine the two passage planes for each main chord.
    area_vertical = 2.0 * pipe_area(0.102, 0.004)  # Combine the two passage planes for each vertical.
    area_diagonal = 2.0 * pipe_area(0.051, 0.004)  # Combine the two passage planes for each diagonal.
    def add_member(node_i: int, node_j: int, area: float) -> None:  # Assemble one passage truss member.
        y1, z1 = coordinates[node_i]  # Read the first endpoint coordinates.
        y2, z2 = coordinates[node_j]  # Read the second endpoint coordinates.
        dy = y2 - y1  # Evaluate the transverse increment.
        dz = z2 - z1  # Evaluate the vertical increment.
        length = math.hypot(dy, dz)  # Evaluate the member length.
        cosine = dy / length  # Evaluate the direction cosine.
        sine = dz / length  # Evaluate the direction sine.
        stiffness = E_STEEL * area / length * np.array([[cosine**2, cosine * sine, -cosine**2, -cosine * sine], [cosine * sine, sine**2, -cosine * sine, -sine**2], [-cosine**2, -cosine * sine, cosine**2, cosine * sine], [-cosine * sine, -sine**2, cosine * sine, sine**2]])  # Form the global truss matrix.
        indices = np.array([2 * node_i, 2 * node_i + 1, 2 * node_j, 2 * node_j + 1])  # Address both member nodes.
        full[np.ix_(indices, indices)] += stiffness  # Assemble the current member.
    for panel in range(count - 1):  # Traverse all six passage modules.
        add_member(panel, panel + 1, area_chord)  # Add the bottom chord segment.
        add_member(count + panel, count + panel + 1, area_chord)  # Add the top chord segment.
        if panel % 2 == 0:  # Alternate the diagonal direction by panel.
            add_member(panel, count + panel + 1, area_diagonal)  # Add the forward diagonal.
        else:  # Handle the opposite diagonal direction.
            add_member(count + panel, panel + 1, area_diagonal)  # Add the backward diagonal.
    for station in range(count):  # Traverse every passage module boundary.
        add_member(station, count + station, area_vertical)  # Add the vertical web member.
    retained_nodes = np.array([0, count, count - 1, 2 * count - 1])  # Retain left-bottom, left-top, right-bottom, and right-top ports.
    retained = np.array([2 * node + component for node in retained_nodes for component in (0, 1)])  # Address all eight retained translations.
    internal = np.setdiff1d(np.arange(full.shape[0]), retained)  # Mark all remaining truss translations as internal.
    kbb = full[np.ix_(retained, retained)]  # Extract the retained port block.
    kbi = full[np.ix_(retained, internal)]  # Extract the port-internal block.
    kii = full[np.ix_(internal, internal)]  # Extract the internal block.
    return kbb - kbi @ np.linalg.solve(kii, kbi.T)  # Return the condensed eight-port passage stiffness.
def passage_increment(portal: np.ndarray, passage: np.ndarray) -> np.ndarray:  # Transfer one passage through two portal frames to all sixty-four floor ports.
    base = np.zeros((88, 88))  # Allocate two uncoupled forty-four-port portal matrices.
    base[:44, :44] = portal  # Insert the upstream portal matrix.
    base[44:, 44:] = portal  # Insert the downstream portal matrix.
    coupled = base.copy()  # Copy the uncoupled state before adding the passage.
    port_indices = np.array([0, 1, 32, 33, 44 + 30, 44 + 31, 44 + 42, 44 + 43])  # Map passage ports to the two outer floor and top portal nodes.
    coupled[np.ix_(port_indices, port_indices)] += passage  # Assemble the condensed passage between both portals.
    retained = np.r_[np.arange(0, 32), np.arange(44, 76)]  # Retain all sixteen floor-node y-z translations per catwalk.
    internal = np.r_[np.arange(32, 44), np.arange(76, 88)]  # Condense all twelve gantry-rope y-z translations.
    def condense(matrix: np.ndarray) -> np.ndarray:  # Condense the current local portal-passage system.
        krr = matrix[np.ix_(retained, retained)]  # Extract the retained floor-port block.
        kri = matrix[np.ix_(retained, internal)]  # Extract the floor-to-top coupling block.
        kii = matrix[np.ix_(internal, internal)]  # Extract the internal top-port block.
        return krr - kri @ np.linalg.solve(kii, kri.T)  # Return the condensed floor-port matrix.
    increment = condense(coupled) - condense(base)  # Isolate the passage-induced coupling without duplicating portal stiffness.
    increment = 0.5 * (increment + increment.T)  # Remove roundoff asymmetry.
    values, vectors = np.linalg.eigh(increment)  # Diagonalize the conservative increment.
    return vectors @ np.diag(np.maximum(values, 0.0)) @ vectors.T  # Remove only numerical negative eigenvalues.
def main() -> int:  # Assemble, solve, classify, and export the repaired model.
    x = np.linspace(0.0, L_MAIN, NSEG + 1)  # Create the main-span longitudinal stations.
    z = -4.0 * F_MAIN * (x / L_MAIN) * (1.0 - x / L_MAIN)  # Create the prescribed main-span formed geometry.
    floor_mass = Q_FLOOR / G / 16.0  # Convert the complete lower-system load to one-rope equivalent line mass.
    floor_horizontal = Q_FLOOR / 16.0 * L_MAIN**2 / (8.0 * F_MAIN)  # Recover one floor-rope horizontal prestress.
    portal_mass = M_PORTAL_BODY + M_BOTTOM_BEAM  # Evaluate one complete portal mass.
    gantry_load = 6.0 * MU_ROPE * G + 71.0 * portal_mass * G / L_MAIN  # Convert rope and portal weights to an equivalent top-system line load.
    gantry_horizontal = gantry_load / 6.0 * L_MAIN**2 / (8.0 * F_MAIN)  # Recover one gantry-rope horizontal prestress.
    cables_per_side = 22  # Count sixteen floor ropes plus six gantry ropes per catwalk.
    cable_count = 44  # Count all explicit longitudinal ropes.
    node_count = cable_count * (NSEG + 1)  # Count all independent rope nodes.
    dof_count = 3 * node_count  # Count all three-translation rope-node degrees of freedom.
    stiffness = lil_matrix((dof_count, dof_count), dtype=float)  # Allocate the sparse tangent stiffness.
    mass = lil_matrix((dof_count, dof_count), dtype=float)  # Allocate the sparse consistent mass.
    def cable_index(catwalk: int, family: str, number: int) -> int:  # Map one physical rope to a global cable index.
        return catwalk * cables_per_side + (number if family == "floor" else 16 + number)  # Return the requested cable index.
    def node_dofs(cable: int, station: int) -> np.ndarray:  # Map one rope node to its three translations.
        first = 3 * (cable * (NSEG + 1) + station)  # Compute the first global degree index.
        return np.array([first, first + 1, first + 2], dtype=int)  # Return longitudinal, transverse, and vertical indices.
    def point(cable: int, station: int) -> np.ndarray:  # Return one explicit rope-node coordinate.
        catwalk = cable // cables_per_side  # Identify the parent catwalk.
        local = cable % cables_per_side  # Identify the local rope number.
        if local < 16:  # Test whether this is a floor rope.
            return np.array([x[station], CAT_CENTRES[catwalk] + FLOOR_Y[local], z[station]])  # Return the floor-rope point.
        return np.array([x[station], CAT_CENTRES[catwalk] + GANTRY_Y[local - 16], z[station] + H_PORTAL])  # Return the gantry-rope point.
    def add_dense(indices: np.ndarray, matrix: np.ndarray, target: lil_matrix) -> None:  # Scatter one dense local matrix into a sparse global matrix.
        target[np.ix_(indices, indices)] += matrix  # Add the local coefficients at the selected global indices.
    def add_truss(cable_i: int, station_i: int, cable_j: int, station_j: int, axial_rigidity: float, force: float = 0.0, member_mass: float = 0.0) -> None:  # Assemble one three-dimensional prestressed truss member.
        delta = point(cable_j, station_j) - point(cable_i, station_i)  # Evaluate the current chord vector.
        length = float(np.linalg.norm(delta))  # Evaluate the current chord length.
        direction = delta / length  # Evaluate the current unit direction.
        projector = np.outer(direction, direction)  # Form the axial projector.
        operator = axial_rigidity / length * projector + force / length * (np.eye(3) - projector)  # Form material plus geometric tangent stiffness.
        local_k = np.block([[operator, -operator], [-operator, operator]])  # Form the two-node six-translation tangent matrix.
        indices = np.r_[node_dofs(cable_i, station_i), node_dofs(cable_j, station_j)]  # Address both member endpoints.
        add_dense(indices, local_k, stiffness)  # Assemble the member tangent stiffness.
        if member_mass > 0.0:  # Test whether this member contributes dynamic mass.
            local_m = member_mass / 6.0 * np.block([[2.0 * np.eye(3), np.eye(3)], [np.eye(3), 2.0 * np.eye(3)]])  # Form the two-node consistent mass matrix.
            add_dense(indices, local_m, mass)  # Assemble the member mass.
    def add_lumped(cable: int, station: int, value: float) -> None:  # Add one physical point mass to a rope node.
        for degree in node_dofs(cable, station):  # Traverse its three translational degrees.
            mass[degree, degree] += value  # Add the same point mass to each translational kinetic-energy direction.
    for catwalk in range(2):  # Assemble both catwalks independently.
        for number in range(16):  # Assemble all sixteen floor ropes.
            cable = cable_index(catwalk, "floor", number)  # Resolve the current floor-rope index.
            for station in range(NSEG):  # Traverse its longitudinal segments.
                delta = point(cable, station + 1) - point(cable, station)  # Evaluate the formed segment chord.
                length = float(np.linalg.norm(delta))  # Evaluate the formed segment length.
                force = floor_horizontal * length / (x[station + 1] - x[station])  # Recover the full current tensile force from its horizontal component.
                add_truss(cable, station, cable, station + 1, E_ROPE * A_ROPE, force, floor_mass * length)  # Assemble floor-rope tangent stiffness and equivalent lower-system mass.
        for number in range(6):  # Assemble all six gantry ropes.
            cable = cable_index(catwalk, "gantry", number)  # Resolve the current gantry-rope index.
            for station in range(NSEG):  # Traverse its longitudinal segments.
                delta = point(cable, station + 1) - point(cable, station)  # Evaluate the formed segment chord.
                length = float(np.linalg.norm(delta))  # Evaluate the formed segment length.
                force = gantry_horizontal * length / (x[station + 1] - x[station])  # Recover the full current tensile force from its horizontal component.
                add_truss(cable, station, cable, station + 1, E_ROPE * A_ROPE, force, MU_ROPE * length)  # Assemble gantry-rope tangent stiffness and mass.
    area_large = 116.93 / (RHO_STEEL * 5.60)  # Recover one large-crossbeam equivalent area from mass conservation.
    area_small = 30.18 / (RHO_STEEL * 5.60)  # Recover one small-crossbeam equivalent area from mass conservation.
    inertia_large = square_tube_inertia(area_large, 0.16)  # Recover one large-crossbeam equivalent inertia.
    inertia_small = square_tube_inertia(area_small, 0.10)  # Recover one small-crossbeam equivalent inertia.
    station_length = L_MAIN / NSEG  # Evaluate one numerical station tributary length.
    floor_flexural = E_STEEL * (585.0 / 4180.0 * inertia_large + 845.0 / 4180.0 * inertia_small) * station_length  # Form the distributed transverse flexural rigidity per numerical station.
    floor_axial_area = (585.0 / 4180.0 * area_large + 845.0 / 4180.0 * area_small) * station_length  # Form the distributed transverse axial area per numerical station.
    floor_bending = beam_condensed(FLOOR_Y, floor_flexural)  # Condense the transverse-beam vertical bending matrix.
    for catwalk in range(2):  # Apply the transverse floor module to both catwalks.
        for station in range(1, NSEG):  # Traverse all internal longitudinal stations.
            vertical_dofs = np.array([node_dofs(cable_index(catwalk, "floor", number), station)[2] for number in range(16)])  # Address all sixteen floor vertical translations.
            add_dense(vertical_dofs, floor_bending, stiffness)  # Assemble objective vertical beam bending.
            for number in range(15):  # Traverse neighboring floor ropes.
                add_truss(cable_index(catwalk, "floor", number), station, cable_index(catwalk, "floor", number + 1), station, E_STEEL * floor_axial_area)  # Assemble transverse axial continuity.
    portal = portal_matrix()  # Build the representative condensed portal frame.
    portal_stations = np.unique(np.rint(np.linspace(1, NSEG - 1, 71)).astype(int))  # Map all seventy-one portals to the numerical stations.
    column_mass = M_PORTAL_BODY - M_TOP_BEAM  # Isolate the portal-column mass package.
    for catwalk in range(2):  # Assemble every portal frame on both catwalks.
        for station in portal_stations:  # Traverse the mapped portal stations.
            portal_dofs: list[int] = []  # Initialize the forty-four y-z portal port degrees.
            for number in range(16):  # Traverse all floor ports.
                current = node_dofs(cable_index(catwalk, "floor", number), station)  # Resolve the current floor-rope node.
                portal_dofs += [int(current[1]), int(current[2])]  # Retain its transverse and vertical translations.
            for number in range(6):  # Traverse all gantry ports.
                current = node_dofs(cable_index(catwalk, "gantry", number), station)  # Resolve the current gantry-rope node.
                portal_dofs += [int(current[1]), int(current[2])]  # Retain its transverse and vertical translations.
            add_dense(np.array(portal_dofs), portal, stiffness)  # Assemble the full condensed portal stiffness.
            for number in range(16):  # Distribute the exact bottom-beam mass.
                add_lumped(cable_index(catwalk, "floor", number), station, M_BOTTOM_BEAM / 16.0)  # Add one sixteenth to each floor port.
            for number in range(6):  # Distribute the exact top-beam mass.
                add_lumped(cable_index(catwalk, "gantry", number), station, M_TOP_BEAM / 6.0)  # Add one sixth to each gantry port.
            for cable in (cable_index(catwalk, "floor", 0), cable_index(catwalk, "floor", 15), cable_index(catwalk, "gantry", 0), cable_index(catwalk, "gantry", 5)):  # Address the four column endpoints.
                add_lumped(cable, station, column_mass / 4.0)  # Preserve the remaining portal mass and eccentric inertia.
    passage = passage_port_matrix()  # Build the six-panel passage matrix directly from member EA values.
    passage_floor_increment = passage_increment(portal, passage)  # Transfer the passage through both portal frames without a fitted stiffness.
    passage_stations = np.unique(np.rint((PASSAGE_GLOBAL_X - X_SADDLE_N) / L_MAIN * NSEG).astype(int))  # Map the thirteen actual main-span passage stations.
    for station in passage_stations:  # Assemble each physical main-span passage.
        floor_dofs: list[int] = []  # Initialize the sixty-four floor y-z port degrees.
        for catwalk in range(2):  # Traverse both catwalks.
            for number in range(16):  # Traverse all floor-rope ports.
                current = node_dofs(cable_index(catwalk, "floor", number), station)  # Resolve the current floor-rope node.
                floor_dofs += [int(current[1]), int(current[2])]  # Retain transverse and vertical translations.
        add_dense(np.array(floor_dofs), passage_floor_increment, stiffness)  # Assemble the formula-derived passage coupling.
        for catwalk in range(2):  # Distribute the complete passage mass once.
            for number in range(16):  # Traverse all floor ports.
                add_lumped(cable_index(catwalk, "floor", number), station, M_PASSAGE / 32.0)  # Preserve total passage mass and system-roll inertia.
    fixed: list[int] = []  # Initialize the physical end constraints.
    for cable in range(cable_count):  # Traverse all forty-four ropes.
        fixed += node_dofs(cable, 0).tolist()  # Constrain the north saddle-end translations.
        fixed += node_dofs(cable, NSEG).tolist()  # Constrain the south saddle-end translations.
    fixed_array = np.unique(np.array(fixed, dtype=int))  # Remove duplicate end constraints.
    free = np.setdiff1d(np.arange(dof_count), fixed_array)  # Build the free-degree set.
    k_free = stiffness.tocsr()[free][:, free]  # Extract the constrained tangent stiffness.
    m_free = mass.tocsr()[free][:, free]  # Extract the constrained mass matrix.
    eigenvalues, eigenvectors = eigsh(k_free, k=120, M=m_free, sigma=0.0, which="LM", tol=1.0e-9, maxiter=20000)  # Solve the lowest one hundred twenty modes.
    order = np.argsort(eigenvalues)  # Sort the eigenpairs in ascending order.
    eigenvalues = eigenvalues[order]  # Reorder the eigenvalues.
    eigenvectors = eigenvectors[:, order]  # Reorder the eigenvectors.
    frequencies = np.sqrt(np.maximum(eigenvalues, 0.0)) / (2.0 * math.pi)  # Convert all eigenvalues to hertz.
    records: list[dict] = []  # Initialize the mode-classification records.
    for mode_index, frequency in enumerate(frequencies):  # Traverse every solved eigenmode.
        full = np.zeros(dof_count)  # Allocate the full constrained eigenvector.
        full[free] = eigenvectors[:, mode_index]  # Restore its free components.
        vertical: list[np.ndarray] = []  # Initialize the two catwalk mean-vertical fields.
        lateral: list[np.ndarray] = []  # Initialize the two catwalk mean-lateral fields.
        for catwalk in range(2):  # Traverse both catwalks.
            vertical.append(np.array([np.mean([full[node_dofs(cable_index(catwalk, "floor", number), station)[2]] for number in range(16)]) for station in range(NSEG + 1)]))  # Recover the catwalk mean vertical field.
            lateral.append(np.array([np.mean([full[node_dofs(cable_index(catwalk, "floor", number), station)[1]] for number in range(16)]) for station in range(NSEG + 1)]))  # Recover the catwalk mean lateral field.
        system_roll = 0.5 * (vertical[1] - vertical[0])  # Define the confirmed double-catwalk torsional displacement field.
        vertical_common = 0.5 * (vertical[1] + vertical[0])  # Define the common vertical field.
        lateral_common = 0.5 * (lateral[1] + lateral[0])  # Define the common lateral field.
        lateral_difference = 0.5 * (lateral[1] - lateral[0])  # Define the differential lateral field.
        energy_t = 32.0 * float(np.dot(system_roll, system_roll))  # Form the system-roll displacement-energy measure.
        energy_v = 32.0 * float(np.dot(vertical_common, vertical_common))  # Form the common-vertical displacement-energy measure.
        energy_l = 16.0 * float(np.dot(lateral_common, lateral_common) + np.dot(lateral_difference, lateral_difference))  # Form the lateral displacement-energy measure.
        family = ("T", "V", "L")[int(np.argmax([energy_t, energy_v, energy_l]))]  # Select the dominant physical family.
        if family == "T":  # Test whether the mode is double-catwalk torsion.
            field = system_roll  # Use the system-roll field for classification.
        elif family == "V":  # Test whether the mode is common vertical bending.
            field = vertical_common  # Use the common vertical field.
        else:  # Handle the lateral family.
            field = lateral_common if np.dot(lateral_common, lateral_common) >= np.dot(lateral_difference, lateral_difference) else lateral_difference  # Use the dominant lateral combination.
        parity_correlation = float(np.dot(field, field[::-1]) / (np.dot(field, field) + 1.0e-30))  # Evaluate main-span midpoint symmetry.
        parity = "S" if parity_correlation >= 0.0 else "A"  # Assign symmetric or antisymmetric parity.
        scores = [abs(float(np.dot(field, np.sin(number * math.pi * x / L_MAIN)))) / (float(np.linalg.norm(field) * np.linalg.norm(np.sin(number * math.pi * x / L_MAIN))) + 1.0e-30) for number in range(1, 9)]  # Project onto the first eight fixed-end sine fields.
        longitudinal_order = int(np.argmax(scores) + 1)  # Select the dominant longitudinal order.
        total_measure = energy_t + energy_v + energy_l + 1.0e-30  # Form the total classification measure.
        residual = float(np.linalg.norm(k_free @ eigenvectors[:, mode_index] - eigenvalues[mode_index] * (m_free @ eigenvectors[:, mode_index])) / (np.linalg.norm(k_free @ eigenvectors[:, mode_index]) + abs(eigenvalues[mode_index]) * np.linalg.norm(m_free @ eigenvectors[:, mode_index]) + 1.0e-30))  # Evaluate the normalized eigen residual.
        records.append({"mode": mode_index + 1, "frequency_hz": float(frequency), "family": family, "parity": parity, "longitudinal_order": longitudinal_order, "order_score": float(max(scores)), "torsion_fraction": energy_t / total_measure, "vertical_fraction": energy_v / total_measure, "lateral_fraction": energy_l / total_measure, "eigen_residual": residual})  # Store the auditable mode record.
    def select(family: str, parity: str, rank: int) -> dict | None:  # Select one physics-only modal family member.
        candidates = sorted([record for record in records if record["family"] == family and record["parity"] == parity], key=lambda record: record["frequency_hz"])  # Filter and sort only computed physical candidates.
        return candidates[rank - 1] if len(candidates) >= rank else None  # Return the requested rank or no result.
    selected = {"LS1": select("L", "S", 1), "LA1": select("L", "A", 1), "LS2": select("L", "S", 2), "LA2": select("L", "A", 2), "VA1": select("V", "A", 1), "VS1": select("V", "S", 1), "VA2": select("V", "A", 2), "VS2": select("V", "S", 2), "TA1": select("T", "A", 1), "TS1": select("T", "S", 1), "TS2": select("T", "S", 2)}  # Select all main-span physical families without target-frequency matching.
    with (OUT / "raw_modes.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the raw modal table.
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))  # Create a named-column CSV writer.
        writer.writeheader()  # Write the raw table header.
        writer.writerows(records)  # Write all solved mode records.
    with (OUT / "selected_modes.csv").open("w", newline="", encoding="utf-8-sig") as handle:  # Open the selected-family table.
        writer = csv.writer(handle)  # Create the selected-family CSV writer.
        writer.writerow(["label", "mode", "frequency_hz", "family", "parity", "longitudinal_order", "torsion_fraction", "eigen_residual"])  # Write the selected table header.
        for label, record in selected.items():  # Traverse every requested label.
            writer.writerow([label, None if record is None else record["mode"], None if record is None else record["frequency_hz"], None if record is None else record["family"], None if record is None else record["parity"], None if record is None else record["longitudinal_order"], None if record is None else record["torsion_fraction"], None if record is None else record["eigen_residual"]])  # Write the current selected result.
    relative_vector = np.r_[np.full(16, -0.5), np.full(16, 0.5)]  # Form a unit relative floor-translation test vector.
    vertical_indices = np.array([2 * number + 1 for number in range(16)] + [32 + 2 * number + 1 for number in range(16)])  # Address vertical terms in the passage floor-port matrix.
    effective_passage_stiffness = float(relative_vector @ passage_floor_increment[np.ix_(vertical_indices, vertical_indices)] @ relative_vector)  # Evaluate the formula-derived relative vertical stiffness per passage.
    summary = {"model": "formula_exact_v4_main_span", "explicit_rope_count": cable_count, "floor_rope_count": 32, "gantry_rope_count": 12, "free_dofs": int(len(free)), "floor_horizontal_force_per_rope_N": floor_horizontal, "gantry_horizontal_force_per_rope_N": gantry_horizontal, "passage_count_main_span": int(len(passage_stations)), "passage_effective_vertical_stiffness_N_per_m": effective_passage_stiffness, "portal_count_total": int(2 * len(portal_stations)), "maximum_eigen_residual": float(max(record["eigen_residual"] for record in records)), "selected": selected, "target_frequency_used": False}  # Assemble the complete calculation summary.
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # Write the machine-readable summary.
    print(json.dumps(summary, ensure_ascii=False, indent=2))  # Print the summary into the GitHub Actions log.
    return 0  # Report successful completion.
if __name__ == "__main__":  # Execute only when run as the main program.
    raise SystemExit(main())  # Return the program status to the shell.
