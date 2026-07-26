"""Generate JWT tokens for testing SmartHandoff API endpoints."""
import os
import sys
from datetime import datetime, timezone
import uuid

# Set minimal environment for JWT generation
os.environ.setdefault("JWT_SIGNING_KEY", "test-secret-key-minimum-32-characters-for-hs256-signing")

from jose import jwt

# JWT Configuration (matches app/core/auth/jwt.py)
ALGORITHM = "HS256"
TOKEN_EXPIRY_SECONDS = 8 * 60 * 60  # 8 hours

def generate_jwt_token(
    user_id: str,
    role: str,
    email: str = "",
    units: list[str] = None,
    signing_key: str = None
) -> str:
    """Generate a SmartHandoff JWT token.
    
    Args:
        user_id: User identifier (sub claim)
        role: User role (admin, physician, nurse, pharmacist, bed_manager, PATIENT)
        email: User email
        units: List of unit codes (e.g., ["ICU", "ER"])
        signing_key: JWT signing key (defaults to environment variable)
    
    Returns:
        str: Signed JWT token
    """
    if signing_key is None:
        signing_key = os.environ.get("JWT_SIGNING_KEY", "")
        if not signing_key or len(signing_key) < 32:
            print("⚠ WARNING: Using default signing key. Set JWT_SIGNING_KEY environment variable.")
            signing_key = "test-secret-key-minimum-32-characters-for-hs256-signing"
    
    now = int(datetime.now(tz=timezone.utc).timestamp())
    jti = str(uuid.uuid4())
    
    payload = {
        "sub": user_id,
        "role": role,
        "email": email,
        "units": units or [],
        "jti": jti,
        "iat": now,
        "exp": now + TOKEN_EXPIRY_SECONDS,
    }
    
    token = jwt.encode(payload, signing_key, algorithm=ALGORITHM)
    return token


def print_token_info(token: str, label: str):
    """Decode and print JWT token information."""
    from jose import jwt
    try:
        decoded = jwt.decode(
            token,
            os.environ.get("JWT_SIGNING_KEY", "test-secret-key-minimum-32-characters-for-hs256-signing"),
            algorithms=[ALGORITHM],
            options={"verify_exp": False}  # Skip expiry check for display
        )
        
        print(f"\n{'='*80}")
        print(f"{label}")
        print('='*80)
        print("\nToken:")
        print(f"{token}\n")
        print("Decoded Payload:")
        for key, value in decoded.items():
            if key == "exp" or key == "iat":
                dt = datetime.fromtimestamp(value, tz=timezone.utc)
                print(f"  {key:8} = {value} ({dt.strftime('%Y-%m-%d %H:%M:%S UTC')})")
            else:
                print(f"  {key:8} = {value}")
        print('='*80)
    except Exception as e:
        print(f"Error decoding token: {e}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SMARTHANDOFF JWT TOKEN GENERATOR")
    print("="*80 + "\n")
    
    # Check if JWT_SIGNING_KEY is set
    signing_key = os.environ.get("JWT_SIGNING_KEY")
    if signing_key and len(signing_key) >= 32:
        print(f"✓ Using JWT_SIGNING_KEY from environment ({len(signing_key)} chars)")
    else:
        print("⚠ JWT_SIGNING_KEY not set, using default test key")
        print("  For production tokens, set: $env:JWT_SIGNING_KEY='your-key-here'\n")
    
    # Generate sample tokens for different roles
    tokens = {}
    
    # 1. Admin Token
    tokens["admin"] = generate_jwt_token(
        user_id="admin-user-123",
        role="admin",
        email="admin@smarthandoff.com",
        units=["ICU", "ER", "SURGERY"]
    )
    
    # 2. Physician Token
    tokens["physician"] = generate_jwt_token(
        user_id="physician-user-456",
        role="physician",
        email="doctor@smarthandoff.com",
        units=["ICU", "CARDIOLOGY"]
    )
    
    # 3. Nurse Token
    tokens["nurse"] = generate_jwt_token(
        user_id="nurse-user-789",
        role="nurse",
        email="nurse@smarthandoff.com",
        units=["ICU"]
    )
    
    # 4. Patient Token
    tokens["patient"] = generate_jwt_token(
        user_id="patient-12345",
        role="PATIENT",
        email="patient@example.com",
        units=[]
    )
    
    # Display all tokens
    for role, token in tokens.items():
        print_token_info(token, f"{role.upper()} TOKEN")
    
    # Usage instructions
    print("\n" + "="*80)
    print("HOW TO USE THESE TOKENS")
    print("="*80 + "\n")
    
    print("1. Copy a token from above")
    print("\n2. Use with curl:")
    print('   curl -H "Authorization: Bearer YOUR_TOKEN_HERE" \\')
    print('        https://smarthandoff-backend-h67r7fyswq-uc.a.run.app/api/v1/patients\n')
    
    print("3. Use with Python requests:")
    print('   import requests')
    print('   headers = {"Authorization": "Bearer YOUR_TOKEN_HERE"}')
    print('   response = requests.get("https://your-api/api/v1/patients", headers=headers)\n')
    
    print("4. Use in Postman/Insomnia:")
    print('   - Auth Type: Bearer Token')
    print('   - Token: YOUR_TOKEN_HERE\n')
    
    print("="*80)
    print("\nCUSTOM TOKEN GENERATION:")
    print("="*80 + "\n")
    print("Run with Python:")
    print('  from generate_jwt_token import generate_jwt_token')
    print('  token = generate_jwt_token(')
    print('      user_id="custom-user-id",')
    print('      role="physician",')
    print('      email="custom@example.com",')
    print('      units=["ICU", "ER"]')
    print('  )')
    print('  print(token)\n')
    
    # Interactive mode
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        print("\n" + "="*80)
        print("INTERACTIVE MODE")
        print("="*80 + "\n")
        
        user_id = input("Enter user ID: ").strip() or "test-user-123"
        role = input("Enter role (admin/physician/nurse/pharmacist/bed_manager/PATIENT): ").strip() or "physician"
        email = input("Enter email: ").strip() or "test@example.com"
        units_input = input("Enter units (comma-separated, e.g., ICU,ER): ").strip()
        units = [u.strip() for u in units_input.split(",")] if units_input else []
        
        custom_token = generate_jwt_token(user_id, role, email, units)
        print_token_info(custom_token, "CUSTOM TOKEN")
    
    print("\n✓ Done!\n")
