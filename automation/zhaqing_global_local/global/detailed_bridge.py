#!/usr/bin/env python3  # Build source-dimensional Zhaqing deck plates and16b channels as explicit full-order structural entities.
import argparse  # Select exact source and output namespaces.
import json  # Preserve drawing facts separately from connection assumptions.
import math  # Derive physical cross-section properties.
from pathlib import Path  # Keep all archived identities explicit.
import numpy as np  # Assemble native mesh coordinates and physical masses without plotting.
import openseespy.opensees as ops  # Use the compiled OpenSees nonlinear finite-element engine.
import opensees_bridge as base  # Reuse source decoding and independently audited equilibrium orchestration.
def build(source,statepath,subdivision=1):  # Construct all physical deck panels, stiffeners, cables and towers without a response basis.
    old,groups,sets,cload,accessory,materials=base.parse(source)  # Decode authenticated original topology for towers, cables and anchors.
    state=json.loads(statepath.read_text())  # Recover nominal cable pretension as an explicit initial guess.
    old.update({int(k):np.array(v) for k,v in state['nodeCoordinatesMm'].items()})  # Apply source-evidenced main cable coordinates.
    cable_nodes={n for eid,conn in groups['MAIN_CABLES'] for n in conn}  # Identify the physical cable points independently of tower-column axes.
    tower_tops=set(sets['TOWER_TOPS'])  # Preserve the authentic column-center coordinates at transverse plus/minus2750mm.
    anchor_left=min(old[n][0] for n in sets['MAIN_CABLE_ANCHORS'])  # Recover the actual historical left anchor station.
    anchor_right=max(old[n][0] for n in sets['MAIN_CABLE_ANCHORS'])  # Recover the actual historical right anchor station.
    def cable_plane(x,sign):  # Apply the reviewed5100mm saddle spacing and4700mm anchor spacing without moving tower columns.
        width=2550. if 0.<=x<=82000. else 2350.+200.*((x-anchor_left)/(-anchor_left) if x<0. else (anchor_right-x)/(anchor_right-82000.))  # Retain straight transverse side-span interpolation between actual interfaces.
        return sign*width  # Return the appropriate actual bridge side.
    for n in cable_nodes-tower_tops:  # Correct only cable coordinates that do not also define source concrete columns.
        old[n][1]=cable_plane(old[n][0],math.copysign(1.,old[n][1]))  # Preserve longitudinal/elevation evidence while correcting transverse geometry.
    for eid,conn in groups['HANGERS']:  # Move physical hanger planes to the reviewed saddle/main-cable plane.
        for n in conn:  # Correct both hanger top and bottom source coordinates consistently.
            old[n][1]=math.copysign(2550.,old[n][1])  # Preserve actual5100mm hanger-line spacing.
    keepgroups=('MAIN_CABLES','TOWER_COLUMNS','TOWER_TOP_BEAMS')  # Preserve only directly compatible original native geometric groups.
    keep={n for g in keepgroups for e,c in groups[g] for n in c}  # Derive the exact original retained geometric node population.
    keep.update(sets['WIND_ANCHORS'])  # Preserve source actual candidate anchorage coordinates explicitly.
    nodes={n:old[n].copy() for n in keep}  # Remove the entire old equivalent deck mesh instead of changing its thickness in place.
    nextnode=max(old)+1  # Allocate all detailed physical node identities above the complete old source range.
    elements,parents,properties,rigids={}, {}, {}, []  # Keep detailed topology, source membership, physical sections, and explicit connections.
    nodalmass={n:0. for n in nodes}  # Assemble complete physical mass independently of display geometry.
    structural=set()  # Track nodes with native rotational stiffness or explicit connection kinematics.
    lookup={tuple(np.round(v,6)):n for n,v in nodes.items()}  # Share only identical physical coordinates.
    def node(p,share=True):  # Create a real mesh point while allowing intentional disconnected panel joints.
        nonlocal nextnode  # Allocate deterministic new physical node IDs.
        key=tuple(np.round(p,6))  # Identify coincident coordinates with micrometre precision.
        if share and key in lookup:  # Preserve physical incidence only when sharing is intended.
            return lookup[key]  # Reuse the existing full-order node.
        result=nextnode  # Reserve one new physical identity.
        nextnode+=1  # Advance allocation without colliding with old source nodes.
        nodes[result]=np.array(p,dtype=float)  # Preserve actual source-dimensional coordinates.
        nodalmass[result]=0.  # Initialize mass for subsequent actual element integration.
        if share:  # Keep explicitly separated panel joints from accidental merging.
            lookup[key]=result  # Register normal shared structural nodes.
        return result  # Return the complete physical node identity.
    def element(group,conn,prop,parent):  # Register one explicit structural finite element.
        tag=len(elements)+1  # Allocate a deterministic native element identity.
        elements[tag]=(group,list(conn))  # Preserve actual connectivity and physical group.
        properties[tag]=dict(prop)  # Bind its material and cross section explicitly.
        parents[tag]=parent  # Preserve drawing or old source-member provenance.
        return tag  # Return native identity for panel mass accounting.
    def rect(b,h):  # Derive a physical rectangular beam section.
        a,c=max(b,h),min(b,h)  # Order cross-section sides for torsion.
        return dict(A=b*h,Iy=b*h**3/12,Iz=h*b**3/12,J=a*c**3*(1/3-.21*c/a*(1-c**4/(12*a**4))))  # Preserve both bending axes and Saint-Venant torsion.
    def hsection(b,h,tw,tf):  # Derive a source-dimensional openIsection.
        return dict(A=2*b*tf+(h-2*tf)*tw,Iy=(b*h**3-(b-tw)*(h-2*tf)**3)/12,Iz=(2*tf*b**3+(h-2*tf)*tw**3)/12,J=(2*b*tf**3+(h-2*tf)*tw**3)/3)  # Use thin-wall open-section torsion and explicit flange/web geometry.
    saddle_map={}  # Keep separate physical saddle and concrete tower-column identities.
    for tower in sorted(tower_tops):  # Create all four real200mm-inboard saddle interfaces.
        point=old[tower].copy()  # Preserve reviewed saddle longitudinal station and source elevation.
        point[1]=math.copysign(2550.,point[1])  # Locate the actual transverse saddle seat independently of the column center.
        saddle_map[tower]=node(point)  # Allocate one actual support point without displacing the concrete column.
        rigids.append((tower,saddle_map[tower],'reviewed200mm inward saddle seat; assumed rigid seat-to-tower connection'))  # Make the physical eccentricity and connection-law assumption explicit.
    for g in keepgroups:  # Restore original source tower and main-cable geometry.
        for eid,conn in groups[g]:  # Keep exact old stable source connectivity.
            if g=='MAIN_CABLES':  # Use actual283wire total area as a true axial cable section.
                prop=dict(A=283*math.pi*2.5**2,E=195000.,rho=7.85e-9,sigma=state['elementStates'][str(eid)]['axialStressMPa'])  # Retain source nominal stress, not an assumed bending-regularized cable.
            else:  # Preserve source concrete tower dimensions pending local tower reinforcement detailing.
                prop=rect(1000.,1500.) if g=='TOWER_COLUMNS' else rect(1500.,500.)  # Retain complete tower cross sections.
                prop.update(E=30000.,nu=.2,rho=2.5e-9)  # Preserve concrete screening material properties.
            element(g,[saddle_map.get(n,n) for n in conn] if g=='MAIN_CABLES' else conn,prop,eid)  # Connect the physical cable to its separate real saddle seat while preserving tower-column topology.
    stations=[2000.+3000.*i for i in range(27)]  # Use source-bound27crossbeam stations rather than the old0/82m substitutions.
    channel_y=[-2340.+1560.*panel+312.*k for panel in range(3) for k in range(6)]  # Place six16b channels in each of the three1560mm panels.
    ys=sorted(set([-2750.,-2550.,2550.,2750.]+channel_y+[-2340.+1560.*p+156.*j for p in range(3) for j in range(11)]))  # Resolve all real plate/channel support positions across the crossbeam.
    cb={}  # Index real crossbeam centroid nodes at every physical transverse attachment location.
    cbprop=dict(A=300.*420.-280.*400.,Iy=(300.*420.**3-280.*400.**3)/12,Iz=(420.*300.**3-400.*280.**3)/12,J=4*(290.*410.)**2/(2*(290.+410.)/10))  # Use sourceIII/III420×300×10closedTWO-WEBboxwithclosedcelltorsion;retain416webtableconflict.
    cbprop.update(E=200000.,nu=.3,rho=7.85e-9)  # Preserve steel material properties.
    for ix,x in enumerate(stations):  # Build every complete real crossbeam.
        row=[node([x,y,-210.]) for y in ys]  # Locate centroid from sourcedrawingtopz0and420overall depth.
        cb.update({(ix,y):n for y,n in zip(ys,row)})  # Preserve exact support interface lookup.
        for a,b in zip(row,row[1:]):  # Subdivide the physical openIsection at each plate/channel support.
            element('CROSSBEAMS',[a,b],cbprop,f'SGT06-11:III:beam{ix+1}')  # Bind actual section profile to sourcedrawing.
        physical=5500.*cbprop['A']*7.85e-9  # Compute mass represented by the explicit flange/web section.
        extra=(.75095-physical)/len(row)  # Preserve drawing-table750.95kg by separately accounting for unmeshed plates/bolts.
        for n in row:  # Distribute only documented extra crossbeam mass.
            nodalmass[n]+=extra  # Do not invent stiffener stiffness from missing geometry.
    la,lb,lt=100.,63.,10.  # Use sourceN5angle100/63mmlegsand10mmthickness.
    lA=la*lt+(lb-lt)*lt  # Avoiddoublecountingtheoverlappingcorner.
    cx=(la*lt*la/2+(lb-lt)*lt*lt/2)/lA  # Locateactualanglecentroidoutwardfromboxface.
    cz=(la*lt*lt/2+(lb-lt)*lt*(lt+(lb-lt)/2))/lA  # Locatecentroidbelowledgetop.
    Ixx=la*lt**3/12+la*lt*(lt/2-cz)**2+lt*(lb-lt)**3/12+(lb-lt)*lt*(lt+(lb-lt)/2-cz)**2  # Integratetheactualasymmetricanglesection.
    Izz=lt*la**3/12+la*lt*(la/2-cx)**2+(lb-lt)*lt**3/12+(lb-lt)*lt*(lt/2-cx)**2  # Retainactualtransversebendinginertia.
    Ixz=la*lt*(la/2-cx)*(lt/2-cz)+(lb-lt)*lt*(lt/2-cx)*(lt+(lb-lt)/2-cz)  # Preserveangleproductofinertiaforprincipalaxisrotation.
    ledge_ys=[y for y in ys if -2340.<=y<=2340.]  # Useverified4680mmcontinuousanglelength.
    for ix,x in enumerate(stations):  # AddthetworealN5supportledgestoeverycrossbeam.
        for side in (-1.,1.):  # Placetheanglesonbothlongitudinalboxfaces.
            tensor=np.array([[Ixx,-side*Ixz],[-side*Ixz,Izz]])  # Expressactualangleinertiaaboutnativebeamlocalaxes.
            principal,axes=np.linalg.eigh(tensor)  # Rotateexactlinearelasticbendingintoprincipalcross-sectionaxes.
            prop=dict(A=lA,Iy=float(principal[0]),Iz=float(principal[1]),J=(la*lt**3+(lb-lt)*lt**3)/3,E=200000.,nu=.3,rho=7.85e-9,vecz=[-float(axes[0,1]),0.,float(axes[1,1])])  # PreserveactualasymmetricLsectionratherthananequivalentrectangle.
            row=[node([x+side*(150.+cx),y,-170.-cz]) for y in ledge_ys]  # Locateangleswithtop170mmbelowcrossbeamtopandsource100mmoutwardleg.
            for a,bn in zip(row,row[1:]):  # Meshtherealcontinuoussupportangletransversely.
                element('PANEL_SUPPORT_ANGLE',[a,bn],prop,'SGT08:N5:angle100/63x10')  # Retainsourceverifiedsupportsteelgeometry.
            for y,n in zip(ledge_ys,row):  # Connectthecontinuouslyweldedangletoitsactualboxweb.
                rigids.append((cb[ix,y],n,'assumed continuous rigid weld angle-to-box; real section and offset'))  # Preserveactualsupportlinewithdeclaredweldkinematics.
            extra=4680.*lA*7.85e-9/len(ys)  # Removeexplicitanglemassfrompreviouscrossbeamunmeshedmassallowance.
            for y in ys:  # Preserveverified750.95kgcrossbeammasswithoutdoublecountingnewangles.
                nodalmass[cb[ix,y]]-=extra  # MovephysicalmassfromallowancetoactualmodeledN5steel.
    girderprop=hsection(400.,400.,13.,21.)  # Use exact sourceHW400×400×13×21 geometry.
    girderprop.update(E=200000.,nu=.3,rho=7.85e-9)  # Preserve source steel elasticity and mass density.
    for bay in range(26):  # Build all26actual2696mm longitudinal-girder pieces per side.
        for y in (-2550.,2550.):  # Use sourceverified5100mmgirdercenter spacing.
            xs=np.linspace(stations[bay]+152.,stations[bay+1]-152.,13)  # Keep source2696mmpiece length and2mmcrossbeam-face clearance exactly.
            row=[node([x,y,-200.]) for x in xs]  # Place400mmdeepgirder topat0mm consistent with sourcedrawingfloor reference.
            for a,b in zip(row,row[1:]):  # Retain every physical girder mesh segment.
                element('LONG_GIRDERS',[a,b],girderprop,'SGT12:5161:5165')  # Preserve actual section and piece-length provenance.
            rigids.extend([(cb[bay,y],row[0],'assumed rigid bolted girder end'),(cb[bay+1,y],row[-1],'assumed rigid bolted girder end')])  # Model unknown connection stiffness explicitly without extending the realgirder length.
    h,b,tw,tf=160.,65.,8.5,10.  # Use source16b channel dimensions from SGT04section and material table.
    chA=2*b*tf+(h-2*tf)*tw  # Compute sharp-corner channel material area; fillets are separately noted.
    yc=(2*b*tf*b/2+(h-2*tf)*tw*tw/2)/chA  # Locate true channel centroid from its outerweb plane.
    chIy=(b*h**3-(b-tw)*(h-2*tf)**3)/12  # Compute channel strong-axis inertia about its centroid.
    chIz=2*(tf*b**3/12+b*tf*(b/2-yc)**2)+(h-2*tf)*tw**3/12+(h-2*tf)*tw*(tw/2-yc)**2  # Retain actual asymmetric weak-axis inertia.
    chprop=dict(A=chA,Iy=chIy,Iz=chIz,J=(2*b*tf**3+(h-2*tf)*tw**3)/3,E=200000.,nu=.3,rho=7.85e-9)  # Bind channel constitutive and fullcross-section data.
    profiles=json.loads((Path(__file__).resolve().parents[3]/'results/zhaqing_global_local_20261026/evidence/panel_stiffener_profiles.json').read_text())  # ReadactualDWG-derivedN4filletoutlinewithoutinventingnotchgeometry.
    contour=np.array(profiles['N4']['points_annotation_fitted_mm'])  # Usetheexplicitdocumented295mmannotation-fitvariantof295.168mmnativeoutline.
    def profile_height(x):  # Intersectthesourcepolygonwithaphysicalverticalsection.
        values=[]  # Collectsource-boundarycrossingsatthisstation.
        for pa,pb in zip(contour,np.roll(contour,-1,axis=0)):  # VisitallactualstraightenednativeLINE/ARCboundarysegments.
            if min(pa[0],pb[0])-1e-8<=x<=max(pa[0],pb[0])+1e-8:  # Retainonlysegmentscrossingthephysicalstation.
                if abs(pb[0]-pa[0])<1e-10:  # Handletheverticalsourceendfaceexplicitly.
                    values.extend([pa[1],pb[1]])  # Keepbothsourceendfaceextrema.
                else:  # Linearlyinterpolatethepublishedarc-polylineboundary.
                    values.append(pa[1]+(x-pa[0])/(pb[0]-pa[0])*(pb[1]-pa[1]))  # Preserveactualsourcegeometrybetweenrecordedpoints.
        return max(values)-min(values)  # Returnactualremainingsteelheightatthisstation.
    panel_ids=[]  # Track each actual discretepanel independently for mass closure and graph ownership.
    for bay in range(26):  # Build26real panel bays between documented3mcrossbeam stations.
        for panel in range(3):  # Build three separate1560mmpanels across eachbay.
            x0=stations[bay]+155.  # Preserve2690mmplate length with5mmclearance inside2700mmcrossbeamface gap.
            y0=-2340.+1560.*panel  # Preserve actual4680mmthree-panel field width.
            xx=sorted(set([0.,12.,2678.,2690.]+np.linspace(0.,2690.,13).tolist()))  # Include exact2666mmchannel endpoints and fineplate longitudinal mesh.
            yy=np.linspace(0.,1560.,11)  # Resolve every312mmchannelweb station and oneinteriorplate point perchannelinterval.
            grid={(i,j):node([x0+x,y0+y,-5.],share=False) for i,x in enumerate(xx) for j,y in enumerate(yy)}  # Keep adjacentpaneljoints distinct and plate midsurface at−5mm.
            tags=[]  # Track actual cells belonging to this onephysical panel.
            for i in range(len(xx)-1):  # Mesh the exactsourceplate footprint longitudinally.
                for j in range(len(yy)-1):  # Mesh the explicit10mmsteelplate across its actualwidth.
                    tags.append(element('DECK_PLATES',[grid[i,j],grid[i+1,j],grid[i+1,j+1],grid[i,j+1]],dict(E=200000.,nu=.3,rho=7.85e-9,t=10.),f'SGT04:762F:bay{bay+1}:panel{panel+1}'))  # Use individualplate shellcells instead of a50mmequivalentdeck.
            for k in range(6):  # Instantiate all sixactual16b channels in each physicalpanel.
                opening=1. if k%2==0 else -1.  # Preserve alternatinginward channelopening from nativecross-section.
                indexes=[i for i,x in enumerate(xx) if 12.-1e-6<=x<=2678.+1e-6]  # Limitchannelsteel to exact2666mmlength.
                chain=[node([x0+xx[i],y0+312.*k+opening*yc,-90.],share=False) for i in indexes]  # Place actualchannelcentroid with exacttransverse andvertical eccentricity.
                for a,bn in zip(chain,chain[1:]):  # Keep eachphysicalchannel as explicitcorotationalsegments.
                    tags.append(element('DECK_CHANNEL16B',[a,bn],chprop,f'SGT04:762A:k{k+1}'))  # Bindgeometry and steelarea to sourcechannelrecord.
                for i,n in zip(indexes,chain):  # Couple weldedchannel motion to its actualplatewebintersection.
                    rigids.append((grid[i,2*k],n,'assumed fully welded plate-channel connection; linear rigid arm at exact eccentricity'))  # Declareconnection law independently from realsteelgeometry.
            for edge,i in ((0,0),(1,len(xx)-1)):  # AddthetwoactualN3transverseendplatesfromnativeplanorientation.
                x=x0+(5. if edge==0 else 2685.)  # Place10mmendplatecentroidsinside2690mmdeckplateends.
                row=[node([x,y0+y,-90.],share=False) for y in yy]  # Preserveactual1560×160×10drawnendplategeometry.
                prop=rect(10.,160.)  # Useactualverticalplatebendingsectioninthisglobalbeamrepresentation.
                prop.update(E=200000.,nu=.3,rho=7.85e-9)  # Preserveactualsteelproperties.
                for a,bn in zip(row,row[1:]):  # Resolveactualendplatefieldacrossallchannelbays.
                    tags.append(element('PANEL_ENDPLATE_N3',[a,bn],prop,'SGT04:N3:drawn1560mm_bill2690mm_CONFLICT'))  # Preservedrawingshapeandbilllengthconflictwithoutclaimingfabricationclosure.
                for j,n in enumerate(row):  # Coupleactualweldedendplatetoptoitsphysicaldeckplateedge.
                    rigids.append((grid[i,j],n,'assumed fully weldedN3endplate-to-deck;drawn1560mmvariant'))  # Bindrealoffsetwhileleavingjointvalidationexplicit.
            for localx in (672.5,1345.,2017.5):  # Usethethreeactual672.5mmcross-stiffenerstations.
                ix=min(range(len(xx)),key=lambda i:abs(xx[i]-localx))  # Matchtheexactsourcequarterpointsalreadyintheplategrid.
                if abs(xx[ix]-localx)>1e-6:  # Rejectasilentlyshiftedsourcecrossstiffenerstation.
                    raise RuntimeError('Crossstiffenerstationnotinthephysicalplategrid')  # Preserveexactdrawinglocation.
                for gap in range(5):  # BuildactualN4,N5,N4,N5,N4acrossthefivechannelgaps.
                    is_n4=gap%2==0  # Distinguishfacingflange-fitprofilesfromback-to-backrectangularinserts.
                    stations_y=[0.,9.,56.5,147.5,238.5,286.,295.] if is_n4 else[0.,156.,312.]  # ResolveactualN4filletshouldersandcentralplatewithoutuniformrectangleapproximation.
                    left=y0+312.*gap+(8.5 if is_n4 else 0.)  # Useactualchannelinnerwebfacefor295mmN4andouterwebfacefor312mmN5.
                    row=[node([x0+localx,left+y,-90.],share=False) for y in stations_y]  # Keepactualmidheightaxesandtrueinsertlengths.
                    for j,(a,bn) in enumerate(zip(row,row[1:])):  # Usepiecewisephysicalsectionheightfromactualsourceprofile.
                        samples=np.linspace(stations_y[j]+1e-7,stations_y[j+1]-1e-7,17)  # Integratethepublishedprofileovertheactualsegment.
                        height=float(np.trapezoid([profile_height(v) for v in samples],samples)/(samples[-1]-samples[0])) if is_n4 else 160.  # Preserveactualnotchedsteelareaasaglobalsectionratherthanfillingremovedcorners.
                        prop=rect(10.,height)  # Retainphysical10mmplatethicknessandprofile-dependentheight.
                        prop.update(E=200000.,nu=.3,rho=7.85e-9)  # Preserveactualsteelmaterial.
                        tags.append(element('PANEL_CROSS_STIFFENER_N4' if is_n4 else 'PANEL_CROSS_STIFFENER_N5',[a,bn],prop,'SGT04:N4:295mm_annotation_fit' if is_n4 else 'SGT04:N5:312mm'))  # Storeactualsourceprofileidentityperphysicalfiniteelement.
                    midpoint=3 if is_n4 else 1  # Locateactualspan-midpointwherefullheightstiffenerreachesdeckunderside.
                    for slave,j in ((row[0],2*gap),(row[midpoint],2*gap+1),(row[-1],2*gap+2)):  # Coupleinsertendsatrealchannelwebsanditsmiddleatdeckweldline.
                        rigids.append((grid[ix,j],slave,'assumed rigid weldedprofile-stiffener connection;sourcegeometryretained'))  # DeclareconnectionkinematicswithoutinventingremovedN4cornermaterial.
            first=xx.index(12.)  # Selectactualchannelstart12mminsidetheplateedge.
            last=xx.index(2678.)  # Selectactual2666mmchannelend.
            for k in range(6):  # PlaceactualchannelbottomsupportswithinN5ledge150..250mmfromboxcenter.
                y=y0+312.*k  # Preserveeachsourcechannelouterwebplane.
                rigids.extend([(cb[bay,y],grid[first,2*k],'assumed bolted channel-bottom bearing on actualN5ledge; no contactuplift'),(cb[bay+1,y],grid[last,2*k],'assumed bolted channel-bottom bearing on actualN5ledge; no contactuplift')])  # Actualchannelend167mmfromcenterfallsonthe100mmwideangleledge.
            panel_ids.append((bay,panel,tags,list(grid.values())))  # Preservepanel identity for truthfulmass andlocalfield exports.
    for eid,conn in groups['HANGERS']:  # Recreateall50sourcehangers at actualcrossbeam lowerinterface.
        top=conn[1] if old[conn[1]][2]>old[conn[0]][2] else conn[0]  # Resolvephysicaluppercable node fromsourcecoordinates.
        bottom=conn[0] if top==conn[1] else conn[1]  # Retainsourcehangerbottom identity forprovenance.
        x,y=old[bottom][:2]  # Preserveactualhangerstation andplane.
        ix=min(range(27),key=lambda i:abs(stations[i]-x))  # Matchtheverified5..77mhangertothesamecrossbeamstation.
        n=node([x,y,-420.])  # Locate the actualcrossbeamundersideinterface fromtop0and420depth.
        rigids.append((cb[ix,float(y)],n,'assumed rigid hanger clevis attachment at crossbeam underside'))  # Keepconnection eccentricity explicit andsource geometry separate fromstiffnessassumption.
        A=math.pi*16**2  # Preserveactual32mmdiameterhanger area.
        element('HANGERS',[n,top],dict(A=A,E=200000.,rho=7.85e-9,sigma=state['elementStates'][str(eid)]['axialStressMPa']),eid)  # Reuse nominalF3stressonlyasinitialguessfornewgeometryequilibrium.
    windanchors=sorted(sets['WIND_ANCHORS'],key=lambda n:(old[n][1],old[n][0]))  # Ordercandidateanchorsdeterministicallybyphysicalplaneandlongitudinalposition.
    for n in windanchors:  # Retainallfourwindcablepathswithoutcallingunverifiedanchorssurveyed.
        ysign=1. if old[n][1]>0 else -1.  # Recovercableplane.
        ix=12 if old[n][0]<50000 else 26  # Use documentedbeam13and27attachmentstations.
        attached=cb[ix,ysign*2750.]  # Attachwindcableatrealcrossbeamend.
        chain=[attached]+[node(nodes[attached]+j/4*(nodes[n]-nodes[attached])) for j in range(1,4)]+[n]  # Resolvephysicalcablesagwithfouraxialsegments.
        for a,bn in zip(chain,chain[1:]):  # Keepwindcablefull-orderinternalnodesexplicit.
            element('WIND_CABLES',[a,bn],dict(A=math.pi*12**2,E=100000.,rho=7.85e-9,sigma=10000/(math.pi*12**2)),'SGT32:nominal10kN')  # Declareprovisionalpretensionandcandidateanchorgeometry.
    ops.wipe()  # Clearonlythisprocess'snativeFEMdomain.
    ops.model('basic','-ndm',3,'-ndf',6)  # Retainallphysical3Dtranslationsandrotations.
    for n,p in nodes.items():  # Createeveryactualdetailedmeshnode.
        ops.node(n,*p.tolist())  # PassrealN-mm-tonnesourcecoordinatesunchanged.
    ops.section('ElasticMembranePlateSection',1,200000.,.3,10.,0.)  # Useactual10mmsteelplateelasticsectionandnativegeometricnonlinearity.
    cellmass={}  # Trackexplicitsteelmassperphysicalelement.
    for tag,(group,conn) in elements.items():  # Instantiateeveryphysicalnativeelement.
        p=properties[tag]  # Recoveritsactualmaterialandcrosssection.
        pts=[nodes[n] for n in conn]  # Readactualmeshcoordinates.
        if group=='DECK_PLATES':  # Useeachphysicaldiscreteplate'snonlinearshellkinematics.
            ops.element('ShellNLDKGQ',tag,*conn,1)  # Keepfullgeometricnonlinearityandindividualpaneljoints.
            mass=np.linalg.norm(np.cross(pts[1]-pts[0],pts[3]-pts[0]))*10*7.85e-9  # Integrateonlytheactualplatefootprint.
            structural.update(conn)  # Shellnodescarryphysicalrotations.
        elif group in ('MAIN_CABLES','HANGERS','WIND_CABLES'):  # Usephysicalaxialmembersratherthanbendingregularization.
            ops.uniaxialMaterial('Elastic',2*tag,p['E'])  # Useelasticwireorhangerconstitutivelawexplicitly.
            ops.uniaxialMaterial('InitStressMaterial',2*tag+1,2*tag,p['sigma'])  # Treatnominalsourceforcesasprestateinitialguess,notacceptedfabricationlengths.
            ops.element('corotTruss',tag,*conn,p['A'],2*tag+1,'-doRayleigh',1)  # Solvethecompletegeometricallynonlinearaxialstructure.
            mass=np.linalg.norm(pts[1]-pts[0])*p['A']*p['rho']  # Preserveactualaxialsteelvolume.
        else:  # Useactualsectioninertiasinlarge-rotationnativebeamelements.
            delta=pts[1]-pts[0]  # Recoveractualmemberdirection.
            vec=p.get('vecz',[1.,0.,0.] if abs(delta[2])>.9*np.linalg.norm(delta) else [0.,0.,1.])  # Avoidadegeneratebeamreferencevector.
            ops.geomTransf('Corotational',tag,*vec)  # Keepfullbeamgeometricnonlinearity.
            ops.element('elasticBeamColumn',tag,*conn,p['A'],p['E'],p['E']/(2*(1+p['nu'])),p['J'],p['Iy'],p['Iz'],tag)  # Retainactualstrong/weakbending,torsion,andaxialresponse.
            mass=np.linalg.norm(delta)*p['A']*p['rho']  # Integrateactualphysicalbeamsteel/concretevolume.
            structural.update(conn)  # Beamnodesretainphysicalrotationdegrees.
        cellmass[tag]=mass  # Retainexplicitmassforpanelclosure.
        for n in conn:  # Distributelumpedphysicalmassconservatively.
            nodalmass[n]+=mass/len(conn)  # Preservetotalmassindependentofmesh.
    for bay,panel,tags,pnodes in panel_ids:  # Closetheactual774.53kgpanelmaterialtablewithoutinventingmissingstiffness.
        difference=.77453-sum(cellmass[t] for t in tags)  # AccountforN3bill-vs-drawnlengthconflict,filletsandboltswithoutduplicatingexplicitstiffenermass.
        if difference<0:  # Rejectanexplicitsteelmodelheavierthanthesourcepaneltable.
            raise RuntimeError('Panelmassovershootsverified774.53kgtable')  # Exposegeometry/massmismatchdirectly.
        for n in pnodes:  # Spreadtheverifiedunmodeledmassoverthatphysicalpanelonly.
            nodalmass[n]+=difference/len(pnodes)  # Preserveactualpanelmasswhileflaggingunmodeledstiffenerstiffness.
    parent_map={slave:(master,meaning) for master,slave,meaning in rigids}  # Resolveallnativephysicalconnectionownershipbeforeconstraintcreation.
    flattened=[]  # Flattenrigid-armchainswithoutchangingtheirrealcoordinateoffsets.
    for slave,(master,meaning) in parent_map.items():  # Visitoneconstraintpereachdependentphysicalnode.
        seen={slave}  # Rejectcyclicconnectiontopologyexplicitly.
        while master in parent_map:  # Replaceonlychainedkinematicmastersbytheultimateindependentparent.
            if master in seen:  # Guardagainstaccidentalrigidconnectioncycles.
                raise RuntimeError('Rigidconnectioncycle')  # Preventasingularorambiguousconstraintmodel.
            seen.add(master)  # Recordthevisitedphysicalmaster.
            master=parent_map[master][0]  # Preservetheexactsumofreferenceoffsetsimplicitlythroughactualcoordinates.
        flattened.append((master,slave,meaning))  # StoreoneindependentnativeMPconstraintperphysicalslave.
    rigids=flattened  # AvoidunsupportedchainedTransformationconstraintswithoutreducingphysicalelements.
    for master,slave,meaning in rigids:  # Applyexplicitdocumentedconnectionassumptionsatrealphysicaloffsets.
        ops.rigidLink('beam',master,slave)  # Useexactsourcelocationswithlinearizedrigid-armkinematics;notclaimfullycalibratedjointbehavior.
        structural.update((master,slave))  # Avoidfixingrotationsalreadycontrolledbyconnectionkinematics.
    fixities={n:[0]*6 for n in nodes}  # Buildindependentsource-supportandunused-rotationconstraints.
    for n in nodes:  # Removeonlyphysicalunusedrotationsatpurecablepoints.
        if n not in structural:  # Puretrussnodeshavenorotationalstiffness.
            fixities[n][3:]=[1,1,1]  # Keepallcabletranslationsfree.
    for n in sets['TOWER_BASES']:  # Preservesourcefixedtowerfoundations.
        fixities[n]=[1]*6  # Applyallsixsourcefoundationrestraints.
    for n in sets['MAIN_CABLE_ANCHORS']+sets['WIND_ANCHORS']:  # Preserveactualsource/candidateanchorfixedtranslations.
        fixities[n][:3]=[1,1,1]  # Keepanchorrotationsemanticsseparate.
    supportnodes=[]  # Documenttheunverifiedbridgeendbearinglocationassumptionexplicitly.
    for ix in (0,26):  # Placeendbearingsatrealfirstandlastcrossbeams2/80m.
        for y in (-2550.,2550.):  # Supportbothactualgirderlines.
            n=cb[ix,y]  # Selectrealcrossbeam/girderinterface.
            fixities[n][:3]=[1,1,1] if ix==0 else [0,1,1]  # Usepin/longitudinalrollerbearingassumptionasoldmodelanalogue.
            supportnodes.append(n)  # Preservetheexplicitassumedbearingidentities.
    gravity={n:np.array([0.,0.,-9810.*mass,0.,0.,0.]) for n,mass in nodalmass.items()}  # Assembleallactualverifiedmassselfweightexactlyonce.
    slaves={b for a,b,c in rigids}  # Identifyconstraintreactiondegreesnotindependentfreeequations.
    for n in nodes:  # Assignphysicalnodalmassandremainingindependentrestraints.
        if n not in slaves:  # AvoidapplyingSPconstraintsatdependentrigid-linkdegrees.
            ops.fix(n,*fixities[n])  # Applyonlyindependentphysicalsupportconditions.
        else:  # Markdependentdegreesforequilibrium-auditexclusiononly.
            fixities[n]=[1]*6  # Do notincorrectlyinterpretconstraintforcesasfreeDOFresiduals.
        ops.mass(n,nodalmass[n],nodalmass[n],nodalmass[n],0.,0.,0.)  # Preserveallphysicalinertialmassunderconstrainttransformation.
    return dict(nodes=nodes,elements=elements,source_ids=parents,sets={**sets,'DECK_BEARINGS':supportnodes,'SADDLE_INTERFACES':list(saddle_map.values())},mass=nodalmass,gravity=gravity,state=state,source_nodes={n:old[n] for n in keep},fixities=fixities,rigid_connections=[dict(master=a,slave=b,assumption=c) for a,b,c in rigids],panel_count=78,channel_count=468,physical_limitations=['towercolumns5500mmspacing;saddle/hangerplanes5100mmspacing;anchorplanes4700mmspacing;200mmsaddleeccentricitywithassumedrigidseat','N3drawn1560mmendplatesconflictwithbill2690mm;N4actualfilletprofile295mmannotationfitmodeledwithpiecewisebeamsections;N5rectangle312mm;verifiedtablemassretained','real100/63x10N5ledgesmodeled;boltedchannelbottomsupportstied,noopening/slip;linearizedrigidweldarmsnotcalibrated','crossbeamactual420x300x10TWO-WEBclosedbox;416webmaterialtableconflictretained','endbearingsat2m/80massumed;actualbearingdrawingrequired','F3cableforceusedonlyasnewgeometryinitialguess;fabricationL0notclaimed','windanchorscandidateand10kNpretensionunverified','elasticmaterials;globalgeometricnonlinearityactive'])  # Returnfullactualgeometryandallunresolvedphysicalassumptionsexplicitly.
if __name__=='__main__':  # Runtherealdiscrete-panelwhole-bridgemodelwithindependentnumericgates.
    p=argparse.ArgumentParser()  # Requireexplicitinheritedsourceandresultpaths.
    p.add_argument('--source',type=Path,required=True)  # Bindauthenticoldsourceforcompatibletower/cablemembers.
    p.add_argument('--state',type=Path,required=True)  # Bindnominalcablestressinitialguess.
    p.add_argument('--output',type=Path,required=True)  # Isolatedetailedphysicalgeometryresultsfromoldscreeningbenchmark.
    args=p.parse_args()  # Parsethereproducibledetailedmodelrequest.
    args.subdivision=1  # Detailedgeometryusesitsownsource-dimensionalmeshspacing.
    base.model=build  # Selectthenewfullphysicalgeneratorwithoutchangingauditedsolverimplementation.
    m,result=base.run(args)  # Executeactualnativeglobalnonlinearequilibriumandfullfieldexport.
    result.update(physical_limitations=m['physical_limitations'],deck_panel_count=78,explicit_channel_count=468,geometry_status='DRAWING_DIMENSIONAL_PARTIAL_STIFFENER_AND_CONNECTION_ASSUMPTIONS',rigid_connections=m['rigid_connections'])  # Distinguishsource-supportedgeometryfromremaininglocaldetailuncertainty.
    (args.output/'equilibrium_summary.json').write_text(json.dumps(result,indent=2)+'\n')  # Publishcompletehonestdetailedmodelreceipt.
