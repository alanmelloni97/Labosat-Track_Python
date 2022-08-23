import orbit_prediction as op
import LabosaTrack as lst
import pandas as pd
import serial

myLatLon=(-34.587353,-58.520116)
az_resolution = 0.9/16
elev_resolution = 0.9/16
elevation_start = 0
timeStep=1
a=0
orbit=pd.DataFrame()
satName=""

print("Labosat-Track")
print("Current configuration:")
print("    Latitude:", myLatLon[0],"Longitude:",myLatLon[1])
print("    Time between points:", timeStep)
print("    Steppers congiguration:")
print("        -Az resolution:", az_resolution)
print("        -Elev resolution:", elev_resolution)


def configure_system():
    
    print("Set Latitude:")
    myLat=int(input())
    while(myLat>90 or myLat<-90):
        print("Invalid entry, set latitude:")
        myLat=int(input())
        
    print("Set Longitude:")
    myLon=int(input())
    while(myLat>180 or myLat<-180):
        print("Invalid entry, set longitude")
        myLat=int(input())
    myLatLon=(myLat,myLon)
    
    print("Set time between samples in seconds:")
    timeStep=int(input())
    while(timeStep<0):
        print("Invalid entry, Set time between samples")
        timeStep=int(input())
    
    print("Set elevation start (angle of elevation to start tracking):")
    elevation_start=int(input())
    while(elevation_start<0):
        print("Invalid entry, Set elevation start")
        elevation_start=int(input())

    print("Set azimutal resolution (degrees per step)")
    az_resolution=int(input())
    while(az_resolution < 0):
        print("Invalid entry, Set azimutal resolution")
        az_resolution=int(input())
        
    print("Set elevation resolution (degrees per step)")
    elev_resolution=int(input())
    while(elev_resolution < 0):
        print("Invalid entry, Set elevation resolution")
        elev_resolution=int(input())
        
    return myLatLon,timeStep,az_resolution,elev_resolution

while True:
        
    if orbit.empty:
        print("----No orbit selected----")
    else:
        print("----Orbit:",satName,"----")
        print("----Orbit start:",op.GetDatetimeFromUNIX(round(orbit["Time"].iloc[0],0)))
        print("----Max altitude:",max(orbit["Altitude"]))
        
    print("Select option:")
    print("1) Configure system")
    print("2) Select satellite by string")
    print("3) Select closest satellite [For testing]")
    if not orbit.empty:
        print("4) Send orbit data to microcontroller")
    print("0) Exit")
    
    a=input()
    
    if a=='0':
        break
    elif a=='1':
        myLatLon,timeStep,az_resolution,elev_resolution=configure_system()
        
    elif a=='2':   
        print("Paste satellite name from https://celestrak.com/NORAD/elements/active.txt")
        satName=int(input())        
        orbit = lst.SatTrack(myLatLon[0], myLatLon[1], satName, timeStep, elevation_start)
        steps,start_data = lst.Orbit2steps(orbit, az_resolution, elev_resolution)
        compressed_steps = lst.CompressOrbitData(steps)
        
    elif a=='3':
        print("Selecting closest satellite...")
        sat = op.NextSatPass(op.DownloadTLEs(),myLatLon[0],myLatLon[1],10, 70)
        print("Satellite selected:",sat)
        orbit = lst.SatTrack(myLatLon[0], myLatLon[1], sat.name, timeStep, elevation_start)
        steps,start_data = lst.Orbit2steps(orbit, az_resolution, elev_resolution)
        compressed_steps = lst.CompressOrbitData(steps)
        satName=sat.name
     
        
    elif a=='4':
        if orbit.empty:
            print("Incorrect input",end="\n\n")
            continue
        print("Sending orbit through serial port...")
        try:
            serial_device=serial.Serial(port='COM8', baudrate=115200,stopbits=1,timeout=16,write_timeout=1)
        except:
            print("ERROR: Couldn't connect to serial port")
        lst.SerialSend(serial_device,compressed_steps,start_data)
        
            
    else:
        print("Incorrect input")
    
    print("")
        
