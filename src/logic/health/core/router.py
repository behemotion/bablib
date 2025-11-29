"""Health command router for flag parsing and routing."""

from enum import Enum

from ..models.category import HealthCategory


class OutputFormat(Enum):
    """Supported output formats for health command."""
    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


class HealthCommandRouter:
    """Router for health command flag parsing and validation."""

    def __init__(self):
        """Initialize health command router."""
        self.valid_formats = {fmt.value for fmt in OutputFormat}
        self.valid_categories = {cat.value.lower() for cat in HealthCategory}

    def parse_flags(self,
                   system: bool = False,
                   services: bool = False,
                   config: bool = False,
                   projects: bool = False,
                   format_type: str = "table",
                   verbose: bool = False,
                   quiet: bool = False,
                   timeout: int = 15,
                   parallel: int = 4) -> tuple[set[HealthCategory], dict]:
        """Parse and validate health command flags.

        Args:
            system: Check only system requirements
            services: Check only external services
            config: Check only configuration validity
            projects: Check project-specific health
            format_type: Output format (table, json, yaml)
            verbose: Include detailed diagnostic information
            quiet: Suppress progress indicators
            timeout: Maximum execution timeout in seconds
            parallel: Maximum parallel health checks

        Returns:
            Tuple of (categories_to_check, validated_options)

        Raises:
            ValueError: For invalid flag combinations or values
        """
        # Validate mutual exclusion flags
        if quiet and verbose:
            raise ValueError("--quiet and --verbose flags cannot be used together")

        # Validate format
        if format_type not in self.valid_formats:
            raise ValueError(f"Invalid format '{format_type}'. Valid formats: {', '.join(self.valid_formats)}")

        # Validate timeout
        if timeout < 1 or timeout > 60:
            raise ValueError("Timeout must be between 1 and 60 seconds")

        # Validate parallel
        if parallel < 1 or parallel > 8:
            raise ValueError("Parallel must be between 1 and 8")

        # Determine categories to check
        categories = self._determine_categories(system, services, config, projects)

        # Build validated options dictionary
        validated_options = {
            'format': OutputFormat(format_type),
            'verbose': verbose,
            'quiet': quiet,
            'timeout': timeout,
            'parallel': parallel,
            'show_detailed': verbose,
            'suppress_progress': quiet
        }

        return categories, validated_options

    def _determine_categories(self, system: bool, services: bool,
                            config: bool, projects: bool) -> set[HealthCategory]:
        """Determine which categories to check based on flags."""
        categories = set()

        # If specific category flags are provided, use only those
        if any([system, services, config, projects]):
            if system:
                categories.add(HealthCategory.SYSTEM)
            if services:
                categories.add(HealthCategory.SERVICES)
            if config:
                categories.add(HealthCategory.CONFIGURATION)
            if projects:
                categories.add(HealthCategory.PROJECTS)
        else:
            # Default: check all categories except projects
            categories = {
                HealthCategory.SYSTEM,
                HealthCategory.SERVICES,
                HealthCategory.CONFIGURATION
            }

        return categories

    def validate_format_compatibility(self, format_type: OutputFormat,
                                    verbose: bool, quiet: bool) -> None:
        """Validate format compatibility with other flags.

        Args:
            format_type: Output format
            verbose: Verbose flag
            quiet: Quiet flag

        Raises:
            ValueError: For incompatible flag combinations
        """
        # JSON and YAML formats should typically be used with quiet
        if format_type in [OutputFormat.JSON, OutputFormat.YAML] and verbose:
            # This is allowed but may produce mixed output
            pass

        # Quiet flag is most useful with JSON/YAML for automation
        if quiet and format_type == OutputFormat.TABLE:
            # This is allowed but may not be very useful
            pass

    def get_title_for_categories(self, categories: set[HealthCategory]) -> str:
        """Get appropriate title for the selected categories."""
        if len(categories) == 1:
            category = next(iter(categories))
            return f"Bablib Health Status - {category.display_name}"
        elif len(categories) == len(HealthCategory):
            return "Bablib Health Status - Complete"
        else:
            category_names = [cat.display_name for cat in categories]
            return f"Bablib Health Status - {', '.join(category_names)}"

    def should_show_resolution_guidance(self, options: dict, has_issues: bool) -> bool:
        """Determine if resolution guidance should be shown."""
        # Show resolution guidance if:
        # 1. Verbose mode is enabled, OR
        # 2. There are issues and we're not in quiet mode
        return options['verbose'] or (has_issues and not options['quiet'])

    def get_output_settings(self, options: dict) -> dict:
        """Get output formatting settings based on options."""
        return {
            'show_progress': not options['suppress_progress'],
            'show_details': options['show_detailed'],
            'use_colors': not options['quiet'],  # Disable colors in quiet mode
            'format_type': options['format'].value,
            'title': None  # Will be set by caller based on categories
        }
