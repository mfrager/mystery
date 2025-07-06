#!/usr/bin/env python3
"""
Example client for the Mystery Protocol Server.
Demonstrates how to use the new server endpoints.
"""

import requests
import json
import base64
import logging
import uuid
import bz2
import traceback
from mystery_protocol import MysteryProtocol

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MysteryServerClient:
    """Client for interacting with the Mystery Protocol Server."""
    
    def __init__(self, server_url: str = "http://localhost:1776"):
        self.server_url = server_url
        self.protocol = MysteryProtocol()
        self._last_compressed_data = None
    
    def submit_challenge_data(self, challenge_package: dict, unencrypted_mapping: list, user_id: str, key_name: str, key_index: int, segments: int = 10):
        """Submit challenge data file with unencrypted mapping to server.
        
        Args:
            challenge_package: Dictionary containing the challenge package data
            unencrypted_mapping: List of mapping dictionaries for verification
            user_id: UUID string identifying the user
            key_name: String identifier for the key (max 64 chars)
            key_index: Integer index for the key
            segments: Number of segments for mapping obfuscation (default: 10)
        """
        url = f"{self.server_url}/submit_challenge_data"
        
        # Compress the challenge package using bz2
        json_str = json.dumps(challenge_package, sort_keys=True)
        compressed = bz2.compress(json_str.encode('utf-8'))
        
        # Store for statistics
        self._last_compressed_data = compressed
        
        # Prepare multipart form data
        files = {
            'challenge_package_compressed': ('challenge_package.bz2', compressed, 'application/octet-stream')
        }
        
        data = {
            'unencrypted_mapping': json.dumps(unencrypted_mapping),
            'user_id': user_id,
            'key_name': key_name,
            'key_index': str(key_index),
            'segments': str(segments)
        }
        
        response = requests.post(url, files=files, data=data)
        return response.json(), response.status_code
    
    def get_authentication_challenge(self, user_id: str, key_name: str, timeout_minutes: int = 30):
        """Get an authentication challenge from the server for a specific user and key."""
        url = f"{self.server_url}/get_authentication_challenge"
        data = {
            'user_id': user_id,
            'key_name': key_name,
            'timeout_minutes': timeout_minutes
        }
        
        response = requests.post(url, json=data)
        return response.json(), response.status_code
    
    def verify_solution(self, session_token: str, target_sequence: list, verifier_private_key: bytes):
        """Verify a solution against the server."""
        url = f"{self.server_url}/verify_solution"
        data = {
            'session_token': session_token,
            'target_sequence': target_sequence,
            'verifier_private_key': base64.b64encode(verifier_private_key).decode('utf-8')
        }
        
        response = requests.post(url, json=data)
        return response.json(), response.status_code
    
    def get_session_status(self, session_token: str):
        """Get the status of an authentication session."""
        url = f"{self.server_url}/session_status/{session_token}"
        
        response = requests.get(url)
        return response.json(), response.status_code
    
    def get_stats(self):
        """Get server statistics."""
        url = f"{self.server_url}/stats"
        
        response = requests.get(url)
        return response.json(), response.status_code
    
    def get_rate_limit_status(self, session_token: str):
        """Get the rate limit status for a specific session."""
        url = f"{self.server_url}/rate_limit_status/{session_token}"
        
        response = requests.get(url)
        return response.json(), response.status_code

def demo_complete_workflow():
    """Demonstrate the complete workflow with the server."""
    print("=" * 80)
    print("MYSTERY PROTOCOL SERVER DEMO")
    print("=" * 80)
    
    client = MysteryServerClient()
    
    # Step 1: Generate protocol data
    print("\n1. Generating protocol data...")
    protocol = MysteryProtocol()
    secret_string = "Demo123!"
    segments = 4  # Use 15 segments for demo (more than default 10 for enhanced obfuscation)
    
    # Generate keys
    verifier_keys, owner_keys = protocol.provision_keys()
    
    # Generate prize and mappings
    prize_data = protocol.generate_prize(owner_keys['public_context'])
    mappings_data = protocol.generate_mappings(len(secret_string), segments)
    
    # Create commitment
    commitment_package = protocol.verifier_commit(mappings_data['secret_mappings'])
    
    # Register data
    registered_data = protocol.owner_register_data(owner_keys['private_key'], secret_string)
    
    # Transform data
    reveal_package = protocol.verifier_transform_data(
        owner_keys['public_context'],
        verifier_keys['public_context'],
        registered_data,
        commitment_package
    )

    # Finalize data
    challenge_package = protocol.owner_finalize_data(
        owner_keys['private_key'],
        verifier_keys['public_context'],
        reveal_package,
        commitment_package['commitment'],
        prize_data
    )

    #print(f"Prize data: {prize_data['original_prize_for_reference']}")
    
    print(f"✅ Protocol data generated for secret: '{secret_string}'")
    
    # Step 2: Submit challenge data to server
    print("\n2. Submitting challenge data to server...")
    
    # Generate user credentials
    user_id = str(uuid.uuid4())
    key_name = "demo_key"
    key_index = 1
    
    # Calculate original size for compression stats
    original_size = len(json.dumps(challenge_package, sort_keys=True).encode('utf-8'))
    
    response, status_code = client.submit_challenge_data(
        challenge_package, 
        mappings_data['secret_mappings'],
        user_id,
        key_name,
        key_index,
        segments
    )
    
    if status_code == 201:
        print(f"✅ Challenge data submitted successfully")
        
        # Show compression statistics
        compressed_size = len(client._last_compressed_data)
        compression_ratio = (1 - compressed_size / original_size) * 100
        print(f"   Compression: {original_size} bytes → {compressed_size} bytes ({compression_ratio:.1f}% reduction)")
    else:
        print(f"❌ Failed to submit challenge data: {response}")
        return
    
    # Step 3: Get authentication challenge
    print("\n3. Getting authentication challenge...")
    challenge_response, status_code = client.get_authentication_challenge(user_id, key_name, timeout_minutes=10)
    
    if status_code == 200:
        session_token = challenge_response['session_token']
        print(f"✅ Authentication challenge received")
        print(f"   Session Token: {session_token}")
        print(f"   Expires At: {challenge_response['expires_at']}")
    else:
        print(f"❌ Failed to get authentication challenge: {challenge_response}")
        return
    
    # Step 4: Solve the challenge
    print("\n4. Solving the authentication challenge...")
    # Use only the actual secret string length from the stored extended mapping
    original_mapping = challenge_response['mapping'][:len(secret_string)]
    correct_sequence = protocol.get_correct_sequence(
        original_mapping,
        secret_string
    )
    
    print(f"   Correct sequence: {correct_sequence}")
    
    # Step 5: Verify solution
    print("\n5. Verifying solution...")
    verify_response, status_code = client.verify_solution(
        session_token,
        correct_sequence,
        verifier_keys['private_key']
    )
    
    if status_code == 200:
        result = verify_response['verification_result']
        print(f"✅ Verification completed")
        print(f"   Match: {result['is_match']}")
        print(f"   Prize Value: {result['prize_value']}")
        print(f"   Message: {verify_response['message']}")
    else:
        print(f"❌ Verification failed: {verify_response}")
        return
    
    # Step 6: Check session status
    print("\n6. Checking session status...")
    status_response, status_code = client.get_session_status(session_token)
    
    if status_code == 200:
        session = status_response['session']
        print(f"✅ Session status retrieved")
        print(f"   Is Verified: {session['is_verified']}")
        print(f"   Attempts: {session['verification_attempts']}/{session['max_attempts']}")
    else:
        print(f"❌ Failed to get session status: {status_response}")
    
    # Step 6.5: Check rate limit status
    print("\n6.5. Checking rate limit status...")
    rate_limit_response, status_code = client.get_rate_limit_status(session_token)
    
    if status_code == 200:
        rate_limit = rate_limit_response['rate_limit_status']
        print(f"✅ Rate limit status retrieved")
        print(f"   Is Rate Limited: {rate_limit['is_rate_limited']}")
        print(f"   Failed Attempts Used: {rate_limit['failed_attempts_used']}/{rate_limit['max_failed_attempts_per_hour']}")
        print(f"   Remaining Failed Attempts: {rate_limit['remaining_failed_attempts']}")
        print(f"   Note: {rate_limit['note']}")
        if rate_limit['reset_time']:
            print(f"   Reset Time: {rate_limit['reset_time']}")
    else:
        print(f"❌ Failed to get rate limit status: {rate_limit_response}")
    
    # Step 7: Get server statistics
    print("\n7. Getting server statistics...")
    stats_response, status_code = client.get_stats()
    
    if status_code == 200:
        stats = stats_response['stats']
        print(f"✅ Server statistics:")
        print(f"   Total Files: {stats['total_challenge_data_files']}")
        print(f"   Used Files: {stats['used_challenge_data_files']}")
        print(f"   Available Files: {stats['available_challenge_data_files']}")
        print(f"   Active Sessions: {stats['active_authentication_sessions']}")
        print(f"   Total Attempts: {stats['total_verification_attempts']}")
        print(f"   Success Rate: {stats['success_rate']:.2f}%")
        if 'rate_limiting' in stats:
            rate_limiting = stats['rate_limiting']
            print(f"   Rate Limiting:")
            print(f"     Max Failed Per Hour Per User: {rate_limiting['max_failed_attempts_per_hour_per_user']}")
            print(f"     Recent Total Attempts (1h): {rate_limiting['recent_total_attempts_last_hour']}")
            print(f"     Recent Failed Attempts (1h): {rate_limiting['recent_failed_attempts_last_hour']}")
            print(f"     Note: {rate_limiting['note']}")
    else:
        print(f"❌ Failed to get server statistics: {stats_response}")
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 80)

def demo_wrong_sequence():
    """Demonstrate verification with wrong sequence."""
    print("\n" + "=" * 80)
    print("DEMONSTRATING WRONG SEQUENCE VERIFICATION")
    print("=" * 80)
    
    client = MysteryServerClient()
    
    # Step 1: First create and upload a new challenge data file
    print("\n1. Creating and uploading new challenge data for wrong sequence test...")
    protocol = MysteryProtocol()
    secret_string = "WrongTest"  # Different secret for this test
    segments = 4
    
    # Generate keys
    verifier_keys, owner_keys = protocol.provision_keys()
    
    # Generate prize and mappings
    prize_data = protocol.generate_prize(owner_keys['public_context'])
    mappings_data = protocol.generate_mappings(len(secret_string), segments)
    
    # Create commitment
    commitment_package = protocol.verifier_commit(mappings_data['secret_mappings'])
    
    # Register data
    registered_data = protocol.owner_register_data(owner_keys['private_key'], secret_string)
    
    # Transform data
    reveal_package = protocol.verifier_transform_data(
        owner_keys['public_context'],
        verifier_keys['public_context'],
        registered_data,
        commitment_package
    )
    
    # Finalize data
    challenge_package = protocol.owner_finalize_data(
        owner_keys['private_key'],
        verifier_keys['public_context'],
        reveal_package,
        commitment_package['commitment'],
        prize_data
    )
    
    # Generate user credentials for wrong sequence test
    user_id = str(uuid.uuid4())
    key_name = "wrong_test_key"
    key_index = 999
    
    # Submit challenge data to server
    response, status_code = client.submit_challenge_data(
        challenge_package, 
        mappings_data['secret_mappings'],
        user_id,
        key_name,
        key_index,
        segments
    )
    
    if status_code == 201:
        print(f"✅ Challenge data uploaded successfully for wrong sequence test")
    else:
        print(f"❌ Failed to upload challenge data: {response}")
        return
    
    # Step 2: Get authentication challenge
    print("\n2. Getting authentication challenge...")
    challenge_response, status_code = client.get_authentication_challenge(user_id, key_name, timeout_minutes=5)
    
    if status_code != 200:
        print(f"❌ No authentication challenge available: {challenge_response}")
        return
    
    session_token = challenge_response['session_token']
    print(f"✅ Got authentication challenge: {session_token}")
    
    # Step 3: Use wrong sequence (values within valid segment range 1-segments)
    print("\n3. Testing with wrong sequence...")
    # Generate random wrong sequence with valid segment numbers (1 to segments) but incorrect for the secret
    import random
    wrong_sequence = [random.randint(1, segments) for _ in range(len(secret_string))]
    print(f"   Using wrong sequence: {wrong_sequence}")
    
    # Step 4: Try to verify with wrong sequence
    verify_response, status_code = client.verify_solution(
        session_token,
        wrong_sequence,
        verifier_keys['private_key']
    )
    
    if status_code == 200:
        result = verify_response['verification_result']
        print(f"✅ Verification completed (expected to fail)")
        print(f"   Match: {result['is_match']}")
        print(f"   Prize Value: {result['prize_value']}")
        print(f"   Message: {verify_response['message']}")
    else:
        print(f"❌ Verification request failed: {verify_response}")
    
    print("\n" + "=" * 80)
    print("WRONG SEQUENCE DEMO COMPLETED!")
    print("=" * 80)

if __name__ == "__main__":
    try:
        demo_complete_workflow()
        demo_wrong_sequence()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the server is running at http://localhost:1776")
    except Exception as e:
        print(f"❌ Demo failed with error: {e}") 
        print(traceback.format_exc())
