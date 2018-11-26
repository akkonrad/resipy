# -*- coding: utf-8 -*-
"""
Created on Tue Apr 10 14:32:14 2018 in python 3.6.5
Wrapper for creating 2d triangular meshes with gmsh and converting it 
into a mesh.dat format for R2. The program tri_mesh () expects a directory "exe"
to be within the api (or working) directory with a gmsh.exe inside it. 

@author: jimmy Boyd - jamyd91@bgs.ac.uk
Programs:
    arange () - creates a list of values like np.arange does
    ccw() - checks cartesian points are oreintated clockwise 
    moving_average() - as says on tin, used to smooth surface topography which is repeated at the base of the fine mesh region in the inversion
    genGeoFile () - generates a .geo file for gmsh
    msh_parse() - converts a 2d gmsh.msh file to a mesh class readable by R2. 

Dependencies: 
    numpy (conda library)
    python3 standard libs
"""
#python standard libraries 
#import tkinter as tk
#from tkinter import filedialog
import os, warnings
#general 3rd party libraries
import numpy as np
#pyR2 library?
#import parsers as prs
#%% utility functions 
def arange(start,incriment,stop,endpoint=0):#create a list with a range without numpy 
    delta=stop-start
    iterations=int(delta/incriment)
    val=start
    cache=[]
    for i in range(iterations):
        cache.append(val)
        val=val+incriment
    if endpoint==1:
        cache.append(stop)
    return cache

def moving_average(array,N=3):
    """compute the moving average for a list/array. N is the number
    of elements averaged over, it always uses the quiered element as the central
    point and hence must be an odd number""" 
    if not isinstance(N,int) or N%2==0:
        raise Exception("N must be an odd integer")
    idx = round(N/2)-1
    length = len(array)
    out = [0]*length
    for i in range(len(array)):
        if i<idx:#cap minimum index
            a = 0
            b = i + idx + 1
        elif length-i<idx: # cap maximum index
            a = i - idx
            b = len(array)-1
        else:
            a = i - idx
            b = i + idx + 1            
        out[i] = sum(array[a:b])/len(array[a:b])
    return out

def ccw(p,q,r):#code expects points as p=(x,y) and so on ... 
    """
    checks if points in a triangle are ordered counter clockwise. When using R2,
    mesh nodes should be given in a counter clockwise order otherwise you'll get negative 
    apparent resistivities. 
    
    Parameters
    ----------
    p - tuple, list,
        The x y coordinates of the point/vertex ie. (x,y) in desired order
    q - " 
    r - " 
    
    Returns
    ----------
    0 if colinear points, 1 if counter clockwise order, 2 if points are ordered clockwise
    """
    val=((q[1]-p[1])*(r[0]-q[0]))-((q[0]-p[0])*(r[1]-q[1]))
    if val==0:
        return 0 # lines are colinear
    elif val>0:
        return 1 # points are oreintated counter clockwise 
    elif val<0:
        return 2 # points are counter clockwise
    
# triangle centriod 
def tri_cent(p,q,r):
    """
    Compute the centre coordinates for a 2d triangle given the x,y coordinates 
    of the vertices.
    program code expects points as p=(x,y) and so on (counter clockwise prefered)
    
    Parameters
    ----------
    
    p - tuple, list,
        The x y coordinates of the point/vertex ie. (x,y) in desired order
    q - " 
    r - " 
    
    Returns
    ----------
    (x,y): tuple    
    """
    Xm=(p[0]+q[0])/2
    Ym=(p[1]+q[1])/2
    k=2/3
    Xc=r[0]+(k*(Xm-r[0]))
    Yc=r[1]+(k*(Ym-r[1]))
    return(Xc,Yc)

#%% write a .geo file for reading into gmsh with topography (and electrode locations)
def genGeoFile(electrodes, electrode_type = None, geom_input = None,
               file_path='mesh.geo',doi=-1,cl=-1,cl_factor=2):
    """
    writes a gmsh .geo file for a 2d study area with topography assuming we wish to add electrode positions
    
    Parameters
    ----------
    electrodes: array like
        first column/list is the x coordinates of electrode positions, second column
        is the elevation
    electrode_type: list, optional
        List should be the same length as the electrode coordinate argument. Each entry in
        the list references the type of electrode: 
            'electrode' = surface electrode coordinate, will be used to construct the topography in the mesh
            'buried' = buried electrode, placed the mesh surface
            'borehole#' = borehole electrode, electrodes will be placed in the mesh with a line connecting them. 
                        borehole numbering starts at 1 and ascends numerically by 1. 
    geom_input: dict, optional
        Allows for further customisation of the 2D mesh, its a
        dictionary contianing surface topography, polygons and boundaries 
    file_path: string, optional 
        name of the generated gmsh file (can include file path also) (optional)
    doi: float, optional 
        depth of investigation (optional) (in meters)
    cl: float, optional
        characteristic length (optional), essentially describes how big the nodes 
        assocaited elements will be. Usually no bigger than 5. 
    cl_factor: float, optional 
        This allows for tuning of the incrimental size increase with depth in the 
        mesh, usually set to 2 such that the elements at the DOI are twice as big as those
        at the surface. The reasoning for this is becuase the sensitivity of ERT drops
        off with depth. 
    
    Returns
    ----------
    Node_pos: numpy array
        The indexes for the mesh nodes corresponding to the electrodes input, the ordering of the nodes
        should be the same as the input of 'electrodes'
    .geo: file
        Can be run in gmsh

    NOTES
    ----------
     geom_input format:
        the code will cycle through numerically ordered keys (strings referencing objects in a dictionary"),
        currently the code expects a 'surface' and 'electrode' key for surface points and electrodes.
        the first borehole string should be given the key 'borehole1' and so on. The code stops
        searching for more keys when it cant find the next numeric key. Same concept goes for adding boundaries
        and polygons to the mesh. See below example:
            
            geom_input = {'surface': [surf_x,surf_z],
              'boundary1':[bound1x,bound1y],
              'polygon1':[poly1x,poly1y]} 
            
    electrodes and electrode_type (if not None) format: 
        
            electrodes = [[x1,x2,x3,...],[y1,y2,y3,...]]
            electrode_type = ['electrode','electrode','buried',...]
        
        like with geom_input, boreholes should be labelled borehole1, borehole2 and so on.
        The code will cycle through each borehole and internally sort them and add them to 
        the mesh. 
        
    The code expects that all polygons, boundaries and electrodes fall within x values 
    of the actaul survey area. So make sure your topography / surface electrode points cover 
    the area you are surveying, otherwise some funky errors will occur in the mesh. 

    #### TODO: search through each set of points and check for repeats 
    """
    print('Generating gmsh input file...\n')
    #formalities and error checks
    if geom_input != None: 
        if not isinstance(geom_input,dict):
            raise TypeError ("'geom_input' is not a dictionary type object. Dict type is expected for the first argument of genGeoFile_adv")
    
    bh_flag = False
    bu_flag = False
    #determine the relevant node ordering for the surface electrodes? 
    if electrode_type is not None:
        if not isinstance(electrode_type,list):
            raise TypeError("electrode_type variable is given but expected a list type argument")
        if len(electrode_type) != len(electrodes[0]):
            raise ValueError("mis-match in length between the electrode type and number of electrodes")
        
        surface_idx=[]#surface electrode index
        bh_idx=[]#borehole index
        bur_idx=[]#buried electrode index 
        for i,key in enumerate(electrode_type):
            if key == 'electrode': surface_idx.append(i)
            if key == 'buried': bur_idx.append(i); bu_flag = True
            if key == 'borehole1': bh_flag = True
        
        if len(surface_idx)>0:# then surface electrodes are present
            elec_x=np.array(electrodes[0])[surface_idx]
            elec_z=np.array(electrodes[1])[surface_idx]
        elif len(surface_idx)==0 and 'surface' not in geom_input:
            #fail safe if no surface electrodes are present to generate surface topography 
            if not isinstance(geom_input, dict):
                geom_input = {}
            max_idx = np.argmax(electrodes[0])
            min_idx = np.argmin(electrodes[0])
            topo_x = [electrodes[0][min_idx],electrodes[0][max_idx]]
            y_idx = np.argmax(electrodes[1])
            topo_z = [electrodes[1][y_idx]+1,electrodes[1][y_idx]+1] # add one so we cut into the buried in electrodes with the mesh
            geom_input['surface'] = [topo_x,topo_z]
            elec_x = np.array([])
            elec_z = np.array([])
        elif len(surface_idx)==0 and 'surface' in geom_input:
            elec_x = np.array([])
            elec_z = np.array([])
    
    else:
        elec_x = np.array(electrodes[0])
        elec_z = np.array(electrodes[1])
        
    if geom_input != None and 'surface' not in geom_input:
        topo_x = [elec_x[0] - 5*np.mean(np.diff(elec_x)),
                  elec_x[-1] + 5*np.mean(np.diff(elec_x))]
        topo_z = [elec_z[0],elec_z[-1]]
    else:
        topo_x = geom_input['surface'][0]
        topo_z = geom_input['surface'][1] 
  
    if doi == -1:#then set to a default 
        doi = np.max(elec_z) - (np.min(elec_z) - abs(np.max(elec_x) - np.min(elec_x))/2)
                    
    print("doi in gmshWrap.py: %f"%doi)
    
    if cl == -1:
        if bh_flag or bu_flag:
            cl = abs(np.mean(np.diff(electrodes[1]))/2)
        else:
            cl = abs(np.mean(np.diff(elec_x))/2)
            
    if len(topo_x) != len(topo_z):
        raise ValueError("topography x and y arrays are not the same length!")
    if len(elec_x) != len(elec_z):
        raise ValueError("electrode x and y arrays are not the same length!")
    
    if file_path.find('.geo')==-1:
        file_path=file_path+'.geo'#add file extension if not specified already
    
    #start to write the file  
    fh = open(file_path,'w') #file handle
    
    fh.write("//Gmsh wrapper code version 1.0 (run the following in gmsh to generate a triangular mesh with topograpghy)\n")
    fh.write("//2D mesh coordinates\n")
    fh.write("cl=%.2f;//define characteristic length\n" %cl)
    fh.write("//Define surface points\n")
    #we have surface topograpghy, and electrode positions to make use of here:
    x_pts=np.append(topo_x,elec_x)#append our electrode positions to our topograpghy 
    y_pts=np.append(topo_z,elec_z)
    flag=['topography point']*len(topo_x)
    flag=flag+(['electrode']*len(elec_x))   
    
    #deal with end case electrodes, check max topo points are outside survey bounds 
    try:
        if min(elec_x) == min(x_pts):
            x_pts = np.append(x_pts,elec_x[0] - 5*np.mean(np.diff(elec_x))) # in this case extend the survey bounds beyond the first electrode 
            y_pts = np.append(y_pts,elec_z[0])
            flag.append('topography point')#add a flag
            
        if max(elec_x) == max(x_pts):
            x_pts = np.append(x_pts,elec_x[-1] + 5*np.mean(np.diff(elec_x)))
            y_pts = np.append(y_pts,elec_z[-1])
            flag.append('topography point')
    except ValueError: # then there are no surface electrodes, in which case 
        min_idx = np.argmin(electrodes[0])
        max_idx = np.argmax(electrodes[0])
        if min(electrodes[0]) == min(x_pts):
            x_pts = np.append(x_pts,electrodes[0][min_idx] - 5*np.mean(np.diff(electrodes[0]))) # in this case extend the survey bounds beyond the first electrode 
            y_pts = np.append(y_pts,max(electrodes[1])+1)
            flag.append('topography point')#add a flag
            
        if max(electrodes[0]) == max(x_pts):
            x_pts = np.append(x_pts,electrodes[0][max_idx] + 5*np.mean(np.diff(electrodes[0])))
            y_pts = np.append(y_pts,max(electrodes[1])+1)
            flag.append('topography point')
            
    #catch an error where the fine mesh region will truncate where the electrodes are        
    if min(electrodes[0]) < min(x_pts):
        raise ValueError("the minimum X coordinate value for the surface of the mesh must be smaller than the minimum electrode X coordinate")
    if max(electrodes[0]) > max(x_pts):
        raise ValueError("The maximum X coordinate value for the surface of the mesh must be greater than the maximum electrode X coordinate") 
    
    idx=np.argsort(x_pts) # now resort the x positions in ascending order
    x_pts=x_pts[idx] # compute sorted arrays
    y_pts=y_pts[idx]
    z_pts=np.zeros((len(x_pts),1))#for now let z = 0
    #add flags which distinguish what each point is 
    flag_sort=[flag[i] for i in idx]
    
    elec_x_cache = elec_x
    elec_z_cache = elec_z
    
    #we need protection against repeated points, as this will throw up an error in R2 when it comes calculating element areas
    cache_idx=[]
    for i in range(len(x_pts)-1):
        if x_pts[i]==x_pts[i+1] and y_pts[i]==y_pts[i+1]:
            cache_idx.append(i)
     
    if len(cache_idx)>0:
        warnings.warn("Duplicated surface and electrode positions were detected, R2 inversion likley to fail due to the presence of elements with 0 area.")
        #if duplicated points were dectected we should remove them?? - now disabled 
#        x_pts=np.delete(x_pts,cache_idx)#deletes first instance of the duplicate       
#        y_pts=np.delete(y_pts,cache_idx)
#        print("%i duplicated coordinate(s) were deleted" %len(cache_idx))
#        for k in range(len(cache_idx)):#what are we actually deleting?
#            if flag_sort[cache_idx[k]] == 'electrode':
#                flag_sort[cache_idx[k]+1] = 'electrode'
#                #this overwrites the flag string to say that this point is an electrode
#                #otherwise we'll get a mismatch between the number of electrodes and mesh nodes assigned to the electrodes
#        flag_sort=np.delete(flag_sort,cache_idx).tolist()
    
    #now add the surface points to the file
    print('adding surface points and electrodes to input file...')
    tot_pnts=0#setup a rolling total for points numbering
    sur_pnt_cache=[] # surface points cache 
    for i in range(len(x_pts)):
        tot_pnts=tot_pnts+1
        fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl};//%s\n"%(tot_pnts,x_pts[i],y_pts[i],z_pts[i],flag_sort[i]))
        sur_pnt_cache.append(tot_pnts)
    
    #make the lines between each point
    fh.write("//construct lines between each surface point\n")
    tot_lins=0
    sur_ln_cache = []
    for i in range(len(x_pts)-1):
        tot_lins=tot_lins+1
        fh.write("Line(%i) = {%i,%i};\n"%(tot_lins,sur_pnt_cache[i],sur_pnt_cache[i+1]))
        sur_ln_cache.append(tot_lins)
        
    fh.write("//add points below surface to make a fine mesh region\n")#okay so we want to add in the lines which make up the base of the survey area
    if bh_flag: #not allowing mesh refinement for boreholes currently
        cl_factor = 1   
    
    #reflect surface topography at base of fine mesh area. 
    x_base = x_pts[::2]
    z_base = moving_average(y_pts[::2] - abs(doi),N=5) # compute the depth to the points at the base of the survey, + downsample
    if len(x_pts)%2 == 0:#bug fix
        z_base = np.append(z_base,y_pts[-1]- abs(doi))#puts in extra point at base underneath last x and y point
        x_base = np.append(x_base,x_pts[-1])
    # a smoothed version of the topography ... 
    if np.max(z_base) > np.min(electrodes[1]):
        #warnings.warn("The depth of investigation is above the the minium z coordinate of electrodes, mesh likely to be buggy!", Warning)   
        raise Exception("The depth of investigation is above the the minium z coordinate of electrodes, mesh likely to be buggy!")
    
    basal_pnt_cache = []
    for i in range(len(x_base)):
        tot_pnts=tot_pnts+1
        fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl*%.2f};//%s\n"%(tot_pnts,x_base[i],z_base[i],0,cl_factor,
                 'base of smoothed mesh region'))
        basal_pnt_cache.append(tot_pnts)
    
    fh.write("//make a polygon by defining lines between points just made.\n")
    basal_ln_cache=[]
    for i in range(len(x_base)-1):
        tot_lins=tot_lins+1
        fh.write("Line(%i) = {%i,%i};\n"%(tot_lins,basal_pnt_cache[i],basal_pnt_cache[i+1]))
        basal_ln_cache.append(tot_lins)
    
    fh.write("//Add lines at the end points of each of the fine mesh region.\n")
    tot_lins=tot_lins+1;# add to the number of lines rolling total 
    fh.write("Line(%i) = {%i,%i};\n"%(tot_lins,sur_pnt_cache[0],basal_pnt_cache[0]))#line from first point on surface to depth
    tot_lins=tot_lins+1
    fh.write("Line(%i) = {%i,%i};\n"%(tot_lins,sur_pnt_cache[-1],basal_pnt_cache[-1]))#line going bottom to last electrode point
    end_ln_cache=[tot_lins-1,tot_lins]
    
    #compile line numbers into a line loop.
    fh.write("//compile lines into a line loop for a mesh surface/region.\n")
    sur_ln_cache_flipped = list(np.flipud(np.array(sur_ln_cache))*-1)
    fine_msh_loop = [end_ln_cache[0]] + basal_ln_cache + [-1*end_ln_cache[1]] + sur_ln_cache_flipped
    fh.write("Line Loop(1) = {%s};\n"%str(fine_msh_loop).strip('[').strip(']')) # line loop for fine mesh region 
    fh.write("Plane Surface(1) = {1};//Fine mesh region surface\n")
    
    #now extend boundaries beyond flanks of survey area (so generate your Neummon boundary)
    fh.write("\n//Add background region (Neumann boundary) points\n")
    cl_factor2=50#characteristic length multipleier for Nuemon boundary 
    cl2=cl*cl_factor2#assign new cl, this is so mesh elements get larger from the main model
    fh.write("cl2=%.2f;//characteristic length for background region\n" %cl2)
    #Background region propeties, follow rule of thumb that background should extend 100*electrode spacing
    e_spacing=abs(np.mean(np.diff(elec_x)))
    if np.isnan(e_spacing):#catch error where e_spacing is nan if no surface electrodes 
        e_spacing=abs(np.mean(np.diff(np.unique(electrodes[0]))))
    flank=e_spacing*100
    b_max_depth=-abs(doi)-flank#background max depth
    #add nuemon boundaries on left hand side
    n_pnt_cache=[0,0,0,0]#cache for the indexes of the neumon boundary points 
    tot_pnts=tot_pnts+1;n_pnt_cache[0]=tot_pnts
    fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl2};//far left upper point\n"%(tot_pnts,x_pts[0]-flank,y_pts[0],z_pts[0]))
    tot_pnts=tot_pnts+1;n_pnt_cache[1]=tot_pnts
    fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl2};//far left lower point\n"%(tot_pnts,x_pts[0]-flank,b_max_depth,z_pts[0]))
    #add nuemon boundary points on right hand side
    tot_pnts=tot_pnts+1;n_pnt_cache[2]=tot_pnts
    fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl2};//far right upper point\n"%(tot_pnts,x_pts[-1]+flank,y_pts[-1],z_pts[-1]))
    tot_pnts=tot_pnts+1;n_pnt_cache[3]=tot_pnts
    fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl2};//far right lower point\n"%(tot_pnts,x_pts[-1]+flank,b_max_depth,z_pts[-1]))
    #make lines encompassing all the points - counter clock wise fashion
    fh.write("//make lines encompassing all the background points - counter clock wise fashion\n")
    
    n_ln_cache=[0,0,0,0,0]
    tot_lins=tot_lins+1;n_ln_cache[0]=tot_lins
    fh.write("Line(%i) = {%i,%i};\n"%(tot_lins,sur_pnt_cache[0],n_pnt_cache[0]))
    tot_lins=tot_lins+1;n_ln_cache[1]=tot_lins
    fh.write("Line(%i) = {%i,%i};\n"%(tot_lins,n_pnt_cache[0],n_pnt_cache[1]))
    tot_lins=tot_lins+1;n_ln_cache[2]=tot_lins
    fh.write("Line(%i) = {%i,%i};\n"%(tot_lins,n_pnt_cache[1],n_pnt_cache[3]))
    tot_lins=tot_lins+1;n_ln_cache[3]=tot_lins
    fh.write("Line(%i) = {%i,%i};\n"%(tot_lins,n_pnt_cache[3],n_pnt_cache[2]))
    tot_lins=tot_lins+1;n_ln_cache[4]=tot_lins
    fh.write("Line(%i) = {%i,%i};\n"%(tot_lins,n_pnt_cache[2],sur_pnt_cache[-1]))
    
    fh.write("//Add line loops and plane surfaces to for nuemon region\n")
    #now add background region line loop (cos this be made more efficent?)
    basal_ln_cache_flipped = list(np.flipud(np.array(basal_ln_cache))*-1)
    coarse_msh_loop = n_ln_cache + [end_ln_cache[1]] + basal_ln_cache_flipped + [-1*end_ln_cache[0]]
    fh.write("Line Loop(2) = {%s};\n"%str(coarse_msh_loop).strip('[').strip(']')) # line loop for fine mesh region 
    fh.write("Plane Surface(2) = {2};//Fine mesh region surface\n")
    
    fh.write("\n//Make a physical surface\n")
    fh.write("Physical Surface(1) = {1, 2};\n")
    
    #now we want to return the point values of the electrodes, as gmsh will assign node numbers to points
    #already specified in the .geo file. This will needed for specifying electrode locations in R2.in   
    node_pos=[i+1 for i, j in enumerate(flag_sort) if j == 'electrode']
    node_pos = np.array(node_pos)
    
    #add borehole vertices and line segments to the survey mesh
    
    no_lin=tot_lins#+1
    no_pts=tot_pnts#+1
    #add borehole electrode strings
    print('probing for boundaries and other additions to the mesh')
    count = 0
    if bh_flag:
        fh.write("\n//Boreholes? \n")
        while True:
            count += 1
            key = 'borehole'+str(count)#count through the borehole keys
            bh_idx=[]#borehole index
            for i,entry in enumerate(electrode_type):
                if entry == key: bh_idx.append(i)
            #break if no entries found
            if len(bh_idx)==0:
                fh.write("//End of borehole electrodes\n")
                break
                
            bhx = electrodes[0][bh_idx]#get borehole coordinate information
            bhy = electrodes[1][bh_idx]
            #cache the x and y coordinates 
            elec_x_cache = np.append(elec_x_cache,bhx)
            elec_z_cache = np.append(elec_z_cache,bhy)
            e_pt_idx = [0] *len(bhx)
            fh.write("// string electrodes for borehole %i\n"%count)
            for k in range(len(bhx)):
                no_pts += 1 
                fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl};//borehole %i electrode\n"%(no_pts,bhx[k],bhy[k],0,count))
                e_pt_idx[k] = no_pts
            
            fh.write("//put lines between each electrode\n")
            line_idx = []
            node_pos = np.append(node_pos,e_pt_idx) #add borehole nodes to electrode node positions 
            for i in range(len(e_pt_idx)-1):
                idx = e_pt_idx[i]
                no_lin += 1
                fh.write("Line (%i) = {%i,%i};//borehole %i segment\n"%(no_lin,idx,idx+1,count))
                line_idx.append(no_lin)
            
            fh.write("Line{%s} In Surface{1};\n"%str(line_idx).strip('[').strip(']'))
    
    #add buried electrodes?         
    if bu_flag:
        print('buried electrodes added to input file')
        fh.write("\n//Buried electrodes \n")  
        buried_x = np.array(electrodes[0])[bur_idx]#get buried electrode coordinate information
        buried_z = np.array(electrodes[1])[bur_idx]
        buried_y = [0]*len(buried_x)
        e_pt_idx = [0]*len(buried_x)
        for k in range(len(buried_x)):
            no_pts += 1 
            fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl};//buried electrode %i\n"%(no_pts,buried_x[k],buried_z[k],buried_y[k],k+1))
            e_pt_idx[k] = no_pts
        
        node_pos = np.append(node_pos,e_pt_idx) #add borehole nodes to electrode node positions 
        fh.write("Point{%s} In Surface{1};\n"%str(e_pt_idx).strip('[').strip(']'))
        fh.write("//end of buried electrodes.\n")
        elec_x_cache = np.append(elec_x_cache,buried_x)
        elec_z_cache = np.append(elec_z_cache,buried_z)
                   
        
    no_plane = 2 # number of plane surfaces so far
    fh.write("\n//Adding polygons?\n")
    count = 0    
    while True:  
        count += 1
        key = 'polygon'+str(count)

        try:
            plyx = geom_input[key][0]
            plyy = geom_input[key][1]
            try:
                plyz = geom_input[key][2]
            except IndexError:
                plyz = [0]*len(plyx)
            pt_idx = [0] *len(plyx)
            fh.write("//polygon vertices for polygon %i\n"%count)
            for k in range(len(plyx)):
                no_pts += 1
                fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl};//polygon vertex \n"%(no_pts,plyx[k],plyy[k],plyz[k]))
                pt_idx[k] = no_pts
            fh.write("//put lines between each vertex\n")
            line_idx = []
            for i in range(len(pt_idx)):
                idx = pt_idx[i]
                no_lin += 1
                if i == len(pt_idx)-1:
                    fh.write("Line (%i) = {%i,%i};\n"%(no_lin,idx,pt_idx[0]))
                else:
                    fh.write("Line (%i) = {%i,%i};\n"%(no_lin,idx,idx+1))
                line_idx.append(no_lin)
            #make line loop out of polygon
            fh.write("//make lines forming polygon into a line loop? - current inactive due to unexpected behaviour in gmsh\n")
            no_lin += 1
            fh.write("//Line Loop(%i) = {%s};\n"%(no_lin,str(line_idx).strip('[').strip(']')))
            no_plane +=1
            fh.write("//Plane Surface(%i) = {%i};\n"%(no_plane,no_lin))
            fh.write("Line{%s} In Surface{1};\n"%str(line_idx).strip('[').strip(']'))
            
        except KeyError:
            fh.write("//end of polygons.\n")
            print('%i polygons added to input file'%(count-1))
            break  

    fh.write("\n//Adding boundaries?\n")
    count = 0   
    while True:
        count += 1        
        key = 'boundary'+str(count)

        try:
            bdx = geom_input[key][0]
            bdy = geom_input[key][1]
            try:
                bdz = geom_input[key][2]
            except IndexError:
                bdz = [0]*len(bdx)
            pt_idx = [0] *len(bdx)
            fh.write("// vertices for boundary line %i\n"%count)
            for k in range(len(bdx)):
                no_pts += 1 
                fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl};//boundary vertex \n"%(no_pts,bdx[k],bdy[k],bdz[k]))
                pt_idx[k] = no_pts
            fh.write("//put lines between each vertex\n")
            line_idx = []
            for i in range(len(pt_idx)-1):
                idx = pt_idx[i]
                no_lin += 1
                fh.write("Line (%i) = {%i,%i};\n"%(no_lin,idx,idx+1))
                line_idx.append(no_lin)
            fh.write("Line{%s} In Surface{1};\n"%str(line_idx).strip('[').strip(']'))
                
        except KeyError:
            fh.write("//end of boundaries.\n")
            print('%i boundary(ies) added to input file'%(count-1))
            break              
                    
    fh.write("\n//j'ai fini!\n")
    fh.close()
    print("writing .geo to file completed, save location:\n%s\n"%os.getcwd())
    
    if len(node_pos) != len(elec_x_cache):
        warnings.warn("looks like something has gone wrong with node orderings, total x != total nodes.")
    
    #sort node ordering back into the original input ordering    
    original_x = np.array(electrodes[0])
    original_z = np.array(electrodes[1])
    #find the original indexes  
    original_idx = [0]*len(node_pos)
    for i in range(len(node_pos)):
        idx = (elec_x_cache == original_x[i]) & (elec_z_cache == original_z[i])
        idx = idx.tolist()
        original_idx[i] = idx.index(True)

    ordered_node_pos = node_pos[original_idx].astype(int)
    
    return ordered_node_pos 

#%% parse a .msh file
def msh_parse(file_path):
    """
    Converts a gmsh mesh file into a mesh class used in pyR2
    
    Parameters
    ----------
    file_path: string
        file path to mesh file. note that a error will occur if the file format is not as expected
   
    Returns
    ----------
    Mesh class
    """
    if not isinstance(file_path,str):
        raise Exception("expected a string argument for msh_parser")
    if file_path=='ask_to_open':#use a dialogue box to open a file
        print("please select the gmsh mesh file you want to convert.\n")
        root=tk.Tk()
        root.withdraw()
        file_path=filedialog.askopenfilename(title='Select mesh file',filetypes=(("mesh files","*.msh"),("all files","*.*")))
    # open file and read in header lines
    print("parsing gmsh mesh...\n")
    fid=open(file_path,'r')# Open text file
    #Idea: Read Mesh format lines $MeshFormat until $Nodes
    line1=fid.readline()
    #check the file is a mesh format
    if line1.strip() != '$MeshFormat':#removes formating strings, checks if the file is a gmsh file
        raise ImportError("unrecognised file type...")
    mesh_format=fid.readline()#reads the next line
    if mesh_format.strip() != '2.2 0 8':#warn people that the code was developed with this file format in mind
        print('Warning: the mesh file type version is different to the mesh converter development version ... some errors may occur!\n')   
    line3=fid.readline()#endofmeshformat
    line4=fid.readline()#nodes
    
    print('importing node coordinates...')
    #read in number of nodes - at line 5
    no_nodes=int(fid.readline().strip())
    #allocate lists for node numbers and coordinates
    node_num=[0]*no_nodes
    x_coord=[0]*no_nodes
    y_coord=[0]*no_nodes
    z_coord=[0]*no_nodes
    #read in node information
    for i in range(no_nodes):
        line_info=fid.readline().split()
        #convert string info into floats
        data_dump=[float(k) for k in line_info]
        node_num[i]=int(data_dump[0])
        x_coord[i]=data_dump[1]
        y_coord[i]=data_dump[2]
        z_coord[i]=data_dump[3]
    
    #### read in elements   
    print('reading connection matrix')
    #read in two lines $EndNodes and $Elements
    Endnodes=fid.readline()
    Elements=fid.readline()
    #number of elements
    no_elements=int(fid.readline().strip())
    #engage for loop - this time we want to filter out elements which are not triangles
    #... looking at the gmsh docs its elements of type 2 we are after (R2 only needs this information) 
    nat_elm_num = []#native element number to gmsh
    elm_type = []#element type
    number_of_tags = []
    phys_entity = []#defines the physical entity type the element is assocaited with
    elem_entity = []#which plane surface the element is assocaited with
    node1 = []#first node of triangle 
    node2 = []
    node3 = []#last node of triangle 
    ignored_elements=0#count the number of ignored elements
    for i in range(no_elements):
        line_info=fid.readline().split()
        if line_info[1]=='2':# then its the right element type!
        #convert string info into floats and cache data
            data_dump=[int(k) for k in line_info]
            nat_elm_num.append(data_dump[0])
            elm_type.append(data_dump[1]) 
            number_of_tags.append(data_dump[2]) 
            phys_entity.append(data_dump[3]) 
            elem_entity.append(data_dump[4]) 
            node1.append(data_dump[5]) 
            node2.append(data_dump[6]) 
            node3.append(data_dump[7])
        else:
            ignored_elements += 1
    print("ignoring %i non-triangle elements in the mesh file, as they are not required for R2"%ignored_elements)
    real_no_elements=len(nat_elm_num) #'real' number of elements that we actaully want
    
    ##clock wise correction and area / centre computations 
    #make sure in nodes in triangle are counterclockwise as this is waht r2 expects
    c_triangles=[]#'corrected' triangles 
    num_corrected=0#number of elements that needed 'correcting'
    centriod_x=[]
    centriod_y=[]
    areas=[]
    for i in range(real_no_elements):
        n1=(x_coord[node1[i]-1],y_coord[node1[i]-1])#define node coordinates
        n2=(x_coord[node2[i]-1],y_coord[node2[i]-1])#we have to take 1 off here cos of how python indexes lists and tuples
        n3=(x_coord[node3[i]-1],y_coord[node3[i]-1])
        #see if triangle is counter-clockwise
        if ccw(n1,n2,n3) == 1: #points are clockwise and therefore need swapping round
            #exchange elements in rows 6 and 7 to change direction
            c_triangles.append((node2[i],node1[i],node3[i]))
            num_corrected=num_corrected+1
        else:
            c_triangles.append((node1[i],node2[i],node3[i]))
        #compute triangle centre
        xy_tuple=tri_cent(n1,n2,n3)#actual calculation
        centriod_x.append(xy_tuple[0])
        centriod_y.append(xy_tuple[1])
        #compute area (for a triangle this is 0.5*base*height)
        base=(((n1[0]-n2[0])**2) + ((n1[1]-n2[1])**2))**0.5
        mid_pt=((n1[0]+n2[0])/2,(n1[1]+n2[1])/2)
        height=(((mid_pt[0]-n3[0])**2) + ((mid_pt[1]-n3[1])**2))**0.5
        areas.append(0.5*base*height)
        
    #print warning if areas of zero found, this will cuase problems in R2
    try:
        if min(areas)==0:
            warnings.warn("elements with no area have been detected in 'mesh.dat', inversion with R2 unlikey to work!" )
    except ValueError:#if mesh hasnt been read in this is where the error occurs 
        raise Exception("It looks like no elements have read into pyR2, its likley gmsh has failed to produced a stable mesh. Consider checking the mesh input (.geo) file.")
            
    print("%i element node orderings had to be corrected becuase they were found to be orientated clockwise\n"%num_corrected)
    fid.close()
    
    ### return dictionary which can be converted to mesh class ### 
    no_regions=max(elem_entity)#number of regions in the mesh
    regions=arange(1,1,no_regions,1)
    assctns=[]
    #following for loop finds the element number ranges assocaited with a distinct region in the mesh
    for k in regions:
        indx=[m for m in range(len(elem_entity)) if elem_entity[m]==k]
        if len(indx) > 0:
            assctns.append((k,min(indx)+1,max(indx)+1))
    #create a dump of the mesh data incase the user wants to see it later on   
    dump={'nat_elm_num':nat_elm_num,
          'elm_type':elm_type,
          'number_of_tags':number_of_tags,
          'phys_entity':phys_entity,
          'elem_entity':elem_entity,
          'string_data':[line1,mesh_format,line3,line4,Endnodes,Elements]} 
    #convert c_triangles into mesh object format for later recall
    node_dump=[[],[],[]]
    for i in range(real_no_elements):
        node_dump[0].append(c_triangles[i][0]-1)#node 1
        node_dump[1].append(c_triangles[i][1]-1)#node 2
        node_dump[2].append(c_triangles[i][2]-1)#node 3
    #return a dictionary detailing the mesh 
    return {'num_elms':real_no_elements,
            'num_nodes':no_nodes,
            'num_regions':no_regions,
            'element_ranges':assctns,
            'dump':dump,      
            'node_x':x_coord,#x coordinates of nodes 
            'node_y':y_coord,#y coordinates of nodes
            'node_z':z_coord,#z coordinates of nodes 
            'node_id':node_num,#node id number 
            'elm_id':np.arange(1,real_no_elements,1),#element id number 
            'num_elm_nodes':3,#number of points which make an element
            'node_data':node_dump,#nodes of element vertices
            'elm_centre':(centriod_x,centriod_y),#centre of elements (x,y)
            'elm_area':areas,
            'cell_type':[5],
            'parameters':phys_entity,#the values of the attributes given to each cell 
            'parameter_title':'material',
            'dict_type':'mesh_info',
            'original_file_path':file_path} 
    
    #we could return a mesh object here, but a dictionary is easier to debug with spyder, 
    #also we'd need to import the mesh class, and its not a good idea to have modules
    #importing each other, as meshTools has a dependency on gmshWrap. 
        
#%% 2D whole space 

def gen_2d_whole_space(electrodes, padding = 20, electrode_type = None, geom_input = None,
                       file_path='mesh.geo',cl=1):
    """
    writes a gmsh .geo for a 2D whole space. Ignores the type of electrode. 
    
    Parameters
    ----------
    electrodes: array like
        first column/list is the x coordinates of electrode positions, second column
        is the elevation
    padding: float, optional
        Padding in percent on the size the fine mesh region extent. Must be bigger than 0.
        
    geom_input: dict, optional
        Allows for further customisation of the 2D mesh, its a
        dictionary contianing surface topography, polygons and boundaries 
    file_path: string, optional 
        name of the generated gmsh file (can include file path also) (optional)
    cl: float, optional
        characteristic length (optional), essentially describes how big the nodes 
        assocaited elements will be. Usually no bigger than 5. 
    
    Returns
    ----------
    Node_pos: numpy array
        The indexes for the mesh nodes corresponding to the electrodes input, the ordering of the nodes
        should be the same as the input of 'electrodes'
    .geo: file
        Can be run in gmsh

    NOTES
    ----------
     geom_input format:
        the code will cycle through numerically ordered keys (strings referencing objects in a dictionary"),
        currently the code expects a 'surface' and 'electrode' key for surface points and electrodes.
        the first borehole string should be given the key 'borehole1' and so on. The code stops
        searching for more keys when it cant find the next numeric key. Same concept goes for adding boundaries
        and polygons to the mesh. See below example:
            
            geom_input = {'surface': [surf_x,surf_z],
              'boundary1':[bound1x,bound1y],
              'polygon1':[poly1x,poly1y]} 
            
    electrodes and electrode_type (if not None) format: 
        
            electrodes = [[x1,x2,x3,...],[y1,y2,y3,...]]
            electrode_type = ['electrode','electrode','buried',...]
        
        like with geom_input, boreholes should be labelled borehole1, borehole2 and so on.
        The code will cycle through each borehole and internally sort them and add them to 
        the mesh. 
        
    The code expects that all polygons, boundaries and electrodes fall within x values 
    of the actaul survey area. So make sure your topography / surface electrode points cover 
    the area you are surveying, otherwise some funky errors will occur in the mesh. 

    #### TODO: search through each set of points and check for repeats ?
    """
    
    elec_x = electrodes[0]
    elec_z = electrodes[1]
    
    if len(elec_x) != len(elec_z):
        raise ValueError("The length of the x coordinate array does not match of the Z coordinate")
    
    if geom_input != None: 
        if not isinstance(geom_input,dict):
            raise TypeError ("'geom_input' is not a dictionary type object. Dict type is expected for the first argument of genGeoFile_adv")
    elif geom_input is None:
        geom_input = {}
        
    if file_path.find('.geo')==-1:
        file_path=file_path+'.geo'#add file extension if not specified already
        
    fh = open(file_path,'w') #file handle
    
    fh.write("//Gmsh wrapper code version 1.0 (run the following in gmsh to generate a triangular mesh for 2D whole space)\n")
    fh.write("//2D mesh coordinates\n")
    fh.write("cl=%.2f;//define characteristic length\n" %cl)
    
    #create square around all of the electrodes
    x_dist = abs(np.max(elec_x) - np.min(elec_x))
    z_dist = abs(np.max(elec_z) - np.min(elec_z))
    max_x = np.max(elec_x) + (padding/100)*x_dist
    min_x = np.min(elec_x) - (padding/100)*x_dist
    max_z = np.max(elec_z) + (padding/100)*z_dist
    min_z = np.min(elec_z) - (padding/100)*z_dist
    
    fh.write("//Fine mesh region.\n")
    #add points to file 
    no_pts = 1
    loop_pt_idx=[no_pts]
    fh.write("Point (%i) = {%.2f,%.2f,%.2f, cl};\n"%(no_pts, max_x, max_z, 0))
    no_pts += 1
    loop_pt_idx.append(no_pts)
    fh.write("Point (%i) = {%.2f,%.2f,%.2f, cl};\n"%(no_pts, max_x, min_z, 0))
    no_pts += 1
    loop_pt_idx.append(no_pts)
    fh.write("Point (%i) = {%.2f,%.2f,%.2f, cl};\n"%(no_pts, min_x, min_z, 0))
    no_pts += 1
    loop_pt_idx.append(no_pts)
    fh.write("Point (%i) = {%.2f,%.2f,%.2f, cl};\n"%(no_pts, min_x, max_z, 0))
    
    #add line loop
    no_lns = 0 
    for i in range(4):
        no_lns += 1 
        if i == 3:
            fh.write("Line(%i) = {%i,%i};\n"%(no_lns,loop_pt_idx[i],loop_pt_idx[0]))
        else:
            fh.write("Line(%i) = {%i,%i};\n"%(no_lns,loop_pt_idx[i],loop_pt_idx[i+1]))
         
    #Nuemon boundary 
    flank_x = 100*x_dist
    flank_z = 100*z_dist 
    fh.write("//Nuemonn boundary \n")
    cl2 = cl*150
    fh.write("cl2 = %.2f;\n"%cl2)
    no_pts += 1
    nmn_pt_idx=[no_pts]
    fh.write("Point (%i) = {%.2f,%.2f,%.2f, cl2};\n"%(no_pts, max_x+flank_x, max_z+flank_z, 0))
    no_pts += 1
    nmn_pt_idx.append(no_pts)
    fh.write("Point (%i) = {%.2f,%.2f,%.2f, cl2};\n"%(no_pts, max_x+flank_x, min_z-flank_z, 0))
    no_pts += 1
    nmn_pt_idx.append(no_pts)
    fh.write("Point (%i) = {%.2f,%.2f,%.2f, cl2};\n"%(no_pts, min_x-flank_x, min_z-flank_z, 0))
    no_pts += 1
    nmn_pt_idx.append(no_pts)
    fh.write("Point (%i) = {%.2f,%.2f,%.2f, cl2};\n"%(no_pts, min_x-flank_x, max_z+flank_z, 0))
    
    for i in range(4):
        no_lns += 1 
        if i == 3:
            fh.write("Line(%i) = {%i,%i};\n"%(no_lns,nmn_pt_idx[i],nmn_pt_idx[0]))
        else:
            fh.write("Line(%i) = {%i,%i};\n"%(no_lns,nmn_pt_idx[i],nmn_pt_idx[i+1]))
            
    fh.write("Line Loop(2) = {5,6,7,8};\n")    
    fh.write("Plane Surface(1) = {2};\n")
    fh.write("Line{1,2,3,4} In Surface{1};\n")
    
    fh.write("//Electrode positions.\n")
    node_pos = [0]*len(elec_x)
    for i in range(len(elec_x)):
        no_pts += 1
        node_pos[i] = no_pts
        fh.write("Point (%i) = {%.2f,%.2f,%.2f, cl};\n"%(no_pts, elec_x[i], elec_z[i], 0))
        fh.write("Point{%i} In Surface{1};\n"%(no_pts))# put the point surface
    fh.write("//End electrodes\n")
    
    fh.write("\n//Adding polygons?\n")
    no_lin=no_lns
    no_plane=0
    count = 0    
    while True:  
        count += 1
        key = 'polygon'+str(count)

        try:
            plyx = geom_input[key][0]
            plyy = geom_input[key][1]
            try:
                plyz = geom_input[key][2]
            except IndexError:
                plyz = [0]*len(plyx)
            pt_idx = [0] *len(plyx)
            fh.write("//polygon vertices for polygon %i\n"%count)
            for k in range(len(plyx)):
                no_pts += 1
                fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl};//polygon vertex \n"%(no_pts,plyx[k],plyy[k],plyz[k]))
                pt_idx[k] = no_pts
            fh.write("//put lines between each vertex\n")
            line_idx = []
            for i in range(len(pt_idx)):
                idx = pt_idx[i]
                no_lin += 1
                if i == len(pt_idx)-1:
                    fh.write("Line (%i) = {%i,%i};\n"%(no_lin,idx,pt_idx[0]))
                else:
                    fh.write("Line (%i) = {%i,%i};\n"%(no_lin,idx,idx+1))
                line_idx.append(no_lin)
            #make line loop out of polygon
            fh.write("//make lines forming polygon into a line loop? - current inactive due to unexpected behaviour in gmsh\n")
            no_lin += 1
            fh.write("//Line Loop(%i) = {%s};\n"%(no_lin,str(line_idx).strip('[').strip(']')))
            no_plane +=1
            fh.write("//Plane Surface(%i) = {%i};\n"%(no_plane,no_lin))
            fh.write("Line{%s} In Surface{1};\n"%str(line_idx).strip('[').strip(']'))
            
        except KeyError:
            fh.write("//end of polygons.\n")
            print('%i polygons added to input file'%(count-1))
            break  

    fh.write("\n//Adding boundaries?\n")
    count = 0   
    while True:
        count += 1        
        key = 'boundary'+str(count)

        try:
            bdx = geom_input[key][0]
            bdy = geom_input[key][1]
            try:
                bdz = geom_input[key][2]
            except IndexError:
                bdz = [0]*len(bdx)
            pt_idx = [0] *len(bdx)
            fh.write("// vertices for boundary line %i\n"%count)
            for k in range(len(bdx)):
                no_pts += 1 
                fh.write("Point(%i) = {%.2f,%.2f,%.2f,cl};//boundary vertex \n"%(no_pts,bdx[k],bdy[k],bdz[k]))
                pt_idx[k] = no_pts
            fh.write("//put lines between each vertex\n")
            line_idx = []
            for i in range(len(pt_idx)-1):
                idx = pt_idx[i]
                no_lin += 1
                fh.write("Line (%i) = {%i,%i};\n"%(no_lin,idx,idx+1))
                line_idx.append(no_lin)
            fh.write("Line{%s} In Surface{1};\n"%str(line_idx).strip('[').strip(']'))
                
        except KeyError:
            fh.write("//end of boundaries.\n")
            print('%i boundary(ies) added to input file'%(count-1))
            break              
    
    fh.close()
    print("writing .geo to file completed, save location:\n%s\n"%os.getcwd())
    return np.array(node_pos)
    
#%% test block 
#import parsers as prs     
#import survey 
#elec, df = prs.res2invInputParser(os.path.join(pyR2_location,r'api/test/res2d_forward_error.dat'))
##elec, df = prs.syscalParser(r'C:\Users\jamyd91\Documents\2PhD_projects\R2gui\Data\example_feild_data.txt')
##slope geometry 
#width=170;#width of slope:
#top=100;#top of slope: 100m above datum
#bottom=50;#base of slope 50m ODM;
#ends_addon=40;# how much to add to the width of the slope
#bottom_addon=10;#how much to add to the bottom of the model 
#X=np.array([-ends_addon,0,width,width+ends_addon]);#compile geometry into arrays
#Y=np.array([bottom,bottom,top,top])
#
##%triangular mesh - create geometry and run gmsh wrapper
#electrodes = [elec.T[0],elec.T[1]]
#geom_input = {'surface':[X,Y]}
##
#genGeoFile(electrodes, None,geom_input)
##%%
#poly2x=np.array([-40,200,200,-40])
#poly2y=np.array([70,70,100,100])
#poly_data = {'region1':[poly2x,poly2y]}
#mesh_dict = gmsh2R2mesh(file_path='ask_to_open',save_path='default',return_mesh=True,poly_data=poly_data)

#%% bore hole test 
#geom_input={'surface':[[-2,10],[0,0]]}
#electrodes=[[0,0,2,2,6,6,8,8],[0,2,0,2,0,2,0,2]]
#typ = ['electrode','buried']*4
#node,old_nodes = genGeoFile(electrodes, typ,geom_input)   

