// Convert genuine native OpenFOAM cell data into a Gmsh view; no image rendering occurs here.
const fs = require('fs'); // Read only the supplied native VTK output.
const [input, output, field = 'p', rhoText = '1.225'] = process.argv.slice(2); // Require explicit source/output and physical field.
if (!input || !output || !['p', 'U'].includes(field)) throw Error('Usage: node vtk_to_gmsh_view.js native.vtk output.pos p|U [rho]'); // Reject ambiguous fields.
const text = fs.readFileSync(input, 'utf8'); // Read the native ASCII legacy VTK file.
if (!text.startsWith('# vtk DataFile') || !text.includes('ASCII\nDATASET UNSTRUCTURED_GRID')) throw Error('Only native ASCII unstructured VTK supported'); // Preserve a strict format contract.
const tokens = text.split('\n').slice(4).join(' ').trim().split(/\s+/); // Tokenize numerical records without geometry reconstruction.
let cursor = 0; // Track the actual VTK record position.
const word = () => tokens[cursor++]; // Read one format token.
const integer = () => Number(word()); // Read native integer counts.
const values = count => { const result = tokens.slice(cursor, cursor + count).map(Number); cursor += count; return result; }; // Read exact native arrays.
const readFields = () => { // Decode standard VTK FIELD arrays.
  word(); const count = integer(); const fields = {}; // Read the field-group name and array count.
  for (let i = 0; i < count; i++) { // Preserve every declared data array.
    const name = word(); const components = integer(); const tuples = integer(); word(); // Read the native array layout and scalar type.
    fields[name] = {components, tuples, data: values(components * tuples)}; // Preserve original floating-point values.
  } // Finish the field group.
  return fields; // Return fields keyed by their native names.
}; // No interpolation is performed during parsing.
if (word() !== 'FIELD') throw Error('Native TimeValue field expected'); // Require the native solver time metadata.
const metadata = readFields(); // Read actual physical result time.
if (word() !== 'POINTS') throw Error('POINTS section missing'); // Check native mesh format.
const pointCount = integer(); word(); const points = values(3 * pointCount); // Retain every native coordinate.
if (word() !== 'CELLS') throw Error('CELLS section missing'); // Require actual cell connectivity.
const cellCount = integer(); word(); const cells = []; // Read cell count and total connectivity size.
for (let index = 0; index < cellCount; index++) cells.push(values(integer())); // Preserve actual finite-volume cells.
if (word() !== 'CELL_TYPES') throw Error('CELL_TYPES section missing'); // Verify native element topology.
const types = values(integer()); // Read original cell types.
if (word() !== 'CELL_DATA' || integer() !== cellCount || word() !== 'FIELD') throw Error('Native CELL_DATA is missing or inconsistent'); // Require cell-supported physical values.
const fields = readFields(); // Read pressure and velocity arrays directly.
if (!fields[field] || fields[field].tuples !== cellCount) throw Error('Requested native field missing'); // Never substitute a different variable.
const density = Number(rhoText); // Convert OpenFOAM kinematic pressure to pascals explicitly.
if (!(density > 0)) throw Error('Air density must be positive'); // Reject invalid physical conversion.
const time = metadata.TimeValue.data[0]; // Retain the solver's actual result time.
const title = field === 'p' ? 'Native CFD static pressure (Pa)' : 'Native CFD speed (m/s)'; // Label only the field actually converted.
const rows = [`// Source ${input}; actual native time=${time}; partial SGT12 girder only.`, `View "${title}; t=${time}s; PARTIAL GIRDER" {`]; // Bind visual data to its provenance.
let used = 0; // Count actual cells included in the explicitly cropped view.
for (let index = 0; index < cellCount; index++) { // Convert native physical cells one-for-one.
  if (types[index] !== 13) throw Error('Only native triangular prism cells supported'); // Avoid guessing element topology.
  const coords = cells[index].map(id => points.slice(3 * id, 3 * id + 3)); // Retrieve original native coordinates.
  const zmin = Math.min(...coords.map(point => point[2])); // Select the actual lower extrusion face.
  const face = coords.filter(point => Math.abs(point[2] - zmin) < 1e-9); // Keep its original triangular vertices.
  if (face.length !== 3) throw Error('Native prism does not have a triangular lower face'); // Reject unexpected cell geometry.
  const center = [0, 1].map(axis => face.reduce((sum, point) => sum + point[axis], 0) / 3); // Determine whether the real cell falls inside the documented crop.
  if (center[0] < -0.7 || center[0] > 2 || Math.abs(center[1]) > 0.8) continue; // Crop only the display to the component near wake.
  const value = field === 'p' ? fields.p.data[index] * density : Math.hypot(...fields.U.data.slice(index * 3, index * 3 + 3)); // Convert native cell pressure or velocity magnitude without smoothing.
  if (!Number.isFinite(value)) throw Error('Nonfinite native physical field'); // Do not render divergent fields as results.
  rows.push(`ST(${face.flat().join(',')}){${value},${value},${value}};`); // Preserve piecewise-constant native cell values on the actual face.
  used++; // Track the rendered native subset.
} // Finish native-cell conversion.
rows.push('};'); // Close the native Gmsh postprocessing view.
fs.writeFileSync(output, rows.join('\n') + '\n'); // Save a native data-view file, not a synthesized image.
fs.writeFileSync(output + '.json', JSON.stringify({source:input,time_s:time,field,source_cells:cellCount,displayed_cells:used,display_crop_m:{x:[-0.7,2],y:[-0.8,0.8]},representation:'piecewise_constant_native_cell_data',density_kgm3:density,renderer:'Gmsh native OpenGL'},null,2)+'\n'); // Preserve conversion and display provenance.
