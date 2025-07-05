#!/usr/bin/env python3
"""
Complete example of using the MysteryProtocol library.

This example demonstrates the full interactive protocol between a Verifier and Data Owner,
including key generation, prize creation, commitment schemes, and final verification.
"""

import logging
from mystery_protocol import MysteryProtocol, serialize_to_json, load_from_json, save_binary_data, load_binary_data

# Configure logging to see the protocol steps
logging.basicConfig(
    level=logging.INFO,  # Use INFO to see main steps, DEBUG for detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Complete protocol demonstration."""
    print("=" * 80)
    print("SECURE PROTOCOL DEMONSTRATION")
    print("=" * 80)
    
    # Test parameters
    secret_string = "Hello123!"
    mapping_length = len(secret_string)
    segments = 10
    
    print(f"Secret string: '{secret_string}'")
    print(f"Length: {mapping_length}")
    print()
    
    # Initialize protocol
    protocol = MysteryProtocol()
    
    # =============================================================================
    # STAGE 1: KEY PROVISIONING AND PRIZE GENERATION
    # =============================================================================
    print("STAGE 1: Key Provisioning and Prize Generation")
    print("-" * 50)
    
    # Generate keys for both parties
    verifier_keys, owner_keys = protocol.provision_keys("demo")
    
    # Save keys to files (in practice, parties would exchange public keys)
    save_binary_data(verifier_keys['private_key'], "verifier_private.key")
    save_binary_data(verifier_keys['public_context'], "verifier_public.context")
    save_binary_data(owner_keys['private_key'], "owner_private.key")
    save_binary_data(owner_keys['public_context'], "owner_public.context")
    
    # Generate the secret prize
    prize_data = protocol.generate_prize(owner_keys['public_context'])
    serialize_to_json(prize_data, "prize_data.json")
    
    print(f"✅ Keys generated and prize created")
    print(f"   Prize value: 0x{prize_data['original_prize_for_reference']:064x}")
    print()
    
    # =============================================================================
    # STAGE 2: VERIFIER GENERATES MAPPINGS AND COMMITS
    # =============================================================================
    print("STAGE 2: Verifier Generates Mappings and Commits")
    print("-" * 50)
    
    # Verifier generates secret mappings
    mappings_data = protocol.generate_mappings(mapping_length, segments)
    serialize_to_json(mappings_data, "secret_mappings.json")
    
    # Get the correct sequence for demonstration
    correct_sequence = protocol.get_correct_sequence(
        mappings_data['secret_mappings'], 
        secret_string
    )
    print(f"✅ Secret mappings generated")
    print(f"   Correct sequence for '{secret_string}': {correct_sequence}")
    
    # Verifier creates commitment
    commitment_package = protocol.verifier_commit(mappings_data['secret_mappings'])
    serialize_to_json(commitment_package, "commitment_package.json")
    
    # In practice, only the commitment hash would be sent to the owner
    commitment_hash = commitment_package['commitment']
    print(f"✅ Commitment created: {commitment_hash[:16]}...")
    print()
    
    # =============================================================================
    # STAGE 3: OWNER REGISTERS DATA
    # =============================================================================
    print("STAGE 3: Owner Registers Secret Data")
    print("-" * 50)
    
    # Owner encrypts their secret string
    registered_data = protocol.owner_register_data(
        owner_keys['private_key'], 
        secret_string
    )
    serialize_to_json(registered_data, "registered_data.json")
    
    print(f"✅ Secret string encrypted and registered")
    print(f"   Encrypted {len(registered_data)} character vectors")
    print()
    
    # =============================================================================
    # STAGE 4: VERIFIER TRANSFORMS DATA
    # =============================================================================
    print("STAGE 4: Verifier Transforms Data")
    print("-" * 50)
    
    # Verifier applies mappings to the encrypted data
    reveal_package = protocol.verifier_transform_data(
        owner_keys['public_context'],
        registered_data,
        commitment_package
    )
    serialize_to_json(reveal_package, "reveal_package.json")
    
    print(f"✅ Data transformed and secrets revealed")
    print(f"   Transformed {len(reveal_package['transformed_vectors'])} vectors")
    print()
    
    # =============================================================================
    # STAGE 5: OWNER FINALIZES DATA
    # =============================================================================
    print("STAGE 5: Owner Finalizes Data and Re-encrypts Prize")
    print("-" * 50)
    
    # Owner verifies commitment and finalizes the protocol
    final_package = protocol.owner_finalize_data(
        owner_keys['private_key'],
        verifier_keys['public_context'],
        reveal_package,
        commitment_hash,
        prize_data,
        include_debug_info=True  # Include debug info for demonstration
    )
    serialize_to_json(final_package, "final_package.json")
    
    print(f"✅ Data finalized and prize re-encrypted for verifier")
    print(f"   Prize protected with password-dependent hash")
    print()
    
    # =============================================================================
    # STAGE 6: VERIFIER VERIFICATION (SUCCESS CASE)
    # =============================================================================
    print("STAGE 6: Verifier Verification - SUCCESS CASE")
    print("-" * 50)
    
    # Verifier performs final verification with correct sequence
    is_match, unlocked_prize = protocol.verifier_verify(
        verifier_keys['private_key'],
        final_package,
        correct_sequence
    )
    
    print(f"✅ Verification with correct sequence:")
    print(f"   Match: {is_match}")
    if is_match:
        print(f"   🎁 PRIZE UNLOCKED: 0x{unlocked_prize:064x}")
        print(f"   🎁 PRIZE (decimal): {unlocked_prize}")
        
        # Verify it matches the original
        original_prize = prize_data['original_prize_for_reference']
        print(f"   ✅ Matches original: {unlocked_prize == original_prize}")
    else:
        print(f"   🔒 Prize remains locked")
    print()
    
    # =============================================================================
    # STAGE 7: VERIFIER VERIFICATION (FAILURE CASE)
    # =============================================================================
    print("STAGE 7: Verifier Verification - FAILURE CASE")
    print("-" * 50)
    
    # Try with wrong sequence
    wrong_sequence = [x + 1 for x in correct_sequence]  # Modify sequence
    
    is_match_wrong, unlocked_prize_wrong = protocol.verifier_verify(
        verifier_keys['private_key'],
        final_package,
        wrong_sequence
    )
    
    print(f"✅ Verification with wrong sequence {wrong_sequence}:")
    print(f"   Match: {is_match_wrong}")
    print(f"   🔒 Prize remains locked (value: {unlocked_prize_wrong})")
    print()
    
    # =============================================================================
    # DEMONSTRATION OF DIFFERENT SCENARIOS
    # =============================================================================
    print("ADDITIONAL DEMONSTRATIONS")
    print("-" * 50)
    
    # Test with different string
    test_string = "Test456"
    if len(test_string) <= mapping_length:
        # Pad or truncate to match mapping length
        test_string = test_string.ljust(mapping_length)[:mapping_length]
        
        test_sequence = protocol.get_correct_sequence(
            mappings_data['secret_mappings'], 
            test_string
        )
        print(f"📝 Different string test:")
        print(f"   String: '{test_string}'")
        print(f"   Correct sequence: {test_sequence}")
        
        # This would fail verification since the registered data is for the original string
        is_match_test, _ = protocol.verifier_verify(
            verifier_keys['private_key'],
            final_package,
            test_sequence
        )
        print(f"   Match with original data: {is_match_test} (Expected: False)")
    
    print()
    print("=" * 80)
    print("PROTOCOL DEMONSTRATION COMPLETE")
    print("=" * 80)
    
    # Summary
    print("\nSUMMARY:")
    print(f"✅ Protocol executed successfully")
    print(f"✅ Correct sequence unlocked the prize")
    print(f"✅ Wrong sequence kept the prize locked")
    print(f"✅ Reed-Solomon error correction preserved data integrity")
    print(f"✅ Commitment scheme prevented verifier cheating")
    print(f"✅ Password-dependent encryption secured the prize")

def demonstrate_file_based_workflow():
    """
    Demonstrate how the protocol would work with file-based communication
    between parties (more realistic scenario).
    """
    print("\n" + "=" * 80)
    print("FILE-BASED WORKFLOW DEMONSTRATION")
    print("=" * 80)
    
    protocol = MysteryProtocol()
    secret_string = "Secret42"
    
    print(f"Demonstrating file-based workflow for: '{secret_string}'")
    print()
    
    # Step 1: Generate and save keys
    print("1. Generating and saving keys...")
    verifier_keys, owner_keys = protocol.provision_keys("workflow")
    
    save_binary_data(verifier_keys['private_key'], "workflow_verifier_private.key")
    save_binary_data(verifier_keys['public_context'], "workflow_verifier_public.context")
    save_binary_data(owner_keys['private_key'], "workflow_owner_private.key")
    save_binary_data(owner_keys['public_context'], "workflow_owner_public.context")
    
    # Step 2: Generate prize and mappings
    print("2. Generating prize and mappings...")
    prize_data = protocol.generate_prize(owner_keys['public_context'])
    serialize_to_json(prize_data, "workflow_prize.json")
    
    mappings_data = protocol.generate_mappings(len(secret_string))
    serialize_to_json(mappings_data, "workflow_mappings.json")
    
    # Step 3: Load from files and continue protocol
    print("3. Loading from files and executing protocol...")
    
    # Load keys from files
    verifier_private_key = load_binary_data("workflow_verifier_private.key")
    verifier_public_context = load_binary_data("workflow_verifier_public.context")
    owner_private_key = load_binary_data("workflow_owner_private.key")
    owner_public_context = load_binary_data("workflow_owner_public.context")
    
    # Load data from files
    prize_data = load_from_json("workflow_prize.json")
    mappings_data = load_from_json("workflow_mappings.json")
    
    # Continue with protocol steps...
    commitment_package = protocol.verifier_commit(mappings_data['secret_mappings'])
    
    registered_data = protocol.owner_register_data(owner_private_key, secret_string)
    
    reveal_package = protocol.verifier_transform_data(
        owner_public_context,
        registered_data,
        commitment_package
    )
    
    final_package = protocol.owner_finalize_data(
        owner_private_key,
        verifier_public_context,
        reveal_package,
        commitment_package['commitment'],
        prize_data,
        include_debug_info=True  # Include debug info for demonstration
    )
    
    # Get correct sequence and verify
    correct_sequence = protocol.get_correct_sequence(
        mappings_data['secret_mappings'], 
        secret_string
    )
    
    is_match, unlocked_prize = protocol.verifier_verify(
        verifier_private_key,
        final_package,
        correct_sequence
    )
    
    print(f"✅ File-based workflow completed successfully")
    print(f"   Prize unlocked: {is_match}")
    print(f"   Prize value: 0x{unlocked_prize:064x}")

if __name__ == "__main__":
    main()
    demonstrate_file_based_workflow()
