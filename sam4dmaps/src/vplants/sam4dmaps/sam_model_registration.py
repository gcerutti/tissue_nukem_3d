import numpy as np
import scipy.ndimage as nd

from openalea.container import array_dict

from vplants.sam4dmaps.parametric_shape import ParametricShapeModel
from vplants.sam4dmaps.sam_model import create_meristem_model, reference_meristem_model

from copy import deepcopy
import pickle


def meristem_model_organ_gap(reference_model, meristem_model, orientation=None, same_individual=False, hour_gap=4.):
    if orientation is None:
        orientation = reference_model.parameters['orientation']

    golden_angle = np.sign(orientation)*(2.*np.pi)/((np.sqrt(5)+1)/2.+1)
    golden_angle = 180.*golden_angle/np.pi

    gap_score = {}
    gap_range = np.arange(10)-3 
    for gap in gap_range:
        angle_gap = {}
        distance_gap = {}
        radius_gap = {}
        height_gap = {}
        
        if gap>=0:
            matching_primordia = (np.arange(8-gap)+1)
        else:
            matching_primordia = (np.arange(8-abs(gap))+1-gap)
        
        for p in matching_primordia:
            #angle_0 = (reference_model.parameters["primordium_"+str(p)+"_angle"] + reference_model.parameters['primordium_offset']*golden_angle) % 360
            #angle_1 = (meristem_model.parameters["primordium_"+str(p+gap)+"_angle"] + meristem_model.parameters['primordium_offset']*golden_angle + gap*golden_angle) % 360
            angle_0 = reference_model.parameters['orientation']*(reference_model.parameters["primordium_"+str(p)+"_angle"]) + reference_model.parameters['primordium_offset']*golden_angle
            angle_1 = meristem_model.parameters['orientation']*(meristem_model.parameters["primordium_"+str(p+gap)+"_angle"]) + meristem_model.parameters['primordium_offset']*golden_angle - gap*golden_angle
            angle_gap[p] = np.cos(np.pi*(angle_1-angle_0)/180.)
            distance_gap[p]  = meristem_model.parameters["primordium_"+str(p+gap)+"_distance"] - reference_model.parameters["primordium_"+str(p)+"_distance"]
            radius_gap[p] = meristem_model.parameters["primordium_"+str(p+gap)+"_radius"] - reference_model.parameters["primordium_"+str(p)+"_radius"]
            height_gap[p] = meristem_model.parameters["primordium_"+str(p+gap)+"_height"] - reference_model.parameters["primordium_"+str(p)+"_height"]
        rotation_0 = (reference_model.parameters['initial_angle'] - reference_model.parameters['primordium_offset']*golden_angle) %360
        rotation_1 = (meristem_model.parameters['initial_angle'] - meristem_model.parameters['primordium_offset']*golden_angle + gap*golden_angle) %360
        rotation_gap = np.cos(np.pi*(rotation_1 - rotation_0)/180.)
        gap_penalty = np.exp(-np.power(gap - (hour_gap)/6.,2.0)/np.power(6.,2.0))

        if same_individual:
            #gap_score.append(10*rotation_gap + np.mean(distance_gap))
            #gap_score[gap] = 10*rotation_gap*np.sign(np.mean(distance_gap.values()))
            gap_score[gap] = 10.0*np.mean(angle_gap.values())*np.exp(rotation_gap)*np.sign(np.mean(distance_gap.values()))*gap_penalty
            #gap_score[gap] = np.mean(angle_gap.values())
        else:
            gap_score[gap] = 10.0*np.mean(angle_gap.values())*np.exp(-np.power(np.mean(np.array(distance_gap.values())/6.),2.0))
            
        # print "Gap = ",gap,"[",gap_penalty,"] : r -> ",np.mean(distance_gap.values()),", A -> ",np.mean(angle_gap.values())," (",rotation_0,"->",rotation_1,":",rotation_gap,") [",gap_score[gap],"]"
    return gap_range[np.argmax([gap_score[gap] for gap in gap_range])]


def meristem_model_alignement(meristem_model, positions, reference_dome_apex, nuclei_image=None, signal_image=None, organ_gap=0., orientation=None):

    if orientation is None:
        orientation = meristem_model.parameters['orientation']
    golden_angle = np.sign(orientation)*(2.*np.pi)/((np.sqrt(5)+1)/2.+1)
    #golden_angle = (2.*np.pi)/((np.sqrt(5)+1)/2.+1)
    golden_angle = 180.*golden_angle/np.pi


    dome_apex = np.array([meristem_model.parameters['dome_apex_'+axis] for axis in ['x','y','z']])
    dome_phi = np.pi*meristem_model.parameters['dome_phi']/180.
    dome_psi = np.pi*meristem_model.parameters['dome_psi']/180.
    
    initial_angle = meristem_model.parameters['initial_angle']
    initial_angle -= meristem_model.parameters['primordium_offset']*golden_angle
    initial_angle += organ_gap*golden_angle 
    dome_theta = np.pi*initial_angle/180.

    if nuclei_image is not None:
        aligned_nuclei_image = deepcopy(nuclei_image)
        aligned_nuclei_image = nd.rotate(aligned_nuclei_image,angle=-180.*dome_phi/np.pi,axes=[0,2],reshape=False)
        aligned_nuclei_image = nd.rotate(aligned_nuclei_image,angle=-180.*dome_psi/np.pi,axes=[1,2],reshape=False)
        aligned_nuclei_image = nd.rotate(aligned_nuclei_image,angle=-180.*dome_theta/np.pi,axes=[0,1],reshape=False)
    else:
        aligned_nuclei_image = None
    
    if signal_image is not None:
        aligned_signal_image = deepcopy(signal_image)
        aligned_signal_image = nd.rotate(aligned_signal_image,angle=-180.*dome_phi/np.pi,axes=[0,2],reshape=False)
        aligned_signal_image = nd.rotate(aligned_signal_image,angle=-180.*dome_psi/np.pi,axes=[1,2],reshape=False)
        aligned_signal_image = nd.rotate(aligned_signal_image,angle=-180.*dome_theta/np.pi,axes=[0,1],reshape=False)
    else:
        aligned_signal_image = None
    
    rotation_phi = np.array([[np.cos(dome_phi),0,np.sin(dome_phi)],[0,1,0],[-np.sin(dome_phi),0,np.cos(dome_phi)]])
    rotation_psi = np.array([[1,0,0],[0,np.cos(dome_psi),np.sin(dome_psi)],[0,-np.sin(dome_psi),np.cos(dome_psi)]])
    rotation_theta = np.array([[np.cos(dome_theta),np.sin(dome_theta),0],[-np.sin(dome_theta),np.cos(dome_theta),0],[0,0,1]])
    
    relative_points = (positions.values()-dome_apex[np.newaxis,:])
    relative_points = np.einsum('...ij,...j->...i',rotation_phi,relative_points)
    relative_points = np.einsum('...ij,...j->...i',rotation_psi,relative_points)
    relative_points = np.einsum('...ij,...j->...i',rotation_theta,relative_points)
    relative_points = relative_points * np.array([1,orientation,1])[np.newaxis,:]
    
    aligned_positions = array_dict(reference_dome_apex + relative_points,positions.keys())
    aligned_position = deepcopy(aligned_positions)
    
    # golden_angle = (2.*np.pi)/((np.sqrt(5)+1)/2.+1)
    # golden_angle = 180.*golden_angle/np.pi
    
    parameters = deepcopy(meristem_model.parameters)
    parameters['orientation'] = orientation
    parameters['dome_apex_x'] = reference_dome_apex[0]
    parameters['dome_apex_y'] = reference_dome_apex[1]
    parameters['dome_apex_z'] = reference_dome_apex[2]
    parameters['dome_phi'] = 0
    parameters['dome_psi'] = 0
    parameters['initial_angle'] = 0
    #parameters['initial_angle'] += meristem_model.parameters['primordium_offset']*golden_angle
    parameters['initial_angle'] -= organ_gap*golden_angle
    for p in parameters.keys():
        if ('primordium' in p) and ('angle' in p):
             parameters[p] += meristem_model.parameters['primordium_offset']*golden_angle
             parameters[p] *= meristem_model.parameters['orientation']

    aligned_meristem_model = create_meristem_model(parameters)
    
    return aligned_meristem_model, aligned_positions, aligned_nuclei_image, aligned_signal_image


def meristem_model_registration(meristem_models, nuclei_positions, reference_dome_apex, nuclei_images=[], signal_images=[], reference_model=None, same_individual=False, model_ids=None):
    if model_ids is None:
        model_ids = np.sort(meristem_models.keys())

    aligned_meristem_models = {}
    aligned_nuclei_positions = {}
    aligned_nuclei_images = {}
    aligned_signal_images = {}

    if reference_model is None:
        if same_individual:
            reference_model = meristem_models[model_ids[0]]
        else:
            reference_model = reference_meristem_model(reference_dome_apex,developmental_time=0)

    if same_individual:
        previous_offset = 0

    for i_model in model_ids:
        model = meristem_models[i_model]
        organ_gap = meristem_model_organ_gap(reference_model,model,same_individual=same_individual)
        if same_individual:
            organ_gap += previous_offset
            # previous_offset = model.parameters['primordium_offset']
            previous_offset = organ_gap
        print "Organ Gap : ",organ_gap
        orientation = reference_model.parameters['orientation']
        positions = nuclei_positions[i_model]

        try:
            nuclei_image = nuclei_images[i_model]
            signal_image = signal_images[i_model]
        except:
            nuclei_image = None
            signal_image = None

        aligned_meristem_model, aligned_positions, aligned_nuclei_image, aligned_signal_image = meristem_model_alignement(model,positions,reference_dome_apex,nuclei_image,signal_image,organ_gap,orientation)
        aligned_meristem_models[i_model] = aligned_meristem_model
        aligned_nuclei_positions[i_model] = aligned_positions
        aligned_nuclei_images[i_model] = aligned_nuclei_image
        aligned_signal_images[i_model] = aligned_signal_image

    return aligned_meristem_models, aligned_nuclei_positions, aligned_nuclei_images, aligned_signal_images
