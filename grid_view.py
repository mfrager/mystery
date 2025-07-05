#!/usr/bin/env python3
"""
Grid Display Library for Mystery Protocol Client
Displays character mappings in a 2x2 grid format using Rich library for enhanced visualization.
"""

# Standard library imports
import sys
import tty
import time
import termios
import itertools
import random
import secrets
import string
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

# Third-party imports
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.layout import Layout
    from rich.align import Align
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'rich' library not found. Install with: pip install rich")


def get_char():
    """Get a single character from stdin without waiting for Enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        char = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return char


class MysteryGridDisplay:
    """Display character mappings in a 2x2 grid format using Rich library."""
    
    # Symbol to represent space character
    SPACE_SYMBOL = "◦"
    
    # Symbol mapping for permutation ordering
    SYMBOL_MAP = {
        1: "○",  # Circle
        2: "X",  # X
        3: "▲",  # Triangle
        4: "■"   # Square
    }
    
    def __init__(self, console: Optional[Console] = None, permutation_index: int = 1, mapping_permutation_index: int = 1):
        """Initialize grid display with Rich console.
        
        Args:
            console: Optional Rich Console instance. If None, creates a new one.
            permutation_index: Index (1-based) for symbol display ordering permutation (1-24)
            mapping_permutation_index: Index (1-based) for symbol-to-segment mapping permutation (1-24)
        """
        if not RICH_AVAILABLE:
            raise ImportError("Rich library is required. Install with: pip install rich")
        
        self.console = console or Console()
        self.permutation_index = permutation_index
        self.mapping_permutation_index = mapping_permutation_index
        self.symbol_order = self._get_symbol_order(permutation_index)
        self.symbol_to_segment_map = self._get_symbol_to_segment_mapping(mapping_permutation_index)
        self.show_mapping = False  # Toggle for showing/hiding mapping
        
    def _get_symbol_order(self, permutation_index: int) -> Tuple[str, str, str, str]:
        """Get symbol order based on permutation index.
        
        Args:
            permutation_index: Index (1-based) for permutation ordering (1-24)
            
        Returns:
            Tuple of symbols in the specified permutation order
        """
        # Base elements for permutation
        elements = [1, 2, 3, 4]
        
        # Calculate all permutations and sort them
        permutations = list(itertools.permutations(elements))
        permutations.sort()
        
        # Validate permutation index
        if permutation_index < 1 or permutation_index > len(permutations):
            raise ValueError(f"Permutation index must be between 1 and {len(permutations)}")
        
        # Get the specific permutation (convert to 0-based index)
        selected_permutation = permutations[permutation_index - 1]
        
        # Map numbers to symbols
        symbol_order = tuple(self.SYMBOL_MAP[num] for num in selected_permutation)
        
        return symbol_order
        
    def _get_symbol_to_segment_mapping(self, mapping_permutation_index: int) -> Dict[str, int]:
        """Get symbol-to-segment mapping based on mapping permutation index.
        
        Args:
            mapping_permutation_index: Index (1-based) for symbol-to-segment mapping (1-24)
            
        Returns:
            Dictionary mapping symbols to segment numbers
        """
        # Base elements for permutation
        elements = [1, 2, 3, 4]
        
        # Calculate all permutations and sort them
        permutations = list(itertools.permutations(elements))
        permutations.sort()
        
        # Validate permutation index
        if mapping_permutation_index < 1 or mapping_permutation_index > len(permutations):
            raise ValueError(f"Mapping permutation index must be between 1 and {len(permutations)}")
        
        # Get the specific permutation (convert to 0-based index)
        selected_permutation = permutations[mapping_permutation_index - 1]
        
        # Create mapping from symbols to segment numbers
        symbol_to_segment = {}
        for i, symbol in enumerate(["○", "X", "▲", "■"]):
            symbol_to_segment[symbol] = selected_permutation[i]
        
        return symbol_to_segment
        
    def show_all_permutations(self) -> None:
        """Display all possible symbol permutations for reference."""
        elements = [1, 2, 3, 4]
        permutations = list(itertools.permutations(elements))
        permutations.sort()
        
        self.console.print("[bold blue]All Symbol Permutations:[/bold blue]")
        
        for i, perm in enumerate(permutations, 1):
            symbol_order = tuple(self.SYMBOL_MAP[num] for num in perm)
            self.console.print(f"[dim]Permutation {i:2d}:[/dim] {symbol_order} [dim]({perm})[/dim]")
        
        self.console.print()
        
    def _parse_mapping_data(self, mapping_data: List[Dict[str, Any]]) -> Dict[int, List[str]]:
        """Parse mapping data and organize characters by segment.
        
        Args:
            mapping_data: List of mapping dictionaries from the protocol
            
        Returns:
            Dictionary mapping segment numbers to sorted character lists
        """
        segments = defaultdict(list)
        
        for mapping in mapping_data:
            char = mapping['character']
            segment = mapping['segment']
            
            # Replace space with symbol
            display_char = self.SPACE_SYMBOL if char == ' ' else char
            segments[segment].append(display_char)
        
        # Sort characters in each segment
        for segment in segments:
            segments[segment].sort()
            
        return dict(segments)
    
    def _calculate_optimal_width(self, all_segments: Dict[int, List[str]]) -> int:
        """Calculate optimal width based on content.
        
        Args:
            all_segments: Dictionary of all segments with their characters
            
        Returns:
            Optimal width for formatting
        """
        max_chars_per_segment = max(len(chars) for chars in all_segments.values())
        
        # Calculate width needed: each char + space, plus some padding
        # Minimum width of 15, maximum of 50 for readability
        optimal_width = min(50, max(15, max_chars_per_segment * 2 + 5))
        return optimal_width
    
    def _format_segment_characters(self, characters: List[str], max_width: int = None, 
                                 all_segments: Dict[int, List[str]] = None) -> str:
        """Format characters for display within a cell.
        
        Args:
            characters: List of characters in the segment
            max_width: Maximum width per line (auto-calculated if None)
            all_segments: All segments for width calculation
            
        Returns:
            Formatted string with line breaks
        """
        if not characters:
            return "[dim]No characters[/dim]"
        
        # Auto-calculate width if not provided
        if max_width is None and all_segments:
            max_width = self._calculate_optimal_width(all_segments)
        elif max_width is None:
            max_width = 20
        
        # Group characters with spacing
        char_groups = []
        current_line = []
        current_width = 0
        
        for char in characters:
            # Each character takes 2 spaces (char + space)
            if current_width + 2 > max_width and current_line:
                char_groups.append(" ".join(current_line))
                current_line = [char]
                current_width = 2
            else:
                current_line.append(char)
                current_width += 2
        
        if current_line:
            char_groups.append(" ".join(current_line))
        
        return "\n".join(char_groups)
    
    def display_mapping_grid(self, mapping_data_sets: List[List[Dict[str, Any]]], 
                           title: Optional[str] = None) -> List[int]:
        """Display the mapping data in a 2x2 grid format using Rich.
        
        Args:
            mapping_data_sets: List of mapping datasets, one for each character position
            title: Optional title to display above the grid
            
        Returns:
            List[int]: The sequence of segment numbers entered by the user
        """
        if not mapping_data_sets:
            raise ValueError("At least one mapping dataset is required")
        
        # Clear screen at program start
        self.console.clear()
        
        # Validate that we have proper segment data
        for mapping_data in mapping_data_sets:
            if len(set(m['segment'] for m in mapping_data)) != 4:
                raise ValueError("Grid display requires exactly 4 segments")
        
        # Interactive segment entry with grid updates
        accumulated_symbols = []
        accumulated_segments = []
        current_position = 0
        
        # Initial display
        self._draw_interface(mapping_data_sets, accumulated_symbols, accumulated_segments, current_position)
        
        while current_position < len(mapping_data_sets):
            # Get immediate character input
            try:
                char = get_char()
                
                # Clear screen and redraw interface
                self.console.clear()
                self._draw_interface(mapping_data_sets, accumulated_symbols, accumulated_segments, current_position)
                
                # Check for quit
                if char.lower() == 'q':
                    self.console.print("\n[yellow]Quit requested.[/yellow]")
                    break
                
                # Check for escape/enter to finish
                if ord(char) in [13, 10, 27]:  # Enter, LF, or Escape
                    self.console.print("\n[yellow]Finished entering symbols.[/yellow]")
                    break
                
                # Check for delete/backspace to go back
                if ord(char) in [8, 127]:  # Backspace or Delete
                    if accumulated_symbols and current_position > 0:
                        removed_symbol = accumulated_symbols.pop()
                        removed_segment = accumulated_segments.pop()
                        current_position -= 1
                        
                        # Clear and redraw at previous position
                        self.console.clear()
                        self._draw_interface(mapping_data_sets, accumulated_symbols, accumulated_segments, current_position)
                    else:
                        # Clear and redraw with error message
                        self.console.clear()
                        self._draw_interface(mapping_data_sets, accumulated_symbols, accumulated_segments, current_position, error_msg="✗ Nothing to delete")
                    continue
                
                # Check for mapping toggle
                if char.lower() == 'm':
                    self.show_mapping = not self.show_mapping
                    
                    # Clear and redraw with mapping toggle
                    self.console.clear()
                    self._draw_interface(mapping_data_sets, accumulated_symbols, accumulated_segments, current_position)
                    continue
                
                # Create letter to symbol mapping (J K L ; map to symbols in display order)
                letter_to_symbol = {
                    'J': self.symbol_order[0],
                    'K': self.symbol_order[1], 
                    'L': self.symbol_order[2],
                    ';': self.symbol_order[3]
                }
                
                # Validate and process input
                if char.upper() in ['J', 'K', 'L'] or char == ';':
                    key = char.upper() if char != ';' else ';'
                    symbol = letter_to_symbol[key]
                    segment_num = self.symbol_to_segment_map[symbol]
                    
                    accumulated_symbols.append(symbol)
                    accumulated_segments.append(segment_num)
                    current_position += 1
                    
                    # Clear and redraw with updated sequence
                    self.console.clear()
                    self._draw_interface(mapping_data_sets, accumulated_symbols, accumulated_segments, current_position)
                else:
                    # Clear and redraw with error message
                    self.console.clear()
                    self._draw_interface(mapping_data_sets, accumulated_symbols, accumulated_segments, current_position, error_msg=f"✗ Invalid input '{char}'. Must be J/K/L/;, 'M' to toggle mapping, Backspace to delete, or 'Q' to quit.")
                    
            except (KeyboardInterrupt, EOFError):
                self.console.clear()
                self.console.print("[yellow]Input interrupted.[/yellow]")
                break
            except Exception as e:
                self.console.clear()
                self.console.print(f"[red]Input error: {e}[/red]")
                break
        
        # Show final sequence after process is complete
        if accumulated_symbols:
            self.console.print(f"\n[bold green]Final symbols:[/bold green] {accumulated_symbols}")
            self.console.print(f"[bold green]Final segments:[/bold green] {accumulated_segments}")
        else:
            self.console.print("\n[yellow]No symbols entered.[/yellow]")
        
        # Return the sequence of segment numbers entered by the user
        return accumulated_segments
    
    def _draw_interface(self, mapping_data_sets: List[List[Dict[str, Any]]], 
                       accumulated_symbols: List[str], accumulated_segments: List[int], current_position: int,
                       show_input: bool = False, success_msg: str = None, error_msg: str = None) -> None:
        """Draw the complete interface including grid, symbols, segments, and prompts."""
        
        if current_position < len(mapping_data_sets):
            self.console.print(f"\n[bold blue]═══ Mystery Protocol ═══[/bold blue]")
            
            # Display the current mapping grid
            current_mapping = mapping_data_sets[current_position]
            current_segments = self._parse_mapping_data(current_mapping)
            
            # Create updated table for current position
            table = Table(
                show_header=False,
                box=box.HEAVY,
                padding=(0, 0)
            )
            
            table.add_column(justify="center", style="cyan", width=25)
            table.add_column(justify="center", style="cyan", width=25)
            
            # Create content for each segment (using current position mapping)
            seg1_chars = self._format_segment_characters(current_segments.get(1, []), 20, current_segments)
            seg2_chars = self._format_segment_characters(current_segments.get(2, []), 20, current_segments)
            seg3_chars = self._format_segment_characters(current_segments.get(3, []), 20, current_segments)
            seg4_chars = self._format_segment_characters(current_segments.get(4, []), 20, current_segments)
            
            # Create panels for each segment
            seg1_panel = Panel(seg1_chars, title="[bold yellow]Segment 1[/bold yellow]", border_style="green", padding=(0, 0))
            seg2_panel = Panel(seg2_chars, title="[bold yellow]Segment 2[/bold yellow]", border_style="green", padding=(0, 0))
            seg3_panel = Panel(seg3_chars, title="[bold yellow]Segment 3[/bold yellow]", border_style="green", padding=(0, 0))
            seg4_panel = Panel(seg4_chars, title="[bold yellow]Segment 4[/bold yellow]", border_style="green", padding=(0, 0))
            
            # Add rows
            table.add_row(seg1_panel, seg2_panel)
            table.add_row(seg3_panel, seg4_panel)
            
            # Display the updated table
            self.console.print(table)
            
            # Add legend row below the main table
            legend_table = Table(
                show_header=False,
                box=None,
                padding=(0, 1),
                show_edge=False
            )
            
            # Add 4 columns for the legend with small fixed width
            legend_table.add_column(justify="center", width=6)
            legend_table.add_column(justify="center", width=6)
            legend_table.add_column(justify="center", width=6)
            legend_table.add_column(justify="center", width=6)
            
            # Create bordered panels for each character using permutation order
            color_map = {
                "○": "bright_cyan",
                "X": "bright_yellow", 
                "▲": "bright_green",
                "■": "bright_orange"
            }
            
            # Show only symbols in legend
            panels = []
            for i in range(4):
                symbol = self.symbol_order[i]
                panel_content = f"[{color_map[symbol]}]{symbol}[/{color_map[symbol]}]"
                panels.append(Panel(panel_content, width=5, padding=(0, 1)))
            
            # Add the legend row
            legend_table.add_row(*panels)
            
            self.console.print(legend_table)
            
            # Show mapping if enabled
            if self.show_mapping:
                self.console.print()
                # Create reverse mapping (segment number to symbol)
                segment_to_symbol = {v: k for k, v in self.symbol_to_segment_map.items()}
                
                # Display mapping in number order (1, 2, 3, 4)
                mapping_text = []
                for segment_num in [1, 2, 3, 4]:
                    if segment_num in segment_to_symbol:
                        symbol = segment_to_symbol[segment_num]
                        color = color_map[symbol]
                        mapping_text.append(f"[bold white]{segment_num}[/bold white] → [{color}]{symbol}[/{color}]")
                
                mapping_display = " | ".join(mapping_text)
                self.console.print(f"[dim]Mapping: {mapping_display}[/dim]")
        
        # Always show accumulated symbols
        if accumulated_symbols:
            # Create colored symbol display with no spaces
            color_map = {
                "○": "bright_cyan",
                "X": "bright_yellow", 
                "▲": "bright_green",
                "■": "bright_orange"
            }
            
            colored_symbols = []
            for symbol in accumulated_symbols:
                colored_symbols.append(f"[{color_map[symbol]}]{symbol}[/{color_map[symbol]}]")
            
            symbols_display = "".join(colored_symbols)
            self.console.print(f"\n[bold white]Symbols: {symbols_display}[/bold white]")
        
        # Show status messages
        if success_msg:
            self.console.print(f"[green]{success_msg}[/green]")
        elif error_msg:
            self.console.print(f"[red]{error_msg}[/red]")
        
        # Show input prompt
        if current_position < len(mapping_data_sets):
            self.console.print(f"\n[bold cyan]Enter key for position {current_position + 1} (J/K/L/;, M to toggle mapping, Backspace to delete, Q to quit): [/bold cyan]", end="")
        

    
    def _display_statistics(self, segments: Dict[int, List[str]]) -> None:
        """Display statistics about the segments."""
        stats_table = Table(
            title="[bold magenta]Segment Statistics[/bold magenta]",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold cyan"
        )
        
        stats_table.add_column("Segment", justify="center", style="yellow")
        stats_table.add_column("Character Count", justify="center", style="green")
        stats_table.add_column("Characters", justify="left", style="white")
        
        for seg_num in sorted(segments.keys()):
            chars = segments[seg_num]
            char_display = "".join(chars)
            stats_table.add_row(
                str(seg_num),
                str(len(chars)),
                char_display
            )
        
        self.console.print()
        self.console.print(stats_table)
    
    def display_mapping_summary(self, mapping_data: List[Dict[str, Any]]) -> None:
        """Display a compact summary of the mapping data using Rich.
        
        Args:
            mapping_data: List of mapping dictionaries from the protocol
        """
        segments = self._parse_mapping_data(mapping_data)
        
        # Create summary panel
        summary_text = Text()
        summary_text.append("Mapping Summary\n", style="bold blue")
        summary_text.append(f"Space character: {self.SPACE_SYMBOL}\n", style="italic")
        summary_text.append(f"Total segments: {len(segments)}\n\n", style="dim")
        
        for seg_num in sorted(segments.keys()):
            chars = segments[seg_num]
            char_display = "".join(chars)
            summary_text.append(f"Segment {seg_num}: ", style="yellow")
            summary_text.append(f"[{char_display}] ", style="green")
            summary_text.append(f"({len(chars)} chars)\n", style="dim")
        
        summary_panel = Panel(
            summary_text,
            title="[bold blue]Character Mapping Summary[/bold blue]",
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(summary_panel)
    

def generate_random_mapping(num_positions: int = 5, seed: Optional[int] = None) -> List[List[Dict[str, Any]]]:
    """Generate random character mappings for multiple positions using mystery protocol format.
    
    This uses the exact same character set as the mystery protocol:
    string.ascii_letters + string.digits + string.punctuation + " "
    
    Args:
        num_positions: Number of character positions to generate mappings for
        seed: Random seed for reproducible results (optional)
        
    Returns:
        List of mapping datasets, one for each character position
    """
    if seed is not None:
        random.seed(seed)
        # Note: When seed is set, we use random for reproducibility
        # When seed is None, we use secrets for cryptographic security
    
    # Use exact mystery protocol character set
    full_alphabet = list(string.ascii_letters + string.digits + string.punctuation + " ")
    
    # Always use exactly 64 characters for consistency
    if len(full_alphabet) >= 64:
        # Take first 64 characters from the mystery protocol alphabet
        alphabet = full_alphabet[:64]
    else:
        # If somehow less than 64, repeat characters to reach 64
        alphabet = full_alphabet[:]
        while len(alphabet) < 64:
            alphabet.extend(full_alphabet[:min(64-len(alphabet), len(full_alphabet))])
        alphabet = alphabet[:64]
    
    # Generate mappings for each position
    mapping_data_sets = []
    
    for position in range(num_positions):
        # Create a new random mapping for this position
        position_mapping = []
        
        # Shuffle alphabet for this position
        alphabet_shuffled = alphabet[:]
        if seed is not None:
            random.shuffle(alphabet_shuffled)
        else:
            # Use cryptographically secure shuffling
            for i in range(len(alphabet_shuffled) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                alphabet_shuffled[i], alphabet_shuffled[j] = alphabet_shuffled[j], alphabet_shuffled[i]
        
        # Generate segment numbers 1-4
        segment_numbers = list(range(1, 5))
        if seed is not None:
            random.shuffle(segment_numbers)
        else:
            # Use cryptographically secure shuffling
            for i in range(len(segment_numbers) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                segment_numbers[i], segment_numbers[j] = segment_numbers[j], segment_numbers[i]
        
        # Calculate partition size (each segment gets roughly equal characters)
        partition_size = len(alphabet_shuffled) // 4
        char_partitions = [alphabet_shuffled[j:j+partition_size] for j in range(0, len(alphabet_shuffled), partition_size)]
        
        # Handle remainder characters by distributing them to first partitions
        remainder_chars = alphabet_shuffled[len(char_partitions) * partition_size:]
        for i, char in enumerate(remainder_chars):
            if i < len(char_partitions):
                char_partitions[i].append(char)
        
        # Create mapping dictionary using exact mystery protocol format
        for seg_num, char_group in zip(segment_numbers, char_partitions):
            for char in char_group:
                position_mapping.append({
                    'character': char,
                    'segment': seg_num
                })
        
        # Shuffle the final mapping order
        if seed is not None:
            random.shuffle(position_mapping)
        else:
            # Use cryptographically secure shuffling
            for i in range(len(position_mapping) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                position_mapping[i], position_mapping[j] = position_mapping[j], position_mapping[i]
        
        mapping_data_sets.append(position_mapping)
    
    return mapping_data_sets


def display_mapping_details(mapping_data_sets: List[List[Dict[str, Any]]], position: int = 0) -> None:
    """Display detailed mapping information for a specific position.
    
    Args:
        mapping_data_sets: List of mapping datasets
        position: Position to display details for (0-based)
    """
    if not mapping_data_sets or position >= len(mapping_data_sets):
        print(f"No mapping data available for position {position}")
        return
    
    console = Console()
    mapping_data = mapping_data_sets[position]
    
    console.print(f"[bold blue]Mapping Details for Position {position + 1}[/bold blue]")
    console.print(f"[dim]Total characters: {len(mapping_data)}[/dim]")
    console.print()
    
    # Group by segment
    segments = defaultdict(list)
    for mapping in mapping_data:
        char = mapping['character']
        segment = mapping['segment']
        display_char = "◦" if char == ' ' else char
        segments[segment].append(display_char)
    
    # Display each segment
    for segment_num in sorted(segments.keys()):
        chars = segments[segment_num]
        char_count = len(chars)
        
        # Create a formatted display of characters
        chars_display = " ".join(chars[:20])  # Show first 20 chars
        if len(chars) > 20:
            chars_display += f" ... (+{len(chars) - 20} more)"
        
        console.print(f"[yellow]Segment {segment_num}[/yellow] ({char_count} chars): {chars_display}")
    
    console.print()


def generate_and_save_mappings(filename: str, num_positions: int = 8, seed: Optional[int] = None) -> None:
    """Generate random mappings using mystery protocol format and save them to a file.
    
    Uses exactly 64 characters from the mystery protocol alphabet:
    string.ascii_letters + string.digits + string.punctuation + " "
    
    Args:
        filename: Output filename for the mappings
        num_positions: Number of character positions to generate
        seed: Random seed for reproducible results
    """
    import json
    
    console = Console()
    
    console.print(f"[bold blue]Generating {num_positions} random mappings...[/bold blue]")
    if seed:
        console.print(f"[dim]Using seed: {seed}[/dim]")
    
    # Generate the mappings
    mapping_data_sets = generate_random_mapping(num_positions, seed=seed)
    
    # Save to file
    with open(filename, 'w') as f:
        json.dump(mapping_data_sets, f, indent=2)
    
    console.print(f"[green]✓ Saved {len(mapping_data_sets)} mappings to {filename}[/green]")
    
    # Show summary
    total_chars = len(mapping_data_sets[0])
    console.print(f"[dim]Each position contains {total_chars} character mappings (64 characters from mystery protocol alphabet)[/dim]")
    
    # Show first position details
    display_mapping_details(mapping_data_sets, position=0)


def demo_grid_display():
    """Demonstrate the grid display functionality with Rich."""
    if not RICH_AVAILABLE:
        print("Error: Rich library is required for this demo.")
        print("Install with: pip install rich")
        return
    
    console = Console()
    
    # Generate random mappings using mystery protocol format
    # Use None for truly random each time, or set a seed for reproducible results
    demo_seed = None  # Change to an integer for reproducible results
    num_positions = 64 
    
    # Generate mappings silently
    mapping_data_sets = generate_random_mapping(num_positions, seed=demo_seed)
    
    # Create display instance with permutation indices
    # Try different permutation indices (1-24) to see different symbol orders
    display_permutation_index = secrets.randbelow(24) + 1   # Change this to test different symbol display orders
    #mapping_permutation_index = secrets.randbelow(24) + 1   # Change this to test different symbol-to-segment mappings
    mapping_permutation_index = 11 
    display = MysteryGridDisplay(console, display_permutation_index, mapping_permutation_index)
    
    # Print the current configurations
    #console.print(f"[bold magenta]Display permutation index {display_permutation_index}:[/bold magenta]")
    #console.print(f"[dim]Symbol display order: {display.symbol_order}[/dim]")
    #console.print(f"[bold magenta]Mapping permutation index {mapping_permutation_index}:[/bold magenta]")
    #console.print(f"[dim]Symbol-to-segment mapping: {display.symbol_to_segment_map}[/dim]")
    #console.print()
#
    #time.sleep(2)
    
    # Show standard grid (displays mapping for position 1)
    entered_sequence = display.display_mapping_grid(mapping_data_sets, "Mystery Protocol - Multi-Position Mappings")
    
    # Show results
    if entered_sequence:
        console.print(f"\n[bold green]Demo completed![/bold green]")
        console.print(f"[cyan]Entered sequence: {entered_sequence}[/cyan]")
        console.print(f"[dim]Sequence length: {len(entered_sequence)}/{num_positions}[/dim]")
    else:
        console.print("\n[yellow]Demo cancelled or incomplete.[/yellow]")


if __name__ == "__main__":
    demo_grid_display()
