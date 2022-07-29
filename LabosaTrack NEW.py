import orbit_prediction as op
from skyfield.api import load, wgs84
import time
import datetime
import pandas as pd
import numpy as np
pd.options.mode.chained_assignment = None  # default='warn'
from tqdm import tqdm
import serial
import math

def SatTrack(my_lat,my_lon,sat_name,mechanical_resolution,time_delta,elevation_start):
    '''Brief: calculates satellite pass and returns two elements: a dataframe containing
    time points and steps and a list of start values
    Parameters:
        -my_lat: observer's latitude
        -my_lon: observer's longitude
        -sat_name: satellite name
        -mechanical_resolution: angle per step
        -time_delta: time between points
        -elevation_start: elevation angle to start calculating orbit
    Returns:
        
    '''
    sat=op.SelectSatFromName(sat_name)  #get satellite object
    print(sat_name)
    
    orbit_df=op.CalculateNextOrbit(sat, my_lat, my_lon, time_delta,24,elevation_start)   #get orbit dataframe
    steps_df,start_df=Orbit2steps(orbit_df, mechanical_resolution) #convert orbit to steps and start values
    steps_df.to_csv("csv/StepperSteps.csv") #generate csv with dataframe data
    
    return steps_df,start_df

def Orbit2steps(orbit_df,mechanical_resolution):
    '''Brief: Calculate steps to make in each point by differenciating both angles.
    Parameters:
        -orbit_df: orbit containing time points, azimuth and elevation columns
        -mechanical_resolution: angle per step
    Returns:
        -steps_df: dataframe containing three columns:
            -time: time point
            -elevation steps: amount of elevation steps to make in that point
            -azimuth steps: amount of azimuth steps to make in that point
        -start: containing the following values:
            
        
    '''
    
    #get azimuth start angle 
    azimuth_start=orbit_df['Azimuth'].iloc[0]
    #convert azimuth start angle from (0,360) to (-180,180)
    if azimuth_start>180:
        azimuth_start-=360
    if azimuth_start<-180:
        azimuth_start+=360
        
    #Calculate azimuth and elevation derivative
    orbit_df['dElev'] = (orbit_df['Elevation'] - orbit_df['Elevation'].shift(1)).fillna(0)
    orbit_df['dAz'] = (orbit_df['Azimuth'] - orbit_df['Azimuth'].shift(1)).fillna(0)
    
    #Initialize steps columns
    orbit_df['Elev Steps']=0
    orbit_df['Az Steps']=0
    orbit_df.index.name="Index"  #set index name (irrelevant)
    
    dir_setted= False    #a boolean is used to know if the direction change in elevation happened
    
    az_step_count,az_angle,alt_step_count,alt_angle=0,0,0,0 #initialize counters
    
    #iterate over each orbit point
    for ind in tqdm(orbit_df.index):
        
        #If azimuth angle changes from 0 to 359 or vice versa, a correction is made to the azimuth delta
        if abs(orbit_df['dAz'][ind])>300:
            if(orbit_df['dAz'][ind])>0:
                orbit_df['dAz'][ind]-=360
            if(orbit_df['dAz'][ind])<0:
                orbit_df['dAz'][ind]+=360
           
        #evaluate if azimuth acumulated angle is greater than the angle per step
        # if it is, add a step to the step column and substract the angle per step
        #repeat until az_angle is smaller than the angle per step
        az_angle+=abs(orbit_df['dAz'][ind]) 
        while az_angle>=mechanical_resolution:
            az_step_count+=1
            az_angle=az_angle-mechanical_resolution
            orbit_df['Az Steps'][ind]+=1
    
        alt_angle+=abs(orbit_df['dElev'][ind])
        while alt_angle>=mechanical_resolution:
            alt_step_count+=1
            alt_angle=alt_angle-mechanical_resolution
            orbit_df['Elev Steps'][ind]+=1
       
        #evaluate if elevation derivative became negative, indicating a
        #direction change. If the point is the direction change, save its time
        if orbit_df['dElev'][ind]<0 and dir_setted==False:
            alt_dir_change=orbit_df['Time'][ind]
            dir_setted=True
        
        #remove rows without steps
        if orbit_df['Steps'][ind]==0:
            orbit_df.drop([ind],axis=0,inplace=True)
    
    start=()
                
    startData={'AzDir':int(np.sign(orbit_df['dAz'].iloc[0])),'Azimuth':azimuthStart,'Altitude':orbitDf['Altitude'].iloc[0],'AltDir Change':AltDirChange,'Stepper Res':stepperRes}
    start_df = pd.DataFrame(startData,index=[0])
    start_df.index.name="start"
    return orbitDf,startDf