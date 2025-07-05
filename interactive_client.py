#!/usr/bin/env python3
"""
Interactive client for the Mystery Protocol Server.
Uses MysteryGridDisplay for interactive verification sequence entry.
"""

import requests
import json
import base64
import logging
import uuid
import bz2
import secrets
from mystery_protocol import MysteryProtocol
from grid_view import MysteryGridDisplay, generate_random_mapping
from rich.console import Console

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InteractiveMysteryClient:
    """Interactive client for Mystery Protocol Server using MysteryGridDisplay."""
    
    def __init__(self, server_url: str = "http://localhost:1776"):
        self.server_url = server_url
        self.protocol = MysteryProtocol()
        self.console = Console()
        self._last_compressed_data = None
    
    def submit_challenge_data(self, challenge_package: dict, unencrypted_mapping: list, user_id: str, key_name: str, key_index: int, segments: int = 10):
        """Submit challenge data file with unencrypted mapping to server."""
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
    
    def interactive_verification_sequence_entry(self, mapping_data_sets: list):
        """Use MysteryGridDisplay to interactively enter verification sequence."""
        
        self.console.print(f"[bold green]═══ INTERACTIVE VERIFICATION SEQUENCE ENTRY ═══[/bold green]")
        self.console.print(f"[dim]Enter verification sequence for {len(mapping_data_sets)} character positions[/dim]")
        self.console.print()
        
        # Use random permutation indices for security
        display_permutation_index = secrets.randbelow(24) + 1
        mapping_permutation_index = secrets.randbelow(24) + 1
        
        # Create display instance
        display = MysteryGridDisplay(self.console, display_permutation_index, mapping_permutation_index)
        
        # Show configuration
        self.console.print(f"[bold magenta]Display permutation index {display_permutation_index}:[/bold magenta]")
        self.console.print(f"[dim]Symbol display order: {display.symbol_order}[/dim]")
        self.console.print(f"[bold magenta]Mapping permutation index {mapping_permutation_index}:[/bold magenta]")
        self.console.print(f"[dim]Symbol-to-segment mapping: {display.symbol_to_segment_map}[/dim]")
        self.console.print()
        
        # Use the full provided mapping data for the actual challenge
        entered_sequence = display.display_mapping_grid(mapping_data_sets)
        
        return entered_sequence

def demo_interactive_authentication():
    """Demonstrate interactive authentication with MysteryGridDisplay."""
    console = Console()
    
    console.print("=" * 80)
    console.print("[bold blue]MYSTERY PROTOCOL INTERACTIVE CLIENT DEMO[/bold blue]")
    console.print("=" * 80)
    
    client = InteractiveMysteryClient()
    
    # Step 1: Generate protocol data
    console.print("\n[bold yellow]1. Generating protocol data...[/bold yellow]")
    protocol = MysteryProtocol()
    secret_string = "ABCD"
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
    
    console.print(f"[green]✅ Protocol data generated for secret: '{secret_string}'[/green]")
    
    # Step 2: Submit challenge data to server
    console.print("\n[bold yellow]2. Submitting challenge data to server...[/bold yellow]")
    
    # Generate user credentials
    user_id = str(uuid.uuid4())
    key_name = "interactive_demo_key"
    key_index = 1
    
    response, status_code = client.submit_challenge_data(
        challenge_package, 
        mappings_data['secret_mappings'],
        user_id,
        key_name,
        key_index,
        segments
    )
    
    if status_code == 201:
        console.print(f"[green]✅ Challenge data submitted successfully[/green]")
    else:
        console.print(f"[red]❌ Failed to submit challenge data: {response}[/red]")
        return
    
    # Step 3: Get authentication challenge
    console.print("\n[bold yellow]3. Getting authentication challenge...[/bold yellow]")
    challenge_response, status_code = client.get_authentication_challenge(user_id, key_name, timeout_minutes=10)
    
    if status_code == 200:
        session_token = challenge_response['session_token']
        console.print(f"[green]✅ Authentication challenge received[/green]")
        console.print(f"[dim]Session Token: {session_token}[/dim]")
        
        # Get the mapping data from the challenge
        mapping_data = challenge_response['mapping']
        
    else:
        console.print(f"[red]❌ Failed to get authentication challenge: {challenge_response}[/red]")
        return
    
    # Step 4: Interactive sequence entry
    console.print("\n[bold yellow]4. Interactive verification sequence entry...[/bold yellow]")
    console.print(f"[cyan]Secret string: '{secret_string}' (for reference - in real use this would be unknown)[/cyan]")
    console.print()
    
    # Convert mapping data to the format expected by MysteryGridDisplay
    mapping_data_sets = []
    for position_mapping in mapping_data:
        position_data = []
        for char, segment in position_mapping.items():
            position_data.append({'character': char, 'segment': segment})
        mapping_data_sets.append(position_data)
    
    # Show what the correct sequence should be for reference
    # Use only the actual secret string length from the stored extended mapping
    original_mapping = mapping_data[:len(secret_string)]
    correct_sequence = protocol.get_correct_sequence(original_mapping, secret_string)
    console.print(f"[dim]Correct sequence (for reference): {correct_sequence}[/dim]")
    console.print()
    
    # Use interactive display to enter sequence
    entered_sequence = client.interactive_verification_sequence_entry(mapping_data_sets)
    
    # Show sequence entry results
    console.print("\n[bold green]Interactive sequence entry completed![/bold green]")
    console.print(f"[cyan]Entered sequence: {entered_sequence if entered_sequence else 'None'}[/cyan]")
    console.print(f"[bold magenta]Correct sequence: {correct_sequence}[/bold magenta]")
    
    # Step 5: Verify the entered sequence (if any was entered)
    if entered_sequence:
        console.print("\n[bold yellow]5. Verifying entered sequence...[/bold yellow]")
        verify_response, status_code = client.verify_solution(
            session_token,
            entered_sequence,
            verifier_keys['private_key']
        )
        
        if status_code == 200:
            result = verify_response['verification_result']
            console.print(f"[green]✅ Verification completed[/green]")
            console.print(f"[cyan]Match: {result['is_match']}[/cyan]")
            console.print(f"[cyan]Prize Value: {result['prize_value']}[/cyan]")
            console.print(f"[cyan]Message: {verify_response['message']}[/cyan]")
            
            # Show comparison with correct sequence
            if result['is_match']:
                console.print(f"[bold green]🎉 SUCCESS! The sequence was correct![/bold green]")
            else:
                console.print(f"[bold red]❌ INCORRECT! The sequence was wrong.[/bold red]")
        else:
            console.print(f"[red]❌ Verification failed: {verify_response}[/red]")
            
        # Step 6: Check session status
        console.print("\n[bold yellow]6. Checking session status...[/bold yellow]")
        status_response, status_code = client.get_session_status(session_token)
        
        if status_code == 200:
            session = status_response['session']
            console.print(f"[green]✅ Session status retrieved[/green]")
            console.print(f"[cyan]Is Verified: {session['is_verified']}[/cyan]")
            console.print(f"[cyan]Attempts: {session['verification_attempts']}/{session['max_attempts']}[/cyan]")
        else:
            console.print(f"[red]❌ Failed to get session status: {status_response}[/red]")
    else:
        console.print("\n[yellow]No sequence entered for verification.[/yellow]")
    
    # Final summary
    console.print("\n[bold blue]═══ FINAL SUMMARY ═══[/bold blue]")
    console.print(f"[bold magenta]Secret string: '{secret_string}'[/bold magenta]")
    console.print(f"[bold magenta]Correct sequence: {correct_sequence}[/bold magenta]")
    console.print(f"[cyan]Entered sequence: {entered_sequence if entered_sequence else 'None'}[/cyan]")
    if entered_sequence:
        console.print(f"[yellow]Entered sequence length: {len(entered_sequence)}[/yellow]")
    console.print(f"[dim]Expected sequence length: {len(secret_string)} (for secret string)[/dim]")
    console.print(f"[dim]Available mapping positions: {len(mapping_data_sets)}[/dim]")
    
    console.print("\n" + "=" * 80)
    console.print("[bold blue]INTERACTIVE DEMO COMPLETED![/bold blue]")
    console.print("=" * 80)

def demo_practice_mode():
    """Demo practice mode with randomly generated mappings."""
    console = Console()
    
    console.print("=" * 80)
    console.print("[bold green]MYSTERY PROTOCOL PRACTICE MODE[/bold green]")
    console.print("=" * 80)
    
    console.print("\n[bold yellow]Practice Mode - No Server Connection Required[/bold yellow]")
    console.print("[dim]This mode uses randomly generated mappings for practice[/dim]")
    
    # Generate random mappings for practice
    num_positions = 8
    practice_mappings = generate_random_mapping(num_positions, seed=None)
    
    # Use random permutation indices
    display_permutation_index = secrets.randbelow(24) + 1
    mapping_permutation_index = secrets.randbelow(24) + 1
    
    # Create display instance
    display = MysteryGridDisplay(console, display_permutation_index, mapping_permutation_index)
    
    console.print(f"[bold magenta]Practice session with {num_positions} positions[/bold magenta]")
    console.print(f"[dim]Display permutation: {display_permutation_index}, Mapping permutation: {mapping_permutation_index}[/dim]")
    console.print()
    
    # Run interactive practice session
    entered_sequence = display.display_mapping_grid(practice_mappings)
    
    # Show results
    if entered_sequence:
        console.print(f"\n[bold green]Practice session completed![/bold green]")
        console.print(f"[cyan]Entered sequence: {entered_sequence}[/cyan]")
        console.print(f"[dim]Sequence length: {len(entered_sequence)}/{num_positions}[/dim]")
    else:
        console.print("\n[yellow]Practice session cancelled or incomplete.[/yellow]")
    
    console.print("\n" + "=" * 80)
    console.print("[bold green]PRACTICE SESSION COMPLETED![/bold green]")
    console.print("=" * 80)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "practice":
        # Practice mode - no server required
        demo_practice_mode()
    else:
        # Full interactive demo with server
        try:
            demo_interactive_authentication()
        except requests.exceptions.ConnectionError:
            console = Console()
            console.print("[red]❌ Could not connect to server. Make sure the server is running at http://localhost:1776[/red]")
            console.print("[yellow]💡 Try running with 'practice' argument for offline practice mode:[/yellow]")
            console.print("[cyan]   python interactive_client.py practice[/cyan]")
        except Exception as e:
            console = Console()
            console.print(f"[red]❌ Demo failed with error: {e}[/red]") 
