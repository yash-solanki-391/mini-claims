import json
from datetime import datetime
created_at = datetime.now()

def get_claim(claim_id, provider_id):
    return {"claim_id": claim_id, 
            
            





            
            "provider_id": provider_id}


claim = Claim(
    claim_id=101,
    provider_id=25,
    patient_id=501,
    claim_amount=15000,
    claim_status="pending",
    claim_date="2023-08-15",
    claim_type="medical",
    claim_description="Medical claim for surgery",
    claim_notes="Requires additional documentation",
)


# x=10

# def sample(is_valid):
#     if x > 5:
#         return True
#     else:
#         return False

# is_valid = sample(True)


