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
    "file_id": "550e8400-e29b-41d4-a716-446655440001",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "key_name": "my_key",
    "key_index": 1,
    "segments": 10,
    "file_hash": "abc123...",
    "mapping_sequence_hash": "def456...",
    "message": "Challenge data file submitted successfully"
}
```

### 2. Get Authentication Challenge
**POST** `/get_authentication_challenge`

Get an unused challenge data instance and mapping for client authentication. Returns only the file hash (not the full challenge package data) and the stored mapping (already extended to a configurable length, default 64 characters, with random mappings).

**Request Body:**
```json
{
    "timeout_minutes": 30
}
```

**Response:**
```json
{
    "success": true,
    "session_token": "secure-token-123",
    "file_hash": "abc123...",
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
- Uses UUID primary key
- Tracks user_id, key_name, and key_index for user association

### AuthenticationSession
- Manages time-limited authentication sessions
- Tracks verification attempts and session validity
- Links to challenge data files
- Uses UUID primary key
- Tracks user_id for rate limiting

### VerificationAttempt
- Records all verification attempts
- Tracks success/failure and prize values
- Does not store attempted sequences for security reasons
- Uses UUID primary key
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