import math
import json
import random
import string
import base64
import hashlib
import logging
import tenseal as ts
from reedsolo import RSCodec
from typing import List, Dict, Any, Tuple

# =============================================================================
# Core Logic Classes
# =============================================================================

class MappingGenerator:
    """Generates the secret character-to-number mappings."""
    
    def __init__(self):
        self.alphabet = list(string.ascii_letters + string.digits + string.punctuation + " ")
        logging.debug(f"Initialized MappingGenerator with alphabet size: {len(self.alphabet)}")
    
    def generate(self, length: int, num_segments: int) -> List[Dict[str, int]]:
        """Generate secret mappings for character-to-number transformation."""
        logging.debug(f"Generating mappings with length={length}, num_segments={num_segments}")
        
        secret_mappings = []
        for i in range(length):
            alphabet_shuffled = self.alphabet[:]
            random.shuffle(alphabet_shuffled)
            
            segment_numbers = list(range(1, num_segments + 1))
            random.shuffle(segment_numbers)
            
            partition_size = math.ceil(len(alphabet_shuffled) / num_segments)
            char_partitions = [alphabet_shuffled[j:j+partition_size] 
                             for j in range(0, len(alphabet_shuffled), partition_size)]
            
            index_mapping_dict = {
                char: seg_num 
                for seg_num, char_group in zip(segment_numbers, char_partitions) 
                for char in char_group
            }
            
            secret_mappings.append(index_mapping_dict)
            logging.debug(f"Generated mapping {i+1}/{length}")
        
        logging.debug(f"Completed generating {len(secret_mappings)} mappings")
        return secret_mappings

# =============================================================================
# Main Protocol Class
# =============================================================================

class MysteryProtocol:
    """Main protocol class that handles all cryptographic operations."""
    
    def __init__(self, poly_mod_degree: int = 8192, plain_modulus: int = 65537):
        self.poly_mod_degree = poly_mod_degree
        self.plain_modulus = plain_modulus
        self.alphabet = list(string.ascii_letters + string.digits + string.punctuation + " ")
        self.char_to_idx = {c: i for i, c in enumerate(self.alphabet)}
        
        logging.debug(f"Initialized SecureProtocol with poly_mod_degree={poly_mod_degree}, plain_modulus={plain_modulus}")
        logging.debug(f"Alphabet size: {len(self.alphabet)}")
    
    def provision_keys(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        S1: Creates key pairs for all parties AND the secret prize.
        
        Returns:
            Tuple of (verifier_keys, owner_keys) dictionaries containing serialized keys
        """
        logging.debug("Starting key provisioning process")
        
        # Verifier Keys
        v_priv_ctx = ts.context(ts.SCHEME_TYPE.BFV, self.poly_mod_degree, self.plain_modulus)
        v_priv_ctx.generate_galois_keys()
        
        v_pub_ctx = v_priv_ctx.copy()
        v_pub_ctx.make_context_public()
        
        verifier_keys = {
            'private_key': v_priv_ctx.serialize(save_secret_key=True),
            'public_context': v_pub_ctx.serialize()
        }
        
        logging.debug("Verifier keys generated")
        
        # Owner Keys
        o_priv_ctx = ts.context(ts.SCHEME_TYPE.BFV, self.poly_mod_degree, self.plain_modulus)
        o_priv_ctx.generate_galois_keys()
        
        o_pub_ctx = o_priv_ctx.copy()
        o_pub_ctx.make_context_public()
        
        owner_keys = {
            'private_key': o_priv_ctx.serialize(save_secret_key=True),
            'public_context': o_pub_ctx.serialize()
        }
        
        logging.debug("Owner keys generated")
        
        return verifier_keys, owner_keys
    
    def generate_prize(self, owner_public_context: bytes) -> Dict[str, Any]:
        """
        Generate a secret prize with Reed-Solomon error correction.
        
        Args:
            owner_public_context: Owner's public context bytes
            
        Returns:
            Dictionary containing encrypted prize data
        """
        logging.debug("Starting prize generation")
        
        # Generate 256-bit secret prize
        secret_prize = random.getrandbits(256)
        logging.debug(f"Generated 256-bit prize: 0x{secret_prize:064x}")
        
        # Convert to bytes and apply Reed-Solomon encoding
        prize_bytes = secret_prize.to_bytes(32, 'big')
        rs_codec = RSCodec(16)  # 16 parity bytes
        encoded_prize_bytes = rs_codec.encode(prize_bytes)
        
        logging.debug(f"Reed-Solomon encoded: {len(prize_bytes)} data bytes + 16 parity bytes = {len(encoded_prize_bytes)} total bytes")
        
        # Load owner's public context
        o_pub_ctx = ts.context_from(owner_public_context)
        
        # Encrypt each byte with owner's public key
        encrypted_prize_chunks = []
        for chunk in encoded_prize_bytes:
            encrypted_chunk = ts.bfv_vector(o_pub_ctx, [chunk])
            encrypted_prize_chunks.append(base64.b64encode(encrypted_chunk.serialize()).decode('utf-8'))
        
        prize_data = {
            "encrypted_prize_chunks_for_owner": encrypted_prize_chunks,
            "chunk_bits": 8,
            "num_chunks": len(encoded_prize_bytes),
            "rs_parity_bytes": 16,
            "original_data_bytes": 32,
            "original_prize_for_reference": secret_prize
        }
        
        logging.debug(f"Prize encrypted in {len(encrypted_prize_chunks)} chunks")
        return prize_data
    
    def generate_mappings(self, length: int, segments: int = 10) -> Dict[str, Any]:
        """
        S2: Generate secret mappings.
        
        Args:
            length: Length of the mappings to generate
            segments: Number of segments for mapping
            
        Returns:
            Dictionary containing secret mappings
        """
        logging.debug(f"Generating mappings with length={length}, segments={segments}")
        
        mapper = MappingGenerator()
        mappings = mapper.generate(length, segments)
        
        return {"secret_mappings": mappings}
    
    def get_correct_sequence(self, secret_mappings: List[Dict[str, int]], input_string: str) -> List[int]:
        """
        UTILITY: Get the correct sequence for a string.
        
        Args:
            secret_mappings: List of character-to-number mappings
            input_string: Input string to convert
            
        Returns:
            List of integers representing the correct sequence
        """
        logging.debug(f"Computing correct sequence for input: '{input_string}'")
        
        target_sequence = []
        for i, char in enumerate(input_string):
            if i < len(secret_mappings):
                target_sequence.append(secret_mappings[i][char])
            else:
                logging.warning(f"Character at position {i} exceeds mapping length")
        
        logging.debug(f"Computed sequence: {target_sequence}")
        return target_sequence
    
    def verifier_commit(self, secret_mappings: List[Dict[str, int]]) -> Dict[str, Any]:
        """
        Verifier Step 1: Create a commitment to the mapping rules.
        
        Args:
            secret_mappings: List of secret mapping dictionaries
            
        Returns:
            Dictionary containing commitment package
        """
        logging.debug("Creating verifier commitment")
        
        salt = base64.b64encode(random.getrandbits(256).to_bytes(32, 'big')).decode('utf-8')
        mappings_str = json.dumps(secret_mappings, sort_keys=True)
        commitment = hashlib.sha256((salt + mappings_str).encode()).hexdigest()
        
        password_hash_salt = base64.b64encode(random.getrandbits(256).to_bytes(32, 'big')).decode('utf-8')
        
        commitment_package = {
            "commitment": commitment,
            "salt": salt,
            "secret_mappings": secret_mappings,
            "password_hash_salt": password_hash_salt
        }
        
        logging.debug(f"Created commitment: {commitment[:16]}...")
        return commitment_package
    
    def owner_register_data(self, owner_private_key: bytes, input_string: str) -> List[str]:
        """
        Owner's Setup Step: Encrypt the secret string for reuse.
        
        Args:
            owner_private_key: Owner's private key bytes
            input_string: String to encrypt
            
        Returns:
            List of base64-encoded encrypted vectors
        """
        logging.debug(f"Registering data for input string of length {len(input_string)}")
        
        o_ctx = ts.context_from(owner_private_key)
        
        encrypted_vectors = []
        for c in input_string:
            # Create one-hot encoding for character
            one_hot = [1 if i == self.char_to_idx.get(c, -1) else 0 for i in range(len(self.alphabet))]
            encrypted_vector = ts.bfv_vector(o_ctx, one_hot)
            encrypted_vectors.append(base64.b64encode(encrypted_vector.serialize()).decode('utf-8'))
        
        logging.debug(f"Encrypted {len(encrypted_vectors)} character vectors")
        return encrypted_vectors
    
    def verifier_transform_data(self, owner_public_context: bytes, registered_data: List[str], 
                              commitment_package: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifier's Interactive Step: Apply mappings and reveal secrets.
        
        Args:
            owner_public_context: Owner's public context bytes
            registered_data: List of encrypted data vectors
            commitment_package: Commitment package from verifier_commit
            
        Returns:
            Dictionary containing reveal package
        """
        logging.debug("Applying mappings to registered data")
        
        o_pub_ctx = ts.context_from(owner_public_context)
        secret_mappings = commitment_package["secret_mappings"]
        
        if len(registered_data) != len(secret_mappings):
            raise ValueError(f"Data length mismatch: {len(registered_data)} vs {len(secret_mappings)}")
        
        transformed_vectors = []
        for i, b64_enc_s in enumerate(registered_data):
            enc_s = ts.bfv_vector_from(o_pub_ctx, base64.b64decode(b64_enc_s))
            mapping_vec = [secret_mappings[i].get(c, 0) for c in self.alphabet]
            enc_sm = enc_s.dot(mapping_vec)
            transformed_vectors.append(base64.b64encode(enc_sm.serialize()).decode('utf-8'))
        
        reveal_package = {
            "transformed_vectors": transformed_vectors,
            "salt": commitment_package["salt"],
            "secret_mappings": secret_mappings,
            "password_hash_salt": commitment_package["password_hash_salt"]
        }
        
        logging.debug(f"Transformed {len(transformed_vectors)} vectors")
        return reveal_package
    
    def owner_finalize_data(self, owner_private_key: bytes, verifier_public_context: bytes,
                          reveal_package: Dict[str, Any], commitment: str, 
                          prize_data: Dict[str, Any], include_debug_info: bool = False) -> Dict[str, Any]:
        """
        Owner's Interactive Step: Verify commitment, decrypt/re-encrypt prize, and finalize data.
        
        Args:
            owner_private_key: Owner's private key bytes
            verifier_public_context: Verifier's public context bytes
            reveal_package: Package from verifier_transform_data
            commitment: Expected commitment hash
            prize_data: Prize data from generate_prize
            include_debug_info: Whether to include original_data_bytes and original_prize_for_reference
            
        Returns:
            Dictionary containing final package (password_dependent_hash never included for security)
        """
        logging.debug("Finalizing data and verifying commitment")
        
        # Verify commitment
        salt = reveal_package["salt"]
        received_mappings = reveal_package["secret_mappings"]
        mappings_str = json.dumps(received_mappings, sort_keys=True)
        recomputed_commitment = hashlib.sha256((salt + mappings_str).encode()).hexdigest()
        
        if recomputed_commitment != commitment:
            raise ValueError("Commitment verification failed - verifier is cheating!")
        
        logging.debug("Commitment verified successfully")
        
        # Load contexts
        o_priv_ctx = ts.context_from(owner_private_key)
        v_pub_ctx = ts.context_from(verifier_public_context)
        
        # Generate password sequence
        password_sequence = []
        for b64_enc_sm in reveal_package["transformed_vectors"]:
            enc_sm = ts.bfv_vector_from(o_priv_ctx, base64.b64decode(b64_enc_sm))
            decrypted_value = enc_sm.decrypt()[0]
            password_sequence.append(decrypted_value)
        
        # Generate password-dependent hash
        password_hash_salt = reveal_package.get("password_hash_salt", "")
        password_sequence_str = ",".join(map(str, password_sequence))
        password_dependent_hash = hashlib.sha256((password_hash_salt + password_sequence_str).encode()).hexdigest()
        
        logging.debug(f"Generated password hash: {password_dependent_hash[:16]}...")
        
        # Re-encrypt prize for verifier with password protection
        decrypted_prize_chunks = []
        for chunk_b64 in prize_data["encrypted_prize_chunks_for_owner"]:
            encrypted_chunk = ts.bfv_vector_from(o_priv_ctx, base64.b64decode(chunk_b64))
            decrypted_chunk = encrypted_chunk.decrypt()[0]
            decrypted_prize_chunks.append(decrypted_chunk)
        
        # Apply password protection
        hash_bytes = bytes.fromhex(password_dependent_hash)
        protected_chunks = []
        for i, chunk in enumerate(decrypted_prize_chunks):
            protection_byte = hash_bytes[i % len(hash_bytes)]
            protected_chunk = chunk ^ protection_byte
            protected_chunks.append(protected_chunk)
        
        # Re-encrypt for verifier
        encrypted_prize_chunks_for_verifier = []
        for protected_chunk in protected_chunks:
            encrypted_chunk = ts.bfv_vector(v_pub_ctx, [protected_chunk])
            encrypted_prize_chunks_for_verifier.append(base64.b64encode(encrypted_chunk.serialize()).decode('utf-8'))
        
        logging.debug("Prize re-encrypted for verifier with password protection")
        
        # Finalize sequence data
        final_sequence_data = []
        for b64_enc_sm in reveal_package["transformed_vectors"]:
            enc_sm = ts.bfv_vector_from(o_priv_ctx, base64.b64decode(b64_enc_sm))
            final_ciphertext = ts.bfv_vector(v_pub_ctx, [enc_sm.decrypt()[0]])
            final_sequence_data.append(base64.b64encode(final_ciphertext.serialize()).decode('utf-8'))
        
        # Build prize data dictionary with conditional debug info
        prize_data_dict = {
            "prize_chunks": encrypted_prize_chunks_for_verifier,
            "password_hash_salt": password_hash_salt,
            "chunk_bits": prize_data["chunk_bits"],
            "num_chunks": prize_data["num_chunks"],
            "rs_parity_bytes": prize_data["rs_parity_bytes"]
        }
        
        # Only include debug information if requested
        if include_debug_info:
            prize_data_dict["original_data_bytes"] = prize_data["original_data_bytes"]
            prize_data_dict["original_prize_for_reference"] = prize_data.get("original_prize_for_reference", 0)
        
        final_package = {
            "sequence_data": final_sequence_data,
            "prize_data": prize_data_dict
        }
        
        logging.debug("Final package created successfully")
        return final_package
    
    def verifier_verify(self, verifier_private_key: bytes, final_package: Dict[str, Any], 
                       target_sequence: List[int]) -> Tuple[bool, int]:
        """
        Verifier's Final Step: Perform the check and unlock the prize.
        
        Args:
            verifier_private_key: Verifier's private key bytes
            final_package: Package from owner_finalize_data
            target_sequence: Target sequence to verify
            
        Returns:
            Tuple of (is_match, prize_value) where prize_value is 0 if no match
        """
        logging.debug("Starting final verification and prize unlocking")
        #logging.info(f"Target sequence: {target_sequence}")
        #logging.info(f"Sequence data: {len(final_package['sequence_data'])}")
        
        v_priv_ctx = ts.context_from(verifier_private_key)
        
        sequence_data = final_package["sequence_data"]
        prize_data = final_package["prize_data"]
        
        # Load encrypted prize chunks
        encrypted_prize_chunks = []
        for chunk_b64 in prize_data["prize_chunks"]:
            encrypted_chunk = ts.bfv_vector_from(v_priv_ctx, base64.b64decode(chunk_b64))
            encrypted_prize_chunks.append(encrypted_chunk)
        
        # Verify sequence using sum of squares
        total_sum_of_squares = ts.bfv_vector(v_priv_ctx, [0])
        for i, b64_enc_final in enumerate(sequence_data):
            enc_final = ts.bfv_vector_from(v_priv_ctx, base64.b64decode(b64_enc_final))
            diff = enc_final - [target_sequence[i] if i < len(target_sequence) else 0]
            squared_diff = diff * diff
            total_sum_of_squares += squared_diff
        
        # Apply blinding
        blinder = random.randint(1, self.plain_modulus - 1)
        locked_sum = total_sum_of_squares * blinder
        decrypted_locked_sum = locked_sum.decrypt()[0]
        
        is_match = (round(decrypted_locked_sum) == 0)
        
        logging.debug(f"Sequence verification result: {is_match}")
        
        if not is_match:
            logging.debug("Sequence doesn't match - prize remains locked")
            return False, 0
        
        # Compute password hash for prize decryption
        password_hash_salt = prize_data.get("password_hash_salt", "")
        password_sequence_str = ",".join(map(str, target_sequence))
        computed_password_hash = hashlib.sha256((password_hash_salt + password_sequence_str).encode()).hexdigest()
        
        logging.debug("Password hash computed - proceeding with prize decryption")
        
        # Decrypt password-protected chunks
        decrypted_protected_chunks = []
        for encrypted_chunk in encrypted_prize_chunks:
            chunk_value = encrypted_chunk.decrypt()[0]
            decrypted_protected_chunks.append(chunk_value)
        
        # Remove password protection
        hash_bytes = bytes.fromhex(computed_password_hash)
        decrypted_chunks = []
        for i, protected_chunk in enumerate(decrypted_protected_chunks):
            protection_byte = hash_bytes[i % len(hash_bytes)]
            original_chunk = protected_chunk ^ protection_byte
            decrypted_chunks.append(original_chunk)
        
        # Reconstruct prize using Reed-Solomon
        try:
            rs_codec = RSCodec(prize_data.get("rs_parity_bytes", 16))
            rs_encoded_bytes = bytes(decrypted_chunks)
            decoded_prize_bytes = rs_codec.decode(rs_encoded_bytes)[0]
            reconstructed_prize = int.from_bytes(decoded_prize_bytes, 'big')
            
            logging.debug(f"Prize successfully reconstructed: 0x{reconstructed_prize:064x}")
            return True, reconstructed_prize
            
        except Exception as e:
            logging.error(f"Reed-Solomon decoding failed: {e}")
            return False, 0

# =============================================================================
# Utility Functions
# =============================================================================

def serialize_to_json(data: Any, filename: str) -> None:
    """Serialize data to JSON file."""
    logging.debug(f"Serializing data to {filename}")
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def load_from_json(filename: str) -> Any:
    """Load data from JSON file."""
    logging.debug(f"Loading data from {filename}")
    with open(filename, 'r') as f:
        return json.load(f)

def save_binary_data(data: bytes, filename: str) -> None:
    """Save binary data to file."""
    logging.debug(f"Saving binary data to {filename}")
    with open(filename, 'wb') as f:
        f.write(data)

def load_binary_data(filename: str) -> bytes:
    """Load binary data from file."""
    logging.debug(f"Loading binary data from {filename}")
    with open(filename, 'rb') as f:
        return f.read()
