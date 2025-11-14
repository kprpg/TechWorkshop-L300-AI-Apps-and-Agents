import os
from azure.identity import DefaultAzureCredential
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, ALL_COMPLETED

# Load environment variables from .env file
load_dotenv()

def inventory_check(product_dict: dict) -> list:
    """
    Simulates checking for inventory details from Microsoft Fabric.

    Args:
        product_dict (dict): Keys are product names, values are product IDs.

    Returns:
        list: Each element is the matching row if the product ID is found, otherwise None.
    """

    # Simulated data
    product_inventory = {
        'PROD0001': {'ProductName': 'Pale Meadow', 'Quantity': 312, 'Price': 29.99},
        'PROD0002': {'ProductName': 'Tranquil Lavender', 'Quantity': 145, 'Price': 31.99},
        'PROD0003': {'ProductName': 'Whispering Blue', 'Quantity': 487, 'Price': 47.99},
        'PROD0004': {'ProductName': 'Whispering Blush', 'Quantity': 56, 'Price': 50.82},
        'PROD0005': {'ProductName': 'Ocean Mist', 'Quantity': 221, 'Price': 84.83},
        'PROD0006': {'ProductName': 'Sunset Coral', 'Quantity': 399, 'Price': 48.57},
        'PROD0007': {'ProductName': 'Forest Whisper', 'Quantity': 78, 'Price': 43.09},
        'PROD0008': {'ProductName': 'Morning Dew', 'Quantity': 305, 'Price': 81.94},
        'PROD0009': {'ProductName': 'Dusty Rose', 'Quantity': 412, 'Price': 75.62},
        'PROD0010': {'ProductName': 'Sage Harmony', 'Quantity': 67, 'Price': 33.26},
        'PROD0011': {'ProductName': 'Vanilla Dream', 'Quantity': 254, 'Price': 54.66},
        'PROD0012': {'ProductName': 'Charcoal Storm', 'Quantity': 188, 'Price': 43.45},
        'PROD0013': {'ProductName': 'Golden Wheat', 'Quantity': 499, 'Price': 109.73},
        'PROD0014': {'ProductName': 'Soft Pebble', 'Quantity': 321, 'Price': 110.92},
        'PROD0015': {'ProductName': 'Misty Gray', 'Quantity': 92, 'Price': 96.04},
        'PROD0016': {'ProductName': 'Rustic Clay', 'Quantity': 276, 'Price': 83.37},
        'PROD0017': {'ProductName': 'Ivory Pearl', 'Quantity': 134, 'Price': 91.99},
        'PROD0018': {'ProductName': 'Deep Forest', 'Quantity': 401, 'Price': 119.93},
        'PROD0019': {'ProductName': 'Autumn Spice', 'Quantity': 58, 'Price': 30.34},
        'PROD0020': {'ProductName': 'Coastal Whisper', 'Quantity': 215, 'Price': 39.99},
        'PROD0021': {'ProductName': 'Effervescent Jade', 'Quantity': 362, 'Price': 42.99},
        'PROD0022': {'ProductName': 'Frosted Blue', 'Quantity': 77, 'Price': 36.99},
        'PROD0023': {'ProductName': 'Frosted Lemon', 'Quantity': 489, 'Price': 28.99},
        'PROD0024': {'ProductName': 'Honeydew Sunrise', 'Quantity': 123, 'Price': 45.99},
        'PROD0025': {'ProductName': 'Lavender Whisper', 'Quantity': 256, 'Price': 33.99},
        'PROD0026': {'ProductName': 'Lilac Mist', 'Quantity': 411, 'Price': 55.99},
        'PROD0027': {'ProductName': 'Soft Creamsicle', 'Quantity': 98, 'Price': 41.99},
        'PROD0028': {'ProductName': 'Whispering Blush', 'Quantity': 312, 'Price': 26.99},
        'PROD0029': {'ProductName': 'Lavender Whisper', 'Quantity': 75, 'Price': 33.99},
        'PROD0030': {'ProductName': 'Lilac Mist', 'Quantity': 201, 'Price': 55.99},
        'PROD0031': {'ProductName': 'Soft Creamsicle', 'Quantity': 487, 'Price': 41.99},
        'PROD0032': {'ProductName': 'Whispering Blush', 'Quantity': 154, 'Price': 26.99},
        'PROD0033': {'ProductName': 'Cordless Airless Pro', 'Quantity': 299, 'Price': 120.99},
        'PROD0034': {'ProductName': 'Cordless Compact Painter', 'Quantity': 412, 'Price': 149.99},
        'PROD0035': {'ProductName': 'Electric Sprayer 350', 'Quantity': 88, 'Price': 135.99},
        'PROD0036': {'ProductName': 'HVLP SuperFinish', 'Quantity': 367, 'Price': 125.99},
        'PROD0037': {'ProductName': 'Handheld Airless 360', 'Quantity': 210, 'Price': 130.99},
        'PROD0038': {'ProductName': 'Handheld HVLP Pro', 'Quantity': 56, 'Price': 139.99},
        'PROD0039': {'ProductName': 'Paint Safe Drop Cloth', 'Quantity': 478, 'Price': 55.99},
        'PROD0040': {'ProductName': 'Paint Guard Reusable Drop Cloth', 'Quantity': 123, 'Price': 60.99},
        'PROD0041': {'ProductName': 'Fine Finish Paint Brush', 'Quantity': 312, 'Price': 2.99},
        'PROD0042': {'ProductName': 'All-Purpose Wall Paint Brush', 'Quantity': 145, 'Price': 3.99},
        'PROD0043': {'ProductName': 'Large Area Applicator Brush', 'Quantity': 487, 'Price': 4.99},
        'PROD0044': {'ProductName': 'Classic Flat Sash Brush', 'Quantity': 56, 'Price': 3.99},
        'PROD0045': {'ProductName': 'Standard Paint Tray', 'Quantity': 221, 'Price': 10.99},
        'PROD0046': {'ProductName': 'Deep Well Paint Tray', 'Quantity': 399, 'Price': 7.99},
        'PROD0047': {'ProductName': 'Compact Paint Tray', 'Quantity': 78, 'Price': 8.99},
        'PROD0048': {'ProductName': 'Heavy-Duty Paint Tray with Grid', 'Quantity': 305, 'Price': 135.99},
        'PROD0049': {'ProductName': "Blue Painter's Tape", 'Quantity': 412, 'Price': 3.99},
        'PROD0050': {'ProductName': "Green Painter's Tape", 'Quantity': 67, 'Price': 2.99},
        'PROD0051': {'ProductName': 'Standard Paint Roller', 'Quantity': 254, 'Price': 15.99},
        'PROD0052': {'ProductName': 'Ergonomic Grip Paint Roller', 'Quantity': 188, 'Price': 10.99},
        'PROD0053': {'ProductName': 'Classic Wood Handle Paint Roller', 'Quantity': 499, 'Price': 9.99},
        'PROD0054': {'ProductName': 'Wooden Handle Paint Roller', 'Quantity': 321, 'Price': 8.99},
    }

    results = [ product_inventory[v] for _,v in product_dict.items() ]
    return results


# Example usage:
# product_dict = { 'item1': 'PROD0004', 'item2': 'PROD0013' }
# inventory_levels = inventory_check(product_dict)
# print(inventory_levels)