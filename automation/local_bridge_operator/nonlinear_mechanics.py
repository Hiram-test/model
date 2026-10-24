import os # Control independent nonlinear numerical resource use.
os.environ['OPENBLAS_NUM_THREADS']='1' # Bound matrix and tensor operations to one BLAS thread.
import json,re # Parse actual native output frames without inferring missing increments.
import numpy as np # Evaluate total-Lagrangian finite-strain internal forces.
from fem import EDGES,REPO,ROOT,sha,write_json # Reuse exact C3D10 node ordering and provenance helpers.
OUT=REPO/'build/local-nonlinear-20261024' # Keep nonlinear evidence separate from previous static datasets.
class FiniteStrain: # Implement C3D10 St-Venant Kirchhoff kinematics consistent with CalculiX ELASTIC+NLGEOM.
    def __init__(self,xyz,tet,groups,E,nu): # Cache reference gradients and constitutive fields.
        self.xyz=xyz;self.tet=tet;corners=xyz[tet[:,:4]];J=np.stack([corners[:,i]-corners[:,0] for i in [1,2,3]],axis=2);det=np.linalg.det(J);assert np.all(det>0);self.weights=det/24 # Preserve exact reference integration weights.
        dL=np.einsum('ij,ejk->eik',np.array([[-1,-1,-1],[1,0,0],[0,1,0],[0,0,1.]]),np.linalg.inv(J));quad=np.full((4,4),.1381966011250105);np.fill_diagonal(quad,.5854101966249685);gradients=[] # Use native four-point tetrahedral integration and affine reference mapping.
        for L in quad: # Evaluate ten-node physical shape-function gradients at every integration point.
            grad=np.empty((len(tet),10,3));grad[:,:4]=(4*L-1)[None,:,None]*dL # Differentiate the four quadratic vertex functions.
            for j,(i,k) in enumerate(EDGES): grad[:,4+j]=4*(L[i]*dL[:,k]+L[k]*dL[:,i]) # Differentiate six quadratic edge functions.
            gradients.append(grad) # Retain the same quadrature rule as the native solver.
        self.gradients=np.asarray(gradients);ev=np.where(groups==1,200000.,E);nv=np.where(groups==1,.3,nu);self.mu=ev/(2*(1+nv));self.lam=ev*nv/((1+nv)*(1-2*nv)) # Preserve heterogeneous linear PK2 constitutive parameters.
    def internal(self,displacement): # Compute full free/support nodal internal forces without using a linear stiffness surrogate.
        element_u=np.asarray(displacement).reshape(-1,3)[self.tet];force=np.zeros_like(self.xyz);energy=0.;min_j=1e30;strain_max=0. # Allocate actual finite-strain state diagnostics.
        for grad in self.gradients: # Integrate total-Lagrangian equilibrium over the reference tetrahedra.
            F=np.eye(3)[None,:,:]+np.einsum('eai,eaj->eij',element_u,grad);green=.5*(np.einsum('eki,ekj->eij',F,F)-np.eye(3));trace=np.trace(green,axis1=1,axis2=2);S=self.lam[:,None,None]*trace[:,None,None]*np.eye(3)+2*self.mu[:,None,None]*green # Calculate deformation gradient, Green strain and second Piola stress.
            P=np.einsum('eik,ekj->eij',F,S);element_force=np.einsum('eij,eaj->eai',P,grad)*self.weights[:,None,None];np.add.at(force,self.tet.ravel(),element_force.reshape(-1,3)) # Assemble first-Piola internal forces on original nodal degrees.
            energy+=float(np.sum((.5*self.lam*trace**2+self.mu*np.sum(green**2,axis=(1,2)))*self.weights));min_j=min(min_j,float(np.linalg.det(F).min()));strain_max=max(strain_max,float(np.abs(green).max())) # Audit elastic energy, orientation and actual strain regime.
        return force,{'energy_Nmm':energy,'min_J':min_j,'max_abs_Green_strain':strain_max} # Return full force field and physical diagnostics.
def parse_dat(path,count): # Read every actual U/RF frame with exact native pseudo-time.
    frames={};active=None;time=None # Preserve displacement and reaction ownership per increment.
    for line in path.read_text().splitlines(): # Parse only explicit native table headers and data rows.
        match=re.search(r'(displacements|forces) \(.*\).*time\s+([\d.Ee+\-]+)',line) # Identify actual printed frame and field.
        if match: # Begin one known frame table.
            time=float(match.group(2));active='u' if match.group(1)=='displacements' else 'rf';frames.setdefault(time,{})[active]=np.full((count,3),np.nan);continue # Require complete source-node coverage.
        if active and re.match(r'^\s*\d+\s+',line): # Read native source-node vectors.
            values=line.split();node=int(values[0])-1 # Recover stable original node ID.
            if 0<=node<count and len(values)>=4: frames[time][active][node]=[float(v.replace('D','E')) for v in values[1:4]] # Assign exact native values without interpolation.
    return [(t,frames[t]) for t in sorted(frames) if 'u' in frames[t] and 'rf' in frames[t]] # Preserve ordered increments with both fields available.
