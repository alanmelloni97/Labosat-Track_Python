from skyfield.api import load, wgs84, EarthSatellite
import datetime
import pandas as pd
from tqdm import tqdm


def DownloadTLEs(): #under
    '''Brief: Download all active satellites TLEs from celestrack.com
    Returns: 
        -dictionary with names and TLEs
    '''
    print("Downloading all active TLEs:")
    tle_url = 'https://celestrak.com/NORAD/elements/active.txt'
    satellites = load.tle_file(tle_url,reload=True)
    return {sat.name: sat for sat in satellites}

def GetSatFromString(line1,line2,name): #programmer
    '''Brief: Get satellite with raw TLE lines
    Parameters:
        -line1: first TLE line (string)
        -line2: second TLE line (string)
        -name: satellite name (string)
    Returns:
        -satellite object
    '''
    ts = load.timescale() #initialize skyfield time scale
    return EarthSatellite(line1, line2, name, ts)

def SelectSat(TLE_list,sat_name): #under
    '''Brief: Selects one satellite from a TLE dictionary
    Parameters: 
        -TLE_list: Dictionary of satellites and satellite names
        -sat_name: satellite name (string)
    Returns: 
        -satellite object
    '''
    return TLE_list[sat_name]

def SelectSatFromName(sat_name): #programmer
    '''Brief: Downloads TLEs and selects a specific satellite
    Parameters:
        -sat_name: satellite name (string)
    Returns: 
        -satellite object
    '''
    return SelectSat(DownloadTLEs(),sat_name)

def GetDatetimeFromUNIX(seconds):
    '''Brief: converts UNIX seconds to datetime.datetime object
    Parameters:
        -seconds: UNIX seconds
    Returns:
        -datetime.datetime object
    '''
    return datetime.datetime.fromtimestamp(seconds,datetime.timezone.utc)

def AddTimeDelta(t0,time_delta):
    '''Brief: adds a time delta to a skyfield.timelib.Time
    Parameters:
        -t0: skyfield.timelib.Time object
        -time_delta: amount of time to add in seconds
    Returns:
        -skyfield.timelib.Time object
    '''
    ts = load.timescale()
    return ts.from_datetime(t0.utc_datetime()+datetime.timedelta(seconds=time_delta))

def TimeSinceEpoch(sat,t): #programmer
    '''Brief: Calculates time since TLE epoch
    Parameters:
        -sat: satellite object
        -t: current time (skyfield.timelib.Time object), usually is load.timescale().now()
    Returns: 
        -datetime.datetime object
    '''
    epoch=sat.epoch.utc_datetime() #get satellite epoch in datetime.datetime format
    t=t.utc_datetime()  #convert t to datetime.datetime format
    return epoch-t

def SGP4(sat,t):
    '''Brief: Runs SGP4 algoritm for a given satellite and time
    Parameters:
        -sat: satellite object
        -t: time point (skyfield.timelib.Time object)
    Returns: 
        -lat: satellite's latitude
        -lon: satellite's longitude
        -hei: satellite's height
    '''
    sat_pos_geocentric = sat.at(t) #get satellite position in Geocentric Celestial Reference System
    lat, lon = wgs84.latlon_of(sat_pos_geocentric) #get lat and long from satellite position
    hei = wgs84.height_of(sat_pos_geocentric).km #get height from satellite position
    return lat,lon,hei

def GetSatElevAzDist(sat,my_lat,my_lon,t):
    '''Brief: Gets satellite elevation, azimuth and distance
    Parameters:
        -sat: satellite object
        -my_lat: observer's latitude
        -my_lon: observer's longitude
    Returns:
        -elev: satellite's elevation
        -az: satellite's azimuth
        -distance: distance between satellite and observer
    '''
    bluffton = wgs84.latlon(my_lat, my_lon) #generates object with observer's position
    difference = sat - bluffton    #calculate satellite position relative to the observer
    topocentric = difference.at(t)  #get coordinates of the relative position
    elev, az, distance = topocentric.altaz() #convert coordinates to azimuth and elevation
    return elev,az,distance

def NextSatPass(TLEs,my_lat,my_lon,t_start_offset,min_elevation):
    '''Brief: Gets a pass from the closest satellite (time wise). Starting from the
    moment this method is called, it will look for an event of surpassing
    'min elevation' elevation after t_start_offset minutes.
    Example: with current time being 10:00,t_start_offset=15 and mi_elevation=20,
    this method will start looking from 10:15 forward for an event where a 
    satellite surpasses 20 degrees of elevation, and return said satellite
    Parameters:
        -TLEs: dictionary with TLEs
        -my_lat: observer's latitude
        -my_lon: observer's longitude
        -t_start_offset: time in minutes
        -min_elevation: minimun orbit elevation in degrees
    Returns:
        -satellite: satellite object
    '''
    ts = load.timescale() #initialize skyfield time scale
    t0 = ts.from_datetime(ts.now().utc_datetime()+datetime.timedelta(minutes=t_start_offset)) #generate timescale object with value current time + t_start_offset
    t1 = AddTimeDelta(t0,5*60) #generate timescale object with value t0 + 5 minutes. This is enough time to get at least 1 satellite with elevation > min_elevation
    bluffton = wgs84.latlon(my_lat,my_lon)  #generates object with observer's position
    for key in TLEs.keys():     #Iterate TLE list
        satellite=SelectSat(TLEs,key)
        t, events = satellite.find_events(bluffton, t0, t1, altitude_degrees=min_elevation) #look for an elevation > min_elevation in the time interval (t0,t1)
        if len(events)==3:      #3 events are needed: rise above min_elevation, zenith and rise below mi:elevation, if 2 or less events are found, rise above happened before t_start_offset, so the satellite is discarded
            return satellite
        
def PredictOrbit(sat,my_lat,my_lon,start_time_unix,period_seconds,time_delta,save_csv=False):
    '''Brief: generate a dataframe containing the orbit pass
    Parameters:
        -sat: satellite object
        -my_lat: observer's latitude
        -my_lon: oberver's longitude
        -start_time_unix: time to start calculating orbit (in UNIX seconds)
        -period_seconds: time interval to calculate orbit in seconds
        -time_delta: time interval bteween each calculated point in seconds
        -save_csv: boolean specifying whether to save dataframe in a csv file or not
    Returns:
        -df: dataframe containing all calculated points in the following columns:
            -Time: time in UNIX seconds
            -Latitude: satellite's latitude
            -Longitude: satellite's longitude
            -Height: satellite's height
            -Elevation: satellite's elevation
            -Azimuth: satellite's azimuth
            -Distance: distance between satellite and observer
    '''
    print("calculating orbit:",flush=True)
    df = pd.DataFrame(columns=["Time","Latitude","Longitude","Height","Elevation","Azimuth","Distance"]) #initialize dataframe

    for i in tqdm(range(0,int(period_seconds/time_delta))): #iterate for amount of points desired: amount_seconds* time_delta
        IterationTime = start_time_unix+datetime.timedelta(seconds=i*time_delta)    #Get iteration time
        lat,lon,hei = SGP4(sat, IterationTime) #get satellite's latitude, longitude and height
        alt,az,distance = GetSatElevAzDist(sat, my_lat, my_lon, IterationTime) #get satellite's elevation, azimuth and distance
        df2=pd.DataFrame( \
            [[round(IterationTime.utc_datetime().timestamp(),3),lat.degrees,lon.degrees,hei,alt.degrees,az.degrees,distance.km]], \
            index=[i], \
            columns=["Time","Latitude","Longitude","Height","Elevation","Azimuth","Distance"]) #save values in an auxiliary one row dataframe
        df=pd.concat([df,df2]) #merge (concatenate) both dataframes
    if save_csv == True:
        df.to_csv("csv/trackedOrbit.csv")   #save dataframe as .csv
    return df
        
def CalculateNextOrbit(sat,my_lat,my_lon,time_delta,in_hours=48,min_elevation=30):
    '''Brief: calculate next orbit of a specific satellite that surpasses min_elevation
    Parameters:
        -sat: satellite object
        -my_lat: observer's latitude
        -my_lon: observer's longitude
        -time_delta: time interval between each calculated point in seconds
        -in_hours: amount of hours to look for a valid orbit
        -min_elevation: minimun orbit elevation in degrees
    Returns:
        -dataframe returned by PredictOrbit
        
    '''
    ts = load.timescale() #initialize skyfield time scale
    t0 = ts.now() #get current time
    t1 = AddTimeDelta(t0,in_hours*60*60) #get time with an in_hours offset from t0
    bluffton = wgs84.latlon(my_lat, my_lon) #generates object with observer's position
    tx, events = sat.find_events(bluffton, t0, t1, altitude_degrees=min_elevation)  #look for an elevation > min_elevation in the time interval (t0,t1)
    
    # Make sure the first event is a 'rise over min_elevation' event
    n=0
    while events[n]!=0: # 'rise over min_elevation' event equals 0
        n+=1
    tx_dt=tx.utc_datetime()  #Convert tx list to datetime object (UTC)
    taux=tx_dt[n+2]-tx_dt[n]  #take 'fall below min_elevation' time [n+2] and substract 'rise over min_elevation', obtaining total relevant orbit time in seconds
    
    return PredictOrbit(sat,my_lat,my_lon,tx[n],taux.seconds,time_delta)
