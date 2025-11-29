"""Flag standardization service for consistent CLI command patterns."""

from typing import Dict, List, Optional, Set, Tuple
import logging
from dataclasses import dataclass

from src.core.lib_logger import get_component_logger

logger = get_component_logger("flag_standardizer")


@dataclass
class FlagMapping:
    """Represents a standardized flag mapping."""
    long_form: str
    short_form: str
    flag_type: str  # boolean, string, integer, choice
    description: str
    choices: Optional[List[str]] = None
    default_value: Optional[str] = None
    is_global: bool = False


class FlagStandardizer:
    """Service for standardizing command line flags across all commands."""

    def __init__(self):
        self._global_flags = self._initialize_global_flags()
        self._command_specific_flags = self._initialize_command_specific_flags()

    def _initialize_global_flags(self) -> Dict[str, FlagMapping]:
        """Initialize standard global flags used across all commands."""
        return {
            "help": FlagMapping(
                long_form="--help",
                short_form="-h",
                flag_type="boolean",
                description="Show help information",
                default_value="false",
                is_global=True
            ),
            "verbose": FlagMapping(
                long_form="--verbose",
                short_form="-v",
                flag_type="boolean",
                description="Enable verbose output",
                default_value="false",
                is_global=True
            ),
            "quiet": FlagMapping(
                long_form="--quiet",
                short_form="-q",
                flag_type="boolean",
                description="Suppress non-error output",
                default_value="false",
                is_global=True
            ),
            "config": FlagMapping(
                long_form="--config",
                short_form="-c",
                flag_type="string",
                description="Specify config file path",
                is_global=True
            ),
            "format": FlagMapping(
                long_form="--format",
                short_form="-f",
                flag_type="choice",
                description="Output format",
                choices=["json", "yaml", "table"],
                default_value="table",
                is_global=True
            ),
            "init": FlagMapping(
                long_form="--init",
                short_form="-i",
                flag_type="boolean",
                description="Launch setup wizard",
                default_value="false",
                is_global=True
            ),
            "force": FlagMapping(
                long_form="--force",
                short_form="-F",
                flag_type="boolean",
                description="Force operation without prompts",
                default_value="false",
                is_global=True
            ),
            "dry_run": FlagMapping(
                long_form="--dry-run",
                short_form="-n",
                flag_type="boolean",
                description="Show what would be done without executing",
                default_value="false",
                is_global=True
            ),
            "timeout": FlagMapping(
                long_form="--timeout",
                short_form="-t",
                flag_type="integer",
                description="Operation timeout in seconds",
                is_global=True
            ),
            "limit": FlagMapping(
                long_form="--limit",
                short_form="-l",
                flag_type="integer",
                description="Limit number of results",
                is_global=True
            )
        }

    def _initialize_command_specific_flags(self) -> Dict[str, Dict[str, FlagMapping]]:
        """Initialize command-specific flag mappings."""
        return {
            "shelf": {
                "description": FlagMapping(
                    long_form="--shelf-description",  # Changed to avoid conflict with box description
                    short_form="-d",  # Keep -d for shelf as it's more common
                    flag_type="string",
                    description="Shelf description"
                ),
                "set_current": FlagMapping(
                    long_form="--set-current",
                    short_form="-s",  # Changed back to -s, will resolve --source conflict differently
                    flag_type="boolean",
                    description="Set as current shelf",
                    default_value="false"
                ),
                "create": FlagMapping(
                    long_form="--create",
                    short_form="-C",  # Keep -C for create
                    flag_type="boolean",
                    description="Force creation mode",
                    default_value="false"
                )
            },
            "box": {
                "type": FlagMapping(
                    long_form="--type",
                    short_form="-T",  # Changed from -t to avoid conflict with --timeout
                    flag_type="choice",
                    description="Box type",
                    choices=["drag", "rag", "bag"]
                ),
                "shelf": FlagMapping(
                    long_form="--shelf",
                    short_form="-B",  # Changed to -B (for Box shelf)
                    flag_type="string",
                    description="Target shelf name"
                ),
                "description": FlagMapping(
                    long_form="--box-description",  # Changed to avoid conflict with shelf description
                    short_form="-D",  # Changed from -d to avoid conflict with --depth
                    flag_type="string",
                    description="Box description"
                )
            },
            "fill": {
                "source": FlagMapping(
                    long_form="--source",
                    short_form="-S",  # Changed from -s to avoid conflict with shelf --set-current
                    flag_type="string",
                    description="Content source (URL, file path, or data)"
                ),
                "max_pages": FlagMapping(
                    long_form="--max-pages",
                    short_form="-m",
                    flag_type="integer",
                    description="Maximum pages to crawl (drag boxes)"
                ),
                "rate_limit": FlagMapping(
                    long_form="--rate-limit",
                    short_form="-R",  # Changed from -r to avoid conflict with setup --reset
                    flag_type="string",
                    description="Requests per second limit (drag boxes)"
                ),
                "depth": FlagMapping(
                    long_form="--depth",
                    short_form="-e",  # Changed from -d to avoid conflict with shelf description
                    flag_type="integer",
                    description="Maximum crawl depth (drag boxes)"
                ),
                "chunk_size": FlagMapping(
                    long_form="--chunk-size",
                    short_form="-z",  # Changed from -C to avoid conflict with --create
                    flag_type="integer",
                    description="Text chunk size for processing (rag boxes)"
                ),
                "overlap": FlagMapping(
                    long_form="--overlap",
                    short_form="-O",
                    flag_type="integer",
                    description="Chunk overlap percentage (rag boxes)"
                ),
                "recursive": FlagMapping(
                    long_form="--recursive",
                    short_form="-x",  # Changed from -r since setup --reset uses -r
                    flag_type="boolean",
                    description="Process directories recursively (bag boxes)",
                    default_value="false"
                ),
                "pattern": FlagMapping(
                    long_form="--pattern",
                    short_form="-P",  # Use -P for Pattern
                    flag_type="string",
                    description="File name pattern matching (bag boxes)"
                )
            },
            "serve": {
                "host": FlagMapping(
                    long_form="--host",
                    short_form="-H",  # Changed from -h to avoid conflict with --help
                    flag_type="string",
                    description="Server host address"
                ),
                "port": FlagMapping(
                    long_form="--port",
                    short_form="-o",  # Changed from -P since fill --pattern now uses -P
                    flag_type="integer",
                    description="Server port number"
                ),
                "admin": FlagMapping(
                    long_form="--admin",
                    short_form="-A",  # Changed from -a to avoid conflict with --auto
                    flag_type="boolean",
                    description="Enable admin server",
                    default_value="false"
                ),
                "foreground": FlagMapping(
                    long_form="--foreground",
                    short_form="-g",  # Changed from -F to avoid conflict with global --force
                    flag_type="boolean",
                    description="Run in foreground",
                    default_value="false"
                ),
                "status": FlagMapping(
                    long_form="--status",
                    short_form="-w",  # Use -w for status (w for "what's running")
                    flag_type="boolean",
                    description="Check server status",
                    default_value="false"
                )
            },
            "setup": {
                "auto": FlagMapping(
                    long_form="--auto",
                    short_form="-a",
                    flag_type="boolean",
                    description="Auto-configure with defaults",
                    default_value="false"
                ),
                "vector_store": FlagMapping(
                    long_form="--vector-store",
                    short_form="-V",
                    flag_type="choice",
                    description="Vector store provider",
                    choices=["sqlite_vec", "qdrant"]
                ),
                "uninstall": FlagMapping(
                    long_form="--uninstall",
                    short_form="-u",
                    flag_type="boolean",
                    description="Uninstall Bablib",
                    default_value="false"
                ),
                "reset": FlagMapping(
                    long_form="--reset",
                    short_form="-r",
                    flag_type="boolean",
                    description="Reset configuration",
                    default_value="false"
                ),
                "preserve_data": FlagMapping(
                    long_form="--preserve-data",
                    short_form="-k",  # Changed from -p to avoid conflicts (k for "keep")
                    flag_type="boolean",
                    description="Preserve user data during reset",
                    default_value="false"
                )
            }
        }

    def get_global_flags(self) -> Dict[str, FlagMapping]:
        """Get all global flag mappings."""
        return self._global_flags.copy()

    def get_command_flags(self, command: str) -> Dict[str, FlagMapping]:
        """Get flag mappings for a specific command."""
        return self._command_specific_flags.get(command, {}).copy()

    def get_all_flags_for_command(self, command: str) -> Dict[str, FlagMapping]:
        """Get both global and command-specific flags for a command."""
        all_flags = self.get_global_flags()
        command_flags = self.get_command_flags(command)

        # Merge command-specific flags, allowing them to override globals if needed
        all_flags.update(command_flags)
        return all_flags

    def validate_flag_consistency(self) -> List[str]:
        """Validate that flag mappings are consistent across commands."""
        issues = []
        short_form_usage = {}
        long_form_usage = {}

        # Check global flags first
        for flag_name, mapping in self._global_flags.items():
            short_form_usage[mapping.short_form] = [f"global:{flag_name}"]
            long_form_usage[mapping.long_form] = [f"global:{flag_name}"]

        # Check command-specific flags
        for command, flags in self._command_specific_flags.items():
            for flag_name, mapping in flags.items():
                # Track short form usage
                if mapping.short_form in short_form_usage:
                    short_form_usage[mapping.short_form].append(f"{command}:{flag_name}")
                else:
                    short_form_usage[mapping.short_form] = [f"{command}:{flag_name}"]

                # Track long form usage
                if mapping.long_form in long_form_usage:
                    long_form_usage[mapping.long_form].append(f"{command}:{flag_name}")
                else:
                    long_form_usage[mapping.long_form] = [f"{command}:{flag_name}"]

        # Find conflicts
        for short_form, usages in short_form_usage.items():
            if len(usages) > 1:
                issues.append(f"Short form '{short_form}' used by multiple flags: {', '.join(usages)}")

        for long_form, usages in long_form_usage.items():
            if len(usages) > 1:
                issues.append(f"Long form '{long_form}' used by multiple flags: {', '.join(usages)}")

        return issues

    def suggest_flag_alias(self, command: str, desired_flag: str) -> Optional[str]:
        """Suggest an available short form for a flag."""
        used_short_forms = set()

        # Collect all used short forms
        for mapping in self._global_flags.values():
            used_short_forms.add(mapping.short_form)

        for cmd_flags in self._command_specific_flags.values():
            for mapping in cmd_flags.values():
                used_short_forms.add(mapping.short_form)

        # Generate suggestions based on the desired flag
        if desired_flag.startswith("--"):
            base_name = desired_flag[2:]  # Remove --
        else:
            base_name = desired_flag

        # Try first letter
        first_letter = f"-{base_name[0].lower()}"
        if first_letter not in used_short_forms:
            return first_letter

        # Try first letter uppercase
        first_letter_upper = f"-{base_name[0].upper()}"
        if first_letter_upper not in used_short_forms:
            return first_letter_upper

        # Try consonants
        consonants = [c for c in base_name.lower() if c.isalpha() and c not in 'aeiou']
        for consonant in consonants:
            candidate = f"-{consonant}"
            if candidate not in used_short_forms:
                return candidate
            candidate_upper = f"-{consonant.upper()}"
            if candidate_upper not in used_short_forms:
                return candidate_upper

        # Try any remaining letters
        for char in 'bcdfghjklmnpqrstvwxyz':
            candidate = f"-{char}"
            if candidate not in used_short_forms:
                return candidate

        return None  # No available short forms

    def generate_click_options(self, command: str) -> List[str]:
        """Generate Click decorator strings for a command."""
        all_flags = self.get_all_flags_for_command(command)
        options = []

        for flag_name, mapping in all_flags.items():
            if mapping.flag_type == "boolean":
                option = f"@click.option('{mapping.long_form}', '{mapping.short_form}', is_flag=True, help='{mapping.description}'"
                if mapping.default_value:
                    option += f", default={mapping.default_value}"
                option += ")"
            elif mapping.flag_type == "choice":
                choices_str = ", ".join([f"'{choice}'" for choice in mapping.choices or []])
                option = f"@click.option('{mapping.long_form}', '{mapping.short_form}', type=click.Choice([{choices_str}]), help='{mapping.description}'"
                if mapping.default_value:
                    option += f", default='{mapping.default_value}'"
                option += ")"
            elif mapping.flag_type == "integer":
                option = f"@click.option('{mapping.long_form}', '{mapping.short_form}', type=int, help='{mapping.description}'"
                if mapping.default_value:
                    option += f", default={mapping.default_value}"
                option += ")"
            else:  # string
                option = f"@click.option('{mapping.long_form}', '{mapping.short_form}', type=str, help='{mapping.description}'"
                if mapping.default_value:
                    option += f", default='{mapping.default_value}'"
                option += ")"

            options.append(option)

        return options

    def get_flag_conflicts_report(self) -> str:
        """Generate a detailed report of flag conflicts and suggestions."""
        issues = self.validate_flag_consistency()

        if not issues:
            return "✅ All flags are consistent across commands."

        report = "⚠️ Flag Consistency Issues Found:\n\n"

        for i, issue in enumerate(issues, 1):
            report += f"{i}. {issue}\n"

        report += "\n🔧 Suggested Actions:\n"
        report += "- Review conflicting flags and ensure they serve the same purpose\n"
        report += "- Consider renaming command-specific flags to avoid conflicts\n"
        report += "- Use global flags for common functionality across commands\n"

        return report