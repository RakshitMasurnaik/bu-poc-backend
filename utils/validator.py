import re

def validate_field(value, business_type: str, rules: dict = None):
    if value is None:
        return False, "Value is None"
        
    try:
        if business_type == "Email":
            if not re.match(r"[^@]+@[^@]+\.[^@]+", str(value)):
                return False, "Invalid email format"
        elif business_type == "Phone":
            if not re.match(r"^\+?1?\d{9,15}$", str(value)):
                return False, "Invalid phone format"
        elif business_type == "Currency" or business_type == "Float":
            val = float(value)
            if rules:
                if 'min_value' in rules and rules['min_value'] is not None and val < rules['min_value']:
                    return False, f"Value below minimum {rules['min_value']}"
                if 'max_value' in rules and rules['max_value'] is not None and val > rules['max_value']:
                    return False, f"Value above maximum {rules['max_value']}"
        elif business_type == "Integer":
            int(value)
        elif business_type == "Boolean":
            if str(value).lower() not in ['true', 'false', '1', '0']:
                return False, "Not a boolean"
    except ValueError:
        return False, f"Type mismatch for {business_type}"
        
    return True, ""
