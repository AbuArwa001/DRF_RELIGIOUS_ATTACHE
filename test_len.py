import json

fields = [
    'id', 'full_name', 'date_of_birth',
    'nationality', 'national_id_number', 'current_residence', 'county',
    'category', 'nominating_institution',
    'phone_number', 'alternative_phone', 'email',
    'id_document', 'passport_photo',
    'submitted_at', 'non_field_errors', 'gender', 'detail'
]

msgs = [
    "This field is required.",
    "This field may not be blank.",
    "This field may not be null.",
    "Enter a valid email address.",
    "No file was submitted.",
    "JSON parse error - Expecting value",
    "Unsupported media type \"multipart/form-data\" in request."
]

for f in fields:
    for m in msgs:
        d = {f: [m]}
        # DRF default includes space after colon and comma
        l = len(json.dumps(d)) 
        if l == 61:
            print(f"MATCH (DRF default): {f} -> {m}")
        
        # Or maybe it's not a list?
        d2 = {f: m}
        l2 = len(json.dumps(d2))
        if l2 == 61:
            print(f"MATCH string (DRF default): {f} -> {m}")
