from decimal import Decimal


def convert_decimal_to_json_serializable(obj):
    """
    Convert DynamoDB Decimal objects to JSON-serializable types.
    
    This function recursively traverses the data structure and converts Decimal objects
    to int or float based on whether they have a fractional part.
    
    :param obj: The object to convert (can be dict, list, Decimal, or other types)
    :return: The object with Decimal values converted to JSON-serializable types
    """
    if isinstance(obj, dict):
        return {key: convert_decimal_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal_to_json_serializable(item) for item in obj]
    elif isinstance(obj, Decimal):
        # Convert Decimal to int if it's a whole number, otherwise to float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj
