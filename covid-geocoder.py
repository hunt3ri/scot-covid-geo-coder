import os
import pandas as pd
import requests
import urllib.parse

from dotenv import load_dotenv
from geojson import Feature, Point, FeatureCollection, dumps


def get_covid_data_for_week(week_id: str):
    """ Function extracts specified weeks data from raw csv file """
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 400)
    covid_df = pd.read_csv("covid_deaths_scot_raw_geo_names.csv")
    week_df = covid_df[(covid_df["DateCode"] == f"w/c {week_id}") &
                       (covid_df["Cause Of Death"] == "COVID-19 related") &
                       (covid_df["Sex"] == "All") &
                       (covid_df["Age"] == "All") &
                       (covid_df["Location Of Death"] == "All") &
                       (covid_df["Value"] > 0) &
                       (covid_df["FeatureCode"].str.contains("S12"))]

    print(week_df.head(50))

    week_data = f"week-{week_id}-covid.csv"
    week_df.to_csv(week_data, index=False)
    return week_data


def get_lat_long(official_name: str):
    """ Function uses a fairly naive approach to getting lat/long but good enough for heat map purposes """
    url_safe_name = urllib.parse.quote(official_name)
    query = f"https://api.ordnancesurvey.co.uk/opennames/v1/find?query={url_safe_name}&maxresults=1&key={os_token}"

    # Get first match as should be good enough to extract region information
    open_names_response = requests.get(query).json()
    gazetteer = open_names_response["results"][0]["GAZETTEER_ENTRY"]
    county_unitary = gazetteer["COUNTY_UNITARY"]
    if county_unitary.upper() != official_name.upper():
        raise ValueError('ERROR - Authority does not match searched for name')

    county_unitary_uri = gazetteer["COUNTY_UNITARY_URI"]
    print(county_unitary_uri)

    # Extract county data from response
    general_response = requests.get(f"{county_unitary_uri}.json").json()
    county_info = general_response[county_unitary_uri]

    # Extract Lat Lon
    lat_json = county_info["http://www.w3.org/2003/01/geo/wgs84_pos#lat"]
    lon_json = county_info["http://www.w3.org/2003/01/geo/wgs84_pos#long"]
    lat = lat_json[0]["value"]
    lon = lon_json[0]["value"]

    return lat, lon


def set_lat_long(week_data_file):
    """ Add Lat/Lon cols to the extracted data for week """
    week_df = pd.read_csv(week_data_file)
    death_cnt = 0
    for index, row in week_df.iterrows():
        lat, lon = get_lat_long(row["official_name"])
        print(lat)
        print(lon)
        week_df.loc[index, "lat"] = lat
        week_df.loc[index, "lon"] = lon
        death_cnt += row["Value"]

    print(week_df.head(50))
    print(f"Total Deaths = {death_cnt}")

    part_name = week_data_file.replace(".csv", "")
    file_name = f"{part_name}_lat_lon.csv"

    week_df.to_csv(file_name, index=False)
    return file_name, death_cnt


def gen_geojson(file_name: str, outputfile: str):
    """ Generate GeoJson file for heatmap """
    stats_df = pd.read_csv(file_name)
    features_list = []

    for index, row in stats_df.iterrows():
        feature_properties = {"deaths": row["Value"], "weight": 0.7, "place": row["official_name"]}
        feature = Feature(geometry=Point((row["lon"], row["lat"])), properties=feature_properties)
        features_list.append(feature)

    collection = FeatureCollection(features_list)

    print(dumps(collection, sort_keys=True))

    with open(f"./data/{outputfile}", 'w') as writer:
        writer.write(dumps(collection, indent=4, sort_keys=True))


if __name__ == "__main__":
    load_dotenv()
    os_token = os.getenv("OS_API_TOKEN", "NOT_SET")
    if os_token == "NOT_SET":
        raise ValueError("ERROR: Set OS_API_TOKEN in .env file")

    # TODO could work with total deaths, validate etc
    week_data_file = get_covid_data_for_week("2020-03-16")
    lat_lon_file, total_deaths = set_lat_long(week_data_file)
    gen_geojson(lat_lon_file, "week1.json")
