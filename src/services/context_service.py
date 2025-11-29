"""Context service for shelf/box existence checking and status detection."""

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.core.config import BablibConfig
from src.models.command_context import CommandContext
from src.models.configuration_state import ConfigurationState
from src.services.database import DatabaseManager
from src.core.lib_logger import get_component_logger

logger = get_component_logger("context_service")


class ContextService:
    """Service for checking shelf/box existence and status."""

    def __init__(self, config: Optional[BablibConfig] = None):
        """Initialize context service."""
        self.config = config or BablibConfig()
        self.db_manager = DatabaseManager(self.config)
        self.cache_ttl = timedelta(minutes=5)  # 5-minute cache TTL

    async def check_shelf_exists(self, name: str) -> CommandContext:
        """Check if shelf exists and return context information."""
        start_time = time.time()

        # Check cache first
        cached_context = await self._get_cached_context(name, "shelf")
        if cached_context:
            elapsed_time = (time.time() - start_time) * 1000
            logger.debug(f"Shelf context retrieved from cache in {elapsed_time:.2f}ms for '{name}'")
            return cached_context

        # Query database for shelf
        async with self.db_manager.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, configuration_state, created_at, updated_at FROM shelves WHERE name = ?",
                (name,)
            )
            row = await cursor.fetchone()

        if row:
            shelf_id, shelf_name, config_state_json, created_at, updated_at = row

            # Parse configuration state
            config_state = self._parse_configuration_state(config_state_json)

            # Check if shelf has content (boxes)
            async with self.db_manager.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM shelf_boxes WHERE shelf_id = ?",
                    (shelf_id,)
                )
                box_count = (await cursor.fetchone())[0]

            is_empty = box_count == 0

            context = CommandContext(
                entity_name=name,
                entity_type="shelf",
                entity_exists=True,
                is_empty=is_empty,
                configuration_state=config_state,
                last_modified=datetime.fromisoformat(updated_at),
                content_summary=f"{box_count} boxes" if box_count > 0 else None
            )
        else:
            # Shelf doesn't exist
            config_state = ConfigurationState(
                is_configured=False,
                has_content=False,
                configuration_version="1.0",
                needs_migration=False
            )

            context = CommandContext(
                entity_name=name,
                entity_type="shelf",
                entity_exists=False,
                is_empty=None,
                configuration_state=config_state,
                last_modified=datetime.now(timezone.utc),
                content_summary=None
            )

        # Cache the result
        await self._cache_context(context)

        # Performance monitoring
        elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        if elapsed_time > 500:
            logger.warning(f"Shelf context detection took {elapsed_time:.2f}ms (target: <500ms) for '{name}'")
        else:
            logger.debug(f"Shelf context detected in {elapsed_time:.2f}ms for '{name}'")

        return context

    async def check_box_exists(self, name: str, shelf: Optional[str] = None) -> CommandContext:
        """Check if box exists and return context information."""
        start_time = time.time()

        # Check cache first
        cache_key = f"{name}_{shelf or 'global'}"
        cached_context = await self._get_cached_context(cache_key, "box")
        if cached_context:
            elapsed_time = (time.time() - start_time) * 1000
            logger.debug(f"Box context retrieved from cache in {elapsed_time:.2f}ms for '{name}'")
            return cached_context

        # Query database for box
        async with self.db_manager.get_connection() as conn:
            if shelf:
                # Box in specific shelf
                cursor = await conn.execute("""
                    SELECT b.id, b.name, b.type, b.configuration_state, b.created_at, b.updated_at
                    FROM boxes b
                    JOIN shelf_boxes sb ON b.id = sb.box_id
                    JOIN shelves s ON sb.shelf_id = s.id
                    WHERE b.name = ? AND s.name = ?
                """, (name, shelf))
            else:
                # Global box lookup
                cursor = await conn.execute(
                    "SELECT id, name, type, configuration_state, created_at, updated_at FROM boxes WHERE name = ?",
                    (name,)
                )

            row = await cursor.fetchone()

        if row:
            box_id, box_name, box_type, config_state_json, created_at, updated_at = row

            # Parse configuration state
            config_state = self._parse_configuration_state(config_state_json)

            # Check if box has content (this would depend on the vector store)
            # For now, assume empty if not configured
            is_empty = not config_state.has_content

            context = CommandContext(
                entity_name=name,
                entity_type="box",
                entity_exists=True,
                is_empty=is_empty,
                configuration_state=config_state,
                last_modified=datetime.fromisoformat(updated_at),
                content_summary=f"Type: {box_type}" + (", has content" if not is_empty else ", empty"),
                box_type=box_type
            )
        else:
            # Box doesn't exist
            config_state = ConfigurationState(
                is_configured=False,
                has_content=False,
                configuration_version="1.0",
                needs_migration=False
            )

            context = CommandContext(
                entity_name=name,
                entity_type="box",
                entity_exists=False,
                is_empty=None,
                configuration_state=config_state,
                last_modified=datetime.now(timezone.utc),
                content_summary=None
            )

        # Cache the result
        await self._cache_context(context, cache_key)

        # Performance monitoring
        elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        if elapsed_time > 500:
            logger.warning(f"Box context detection took {elapsed_time:.2f}ms (target: <500ms) for '{name}'")
        else:
            logger.debug(f"Box context detected in {elapsed_time:.2f}ms for '{name}'")

        return context

    async def _get_cached_context(self, name: str, entity_type: str) -> Optional[CommandContext]:
        """Get cached context if it exists and hasn't expired."""
        async with self.db_manager.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT entity_name, entity_type, entity_exists, is_empty,
                       configuration_state, last_modified, content_summary, expires_at
                FROM command_contexts
                WHERE entity_name = ? AND entity_type = ? AND expires_at > datetime('now')
            """, (name, entity_type))

            row = await cursor.fetchone()

        if not row:
            return None

        entity_name, entity_type, entity_exists, is_empty, config_state_json, last_modified_str, content_summary, expires_at = row

        config_state = self._parse_configuration_state(config_state_json)

        return CommandContext(
            entity_name=entity_name,
            entity_type=entity_type,
            entity_exists=bool(entity_exists),
            is_empty=bool(is_empty) if is_empty is not None else None,
            configuration_state=config_state,
            last_modified=datetime.fromisoformat(last_modified_str),
            content_summary=content_summary
        )

    async def _cache_context(self, context: CommandContext, cache_key: Optional[str] = None) -> None:
        """Cache context information with TTL."""
        key = cache_key or context.entity_name
        expires_at = datetime.now(timezone.utc) + self.cache_ttl

        async with self.db_manager.get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO command_contexts
                (entity_name, entity_type, entity_exists, is_empty, configuration_state,
                 last_modified, content_summary, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                key,
                context.entity_type,
                context.entity_exists,
                context.is_empty,
                json.dumps(context.configuration_state.model_dump()),
                context.last_modified.isoformat(),
                context.content_summary,
                expires_at.isoformat()
            ))
            await conn.commit()

    def _parse_configuration_state(self, config_json: Optional[str]) -> ConfigurationState:
        """Parse configuration state from JSON string."""
        if not config_json:
            return ConfigurationState(
                is_configured=False,
                has_content=False,
                configuration_version="1.0",
                needs_migration=False
            )

        try:
            data = json.loads(config_json)
            return ConfigurationState(**data)
        except (json.JSONDecodeError, ValueError):
            # Fallback to default if parsing fails
            return ConfigurationState(
                is_configured=False,
                has_content=False,
                configuration_version="1.0",
                needs_migration=True
            )

    async def clear_cache(self) -> None:
        """Clear expired context cache entries."""
        async with self.db_manager.get_connection() as conn:
            await conn.execute(
                "DELETE FROM command_contexts WHERE expires_at <= datetime('now')"
            )
            await conn.commit()

    async def invalidate_context(self, name: str, entity_type: str) -> None:
        """Invalidate specific context cache entry."""
        async with self.db_manager.get_connection() as conn:
            await conn.execute(
                "DELETE FROM command_contexts WHERE entity_name = ? AND entity_type = ?",
                (name, entity_type)
            )
            await conn.commit()