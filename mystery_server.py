#!/usr/bin/env python3

import traceback
import hashlib
import base64
import json
import secrets
import logging
import uuid
import bz2
from typing import Dict, List, Any, Tuple, Optional
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, UTC

# Import the MysteryProtocol
from mystery_protocol import MysteryProtocol

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mystery_server.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize the MysteryProtocol
protocol = MysteryProtocol()

# Rate limiting configuration
VERIFICATION_ATTEMPTS_PER_HOUR_PER_CHALLENGE = 20  # Max failed attempts per user per hour

# Database Models
class ChallengeDataFile(db.Model):
    __tablename__ = 'challenge_data_files'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), nullable=False)
    key_name = db.Column(db.String(64), nullable=False)
    key_index = db.Column(db.Integer, nullable=False)
    file_hash = db.Column(db.String(64), unique=True, nullable=False)
    challenge_package = db.Column(db.LargeBinary, nullable=False)  # Compressed raw bytes
    unencrypted_mapping = db.Column(db.Text, nullable=False)  # JSON string (extended to 64 chars)
    mapping_sequence_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    is_used = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'key_name': self.key_name,
            'key_index': self.key_index,
            'file_hash': self.file_hash,
            'challenge_package': decompress_challenge_package(bytes(self.challenge_package)),
            'unencrypted_mapping': json.loads(self.unencrypted_mapping),
            'mapping_sequence_hash': self.mapping_sequence_hash,
            'created_at': ensure_timezone_aware(self.created_at).isoformat(),
            'is_used': self.is_used
        }

class AuthenticationSession(db.Model):
    __tablename__ = 'authentication_sessions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_token = db.Column(db.String(64), unique=True, nullable=False)
    data_file_id = db.Column(db.String(36), db.ForeignKey('challenge_data_files.id'), nullable=False)
    user_id = db.Column(db.String(36), nullable=False)
    mapping_sequence_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_attempts = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)
    
    # Relationship
    data_file = db.relationship('ChallengeDataFile', backref='sessions')
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_token': self.session_token,
            'data_file_id': self.data_file_id,
            'user_id': self.user_id,
            'mapping_sequence_hash': self.mapping_sequence_hash,
            'created_at': ensure_timezone_aware(self.created_at).isoformat(),
            'expires_at': ensure_timezone_aware(self.expires_at).isoformat(),
            'is_verified': self.is_verified,
            'verification_attempts': self.verification_attempts,
            'max_attempts': self.max_attempts
        }

class VerificationAttempt(db.Model):
    __tablename__ = 'verification_attempts'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey('authentication_sessions.id'), nullable=False)
    user_id = db.Column(db.String(36), nullable=False)
    was_successful = db.Column(db.Boolean, nullable=False)
    attempted_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    
    # Relationship
    session = db.relationship('AuthenticationSession', backref='attempts')
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'was_successful': self.was_successful,
            'attempted_at': ensure_timezone_aware(self.attempted_at).isoformat()
        }

# Utility Functions
def decompress_challenge_package(compressed_bytes: bytes) -> Dict[str, Any]:
    """Decompress bz2 compressed challenge package from raw bytes."""
    decompressed = bz2.decompress(compressed_bytes)
    return json.loads(decompressed.decode('utf-8'))

def create_mapping_sequence_hash(mapping: List[Dict[str, int]]) -> str:
    """Create a hash of the mapping sequence for uniqueness checking."""
    mapping_str = json.dumps(mapping, sort_keys=True)
    return hashlib.sha256(mapping_str.encode()).hexdigest()

def create_file_hash(compressed_challenge_package: bytes) -> str:
    """Create a hash of the compressed challenge package for uniqueness checking."""
    return hashlib.sha256(compressed_challenge_package).hexdigest()

def ensure_timezone_aware(dt: datetime) -> datetime:
    """
    Convert timezone-naive datetime to timezone-aware (assuming UTC).
    If already timezone-aware, return as-is.
    """
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        return dt.replace(tzinfo=UTC)
    return dt

def is_session_valid(session: AuthenticationSession) -> bool:
    """Check if a session is still valid (not expired and not exceeded max attempts)."""
    now = datetime.now(UTC)
    expires_at_aware = ensure_timezone_aware(session.expires_at)
    return (expires_at_aware > now and 
            session.verification_attempts < session.max_attempts and
            not session.is_verified)

def extend_mapping_to_length(original_mapping: List[Dict[str, int]], target_length: int = 64, segments: int = 10) -> List[Dict[str, int]]:
    """
    Extend mapping to target length with random mappings for unused positions.
    
    Args:
        original_mapping: List of character-to-number mappings
        target_length: Target length for the extended mapping (default: 64)
        segments: Number of segments to use for random mappings (default: 10)
        
    Returns:
        Extended mapping list with target_length character positions
    """
    import random
    import string
    
    # If original mapping is already at or beyond target length, return as-is
    if len(original_mapping) >= target_length:
        return original_mapping[:target_length]
    
    # Create alphabet for mappings
    alphabet = list(string.ascii_letters + string.digits + string.punctuation + " ")
    extended_mapping = original_mapping.copy()
    
    # Extend to target length
    for i in range(len(original_mapping), target_length):
        # Create random mapping for this position
        alphabet_shuffled = alphabet[:]
        random.shuffle(alphabet_shuffled)
        
        # Generate random segment numbers (1-segments)
        segment_numbers = list(range(1, segments + 1))
        random.shuffle(segment_numbers)
        
        # Partition alphabet into segments
        partition_size = len(alphabet_shuffled) // segments
        char_partitions = [alphabet_shuffled[j:j+partition_size] 
                          for j in range(0, len(alphabet_shuffled), partition_size)]
        
        # Create mapping dictionary
        mapping_dict = {}
        for seg_num, char_group in zip(segment_numbers, char_partitions):
            for char in char_group:
                mapping_dict[char] = seg_num
        
        extended_mapping.append(mapping_dict)
    
    return extended_mapping

def count_recent_verification_attempts(user_id: str, hours: int = 1) -> int:
    """
    Count failed verification attempts for a specific user within the last N hours.
    Only failed attempts count towards rate limiting to prevent brute force attacks
    while not penalizing legitimate successful verifications.
    
    Args:
        user_id: UUID of the user to check
        hours: Number of hours to look back (default: 1)
        
    Returns:
        Number of failed verification attempts in the time window
    """
    cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
    
    # Convert cutoff_time to naive for comparison with database fields that might be naive
    cutoff_time_naive = cutoff_time.replace(tzinfo=None)
    
    count = db.session.query(VerificationAttempt).filter(
        VerificationAttempt.user_id == user_id,
        VerificationAttempt.attempted_at >= cutoff_time_naive,
        VerificationAttempt.was_successful == False  # Only count failed attempts
    ).count()
    
    return count

def is_rate_limited(user_id: str) -> bool:
    """
    Check if a user has exceeded the hourly rate limit for failed attempts.
    Only failed verification attempts count towards rate limiting.
    
    Args:
        user_id: UUID of the user to check
        
    Returns:
        True if rate limited, False otherwise
    """
    recent_failed_attempts = count_recent_verification_attempts(user_id, hours=1)
    return recent_failed_attempts >= VERIFICATION_ATTEMPTS_PER_HOUR_PER_CHALLENGE

# Routes
@app.route('/submit_challenge_data', methods=['POST'])
def submit_challenge_data():
    """
    Endpoint for client to post challenge data files along with unencrypted mappings.
    """
    try:
        # Get form data
        challenge_package_file = request.files.get('challenge_package_compressed')
        unencrypted_mapping = request.form.get('unencrypted_mapping')
        user_id = request.form.get('user_id')
        key_name = request.form.get('key_name')
        key_index = request.form.get('key_index')
        segments = request.form.get('segments')
        
        # Only accept compressed challenge package file
        if not challenge_package_file:
            return jsonify({'success': False, 'error': 'Missing challenge_package_compressed file'}), 400
        
        # Convert key_index to integer
        try:
            key_index = int(key_index) if key_index else None
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid key_index (must be integer)'}), 400
        
        # Convert segments to integer with default
        try:
            segments = int(segments) if segments else 10
            if segments < 1:
                return jsonify({'success': False, 'error': 'Invalid segments (must be positive integer)'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid segments (must be integer)'}), 400
        
        # Parse unencrypted_mapping JSON
        try:
            unencrypted_mapping = json.loads(unencrypted_mapping) if unencrypted_mapping else None
        except json.JSONDecodeError:
            return jsonify({'success': False, 'error': 'Invalid unencrypted_mapping JSON'}), 400
        
        if not all([challenge_package_file, unencrypted_mapping, user_id, key_name, key_index is not None]):
            return jsonify({'success': False, 'error': 'Missing required fields: challenge_package_compressed, unencrypted_mapping, user_id, key_name, key_index'}), 400
        
        # Validate UUID format
        try:
            uuid.UUID(user_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid user_id format (must be UUID)'}), 400
        
        # Read the compressed challenge package data
        challenge_package_compressed = challenge_package_file.read()
        
        # Validate that we can decompress the data
        try:
            decompress_challenge_package(challenge_package_compressed)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Invalid compressed challenge package: {str(e)}'}), 400
        
        # Create hashes
        file_hash = create_file_hash(challenge_package_compressed)
        mapping_sequence_hash = create_mapping_sequence_hash(unencrypted_mapping)
        
        # Check if this exact file already exists
        existing_file = ChallengeDataFile.query.filter_by(file_hash=file_hash).first()
        if existing_file:
            return jsonify({
                'success': False, 
                'error': 'This challenge data file has already been submitted',
                'existing_file_id': existing_file.id
            }), 409
        
        # Check if this mapping sequence already exists
        existing_mapping = ChallengeDataFile.query.filter_by(mapping_sequence_hash=mapping_sequence_hash).first()
        if existing_mapping:
            return jsonify({
                'success': False, 
                'error': 'This mapping sequence has already been submitted',
                'existing_file_id': existing_mapping.id
            }), 409
        
        # Extend the mapping to target length before storing
        extended_mapping = extend_mapping_to_length(unencrypted_mapping, 64, segments)
        
        # Create new challenge data file record
        challenge_data_file = ChallengeDataFile(
            user_id=user_id,
            key_name=key_name,
            key_index=key_index,
            file_hash=file_hash,
            challenge_package=challenge_package_compressed,
            unencrypted_mapping=json.dumps(extended_mapping),
            mapping_sequence_hash=mapping_sequence_hash
        )
        
        db.session.add(challenge_data_file)
        db.session.commit()
        
        logger.info(f"New challenge data file submitted with ID: {challenge_data_file.id} for user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Challenge data file submitted successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error submitting challenge data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_authentication_challenge', methods=['POST'])
def get_authentication_challenge():
    """
    Endpoint to offer unused challenge data instances and their mappings for client authentication.
    Creates a new authentication session with timeout for a specific user_id and key_name.
    """
    try:
        data = request.json
        timeout_minutes = data.get('timeout_minutes', 30)  # Default 30 minutes
        user_id = data.get('user_id')
        key_name = data.get('key_name')
        
        # Validate required parameters
        if not all([user_id, key_name]):
            return jsonify({
                'success': False, 
                'error': 'Missing required parameters: user_id and key_name'
            }), 400
        
        # Validate UUID format for user_id
        try:
            uuid.UUID(user_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid user_id format (must be UUID)'}), 400
        
        # Find the next unused challenge data file for this user_id and key_name, ordered by key_index
        unused_file = ChallengeDataFile.query.filter_by(
            user_id=user_id,
            key_name=key_name,
            is_used=False
        ).order_by(ChallengeDataFile.key_index.asc()).first()
        
        if not unused_file:
            return jsonify({
                'success': False, 
                'error': f'No unused challenge data files available for user_id: {user_id}, key_name: {key_name}'
            }), 404
        
        # Create authentication session
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(minutes=timeout_minutes)
        
        auth_session = AuthenticationSession(
            session_token=session_token,
            data_file_id=unused_file.id,
            user_id=unused_file.user_id,
            mapping_sequence_hash=unused_file.mapping_sequence_hash,
            expires_at=expires_at
        )
        
        db.session.add(auth_session)
        db.session.commit()
        
        # Get the stored mapping (already extended to 64 characters)
        stored_mapping = json.loads(unused_file.unencrypted_mapping)
        
        logger.info(f"Authentication challenge created with session token: {session_token} for user: {user_id}, key: {key_name}, index: {unused_file.key_index}")
        
        return jsonify({
            'success': True,
            'session_token': session_token,
            'mapping': stored_mapping,
            'expires_at': ensure_timezone_aware(expires_at).isoformat(),
            'timeout_minutes': timeout_minutes
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating authentication challenge: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/verify_solution', methods=['POST'])
def verify_solution():
    """
    Endpoint to verify a solution using the MysteryProtocol.
    Only allows one successful verification per unique mapping sequence.
    """
    try:
        data = request.json
        session_token = data.get('session_token')
        target_sequence = data.get('target_sequence')
        verifier_private_key_b64 = data.get('verifier_private_key')
        
        if not all([session_token, target_sequence, verifier_private_key_b64]):
            return jsonify({
                'success': False, 
                'error': 'Missing session_token, target_sequence, or verifier_private_key'
            }), 400
        
        # Find the authentication session
        auth_session = AuthenticationSession.query.filter_by(session_token=session_token).first()
        if not auth_session:
            return jsonify({'success': False, 'error': 'Invalid session token'}), 404
        
        # Check if session is still valid
        if not is_session_valid(auth_session):
            return jsonify({
                'success': False, 
                'error': 'Session expired or maximum attempts exceeded'
            }), 410
        
        # Check hourly rate limit for this user
        if is_rate_limited(auth_session.user_id):
            recent_failed_attempts = count_recent_verification_attempts(auth_session.user_id)
            return jsonify({
                'success': False, 
                'error': f'Rate limit exceeded: {recent_failed_attempts}/{VERIFICATION_ATTEMPTS_PER_HOUR_PER_CHALLENGE} failed attempts in the last hour for this user'
            }), 429
        
        # Check if this mapping sequence has already been successfully verified
        existing_success = VerificationAttempt.query.join(AuthenticationSession).filter(
            AuthenticationSession.mapping_sequence_hash == auth_session.mapping_sequence_hash,
            VerificationAttempt.was_successful == True
        ).first()
        
        if existing_success:
            return jsonify({
                'success': False, 
                'error': 'This mapping sequence has already been successfully verified'
            }), 409
        
        # Decode the verifier private key
        try:
            verifier_private_key = base64.b64decode(verifier_private_key_b64)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid verifier private key format'}), 400
        
        # Get the challenge package from the data file (decompress it)
        challenge_package = decompress_challenge_package(bytes(auth_session.data_file.challenge_package))
        
        # Perform verification using MysteryProtocol
        try:
            is_match, prize_value = protocol.verifier_verify(
                verifier_private_key, 
                challenge_package, 
                target_sequence
            )
        except Exception as e:
            logger.error(f"Error during protocol verification: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': f'Protocol verification failed: {str(e)}'}), 500
        
        # Record the verification attempt
        attempt = VerificationAttempt(
            session_id=auth_session.id,
            user_id=auth_session.user_id,
            was_successful=is_match,
        )
        
        db.session.add(attempt)
        
        # Update session
        auth_session.verification_attempts += 1
        if is_match:
            auth_session.is_verified = True
            auth_session.data_file.is_used = True
        
        db.session.commit()
        
        logger.info(f"Verification attempt recorded: session={session_token}, success={is_match}")
        
        response_data = {
            'success': True,
            'verification_result': {
                'is_match': is_match,
                'prize_value': str(prize_value) if prize_value else None
            }
        }
        
        if is_match:
            response_data['message'] = 'Verification successful! Prize unlocked.'
        else:
            response_data['message'] = 'Verification failed. Incorrect sequence.'
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error during solution verification: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/session_status/<session_token>', methods=['GET'])
def get_session_status(session_token):
    """Get the status of an authentication session."""
    try:
        auth_session = AuthenticationSession.query.filter_by(session_token=session_token).first()
        if not auth_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        return jsonify({
            'success': True,
            'session': auth_session.to_dict(),
            'is_valid': is_session_valid(auth_session)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting session status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get server statistics."""
    try:
        total_files = ChallengeDataFile.query.count()
        used_files = ChallengeDataFile.query.filter_by(is_used=True).count()
        # Convert to naive datetime for comparison with database fields that might be naive
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        active_sessions = AuthenticationSession.query.filter(
            AuthenticationSession.expires_at > now_naive,
            AuthenticationSession.is_verified == False
        ).count()
        total_attempts = VerificationAttempt.query.count()
        successful_attempts = VerificationAttempt.query.filter_by(was_successful=True).count()
        
        # Calculate rate limiting stats
        cutoff_time = datetime.now(UTC) - timedelta(hours=1)
        cutoff_time_naive = cutoff_time.replace(tzinfo=None)
        recent_attempts_all = db.session.query(VerificationAttempt).filter(
            VerificationAttempt.attempted_at >= cutoff_time_naive
        ).count()
        recent_failed_attempts = db.session.query(VerificationAttempt).filter(
            VerificationAttempt.attempted_at >= cutoff_time_naive,
            VerificationAttempt.was_successful == False
        ).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_challenge_data_files': total_files,
                'used_challenge_data_files': used_files,
                'available_challenge_data_files': total_files - used_files,
                'active_authentication_sessions': active_sessions,
                'total_verification_attempts': total_attempts,
                'successful_verification_attempts': successful_attempts,
                'success_rate': (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0,
                'rate_limiting': {
                    'max_failed_attempts_per_hour_per_user': VERIFICATION_ATTEMPTS_PER_HOUR_PER_CHALLENGE,
                    'recent_total_attempts_last_hour': recent_attempts_all,
                    'recent_failed_attempts_last_hour': recent_failed_attempts,
                    'note': 'Only failed attempts count towards rate limiting per user'
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/rate_limit_status/<session_token>', methods=['GET'])
def get_rate_limit_status(session_token):
    """Get the rate limit status for a specific user session."""
    try:
        auth_session = AuthenticationSession.query.filter_by(session_token=session_token).first()
        if not auth_session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        recent_failed_attempts = count_recent_verification_attempts(auth_session.user_id)
        is_limited = is_rate_limited(auth_session.user_id)
        remaining_failed_attempts = max(0, VERIFICATION_ATTEMPTS_PER_HOUR_PER_CHALLENGE - recent_failed_attempts)
        
        # Calculate time until rate limit resets (when oldest failed attempt in the hour expires)
        cutoff_time = datetime.now(UTC) - timedelta(hours=1)
        cutoff_time_naive = cutoff_time.replace(tzinfo=None)
        oldest_failed_attempt = db.session.query(VerificationAttempt).filter(
            VerificationAttempt.user_id == auth_session.user_id,
            VerificationAttempt.attempted_at >= cutoff_time_naive,
            VerificationAttempt.was_successful == False
        ).order_by(VerificationAttempt.attempted_at.asc()).first()
        
        reset_time = None
        if oldest_failed_attempt:
            # Ensure timezone-aware datetime for reset_time calculation
            attempt_time_aware = ensure_timezone_aware(oldest_failed_attempt.attempted_at)
            reset_time = (attempt_time_aware + timedelta(hours=1)).isoformat()
        
        return jsonify({
            'success': True,
            'rate_limit_status': {
                'is_rate_limited': is_limited,
                'failed_attempts_used': recent_failed_attempts,
                'max_failed_attempts_per_hour': VERIFICATION_ATTEMPTS_PER_HOUR_PER_CHALLENGE,
                'remaining_failed_attempts': remaining_failed_attempts,
                'reset_time': reset_time,
                'user_id': auth_session.user_id,
                'note': 'Only failed attempts count towards rate limiting per user'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting rate limit status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logger.info("Mystery Protocol Server starting...")
        logger.info("Database initialized successfully")
    
    app.run(debug=True, host='0.0.0.0', port=1776)

