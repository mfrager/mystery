# Mystery Protocol Server

A Flask-based server implementing the MysteryProtocol with SQLAlchemy database storage for secure verification and authentication.

## Features

- **SQLAlchemy Database Integration**: Uses SQLite for persistent storage
- **MysteryProtocol Implementation**: Full implementation of the cryptographic protocol
- **Authentication Sessions**: Time-limited sessions with attempt tracking
- **Unique Verification**: Ensures each mapping sequence can only be verified once
- **Statistics Tracking**: Comprehensive server statistics and monitoring
- **Data Compression**: Challenge packages must be compressed using bz2 and uploaded as binary files for reduced transfer and storage size

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python mystery_server.py
```

The server will start on `http://localhost:1776` and create a SQLite database file `mystery_server.db`.

## API Endpoints

### 1. Submit Challenge Data
**POST** `/submit_challenge_data`

Submit challenge data files with unencrypted mappings to the server. The challenge package must be compressed using bz2 compression and uploaded as a binary file using multipart form data.

**Request Body (multipart/form-data):**
- `challenge_package_compressed` (file): Binary bz2-compressed challenge package
- `unencrypted_mapping` (form field): JSON string of the mapping array
- `user_id` (form field): UUID string identifying the user
- `key_name` (form field): String identifier for the key (max 64 characters)
- `key_index` (form field): Integer index for the key (as string)
- `segments` (form field, optional): Number of segments for mapping obfuscation (default: 10)

**Notes:**
- The `challenge_package_compressed` file must contain the challenge package compressed with bz2 as raw bytes
- Only compressed challenge packages are accepted
- Challenge packages are stored as compressed binary data in the database
- Mappings are extended to 64 characters with random data during submission for obfuscation
- The `segments` parameter controls how many segments are used for mapping obfuscation (default: 10, minimum: 1)
- Uses multipart/form-data for efficient binary file upload
- Compression typically reduces transfer and storage size by 60-80% depending on the data

**Response:**
```json
{
    "success": true,
    "message": "Challenge data file submitted successfully"
}
```

### 2. Get Authentication Challenge
**POST** `/get_authentication_challenge`

Get an unused challenge data instance and mapping for client authentication. Returns only the file hash (not the full challenge package data) and the stored mapping (already extended to a configurable length, default 64 characters, with random mappings).

**Request Body:**
```json
{
    "user_id": "user-123",
    "key_name": "keyname-A",
    "timeout_minutes": 30
}
```

**Response:**
```json
{
    "success": true,
    "session_token": "secure-token-123",
    "mapping": [...],
    "expires_at": "2024-01-01T12:00:00",
    "timeout_minutes": 30
}
```

### 3. Verify Solution
**POST** `/verify_solution`

Verify a solution using the MysteryProtocol.

**Request Body:**
```json
{
    "session_token": "secure-token-123",
    "target_sequence": [1, 2, 3, 4, 5],
    "verifier_private_key": "base64-encoded-key"
}
```

**Response:**
```json
{
    "success": true,
    "verification_result": {
        "is_match": true,
        "prize_value": "123456789"
    },
    "message": "Verification successful! Prize unlocked."
}
```

### 4. Get Session Status
**GET** `/session_status/<session_token>`

Get the status of an authentication session.

**Response:**
```json
{
    "success": true,
    "session": {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "session_token": "secure-token-123",
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "is_verified": true,
        "verification_attempts": 1,
        "max_attempts": 3,
        "expires_at": "2024-01-01T12:00:00"
    },
    "is_valid": false
}
```

### 5. Get Server Statistics
**GET** `/stats`

Get comprehensive server statistics.

**Response:**
```json
{
    "success": true,
    "stats": {
        "total_challenge_data_files": 5,
        "used_challenge_data_files": 2,
        "available_challenge_data_files": 3,
        "active_authentication_sessions": 1,
        "total_verification_attempts": 10,
        "successful_verification_attempts": 8,
        "success_rate": 80.0,
        "rate_limiting": {
            "max_failed_attempts_per_hour_per_user": 50,
            "recent_total_attempts_last_hour": 15,
            "recent_failed_attempts_last_hour": 3,
            "note": "Only failed attempts count towards rate limiting per user"
        }
    }
}
```

### 6. Get Rate Limit Status
**GET** `/rate_limit_status/<session_token>`

Get the rate limit status for a specific user session. Only failed verification attempts count towards rate limiting per user.

**Response:**
```json
{
    "success": true,
    "rate_limit_status": {
        "is_rate_limited": false,
        "failed_attempts_used": 5,
        "max_failed_attempts_per_hour": 50,
        "remaining_failed_attempts": 45,
        "reset_time": "2024-01-01T13:00:00",
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "note": "Only failed attempts count towards rate limiting per user"
    }
}
```

## Database Schema

The server uses SQLAlchemy with the following models:

### ChallengeDataFile
- Stores challenge data packages (compressed binary data) with their unencrypted mappings (extended to 64 characters)
- Tracks usage status and creation timestamps
- Creates unique hashes for deduplication based on compressed binary data
- Tracks user_id, key_name, and key_index for user association

### AuthenticationSession
- Manages time-limited authentication sessions
- Tracks verification attempts and session validity
- Links to challenge data files
- Tracks user_id for rate limiting

### VerificationAttempt
- Records all verification attempts
- Tracks success/failure
- Does not store attempted sequences for security reasons
- Tracks user_id for rate limiting

## Security Features

1. **Unique Verification**: Each mapping sequence can only be successfully verified once
2. **Session Timeouts**: Authentication sessions expire after a configurable time
3. **Attempt Limits**: Maximum number of verification attempts per session
4. **Hash-based Deduplication**: Prevents duplicate challenge data submissions
5. **Cryptographic Verification**: Uses the full MysteryProtocol for secure verification
6. **Privacy Protection**: Only file hashes are returned to clients, not full challenge data
7. **Mapping Obfuscation**: Mappings are extended to a configurable length (default 64) with random data during submission using configurable segments (default 10) to hide actual length
8. **Rate Limiting**: Global hourly limit on failed verification attempts per user (default: 50 failed attempts/hour) to prevent brute force attacks while not penalizing successful verifications
9. **Data Compression**: Mandatory bz2 compression with binary upload reduces transfer and storage size while maintaining security

## Usage Example

See `client_example.py` for a complete demonstration of the server workflow:

```bash
python client_example.py
```

This will:
1. Generate protocol data
2. Submit challenge data to the server (with mandatory bz2 compression as binary upload)
3. Get an authentication challenge
4. Solve the challenge
5. Verify the solution
6. Check session status
7. Check rate limit status
8. Get server statistics

## Error Handling

The server provides comprehensive error handling with appropriate HTTP status codes:

- `400` - Bad Request (missing required fields)
- `404` - Not Found (invalid session or no available data)
- `409` - Conflict (duplicate submission or already verified)
- `410` - Gone (session expired)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

## Logging

The server includes comprehensive logging for:
- Authentication session creation
- Verification attempts
- Database operations
- Error conditions

## Dependencies

- Flask: Web framework
- Flask-SQLAlchemy: Database ORM
- TenSEAL: Homomorphic encryption
- Reed-Solomon: Error correction
- Cryptography: Additional crypto functions
- bz2: Data compression (built-in Python library, required)

## Development

The server runs in debug mode by default. For production deployment:

1. Set `debug=False` in the app.run() call
2. Use a production WSGI server (e.g., Gunicorn)
3. Configure proper database settings
4. Set up proper logging configuration

---

## Mystery Protocol Technical Analysis

### Protocol Overview

The Mystery Protocol is a sophisticated cryptographic protocol that enables secure password/string verification between two parties (Owner and Verifier) without revealing sensitive information. The protocol uses homomorphic encryption, commitment schemes, and Reed-Solomon error correction to provide:

1. **Secure Verification**: Verify if an owner knows a secret string without revealing the string
2. **Prize Mechanism**: A cryptographic prize that can only be unlocked with the correct sequence
3. **Privacy Protection**: All operations are performed on encrypted data
4. **Commitment Security**: Uses cryptographic commitments to prevent cheating
5. **Error Correction**: Reed-Solomon encoding ensures prize integrity

### Key Components

#### 1. **MappingGenerator Class**
- Generates secret character-to-number mappings
- Uses configurable segmentation (default: 10 segments)
- Creates position-dependent mappings for each character in the alphabet
- Alphabet includes: letters, digits, punctuation, and space (95 characters total)

#### 2. **MysteryProtocol Class**
- Main protocol implementation using TenSEAL homomorphic encryption
- BFV encryption scheme with configurable parameters
- Default: 8192 polynomial modulus degree, 65537 plain modulus
- Supports full alphabet of 95 printable ASCII characters

### Detailed Protocol Flow

#### **Phase 1: Setup and Key Generation**

**Step 1: Key Provisioning (`provision_keys()`)**
- Creates BFV homomorphic encryption contexts for both parties
- Generates Galois keys for homomorphic operations
- Produces public/private key pairs for Owner and Verifier
- Keys are serialized for storage and transmission

**Step 2: Prize Generation (`generate_prize()`)**
- Generates a 256-bit cryptographic prize (random number)
- Applies Reed-Solomon error correction (32 data bytes + 16 parity bytes)
- Encrypts each byte individually using Owner's public key
- Stores encrypted prize chunks with metadata

**Step 3: Mapping Generation (`generate_mappings()`)**
- Creates position-dependent character-to-number mappings
- Each position has its own randomized mapping dictionary
- Characters are partitioned into configurable segments (default: 10)
- Each segment gets a random number assignment

#### **Phase 2: Commitment Phase**

**Step 4: Verifier Commitment (`verifier_commit()`)**
- Verifier creates a cryptographic commitment to the secret mappings
- Uses SHA-256 hash of (salt + mappings) as commitment
- Generates additional salt for password-dependent hashing
- Commitment prevents the verifier from changing mappings after seeing Owner's data

#### **Phase 3: Data Registration and Transformation**

**Step 5: Owner Data Registration (`owner_register_data()`)**
- Owner encrypts their secret string character by character
- Each character is encoded as a one-hot vector (95 dimensions)
- Vectors are encrypted using Owner's private key
- Results in homomorphically encrypted character representations

**Step 6: Verifier Data Transformation (`verifier_transform_data()`)**
- Verifier applies secret mappings to Owner's encrypted data
- Uses homomorphic dot product: encrypted_char_vector · mapping_vector
- Transforms encrypted characters into encrypted mapped numbers
- Creates reveal package with transformed data and commitment details

#### **Phase 4: Finalization and Verification**

**Step 7: Owner Finalization (`owner_finalize_data()`)**
- **Commitment Verification**: Owner verifies Verifier's commitment to prevent cheating
- **Password Sequence Generation**: Decrypts transformed vectors to get the password sequence
- **Password-Dependent Hashing**: Creates a hash from the password sequence
- **Prize Protection**: XORs prize chunks with password hash bytes for protection
- **Re-encryption**: Encrypts protected prize chunks with Verifier's public key
- **Final Package Creation**: Produces sequence data encrypted for Verifier

**Step 8: Final Verification (`verifier_verify()`)**
- **Sequence Verification**: Uses sum of squares to check if target sequence matches
  - Computes: Σ(encrypted_sequence[i] - target_sequence[i])²
  - Applies cryptographic blinding for security
  - Sequence matches if and only if sum equals zero
- **Prize Unlocking**: If verification succeeds:
  - Computes same password-dependent hash from target sequence
  - Decrypts password-protected prize chunks
  - Removes password protection using XOR with hash bytes
  - Reconstructs original prize using Reed-Solomon decoding
  - Returns the unlocked prize value

### Security Features

#### **Cryptographic Security**
1. **Homomorphic Encryption**: All computations on encrypted data using TenSEAL/BFV
2. **Commitment Scheme**: SHA-256 commitments prevent verifier cheating
3. **Blinding**: Random blinding factor protects verification computation
4. **Password Protection**: Prize is protected by password-dependent hash

#### **Privacy Protection**
1. **No Information Leakage**: Owner's secret string never revealed
2. **Mapping Secrecy**: Verifier's mappings remain secret until commitment reveal
3. **Encrypted Storage**: All sensitive data stored in encrypted form
4. **One-Time Use**: Each mapping sequence can only be verified once

#### **Error Correction and Integrity**
1. **Reed-Solomon Coding**: 16 parity bytes allow correction of up to 8 byte errors
2. **Hash Verification**: Multiple hash checks ensure data integrity
3. **Cryptographic Hashing**: SHA-256 used throughout for integrity checks

#### **Anti-Cheating Measures**
1. **Commitment Binding**: Verifier cannot change mappings after commitment
2. **Zero-Knowledge Verification**: Verification reveals only success/failure
3. **Unique Verification**: Each challenge can only be solved once
4. **Tamper Detection**: Hash mismatches detect any data tampering

### Protocol Properties

#### **Security Properties**
- **Completeness**: If Owner knows the correct string, verification succeeds
- **Soundness**: If Owner doesn't know the correct string, verification fails
- **Zero-Knowledge**: Verifier learns nothing about Owner's string except match/no-match
- **Commitment Binding**: Verifier cannot change mappings after commitment

#### **Performance Characteristics**
- **Homomorphic Operations**: O(n) where n is string length
- **Memory Usage**: Linear in string length and alphabet size
- **Communication Complexity**: O(n × alphabet_size) for encrypted vectors
- **Computational Complexity**: Dominated by homomorphic encryption operations

### Summary

The Mystery Protocol represents a sophisticated implementation of secure multi-party computation for password/string verification. It combines multiple cryptographic primitives:

- **Homomorphic Encryption** for privacy-preserving computation
- **Commitment Schemes** for preventing cheating
- **Reed-Solomon Codes** for error correction
- **Cryptographic Hashing** for integrity and password protection

The protocol ensures that:
1. The Owner's secret string remains completely private
2. The Verifier's mappings remain secret until the commitment reveal
3. Verification can only succeed with the correct string
4. The cryptographic prize can only be unlocked with successful verification
5. All operations are performed without revealing sensitive information

This makes it suitable for applications requiring secure authentication, zero-knowledge proofs, or cryptographic challenges where privacy and security are paramount. 

---

## The "Interactive Transformation" Protocol

This protocol requires a two-step interaction after the initial data is sent. It perfectly satisfies all your constraints:
1. Two Key Pairs: The Data Owner (O) and Verifier (V) each have their own (pk_O, sk_O) and (pk_V, sk_V).
2. sk_O is Never Sent: The Data Owner's private key is only ever used locally by the owner.
3. Mappings are Secret to Verifier: The Data Owner has no knowledge of the mapping rules.
4. sk_V Cannot Decrypt s: The Verifier never receives a decryptable version of the original secret string s.

Here is the flow:
1. Data Owner -> Verifier (Round 1):
    * The Data Owner encrypts the secret string s using its own public key pk_O.
    * It sends C_s = Encrypt(s, pk_O) to the Verifier.
2. Verifier -> Data Owner (Round 2):
    * The Verifier receives C_s. It cannot decrypt this.
    * The Verifier applies its secret mapping rules m homomorphically: C_sm = C_s * m.
    * The result, C_sm = Encrypt(s*m, pk_O), is still encrypted under the owner's key. The Verifier learns nothing about s.
    * The Verifier sends the transformed ciphertext C_sm back to the Data Owner.
3. Data Owner -> Verifier (Round 3):
    * The Data Owner receives C_sm.
    * It uses its own private key sk_O to decrypt it, revealing the plaintext numerical result: result = Decrypt(C_sm, sk_O) = s*m.
    * The Data Owner now has the final number but does not know the mapping rule m that produced it.
    * The Data Owner then encrypts this final number using the Verifier's public key pk_V.
    * It sends C_final = Encrypt(result, pk_V) to the Verifier.
4. Verifier (Final Check):
    * The Verifier receives C_final, which is encrypted under its own key.
    * It can now use this ciphertext in the final sum-of-squared-differences calculation and decrypt the result with its private key sk_V.

The verifier's private key can never be used to decrypt or otherwise discover the data owner's private key. Here is a detailed breakdown of why.

### 1. Mathematically Independent Key Pairs

The most critical security feature of the protocol is established in the provision_keys function.

```python
# Verifier Keys
v_priv_ctx = ts.context(ts.SCHEME_TYPE.BFV, poly_mod_degree, plain_modulus)
# ...
# Owner Keys
o_priv_ctx = ts.context(ts.SCHEME_TYPE.BFV, poly_mod_degree, plain_modulus)
```

This code calls ts.context() twice. Each call independently generates a completely separate and mathematically unrelated key pair (a public key and a secret/private key).
* Owner's Keys: Reside in owner_private.key (private) and owner_public.context (public).
* Verifier's Keys: Reside in verifier_private.key (private) and verifier_public.context (public).

Think of these as two different high-security locks from two different manufacturers. The key for the Verifier's lock (verifier_private.key) has no mathematical relationship to the key for the Owner's lock (owner_private.key). Possessing one tells you nothing about the other.

### 2. Strict Segregation of Keys in the Protocol

The code is carefully designed to ensure that no party ever has access to the other party's private key. Let's trace the key usage:

1. **Owner (owner_register_data, owner_finalize_data):**
    * Loads its own private key (owner_key) to encrypt initial data and later to decrypt the intermediate result.
    * Loads the Verifier's public context (verifier_public_context) to re-encrypt the final result for the Verifier.
    * The Owner never sees or uses the Verifier's private key.

2. **Verifier (verifier_transform_data, verifier_verify):**
    * Loads the Owner's public context (owner_public_context) to perform homomorphic operations on the data encrypted by the Owner. These operations (like dot product) do not require the private key.
    * Loads its own private key (verifier_private_key) to decrypt the final package that the Owner specifically encrypted for it.
    * The Verifier never sees or uses the Owner's private key.

### 3. Data vs. Keys

The data being exchanged between the Owner and Verifier is ciphertext (encrypted data), not the keys themselves.
* In owner_finalize_data, the owner's private key is used to perform a decryption: plaintext_result = enc_sm.decrypt()[0].
* Crucially, the result of this decryption (plaintext_result) is immediately re-encrypted with the Verifier's public key.
* The owner's private key itself is never serialized, written to a file (other than its own secure key file), or included in any data package sent to the Verifier.

### 4. Underlying Cryptographic Security

The entire system relies on the security of the BFV (Brakerski-Fan-Vercauteren) scheme, which is based on the Ring Learning with Errors (RLWE) problem. This problem is widely believed to be computationally "hard," meaning that even with massive computing power, it is infeasible to:
* Derive a private key from a public key.
* Decrypt a ciphertext without its corresponding private key.

Since the Verifier never possesses the Owner's private key, it cannot decrypt any data encrypted with the Owner's public key (like the registered_data.json or transformed_data.json). Attempting to use its own verifier_private.key on this data would produce meaningless garbage. Consequently, it has no cryptographic means to attack or discover the Owner's private key.

### Summary Table

This table illustrates the strict separation of roles and assets:

| Party | Has Access To | Does NOT Have Access To |
| :--- | :--- | :--- |
| Data Owner | • Its own private key<br>• The Verifier's public key | • The Verifier's private key |
| Verifier | • Its own private key<br>• The Owner's public key | • The Data Owner's private key |

### Protocol Data Flow Security

| Phase | Data File | Encrypted With | Can Decrypt? |
| :--- | :--- | :--- | :--- |
| 1. Owner Registers | registered_data.json | Owner's Public Key | Only the Owner |
| 2. Verifier Transforms | transformed_data.json| Owner's Public Key | Only the Owner |
| 3. Owner Finalizes | final_package.json | Verifier's Public Key | Only the Verifier |
| 4. Verifier Verifies | (Final plaintext result) | N/A (decrypted in memory) | Verifier |

As you can see from the table, at no point does the Verifier have access to data that its key can decrypt until after the Owner has explicitly decrypted the intermediate result and re-encrypted it for the Verifier. The Owner's private key is only ever used by the Owner on their own machine, and the Verifier's private key is only ever used by the Verifier. The system is secure precisely because these two keys are independent and are never shared.

### Conclusion

The security of this protocol is fundamentally sound in its design. The use of two independent key pairs and the strict adherence to the principles of asymmetric cryptography ensure that the Verifier's private key is only useful for decrypting data specifically encrypted for it. It provides no leverage whatsoever to decrypt, reverse-engineer, or discover the Data Owner's private key.
