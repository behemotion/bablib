"""Unit tests for command flag validation and conflict detection."""

import pytest
from unittest.mock import Mock

pytestmark = [pytest.mark.unit, pytest.mark.setup]


class TestFlagConflictDetection:
    """Test detection of conflicting command flags."""

    @pytest.fixture
    def router(self):
        """Create command router instance."""
        from src.logic.setup.core.router import CommandRouter
        return CommandRouter()

    def test_detect_operation_flag_conflicts(self, router):
        """Test detection of conflicting operation flags."""
        # Single operation flags should be valid
        assert router.validate_flags(init=True) is True
        assert router.validate_flags(uninstall=True) is True
        assert router.validate_flags(reset=True) is True

        # Multiple operation flags should conflict
        with pytest.raises(ValueError, match="conflicting"):
            router.validate_flags(init=True, uninstall=True)

        with pytest.raises(ValueError, match="conflicting"):
            router.validate_flags(init=True, reset=True)

        with pytest.raises(ValueError, match="conflicting"):
            router.validate_flags(uninstall=True, reset=True)

    def test_vector_store_requires_init(self, router):
        """Test vector-store flag requires init flag."""
        # vector-store without init should fail
        with pytest.raises(ValueError, match="vector-store.*init"):
            router.validate_flags(vector_store="sqlite_vec")

        # vector-store with init should succeed
        assert router.validate_flags(init=True, vector_store="sqlite_vec") is True

    def test_auto_flag_requires_operation(self, router):
        """Test auto flag requires an operation flag."""
        # auto without operation should fail
        with pytest.raises(ValueError, match="auto.*operation"):
            router.validate_flags(auto=True)

        # auto with operation should succeed
        assert router.validate_flags(init=True, auto=True) is True
        assert router.validate_flags(uninstall=True, auto=True) is True

    def test_non_interactive_requires_operation(self, router):
        """Test non-interactive requires an operation."""
        # non-interactive alone should fail
        with pytest.raises(ValueError, match="non-interactive.*operation"):
            router.validate_flags(non_interactive=True)

        # non-interactive with operation should succeed
        assert router.validate_flags(init=True, non_interactive=True) is True

    def test_force_flag_combinations(self, router):
        """Test force flag is valid with certain operations."""
        # force alone is invalid
        with pytest.raises(ValueError, match="force.*operation"):
            router.validate_flags(force=True)

        # force with uninstall is valid
        assert router.validate_flags(uninstall=True, force=True) is True

        # force with reset is valid
        assert router.validate_flags(reset=True, force=True) is True

        # force with init is questionable but allowed
        assert router.validate_flags(init=True, force=True) is True


class TestFlagRouting:
    """Test routing of flags to appropriate operations."""

    @pytest.fixture
    def router(self):
        """Create command router instance."""
        from src.logic.setup.core.router import CommandRouter
        return CommandRouter()

    def test_route_init_flags(self, router):
        """Test routing of init-related flags."""
        operation = router.route_operation(
            init=True,
            vector_store="sqlite_vec",
            auto=True
        )

        assert operation.type == "init"
        assert operation.options["vector_store"] == "sqlite_vec"
        assert operation.options["auto"] is True

    def test_route_uninstall_flags(self, router):
        """Test routing of uninstall-related flags."""
        operation = router.route_operation(
            uninstall=True,
            force=True
        )

        assert operation.type == "uninstall"
        assert operation.options["force"] is True

    def test_route_reset_flags(self, router):
        """Test routing of reset flags."""
        operation = router.route_operation(
            reset=True,
            force=True
        )

        assert operation.type == "reset"
        assert operation.options["force"] is True

    def test_route_no_flags_to_menu(self, router):
        """Test no flags routes to interactive menu."""
        operation = router.route_operation()

        assert operation.type == "menu"
        assert operation.options == {}


class TestFlagErrorMessages:
    """Test error message generation for flag conflicts."""

    @pytest.fixture
    def router(self):
        """Create command router instance."""
        from src.logic.setup.core.router import CommandRouter
        return CommandRouter()

    def test_conflict_error_message_format(self, router):
        """Test format of conflict error messages."""
        try:
            router.validate_flags(init=True, uninstall=True)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            error_msg = str(e)
            assert "--init" in error_msg
            assert "--uninstall" in error_msg
            assert "cannot be used together" in error_msg.lower()

    def test_suggestion_in_error_message(self, router):
        """Test that error messages include suggestions."""
        try:
            router.validate_flags(vector_store="sqlite_vec")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            error_msg = str(e)
            assert "suggestion" in error_msg.lower() or "try" in error_msg.lower()
            assert "--init" in error_msg

    def test_list_valid_combinations(self, router):
        """Test that help lists valid flag combinations."""
        help_text = router.get_flag_help()

        assert "--init" in help_text
        assert "--uninstall" in help_text
        assert "--reset" in help_text
        assert "Examples:" in help_text
        assert "bablib setup --init --auto" in help_text