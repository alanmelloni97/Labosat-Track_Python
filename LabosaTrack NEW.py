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
        -steps_df: dataframe returnde by Orbit2steps
        -start_data: list returned by Orbit2steps
    '''
    sat=op.SelectSatFromName(sat_name)  #get satellite object
    print(sat_name)
    
    orbit_df=op.CalculateNextOrbit(sat, my_lat, my_lon, time_delta,24,elevation_start)   #get orbit dataframe
    steps_df,start_data=Orbit2steps(orbit_df, mechanical_resolution) #convert orbit to steps and start values
    steps_df.to_csv("csv/StepperSteps.csv") #generate csv with dataframe data
    return steps_df,start_data

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
        -start: list containing the following values:
            -orbit_start: time point where orbit starts
            -az_dir: azimuth direction (1: clockwise, -1: counterclockwise)
            -azimuth_start: azimuth angle in orbit start
            -elevation_start: elevation angle in orbit start
            -elev_dir_change: time point where elevation changes direction
            -mechanical_resolution: angle per step
        
    '''
    #get start point time
    orbit_start=orbit_df['Time'].iloc[0]
    orbit_df['Time']-=orbit_start
    
    #get elevation start angle
    elevation_start=orbit_df['Elevation'].iloc[0]
    #get azimuth start angle 
    azimuth_start=orbit_df['Azimuth'].iloc[0]
    
    #get azimuth direction
    az_dir=int(np.sign(orbit_df['dAz'].iloc[0]))
    
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
    
    az_step_count,az_angle,elev_step_count,elev_angle=0,0,0,0 #initialize counters
    
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
    
        elev_angle+=abs(orbit_df['dElev'][ind])
        while elev_angle>=mechanical_resolution:
            elev_step_count+=1
            elev_angle=elev_angle-mechanical_resolution
            orbit_df['Elev Steps'][ind]+=1
       
        #evaluate if elevation derivative became negative, indicating a
        #direction change. If the point is the direction change, save its time
        if orbit_df['dElev'][ind]<0 and dir_setted==False:
            elev_dir_change=orbit_df['Time'][ind]
            dir_setted=True
        
        #remove rows without steps
        if orbit_df['Steps'][ind]==0:
            orbit_df.drop([ind],axis=0,inplace=True)
    
    #Create list of start values
    start_data=(orbit_start,az_dir,azimuth_start,elevation_start,elev_dir_change,mechanical_resolution)
         
    #remove irrelevant columns
    orbit_df.drop(orbit_df.columns.difference(['Time','Elev Steps','Az Steps']), 1, inplace=True)
    
    return orbit_df,start_data


def CompressOrbitData(steps_df,start_data,mechanical_resolution):